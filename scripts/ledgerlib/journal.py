"""序时簿文本的分块：一条指令连同紧贴在它上方的注释为一块，带行号与编号。

fmt 靠它重排，find / void / amend 靠它按编号定位某一笔。编号取自分录内容本身，
不随行号漂移：前面删掉一笔之后，后面各笔的编号不变。
"""
import glob
import hashlib
import os
import re
from dataclasses import dataclass

from . import config
from .entry import DATE_RE

ID_LEN = 8
TIME_META_RE = re.compile(r'^[ \t]+time:[ \t]*"(\d{1,2}):(\d{2})')


@dataclass
class Block:
    lines: list      # 块内各行：紧贴的上方注释 + 指令本身（尾部空行已去掉）
    start: int       # 块在文件中的起始行下标（从 0 起，含上方注释）
    end: int         # 下一块的起始行下标（不含）；之间是本块和块后的空行
    path: str = ""   # 所在序时簿文件的绝对路径

    @property
    def head(self):
        """指令首行（日期行）在 lines 中的下标。"""
        for i, line in enumerate(self.lines):
            if DATE_RE.match(line):
                return i
        return 0

    @property
    def lineno(self):
        """指令首行在文件中的行号（从 1 起），与 beancount 报的 lineno 一致。"""
        return self.start + self.head + 1

    @property
    def text(self):
        return "\n".join(self.lines)

    @property
    def ident(self):
        body = "\n".join(line.rstrip() for line in self.lines[self.head:])
        return hashlib.sha1(body.encode("utf-8")).hexdigest()[:ID_LEN]

    @property
    def date(self):
        return self.lines[self.head][:10]

    @property
    def sort_key(self):
        """(日期, 时间)：time 规范成 HH:MM 再比；没有 time 的排在同日有 time 的之前。"""
        for line in self.lines[self.head + 1:]:
            m = TIME_META_RE.match(line)
            if m:
                return (self.date, f"{int(m.group(1)):02d}:{m.group(2)}")
        return (self.date, "")


def _rstrip_blank(lines):
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def _is_comment(line):
    return line.startswith(";")


def split(text, path=""):
    """拆成 (文件头各行, [Block])。文件头是第一条指令之前的注释与空行。

    顶格注释紧贴在某条指令上方（中间没有空行）时归这条指令，重排时跟着它走；
    文件头里只有“与前文隔了空行、又紧贴第一条指令”的注释才算第一条指令的。
    """
    lines = text.split("\n")
    first = next((i for i, line in enumerate(lines) if DATE_RE.match(line)), len(lines))
    start = first
    if any(not line.strip() for line in lines[:first]):
        while start > 0 and _is_comment(lines[start - 1]):
            start -= 1
    header = lines[:start]

    blocks = []
    cur = None
    lead = list(lines[start:first])
    for i in range(first, len(lines)):
        line = lines[i]
        if DATE_RE.match(line):
            if cur is not None:
                while len(cur.lines) > 1 and _is_comment(cur.lines[-1]):
                    lead.insert(0, cur.lines.pop())
                cur.end = i - len(lead)
                blocks.append(cur)
            cur = Block(lines=lead + [line], start=i - len(lead), end=len(lines), path=path)
            lead = []
        elif cur is not None:
            cur.lines.append(line)
    if cur is not None:
        blocks.append(cur)
    for b in blocks:
        _rstrip_blank(b.lines)
    return header, blocks


def journal_files(book):
    _, jdir, _ = config.book_paths(book)
    return sorted(glob.glob(os.path.join(jdir, "*.beancount")))


def book_blocks(book):
    """账本全部序时簿里的分录块，按文件名与出现顺序。"""
    blocks = []
    for path in journal_files(book):
        with open(path, encoding="utf-8") as f:
            blocks += split(f.read(), path)[1]
    return blocks


def ident_index(book):
    """{(序时簿绝对路径, 指令首行行号): 编号}，用来给 beancount 加载出的交易对上编号。"""
    return {(os.path.realpath(b.path), b.lineno): b.ident for b in book_blocks(book)}


def ident_of(index, entry):
    meta = entry.meta or {}
    filename = meta.get("filename")
    if not filename:
        return None
    return index.get((os.path.realpath(filename), meta.get("lineno")))


def sort_key_of(block_text):
    """一笔分录文本的排序键 (日期, 时间)；文本里没有指令时返回 None。"""
    blocks = split(block_text)[1]
    return blocks[0].sort_key if blocks else None


def insert_sorted(text, block_text):
    """把一笔分录按日期时间插进序时簿文本，返回 (新文本, 分录首行的行号)。

    只在现有分录已经有序、且新分录不该排在最后时才插入；其余情况返回 None，由调用方追加到末尾。
    同日同时间的排在已有分录之后，与 fmt 的稳定排序结果一致。
    """
    key = sort_key_of(block_text)
    blocks = split(text)[1]
    if key is None or any(a.sort_key > b.sort_key for a, b in zip(blocks, blocks[1:])):
        return None
    after = next((b for b in blocks if b.sort_key > key), None)
    if after is None:
        return None
    lines = text.split("\n")
    # 前一行不是空行时先补一个，保证分录之间恰好空一行
    gap = [""] if after.start > 0 and lines[after.start - 1].strip() else []
    lines[after.start:after.start] = gap + block_text.split("\n") + [""]
    return "\n".join(lines), after.start + len(gap) + 1
