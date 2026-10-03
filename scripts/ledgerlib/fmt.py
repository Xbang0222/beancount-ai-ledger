"""序时簿格式化：分录间空一行、按日期与时间重排（紧贴分录上方的注释跟着分录走）。

序时簿是顺序追加的，补记历史账会造成日期逆序，且分录之间没有空行，
几百行连成一片，diff 和肉眼翻账都很费劲。

本模块只动排版，不动任何金额、日期与文字。写入前后各加载一次账本比对
交易笔数与全部科目余额，任一不符立即还原——否则不敢对历史账跑。
"""
import os
from collections import Counter

from . import config, journal
from .books import balances, load_book, print_errors, transactions
from .journal import journal_files


def _rstrip_blank(block):
    while block and not block[-1].strip():
        block.pop()
    return block


def format_text(text):
    header, blocks = journal.split(text)
    # sorted 是稳定排序：同日同时间的分录保持原有先后
    ordered = [b.lines for b in sorted(blocks, key=lambda b: b.sort_key)]
    head = "\n".join(_rstrip_blank(list(header)))
    body = "\n\n".join("\n".join(b) for b in ordered)
    if not body:
        return head + "\n" if head else ""
    return (head + "\n\n" if head else "") + body + "\n"


def _content_fingerprint(text):
    """非空非注释行的多重集：排版怎么变都不该改变它。"""
    return Counter(
        line.strip() for line in text.split("\n")
        if line.strip() and not line.strip().startswith(";")
    )


def _book_state(book):
    entries, errors, _ = load_book(book)
    if errors:
        return None, errors
    bals = balances(entries)
    state = (len(transactions(entries)), {a: dict(c) for a, c in bals.items()})
    return state, None


def cmd_fmt(books=None, check_only=False):
    if books is None:
        books = tuple(config.load().books)
    rc = 0
    for book in books:
        rc |= _fmt_book(book, check_only)
    return 1 if rc else 0


def _rel(path):
    return os.path.relpath(path, config.ROOT)


def _fmt_book(book, check_only):
    files = journal_files(book)
    if not files:
        print(f"[skip] {book}: 没有序时簿文件")
        return 0

    originals = {}
    pending = {}
    for path in files:
        with open(path, encoding="utf-8") as f:
            text = f.read()
        originals[path] = text
        new = format_text(text)
        if _content_fingerprint(text) != _content_fingerprint(new):
            print(f"[FAIL] {_rel(path)}: 格式化前后内容不一致，已放弃，请人工检查。")
            return 1
        if new != text:
            pending[path] = new

    if not pending:
        print(f"[OK] {book}: 序时簿已是规范格式")
        return 0

    rel = ", ".join(_rel(p) for p in pending)
    if check_only:
        print(f"[FAIL] {book}: 以下序时簿未格式化，请运行 ledger.py fmt：{rel}")
        return 1

    before, errors = _book_state(book)
    if before is None:
        print_errors(book, errors)
        print("[FAIL] 账本本来就有错误，先修复再格式化。")
        return 1

    for path, new in pending.items():
        with open(path, "w", encoding="utf-8") as f:
            f.write(new)

    after, errors = _book_state(book)
    if after is None or after != before:
        for path, text in originals.items():
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
        print(f"[FAIL] {book}: 格式化后账本校验不一致，已全部还原。")
        if errors:
            print_errors(book, errors)
        return 1

    print(f"[OK] {book}: 已格式化 {rel}（交易 {after[0]} 笔，余额未变）")
    return 0
