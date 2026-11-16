"""按关键词检索规则文档与科目表：给出命中的表格行（连同表头）、条款所在章节、科目说明。

用途是把“通读分类表和规则文档”换成“查一个词”：归类拿不准时查东西或商家名，遇到少见业务时查业务名，
按输出里的章节去读对应一节即可。只读不写。
"""
import os
import re

from . import config, rulebook
from .books import Chart, load_book
from .display import pad

MAX_HITS = 12            # 每个关键词在规则文档里最多列出的命中数
HEADING_RE = re.compile(r"^(#+)\s+(.*\S)\s*$")
TABLE_SEP_RE = re.compile(r"^\|\s*:?-{2,}")


class Hit:
    """一处命中：所在文件、章节、行号、原文；表格行带表头。"""

    def __init__(self, doc, section, lineno, text, header=None):
        self.doc, self.section, self.lineno, self.text, self.header = doc, section, lineno, text, header


def scan(doc, text, word):
    """在一份 Markdown 里找含 word 的行（不分大小写）。代码块里的示例分录不算；标题命中表示整节相关。"""
    needle = word.lower()
    hits, section, header, fenced = [], "", None, False
    lines = text.split("\n")
    for i, raw in enumerate(lines):
        line = raw.strip()
        if line.startswith("```"):
            fenced = not fenced
            continue
        if fenced or not line:
            header = None if not line else header
            continue
        m = HEADING_RE.match(line)
        if m:
            section, header = m.group(2), None
            if needle in section.lower():
                hits.append(Hit(doc, section, i + 1, "（本节标题命中，整节相关）"))
            continue
        if line.startswith("|"):
            if TABLE_SEP_RE.match(line):
                continue
            if i + 1 < len(lines) and TABLE_SEP_RE.match(lines[i + 1].strip()):
                header = line           # 表头行：记下来，供本表命中的行带出
                continue
            if needle in line.lower():
                hits.append(Hit(doc, section, i + 1, line, header))
            continue
        header = None
        if needle in line.lower():
            hits.append(Hit(doc, section, i + 1, line))
    return hits


def search_docs(word):
    hits = []
    for doc in rulebook.files():
        try:
            with open(os.path.join(config.ROOT, *doc.split("/")), encoding="utf-8") as f:
                hits.extend(scan(doc, f.read(), word))
        except OSError:
            continue
    return hits


def search_accounts(cfg, word):
    """各账本里科目名或科目说明含 word 的在用科目：[(账本, 科目, 币种, 说明)]。账本有错时跳过该账本。"""
    needle, out = word.lower(), []
    for book in cfg.books:
        entries, errors, _ = load_book(book)
        if errors:
            continue
        chart = Chart(entries)
        for acc in chart.active:
            note = chart.note(acc)
            if needle in acc.lower() or needle in note.lower():
                out.append((book, acc, "/".join(chart.opens[acc].currencies or []) or "不限", note))
    return out


def _print_hits(hits):
    shown, last = hits[:MAX_HITS], (None, None, None)
    for h in shown:
        if (h.doc, h.section) != last[:2]:
            print(f"\n  {h.doc}「{h.section}」" if h.section else f"\n  {h.doc}")
            last = (h.doc, h.section, None)
        if h.header and h.header != last[2]:
            print(f"    {h.header}")
            last = (h.doc, h.section, h.header)
        print(f"    {h.text}" if h.header else f"    第 {h.lineno} 行：{h.text}")
    rest = hits[MAX_HITS:]
    if rest:
        where = "、".join(dict.fromkeys(f"{h.doc}「{h.section}」" for h in rest))
        print(f"\n  另有 {len(rest)} 处命中未列出：{where}")


def cmd_lookup(words):
    cfg = config.load()
    for word in words:
        print(f"\n===== {word} =====")
        hits, accounts = search_docs(word), search_accounts(cfg, word)
        if not hits and not accounts:
            print("  未命中。换用通称、商家或平台名再查；仍未命中时按 brief 输出的「找不到分类时」处理。")
            continue
        _print_hits(hits)
        if accounts:
            print("\n  科目表")
            for book, acc, currencies, note in accounts:
                print(f"    {pad(book, 10)}{pad(acc, 38)}{pad(currencies, 8)}{note}".rstrip())
    return 0
