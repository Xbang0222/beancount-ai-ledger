"""查询命令：recent 的排序、report 按账本性质区分口径、tag 的分桶汇总。"""
from ledgerlib import query

TRIP = '''
2026-09-03 * "12306" "旅行-城际高铁票" #trip #chengdu
  time: "07:30"
  Expenses:Other  110.00 CNY
  Assets:Alipay
'''


def _append(path, text):
    path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")


def test_recent_按发生日期时间排序而非录入顺序(ledger, capsys):
    """序时簿里 09-02 写在 09-01 前面，recent 仍要把 09-02 当作最近一笔。"""
    assert query.cmd_recent("personal", 1) == 0
    out = capsys.readouterr().out
    assert "餐饮-午餐" in out and "代垫商店" not in out
    assert "最近 1 笔" in out and "共 2 笔" in out


def test_recent_同日按_time_排序(ledger, capsys):
    _append(ledger / "personal" / "journal" / "2026-09.beancount",
            '\n2026-09-02 * "便利店" "餐饮-早餐"\n  time: "8:05"\n  Expenses:Food:Dining  6.00 CNY\n  Assets:Alipay\n')
    assert query.cmd_recent("personal", 2) == 0
    out = capsys.readouterr().out
    assert out.index("餐饮-早餐") < out.index("餐饮-午餐")


def test_个人账报告算储蓄率(ledger, capsys):
    assert query.cmd_report("personal", "2026-09") == 0
    out = capsys.readouterr().out
    assert "【结余与储蓄率】" in out


def test_经营账报告看经营结余不算储蓄率(ledger, capsys):
    assert query.cmd_report("shop", "2026-09") == 0
    out = capsys.readouterr().out
    assert "【经营结余】" in out
    assert "储蓄率" not in out


def test_标签查账分桶汇总(ledger, capsys):
    _append(ledger / "personal" / "journal" / "2026-09.beancount", TRIP)
    assert query.cmd_tag("personal", "#trip") == 0
    out = capsys.readouterr().out
    assert "共 1 笔" in out
    assert "110.00 CNY" in out.split("----- 支出 -----")[1]
