"""序时簿分块：行号、编号、注释归属。"""
from ledgerlib import journal

TEXT = '''; 文件头

2026-09-05 * "乙" "餐饮-晚餐"
  time: "19:00"
  Expenses:Food:Dining  20.00 CNY
  Assets:Alipay

; 补记
2026-09-02 * "甲" "餐饮-午餐"
  Expenses:Food:Dining  10.00 CNY
  Assets:Alipay
'''


def test_行号与_beancount_一致(ledger):
    """编号要能对上 beancount 加载出的交易，靠的是 (文件, 行号) 完全一致。"""
    from ledgerlib.books import load_book, transactions

    index = journal.ident_index("personal")
    txns = [t for t in transactions(load_book("personal")[0]) if "journal" in t.meta["filename"]]
    assert txns and all(journal.ident_of(index, t) for t in txns)


def test_分块的行号与范围():
    header, (a, b) = journal.split(TEXT)
    assert header == ["; 文件头", ""]
    assert (a.lineno, a.start, a.end) == (3, 2, 7)
    assert (b.lineno, b.start) == (9, 7)
    assert b.lines[0] == "; 补记" and b.date == "2026-09-02"


def test_编号不受排版与上方注释影响():
    _, (_, b) = journal.split(TEXT)
    _, (_, c) = journal.split(TEXT.replace("; 补记\n", "").replace("10.00 CNY", "10.00 CNY   "))
    assert b.ident == c.ident and len(b.ident) == journal.ID_LEN


def test_内容不同编号不同():
    _, (a, b) = journal.split(TEXT)
    assert a.ident != b.ident


def test_排序键把一位数小时补零_无_time_排最前():
    _, (a, b) = journal.split(TEXT.replace('"19:00"', '"9:05"'))
    assert a.sort_key == ("2026-09-05", "09:05")
    assert b.sort_key == ("2026-09-02", "")


def test_隔了空行的注释不算下一笔的():
    text = TEXT.replace("; 补记\n", "; 游离注释\n\n")
    _, (a, b) = journal.split(text)
    assert "; 游离注释" in a.lines and b.lines[0].startswith("2026-09-02")


def test_按时间插入_同日同时间排在已有分录之后():
    blocks = sorted(journal.split(TEXT)[1], key=lambda b: b.sort_key)
    sorted_text = "; 头\n\n" + "\n\n".join(b.text for b in blocks) + "\n"
    new = '2026-09-02 * "丙" "餐饮-早餐"\n  Expenses:Food:Dining  3.00 CNY\n  Assets:Alipay'
    text, lineno = journal.insert_sorted(sorted_text, new)
    assert text.split("\n")[lineno - 1].startswith('2026-09-02 * "丙"')
    assert text.index('"甲"') < text.index('"丙"') < text.index('"乙"')
    assert "\n\n\n" not in text


def test_按时间插入_该排最后或原文乱序时交回调用方追加():
    last = '2026-09-09 * "丙" "餐饮-早餐"\n  Expenses:Food:Dining  3.00 CNY\n  Assets:Alipay'
    assert journal.insert_sorted(TEXT, last.replace("09-09", "09-01")) is None  # TEXT 本身乱序
    ordered = "\n\n".join(b.text for b in sorted(journal.split(TEXT)[1], key=lambda b: b.sort_key)) + "\n"
    assert journal.insert_sorted(ordered, last) is None
