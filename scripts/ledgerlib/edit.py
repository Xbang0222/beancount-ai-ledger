"""查找、作废、更正已入账的分录。

改账和入账走同一套保护：写盘后整本校验，不通过就原样还原。分录用编号定位
（find / recent 会显示），编号取自分录内容，不随行号漂移。
作废是把这一笔从序时簿里删掉，原文会打印出来；之后要找回，查 Git 历史或更早的备份压缩包。
"""
import os

from . import config, journal
from .add import append_plan, find_duplicate, mirror_hint, precheck, read_block, reject_duplicate
from .entry import time_line, with_time_line
from .query import print_summary
from .store import book_lock, commit


def _rel(path):
    return os.path.relpath(path, config.ROOT).replace(os.sep, "/")


def _show(block, prefix="   "):
    for line in block.lines:
        print(f"{prefix}{line}")


def _locate(book, ident):
    """按编号找分录块；找不到时打印原因并返回 None。内容完全相同的多笔取最后一笔。"""
    ident = ident.strip().strip("[]").lower()
    hits = [b for b in journal.book_blocks(book) if b.ident == ident]
    if not hits:
        print(f"[FAIL] {book} 账里没有编号为 {ident} 的分录（本次未改动）。"
              f"编号随内容变化，改过之后要重新查：ledger.py find {book} <关键词> 或 recent {book}。")
        return None
    return hits[-1]


def _without(block):
    """所在文件去掉这一块之后的文本。"""
    with open(block.path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    rest = lines[:block.start] + lines[block.end:]
    while rest and not rest[-1].strip():
        rest.pop()
    return "\n".join(rest) + "\n"


def cmd_find(book, keywords, ym=None, limit=20):
    """按关键词找分录（对方、摘要、科目、金额、标签、日期都能搜），多个关键词要同时出现。"""
    words = [w.lower() for w in keywords]
    hits = []
    for b in journal.book_blocks(book):
        if ym and b.date[:7] != ym:
            continue
        text = b.text.lower()
        if all(w in text for w in words):
            hits.append(b)
    hits.sort(key=lambda b: b.sort_key)
    shown = hits[-limit:]
    scope = f" · {ym}" if ym else ""
    print(f"\n===== {book}{scope} · 含「{' '.join(keywords)}」的分录 {len(hits)} 笔"
          + (f"，显示最近 {len(shown)} 笔" if len(shown) < len(hits) else "") + " =====")
    if not shown:
        print("  （没有找到）")
    for b in shown:
        print(f"\n[{b.ident}] {_rel(b.path)}:{b.lineno}")
        _show(b, prefix="  ")
    return 0


def cmd_void(book, ident):
    with book_lock():
        block = _locate(book, ident)
        if block is None:
            return 1
        entries, _ = commit(book, {block.path: _without(block)})
        if entries is None:
            return 1
    print(f"[OK] 已作废：{book} -> {_rel(block.path)}（原文如下；之后要找回，查 Git 历史或更早的备份）")
    _show(block)
    print_summary(book, block.date[:7], entries=entries)
    mirror_hint(book, block.text, action="同步作废或更正")
    return 0


def cmd_amend(book, ident, stream=None, path=None, allow_duplicate=False):
    new = read_block(stream, path)
    if new is None:
        return 1
    ymd = precheck(new)
    if ymd is None:
        return 1
    ym = f"{ymd[0]}-{ymd[1]}"

    with book_lock():
        block = _locate(book, ident)
        if block is None:
            return 1
        # 新分录没写 time 就沿用原来的：更正不改变这笔交易的发生时间，也不凭空补一个
        old_time = time_line(block.text)
        if old_time:
            new = with_time_line(new, old_time)
        # 原分录上方紧贴的注释留着，除非新分录自带了注释
        lead = [] if new.lstrip().startswith(";") else block.lines[:block.head]
        new_lines = lead + new.split("\n")
        jpath = os.path.join(config.book_paths(book)[1], f"{ym}.beancount")

        same_file = os.path.realpath(jpath) == os.path.realpath(block.path)
        if same_file and journal.sort_key_of(new) == block.sort_key:
            # 日期时间没变：原位替换，diff 只有改动的那几行
            with open(block.path, encoding="utf-8") as f:
                lines = f.read().split("\n")
            lines[block.start:block.start + len(block.lines)] = new_lines
            changes = {block.path: "\n".join(lines)}
            first = block.start + 1
        else:
            # 日期或时间变了：从原处删掉，再按新的日期时间写进对应月份的序时簿
            removed = {jpath if same_file else block.path: _without(block)}
            changes, jpath, _, first = append_plan(book, ym, "\n".join(new_lines), removed)
        entries, rollback = commit(book, changes)
        if entries is None:
            return 1
        if not allow_duplicate:
            dup = find_duplicate(entries, jpath, first, first + len(new_lines) - 1)
            if dup is not None:
                return reject_duplicate(dup, rollback)

    print(f"[OK] 已更正：{book} -> {_rel(jpath)}")
    print("   原：")
    _show(block, prefix="     ")
    print("   新：")
    for line in new_lines:
        print(f"     {line}")
    print_summary(book, ym, entries=entries)
    mirror_hint(book, block.text + "\n" + new, action="同步更正")
    return 0
