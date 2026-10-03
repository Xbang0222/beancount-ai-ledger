"""查找、作废、更正：改账和入账一样，坏账绝不能落盘。"""
import io

from ledgerlib import add, cli, edit, journal

LUNCH_FIXED = '2026-09-02 * "食堂" "餐饮-午餐"\n  Expenses:Food:Dining  25.00 CNY\n  Assets:Wechat'
LUNCH_BAD = '2026-09-02 * "食堂" "餐饮-午餐"\n  Expenses:Food:Dining  25.00 CNY\n  Expenses:Other  1.00 CNY'
LUNCH_MOVED = '2026-08-31 * "食堂" "餐饮-午餐"\n  Expenses:Food:Dining  20.00 CNY\n  Assets:Alipay'
ADVANCE_DUP = '2026-09-02 * "食堂" "餐饮-午餐"\n  Expenses:Food:Dining  20.00 CNY\n  Assets:Alipay'


def _journal(ledger, ym="2026-09"):
    return ledger / "personal" / "journal" / f"{ym}.beancount"


def _id(keyword, book="personal"):
    return next(b.ident for b in journal.book_blocks(book) if keyword in b.text)


def _amend(ident, block, **kw):
    return edit.cmd_amend("personal", ident, stream=io.StringIO(block), **kw)


def test_编号只取决于分录内容_不随位置变(ledger):
    before = _id("代垫商店采购款")
    assert edit.cmd_void("personal", _id("餐饮-午餐")) == 0
    assert _id("代垫商店采购款") == before


def test_find_按关键词列出分录与编号(ledger, capsys):
    assert cli.main(["find", "personal", "食堂", "20.00"]) == 0
    out = capsys.readouterr().out
    assert f"[{_id('餐饮-午餐')}]" in out
    assert "代垫商店采购款" not in out


def test_find_找不到时明确提示(ledger, capsys):
    assert cli.main(["find", "personal", "不存在的关键词"]) == 0
    assert "没有找到" in capsys.readouterr().out


def test_recent_显示编号(ledger, capsys):
    assert cli.main(["recent", "personal"]) == 0
    assert f"[{_id('餐饮-午餐')}]" in capsys.readouterr().out


def test_作废后分录消失且账本仍可校验(ledger, capsys):
    assert cli.main(["void", "personal", _id("餐饮-午餐")]) == 0
    assert "餐饮-午餐" not in _journal(ledger).read_text(encoding="utf-8")
    assert "已作废" in capsys.readouterr().out
    assert cli.main(["check", "--no-reconcile"]) == 0


def test_作废不动其他分录(ledger):
    assert edit.cmd_void("personal", _id("餐饮-午餐")) == 0
    text = _journal(ledger).read_text(encoding="utf-8")
    assert text.startswith("; 测试个人账 · 2026-09 流水\n\n2026-09-01 ")
    assert text.endswith("  Assets:Wechat\n")


def test_编号不存在时不改动(ledger, capsys):
    before = _journal(ledger).read_bytes()
    assert edit.cmd_void("personal", "deadbeef") == 1
    assert _journal(ledger).read_bytes() == before
    assert "没有编号为 deadbeef" in capsys.readouterr().out


def test_作废往来分录时提醒处理另一边(ledger, capsys):
    assert edit.cmd_void("personal", _id("代垫商店采购款")) == 0
    out = capsys.readouterr().out
    assert "Liabilities:OwnerLoan" in out and "同步作废或更正" in out


def test_作废导致余额断言不符时回滚(ledger, capsys):
    assert add.cmd_add("personal", stream=io.StringIO(
        "2026-09-10 balance Assets:Alipay  -20.00 CNY")) == 0
    before = _journal(ledger).read_bytes()
    assert edit.cmd_void("personal", _id("餐饮-午餐")) == 1
    assert _journal(ledger).read_bytes() == before
    assert "已回滚" in capsys.readouterr().out


def test_更正替换原分录并沿用原_time(ledger, capsys):
    assert _amend(_id("餐饮-午餐"), LUNCH_FIXED) == 0
    text = _journal(ledger).read_text(encoding="utf-8")
    assert "20.00 CNY\n  Assets:Alipay" not in text
    assert '"餐饮-午餐"\n  time: "12:30"\n  Expenses:Food:Dining  25.00 CNY\n  Assets:Wechat' in text
    assert "已更正" in capsys.readouterr().out


def test_更正保持原位置(ledger):
    assert _amend(_id("餐饮-午餐"), LUNCH_FIXED) == 0
    text = _journal(ledger).read_text(encoding="utf-8")
    assert text.index("餐饮-午餐") < text.index("代垫商店采购款")


def test_更正不平衡时回滚后文件字节级不变(ledger, capsys):
    before = _journal(ledger).read_bytes()
    assert _amend(_id("餐饮-午餐"), LUNCH_BAD) == 1
    assert _journal(ledger).read_bytes() == before


def test_更正的新分录同样过入账检查(ledger, capsys):
    before = _journal(ledger).read_bytes()
    assert _amend(_id("餐饮-午餐"), LUNCH_FIXED.replace("2026-09-02", "2026-09-24")) == 1
    assert "晚于今天" in capsys.readouterr().out
    assert _journal(ledger).read_bytes() == before


def test_更正日期跨月时挪到对应月份的序时簿(ledger):
    assert _amend(_id("餐饮-午餐"), LUNCH_MOVED) == 0
    assert "餐饮-午餐" not in _journal(ledger).read_text(encoding="utf-8")
    assert "餐饮-午餐" in _journal(ledger, "2026-08").read_text(encoding="utf-8")
    assert 'include "personal/journal/2026-08.beancount"' in (
        ledger / "personal.beancount").read_text(encoding="utf-8")
    assert cli.main(["check", "--no-reconcile"]) == 0


def test_跨月更正失败时两个月份都还原(ledger):
    before = _journal(ledger).read_bytes()
    main_before = (ledger / "personal.beancount").read_bytes()
    assert _amend(_id("餐饮-午餐"), LUNCH_BAD.replace("2026-09-02", "2026-08-31")) == 1
    assert _journal(ledger).read_bytes() == before
    assert (ledger / "personal.beancount").read_bytes() == main_before
    assert not _journal(ledger, "2026-08").exists()


def test_更正成与另一笔相同时按重复拒绝(ledger, capsys):
    assert add.cmd_add("personal", stream=io.StringIO(
        '2026-09-03 * "食堂" "餐饮-晚餐"\n  Expenses:Food:Dining  20.00 CNY\n  Assets:Alipay')) == 0
    before = _journal(ledger).read_bytes()
    assert _amend(_id("餐饮-晚餐"), ADVANCE_DUP) == 1
    assert _journal(ledger).read_bytes() == before
    assert "疑似重复" in capsys.readouterr().out
    assert _amend(_id("餐饮-晚餐"), ADVANCE_DUP, allow_duplicate=True) == 0


def test_命令行_amend_从文件读新分录(ledger, tmp_path):
    f = tmp_path / "entry.tmp"
    f.write_text(LUNCH_FIXED, encoding="utf-8")
    assert cli.main(["amend", "personal", _id("餐饮-午餐"), "--file", str(f)]) == 0
    assert "25.00 CNY" in _journal(ledger).read_text(encoding="utf-8")


def test_更正改了时间就挪到按时间该在的位置(ledger):
    from ledgerlib import fmt

    assert fmt.cmd_fmt(("personal",)) == 0
    moved = '2026-09-01 * "食堂" "餐饮-午餐"\n  time: "08:00"\n  Expenses:Food:Dining  20.00 CNY\n  Assets:Alipay'
    assert _amend(_id("餐饮-午餐"), moved) == 0
    text = _journal(ledger).read_text(encoding="utf-8")
    assert text.count("餐饮-午餐") == 1
    assert text.index("餐饮-午餐") < text.index("代垫商店采购款")
    assert fmt.cmd_fmt(("personal",), check_only=True) == 0


def test_作废后序时簿仍是规范格式(ledger):
    from ledgerlib import fmt

    assert fmt.cmd_fmt(("personal",)) == 0
    assert edit.cmd_void("personal", _id("代垫商店采购款")) == 0
    assert fmt.cmd_fmt(("personal",), check_only=True) == 0
