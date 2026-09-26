"""入账与回滚：坏账绝不能落盘。"""
import io

from ledgerlib import add

GOOD = '2026-09-23 * "食堂" "餐饮-晚餐"\n  Expenses:Food:Dining  30.00 CNY\n  Assets:Alipay'
UNBALANCED = '2026-09-23 * "食堂" "餐饮-晚餐"\n  Expenses:Food:Dining  30.00 CNY\n  Expenses:Other  5.00 CNY'
BAD_ACCOUNT = '2026-09-23 * "食堂" "餐饮-晚餐"\n  Expenses:NotOpened  30.00 CNY\n  Assets:Alipay'
LAST_MONTH = '2026-08-31 * "食堂" "餐饮-晚餐"\n  Expenses:Food:Dining  30.00 CNY\n  Assets:Alipay'
LAST_MONTH_BAD = '2026-08-31 * "食堂" "餐饮-晚餐"\n  Expenses:Food:Dining  30.00 CNY\n  Expenses:Other  5.00 CNY'
MIRROR = '2026-09-23 * "商店" "代垫商店采购款（股东往来）"\n  Assets:Receivable:Shop  50.00 CNY\n  Assets:Wechat'


def _add(block, book="personal"):
    return add.cmd_add(book, stream=io.StringIO(block))


def _journal(root, month="2026-09", book="personal"):
    return root / book / "journal" / f"{month}.beancount"


def test_正常入账并注入_time(ledger):
    assert _add(GOOD) == 0
    text = _journal(ledger).read_text(encoding="utf-8")
    assert "餐饮-晚餐" in text
    assert '  time: "21:30"' in text.split("餐饮-晚餐")[1]


def test_分录之间空一行(ledger):
    assert _add(GOOD) == 0
    assert "\n\n2026-09-23" in _journal(ledger).read_text(encoding="utf-8")


def test_不平衡回滚后文件字节级不变(ledger):
    before = _journal(ledger).read_bytes()
    assert _add(UNBALANCED) == 1
    assert _journal(ledger).read_bytes() == before


def test_未开科目回滚后文件字节级不变(ledger, capsys):
    before = _journal(ledger).read_bytes()
    assert _add(BAD_ACCOUNT) == 1
    assert _journal(ledger).read_bytes() == before
    assert "已回滚" in capsys.readouterr().out


def test_多笔被拒且不写入(ledger):
    before = _journal(ledger).read_bytes()
    assert _add(GOOD + "\n" + GOOD) == 1
    assert _journal(ledger).read_bytes() == before


def test_无日期被拒(ledger):
    assert _add('* "食堂" "没有日期"\n  Expenses:Other  1.00 CNY\n  Assets:Alipay') == 1


def test_空输入被拒(ledger, capsys):
    assert _add("  \n\n") == 1
    assert "没有读到分录" in capsys.readouterr().out


def test_Windows_换行符被规范化(ledger):
    assert _add(GOOD.replace("\n", "\r\n")) == 0
    assert "\r" not in _journal(ledger).read_text(encoding="utf-8")


def test_跨月新建文件并追加_include(ledger):
    main = ledger / "personal.beancount"
    assert _add(LAST_MONTH) == 0
    assert _journal(ledger, "2026-08").exists()
    assert 'include "personal/journal/2026-08.beancount"' in main.read_text(encoding="utf-8")


def test_新建月份文件带账本标题(ledger):
    assert _add(LAST_MONTH) == 0
    assert _journal(ledger, "2026-08").read_text(encoding="utf-8").startswith("; 测试个人账 · 2026-08 流水")


def test_跨月失败时还原_include_并删除孤儿文件(ledger):
    """旧实现回滚后会留下一个只有表头的空月份文件。"""
    main = ledger / "personal.beancount"
    before = main.read_bytes()
    assert _add(LAST_MONTH_BAD) == 1
    assert main.read_bytes() == before
    assert not _journal(ledger, "2026-08").exists()


def test_第二次跨月入账不重复追加_include(ledger):
    main = ledger / "personal.beancount"
    assert _add(LAST_MONTH) == 0
    assert _add(LAST_MONTH) == 0
    assert main.read_text(encoding="utf-8").count('include "personal/journal/2026-08.beancount"') == 1


def test_未来日期被拒且不写入(ledger, capsys):
    before = _journal(ledger).read_bytes()
    assert _add(GOOD.replace("2026-09-23", "2026-09-24")) == 1
    assert _journal(ledger).read_bytes() == before
    assert "晚于今天" in capsys.readouterr().out


def test_当天手写_time_晚于此刻被拒(ledger, capsys):
    block = GOOD.replace('"餐饮-晚餐"', '"餐饮-晚餐"\n  time: "23:10"')
    assert _add(block) == 1
    assert "不要估" in capsys.readouterr().out


def test_当天手写_time_早于此刻照常入账且不被覆盖(ledger):
    block = GOOD.replace('"餐饮-晚餐"', '"餐饮-晚餐"\n  time: "08:05"')
    assert _add(block) == 0
    text = _journal(ledger).read_text(encoding="utf-8")
    assert '  time: "08:05"' in text
    assert '  time: "21:30"' not in text


def test_触及往来科目时提醒记另一边(ledger, capsys):
    assert _add(MIRROR) == 0
    out = capsys.readouterr().out
    assert "[提示]" in out and "shop 账的 Liabilities:OwnerLoan" in out


def test_普通分录不出往来提醒(ledger, capsys):
    assert _add(GOOD) == 0
    assert "[提示]" not in capsys.readouterr().out


def test_只有个人账时照常入账(solo):
    assert _add(GOOD) == 0


def test_入口文件不在根目录时_include_按入口文件相对路径写(ledger):
    """beancount 的 include 相对“写 include 的那个文件”解析；入口放子目录时路径要跟着变。"""
    cfg = ledger / "ledger.toml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace(
        '[books.personal]\n', '[books.personal]\nmain = "books/personal.beancount"\n'), encoding="utf-8")
    (ledger / "books").mkdir()
    (ledger / "books" / "personal.beancount").write_text(
        'option "operating_currency" "CNY"\ninclude "../personal/accounts.beancount"\n', encoding="utf-8")
    assert _add(GOOD) == 0
    main_text = (ledger / "books" / "personal.beancount").read_text(encoding="utf-8")
    assert 'include "../personal/journal/2026-09.beancount"' in main_text
