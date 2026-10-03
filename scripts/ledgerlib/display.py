"""终端输出对齐：中日韩全角字符按两列宽计算，避免中文列错位。"""
import unicodedata
from decimal import Decimal


def width(text):
    """终端显示宽度。"""
    return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in text)


def pad(text, w):
    """按显示宽度左对齐补空格。"""
    return text + " " * max(0, w - width(text))


def rpad(text, w):
    """按显示宽度右对齐补空格。"""
    return " " * max(0, w - width(text)) + text


def print_txn(txn, indent="  ", ident=None):
    """打印一笔交易：首行日期、时间、对方、摘要、标签，下面逐行列出科目与金额。

    给了 ident 就在行首标出分录编号（void / amend 用它定位这一笔）。
    """
    payee = txn.payee or ""
    narr = txn.narration or ""
    tags_str = " ".join(f"#{t}" for t in sorted(txn.tags or []))
    time_str = (txn.meta or {}).get("time", "")
    time_display = f" {time_str}" if time_str else ""
    mark = f"[{ident}] " if ident else ""
    print(f"\n{mark}{txn.date}{time_display}  {payee}  {narr}  {tags_str}".rstrip())
    for p in txn.postings:
        if p.units is None:
            continue
        print(f"{indent}{p.account:<38}{Decimal(p.units.number):>12.2f} {p.units.currency}")
