"""入账与回滚：坏账绝不能落盘。"""
import io

import pytest

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
    assert _add(LAST_MONTH.replace("晚餐", "夜宵")) == 0
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


def test_从文件读取分录_兼容_BOM_与_CRLF(ledger, tmp_path):
    """PowerShell 管道会把中文变成问号，所以 add 也能从 UTF-8 文件读。"""
    f = tmp_path / "entry.tmp"
    f.write_bytes(b"\xef\xbb\xbf" + GOOD.replace("\n", "\r\n").encode("utf-8"))
    assert add.cmd_add("personal", path=str(f)) == 0
    text = _journal(ledger).read_text(encoding="utf-8")
    assert "餐饮-晚餐" in text and "\r" not in text


def test_分录文件不存在时报错且不写入(ledger, tmp_path, capsys):
    before = _journal(ledger).read_bytes()
    assert add.cmd_add("personal", path=str(tmp_path / "nope.tmp")) == 1
    assert _journal(ledger).read_bytes() == before
    assert "读不了分录文件" in capsys.readouterr().out


def test_命令行_add_支持_file_参数(ledger, tmp_path):
    from ledgerlib import cli

    f = tmp_path / "entry.tmp"
    f.write_text(GOOD, encoding="utf-8")
    assert cli.main(["add", "personal", "--file", str(f)]) == 0
    assert "餐饮-晚餐" in _journal(ledger).read_text(encoding="utf-8")


def test_余额断言对得上时写入且不注入_time(ledger, capsys):
    """用户报“支付宝现在还剩多少”时，用 balance 断言核对；断言日期写明天才包含今天的交易。"""
    assert _add("2026-09-24 balance Assets:Alipay  -20.00 CNY") == 0
    text = _journal(ledger).read_text(encoding="utf-8")
    assert text.rstrip().endswith("2026-09-24 balance Assets:Alipay  -20.00 CNY")
    assert "通过校验" in capsys.readouterr().out


def test_余额断言对不上时回滚并报出差额(ledger, capsys):
    before = _journal(ledger).read_bytes()
    assert _add("2026-09-24 balance Assets:Alipay  0.00 CNY") == 1
    assert _journal(ledger).read_bytes() == before
    out = capsys.readouterr().out
    assert "已回滚" in out and "20.00" in out


def test_内容相同的分录第二次入账被拒且回滚(ledger, capsys):
    journal = ledger / "personal" / "journal" / "2026-09.beancount"
    assert _add(GOOD) == 0
    before = journal.read_bytes()
    assert _add(GOOD) == 1
    assert journal.read_bytes() == before
    assert "疑似重复" in capsys.readouterr().out


def test_重复判定不看_time_与金额留空的写法(ledger):
    assert _add(GOOD) == 0
    same = GOOD.replace('"餐饮-晚餐"', '"餐饮-晚餐"\n  time: "08:00"').replace(
        "  Assets:Alipay", "  Assets:Alipay  -30.00 CNY")
    assert _add(same) == 1


def test_确实是两笔时可用_allow_duplicate_放行(ledger):
    assert _add(GOOD) == 0
    assert add.cmd_add("personal", stream=io.StringIO(GOOD), allow_duplicate=True) == 0


def test_金额不同不算重复(ledger):
    assert _add(GOOD) == 0
    assert _add(GOOD.replace("30.00", "31.00")) == 0


@pytest.mark.parametrize("header", ['* "食堂"', '* "" "餐饮-晚餐"', '* "食堂" ""', '*'])
def test_缺对方或摘要被拒且不写入(ledger, capsys, header):
    journal = ledger / "personal" / "journal" / "2026-09.beancount"
    before = journal.read_bytes()
    assert _add(f"2026-09-23 {header}\n  Expenses:Food:Dining  30.00 CNY\n  Assets:Alipay") == 1
    assert journal.read_bytes() == before
    assert "对方和摘要" in capsys.readouterr().out


@pytest.mark.parametrize("value", ["25:99", "下午", "9:40", "12:60", "12:00:00"])
def test_非法_time_被拒且不写入(ledger, capsys, value):
    journal = ledger / "personal" / "journal" / "2026-09.beancount"
    before = journal.read_bytes()
    block = GOOD.replace('"餐饮-晚餐"', f'"餐饮-晚餐"\n  time: "{value}"').replace("09-23", "09-20")
    assert _add(block) == 1
    assert journal.read_bytes() == before
    assert "HH:MM" in capsys.readouterr().out


@pytest.mark.parametrize("directive", [
    "2026-09-20 open Expenses:Whatever CNY",
    "2026-09-20 close Assets:Wechat",
    '2026-09-20 commodity BTC',
])
def test_开户等科目表指令不进序时簿(ledger, capsys, directive):
    journal = ledger / "personal" / "journal" / "2026-09.beancount"
    before = journal.read_bytes()
    assert _add(directive) == 1
    assert journal.read_bytes() == before
    assert "序时簿不收" in capsys.readouterr().out


@pytest.mark.parametrize("amount", ["30", "30.0", "30.000"])
def test_重复判定按数值比金额_写法不同也算重复(ledger, amount):
    assert _add(GOOD) == 0
    assert _add(GOOD.replace("30.00", amount)) == 1


EARLY = '2026-09-01 * "食堂" "餐饮-早餐"\n  time: "07:00"\n  Expenses:Food:Dining  8.00 CNY\n  Assets:Alipay'


def _sorted_ledger(ledger):
    from ledgerlib import fmt

    assert fmt.cmd_fmt(("personal",)) == 0
    return ledger / "personal" / "journal" / "2026-09.beancount"


def test_补记较早的账插到按时间该在的位置(ledger):
    """旧实现一律追加到末尾，补记之后序时簿乱序，fmt --check 不过、提交被钩子拒绝。"""
    from ledgerlib import fmt

    journal = _sorted_ledger(ledger)
    assert _add(EARLY) == 0
    text = journal.read_text(encoding="utf-8")
    assert text.index("餐饮-早餐") < text.index("代垫商店采购款") < text.index("餐饮-午餐")
    assert fmt.cmd_fmt(("personal",), check_only=True) == 0


def test_最新的一笔仍然追加到末尾(ledger):
    from ledgerlib import fmt

    journal = _sorted_ledger(ledger)
    assert _add(GOOD) == 0
    assert journal.read_text(encoding="utf-8").rstrip().endswith("Assets:Alipay")
    assert fmt.cmd_fmt(("personal",), check_only=True) == 0


def test_插到中间的分录同样做重复检测(ledger, capsys):
    journal = _sorted_ledger(ledger)
    assert _add(EARLY) == 0
    before = journal.read_bytes()
    assert _add(EARLY) == 1
    assert journal.read_bytes() == before
    assert "疑似重复" in capsys.readouterr().out


def test_序时簿本来就乱序时只追加不替用户重排(ledger):
    journal = ledger / "personal" / "journal" / "2026-09.beancount"
    before = journal.read_text(encoding="utf-8")
    assert _add(EARLY) == 0
    after = journal.read_text(encoding="utf-8")
    assert after.startswith(before) and after.rstrip().endswith("Assets:Alipay")


def test_原文件是_CRLF_时入账后仍是_CRLF(ledger):
    journal = ledger / "personal" / "journal" / "2026-09.beancount"
    # 先统一成 LF 再转：Windows 上测试夹具写出来的文件本身就是 CRLF
    journal.write_bytes(journal.read_bytes().replace(b"\r\n", b"\n").replace(b"\n", b"\r\n"))
    assert _add(GOOD) == 0
    data = journal.read_bytes()
    assert "餐饮-晚餐".encode() in data
    assert data.count(b"\n") == data.count(b"\r\n")


def test_原文件是_LF_时不引入_CRLF(ledger):
    journal = ledger / "personal" / "journal" / "2026-09.beancount"
    journal.write_bytes(journal.read_bytes().replace(b"\r\n", b"\n"))
    assert _add(GOOD) == 0
    assert b"\r" not in journal.read_bytes()
