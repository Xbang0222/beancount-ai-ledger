"""序时簿格式化：只动排版，绝不动账。"""
from ledgerlib import fmt

MESSY = '''; personal 账本 · 2026-09 流水
; 第二行注释
2026-09-05 * "乙" "餐饮-晚餐"
  time: "19:00"
  Expenses:Food:Dining  20.00 CNY
  Assets:Alipay
2026-09-02 * "甲" "餐饮-午餐"
  time: "12:00"
  Expenses:Food:Dining  10.00 CNY
  Assets:Alipay


2026-09-05 * "丙" "餐饮-夜宵"
  time: "8:00"
  Expenses:Food:Dining  5.00 CNY
  Assets:Alipay
'''


def test_按日期与时间重排():
    out = fmt.format_text(MESSY)
    dates = [line[:10] for line in out.split("\n") if line[:1].isdigit()]
    assert dates == sorted(dates)
    # 同日按 time 排：8:00 的排在 19:00 之前（不能按字符串比较，"8:00" > "19:00"）
    assert out.index('"丙"') < out.index('"乙"')


def test_文件头注释保留():
    out = fmt.format_text(MESSY)
    assert out.startswith("; personal 账本 · 2026-09 流水\n; 第二行注释\n\n")


def test_分录间恰好空一行():
    out = fmt.format_text(MESSY)
    assert "\n\n\n" not in out
    assert out.count("\n\n") == 3  # 头后 1 次 + 分录间 2 次


def test_幂等():
    once = fmt.format_text(MESSY)
    assert fmt.format_text(once) == once


def test_不增删任何实质内容():
    assert fmt._content_fingerprint(MESSY) == fmt._content_fingerprint(fmt.format_text(MESSY))


def test_空文件不炸():
    assert fmt.format_text("") == ""
    assert fmt.format_text("; 只有注释\n") == "; 只有注释\n"


def test_check_模式检出未格式化且不写盘(ledger, capsys):
    j = ledger / "personal" / "journal" / "2026-09.beancount"
    before = j.read_bytes()
    assert fmt.cmd_fmt(("personal",), check_only=True) == 1
    assert j.read_bytes() == before
    assert "未格式化" in capsys.readouterr().out


def test_格式化后账本余额不变(ledger, capsys):
    before, _ = fmt._book_state("personal")
    assert fmt.cmd_fmt(("personal",)) == 0
    after, _ = fmt._book_state("personal")
    assert after == before
    assert "余额未变" in capsys.readouterr().out


def test_格式化后再跑_check_为已规范(ledger):
    assert fmt.cmd_fmt(("personal",)) == 0
    assert fmt.cmd_fmt(("personal",), check_only=True) == 0


def test_不指定账本时处理全部账本(ledger, capsys):
    assert fmt.cmd_fmt() == 0
    out = capsys.readouterr().out
    assert "personal" in out and "shop" in out


def test_账本本身有错时拒绝格式化(ledger, capsys):
    j = ledger / "personal" / "journal" / "2026-09.beancount"
    j.write_text(j.read_text(encoding="utf-8") +
                 '\n2026-09-06 * "甲" "坏账"\n  Expenses:Food:Dining  1.00 CNY\n  Expenses:Other  1.00 CNY\n',
                 encoding="utf-8")
    before = j.read_bytes()
    assert fmt.cmd_fmt(("personal",)) == 1
    assert j.read_bytes() == before
    assert "先修复再格式化" in capsys.readouterr().out


COMMENTED = '''; 文件头

2026-09-05 * "乙" "餐饮-晚餐"
  time: "19:00"
  Expenses:Food:Dining  20.00 CNY
  Assets:Alipay

; 补记：对账发现遗漏
2026-09-02 * "甲" "餐饮-午餐"
  time: "12:00"
  Expenses:Food:Dining  10.00 CNY
  Assets:Alipay
'''


def test_紧贴分录上方的注释跟着分录走():
    """旧实现把注释算给上一笔，重排后注释和它说明的分录被拆开。"""
    out = fmt.format_text(COMMENTED)
    assert '; 补记：对账发现遗漏\n2026-09-02 * "甲"' in out
    assert out.index("补记") < out.index('"乙"')
    assert out.startswith("; 文件头\n\n; 补记")
    assert fmt.format_text(out) == out


def test_一位数小时按时间而不是按字符串排序():
    text = MESSY.replace('"19:00"', '"12:00"').replace('"08:00"', '"9:40"')
    out = fmt.format_text(text)
    assert out.index('"丙"') < out.index('"乙"')
