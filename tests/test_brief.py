"""brief：入账前的一页现场信息；周期事项算出哪几天还没记。"""
from datetime import date

from ledgerlib import brief, cli, config, recurring
from ledgerlib.books import load_book

RECURRING = '''
[[recurring]]
book = "shop"
name = "每周进货"
every = "tuesday"
since = 2026-09-01
match = "主营业务成本-采购"
entry = """
{date} * "供应商" "主营业务成本-采购"
  Expenses:COGS  100.00 CNY
  Assets:Bank:Main
"""
'''


def _rule(**kw):
    base = dict(book="shop", name="x", kind="weekly", day=1, since=date(2026, 9, 1), match="主营业务成本-采购")
    base.update(kw)
    return config.Recurring(**base)


def test_按周按日按月算出应有的日期():
    today = date(2026, 9, 23)
    assert recurring.due_dates(_rule(), today) == [date(2026, 9, d) for d in (1, 8, 15, 22)]
    assert len(recurring.due_dates(_rule(kind="daily"), today)) == 23
    assert recurring.due_dates(_rule(kind="monthly", day=15), today) == [date(2026, 9, 15)]


def test_每月31号在小月取月末():
    rule = _rule(kind="monthly", day=31, since=date(2026, 2, 1))
    assert recurring.due_dates(rule, date(2026, 4, 30)) == [date(2026, 2, 28), date(2026, 3, 31), date(2026, 4, 30)]


def test_当天有含关键词的交易就算记过(ledger):
    entries = load_book("shop")[0]   # 夹具里 09-01 有一笔「主营业务成本-采购」
    assert recurring.missing(_rule(), entries, date(2026, 9, 23)) == [date(2026, 9, d) for d in (8, 15, 22)]
    assert recurring.missing(_rule(match="没有这种账"), entries, date(2026, 9, 2)) == [date(2026, 9, 1)]


def test_模板里的日期被替换():
    rule = _rule(entry='{date} * "供应商" "主营业务成本-采购"')
    assert recurring.render(rule, date(2026, 9, 8)) == '2026-09-08 * "供应商" "主营业务成本-采购"'


def test_brief_打印日期科目和范例(ledger, capsys):
    assert cli.main(["brief"]) == 0
    out = capsys.readouterr().out
    assert "2026-09-23 周三 21:30（Asia/Shanghai）" in out
    assert "（无进行中事项）" in out
    assert "===== personal（测试个人账）可用科目 =====" in out and "===== shop（测试商店账）可用科目 =====" in out
    assert "Assets:Alipay" in out and "Expenses:COGS" in out
    assert "【往来，对应 shop Liabilities:OwnerLoan，用 pair 两本账一起录】" in out
    assert '2026-09-02 * "食堂" "餐饮-午餐"' not in out       # 最近入账的分录不当范例
    assert "中没有「分录范例」一节" in out
    assert "python3 scripts/ledger.py pair" in out
    assert "该补的周期分录" not in out                          # 没配 [[recurring]] 就不出这一节


def test_brief_只看一本账(ledger, capsys):
    assert cli.main(["brief", "personal"]) == 0
    out = capsys.readouterr().out
    assert "personal（测试个人账）可用科目" in out and "shop（测试商店账）可用科目" not in out


def test_brief_带出_STATE_里生效的事项并去掉注释模板(ledger, capsys):
    (ledger / "STATE.md").write_text(
        "# 当前临时状态\n\n说明段落不用打印。\n\n## 当前生效\n\n### 进行中的行程\n"
        "- 9月20日至25日成都旅行：打 #trip #chengdu\n\n<!--\n- 例：这是模板，不该出现\n-->\n", encoding="utf-8")
    assert cli.main(["brief"]) == 0
    out = capsys.readouterr().out
    assert "9月20日至25日成都旅行" in out
    assert "这是模板" not in out and "说明段落" not in out and "（无进行中事项）" not in out


def test_brief_STATE_只有标题时算没有事项(ledger, capsys):
    (ledger / "STATE.md").write_text("# 状态\n\n## 当前生效\n\n### 进行中事项\n\n<!-- 模板 -->\n", encoding="utf-8")
    assert brief.state_lines() == []


def test_brief_不列已停用的科目(ledger, capsys):
    accounts = ledger / "personal" / "accounts.beancount"
    accounts.write_text(accounts.read_text(encoding="utf-8") + "2026-09-10 close Assets:Bank:USD\n", encoding="utf-8")
    assert cli.main(["brief", "personal"]) == 0
    assert "Assets:Bank:USD" not in capsys.readouterr().out


def test_brief_列出漏记的周期分录和现成写法(ledger, capsys):
    cfg = ledger / "ledger.toml"
    cfg.write_text(cfg.read_text(encoding="utf-8") + RECURRING, encoding="utf-8")
    assert cli.main(["brief"]) == 0
    out = capsys.readouterr().out
    assert "shop · 每周进货：3 天没记（2026-09-08、2026-09-15、2026-09-22）" in out
    assert '2026-09-22 * "供应商" "主营业务成本-采购"' in out
    assert "先跟用户确认这几天确实发生了" in out


def test_brief_约定直接补的周期分录不让先问(ledger, capsys):
    cfg = ledger / "ledger.toml"
    cfg.write_text(cfg.read_text(encoding="utf-8") + RECURRING.replace('match =', 'confirm = false\nmatch ='),
                   encoding="utf-8")
    assert cli.main(["brief"]) == 0
    out = capsys.readouterr().out
    assert "按约定直接逐笔补记，不用问用户" in out and "先跟用户确认" not in out


def test_brief_周期分录都记了(ledger, capsys):
    cfg = ledger / "ledger.toml"
    cfg.write_text(cfg.read_text(encoding="utf-8") + RECURRING.replace("2026-09-01", "2026-09-23"), encoding="utf-8")
    assert cli.main(["brief"]) == 0
    assert "（无待补记）" in capsys.readouterr().out


def test_doctor_提醒漏记的周期事项(ledger, capsys):
    cfg = ledger / "ledger.toml"
    cfg.write_text(cfg.read_text(encoding="utf-8") + RECURRING, encoding="utf-8")
    cli.main(["doctor"])
    out = capsys.readouterr().out
    assert "[WARN] shop：周期事项「每周进货」有 3 天没记（最早 2026-09-08，最近 2026-09-22）" in out
    assert "ledger.py brief shop" in out


def test_brief_只有一本账没有往来也能用(solo, capsys):
    assert cli.main(["brief"]) == 0
    out = capsys.readouterr().out
    assert "Assets:Alipay" in out and "pair" not in out


def test_brief_账本有错时不出报告(ledger, capsys):
    j = ledger / "personal" / "journal" / "2026-09.beancount"
    j.write_text(j.read_text(encoding="utf-8") + '\n2026-09-03 * "食堂" "餐饮-午餐"\n  Expenses:NotOpened  1.00 CNY\n'
                 "  Assets:Alipay\n", encoding="utf-8")
    assert cli.main(["brief"]) == 1
    assert "请先运行 check 修复" in capsys.readouterr().out


DAILY = """# 日常入账

## 9 标签

- 标签写在首行。

## 10 分录范例

日常消费：

```
2026-09-26 * "面馆" "餐饮-午餐"
  Expenses:Food:Dining  18.00 CNY
  Assets:Wechat
```

## 11 其他

不属于范例。
"""


def test_brief_范例取自规则文档的分录范例一节(ledger, capsys):
    (ledger / "rules").mkdir()
    (ledger / "rules" / "daily.md").write_text(DAILY, encoding="utf-8")
    assert cli.main(["brief"]) == 0
    out = capsys.readouterr().out
    section = out.split("===== 写法范例", 1)[1].split("=====\n", 1)[1].split("=====", 1)[0]
    assert "rules/daily.md「分录范例」" in out
    assert '  2026-09-26 * "面馆" "餐饮-午餐"' in section and "日常消费：" in section
    assert "```" not in section and "不属于范例" not in section and "标签写在首行" not in section
    assert "ledger.py recent" in section
