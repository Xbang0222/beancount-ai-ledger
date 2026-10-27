"""对方与摘要的写法检查：配了 [naming] 就在 add / amend / check 时把关，没配不影响任何东西。"""
import io

import pytest

from ledgerlib import add, cli, config, edit, journal

NAMING = """
[naming]
markers = ["股东往来", "测试", "建行入账"]
banned_payees = ["商家"]
vague_items = ["日用品"]
refund_suffix = ["退款", "退回"]
note_required = ["Expenses:Other"]
fallback = ["先查速查词典", "实在不行记 Expenses:Other"]

[naming.prefix.personal]
"Expenses:Food" = "餐饮-"
"Expenses:Other" = "其他-"
"Income:Other" = "其他收入-"

[naming.prefix.shop]
"Expenses:COGS" = "主营业务成本-"
"Income:Revenue" = ["主营业务收入（", "销售退回"]

[[naming.patterns]]
book = "shop"
name = "经营卡付股东个人消费"
when = ["Liabilities:OwnerLoan"]
with = ["Assets:Bank:Main"]
payee = "股东"
narration = "股东占用经营资金-"
hint = "商店不跟餐馆发生业务"

[[naming.patterns]]
book = "personal"
name = "个人账与商店往来"
when = ["Assets:Receivable:Shop", "Liabilities:Shop"]
with = ["Assets:Wechat", "Assets:Alipay"]
payee = ["商店", "往来对冲"]
"""


@pytest.fixture
def named(ledger):
    with open(ledger / "ledger.toml", "a", encoding="utf-8") as f:
        f.write(NAMING)
    return ledger


def _add(block, book="personal"):
    return add.cmd_add(book, stream=io.StringIO(block))


def _txn(head, *legs):
    return "\n".join([head] + [f"  {leg}" for leg in legs])


def test_合规写法照常入账(named):
    assert _add(_txn('2026-09-23 * "食堂" "餐饮-晚餐"', "Expenses:Food:Dining  30.00 CNY", "Assets:Alipay")) == 0


@pytest.mark.parametrize("head,legs,expect", [
    ('2026-09-23 * "食堂" "晚餐支出"', ("Expenses:Food:Dining  30.00 CNY", "Assets:Alipay"), "「餐饮-」开头"),
    ('2026-09-23 * "商家" "餐饮-晚餐"', ("Expenses:Food:Dining  30.00 CNY", "Assets:Alipay"), "太空泛"),
    ('2026-09-23 * "超市" "其他-日用品"', ("Expenses:Other  9.00 CNY", "Assets:Alipay"), "太笼统"),
    ('2026-09-23 * "超市" "其他-神秘礼盒"', ("Expenses:Other  9.00 CNY", "Assets:Alipay"), "要写 note"),
    ('2026-09-23 * "食堂" "餐饮-晚餐（和同事一起）"', ("Expenses:Food:Dining  30.00 CNY", "Assets:Alipay"), "note"),
    ('2026-09-23 * "水果店" "餐饮-水果-黄桃"', ("Expenses:Food:Dining  30.00 CNY", "Assets:Alipay"), "只用一个"),
    ('2026-09-23 * "客户" "其他代收"', ("Assets:Wechat  30.00 CNY", "Liabilities:Shop"), "对方写「商店」"),
])
def test_不合规写法被拒且不落盘(named, capsys, head, legs, expect):
    path = named / "personal" / "journal" / "2026-09.beancount"
    before = path.read_bytes()
    assert _add(_txn(head, *legs)) == 1
    out = capsys.readouterr().out
    assert "写法不合规" in out and expect in out
    assert path.read_bytes() == before


def test_固定标记允许留在括号里(named):
    assert _add(_txn('2026-09-23 * "商店" "代收商店营业款-微信（股东往来）"',
                     "Assets:Wechat  30.00 CNY", "Liabilities:Shop")) == 0


def test_省略金额的那条按其余之和定主科目(named, capsys):
    # 收入科目省略金额：仍按它判摘要开头，且不因缺金额报错
    assert _add(_txn('2026-09-23 * "客户" "主营业务收入"', "Assets:Bank:Main  100.00 CNY", "Income:Revenue"),
                book="shop") == 1
    assert "主营业务收入（" in capsys.readouterr().out
    assert _add(_txn('2026-09-23 * "客户" "主营业务收入（建行入账）"',
                     "Assets:Bank:Main  100.00 CNY", "Income:Revenue"), book="shop") == 0


def test_多个收支科目按金额最大的定开头(named):
    assert _add(_txn('2026-09-23 * "食堂" "餐饮-晚餐"', 'note: "另付餐具费"', "Expenses:Food:Dining  30.00 CNY",
                     "Expenses:Other  1.00 CNY", "Assets:Alipay")) == 0


def test_经营卡付个人消费只能记成股东占用(named, capsys):
    bad = _txn('2026-09-23 * "餐馆" "代股东支付个人消费"', "Liabilities:OwnerLoan  12.00 CNY", "Assets:Bank:Main")
    assert _add(bad, book="shop") == 1
    assert "商店不跟餐馆发生业务" in capsys.readouterr().out
    good = _txn('2026-09-23 * "股东" "股东占用经营资金-过桥豆腐"', "Liabilities:OwnerLoan  12.00 CNY",
                "Assets:Bank:Main")
    assert _add(good, book="shop") == 0


def test_场景只管只涉及这些科目的分录(named):
    # 多了一个场景外的科目（费用），就不按“股东往来”场景要求对方写股东
    assert _add(_txn('2026-09-23 * "OpenToken" "主营业务成本-采购API额度"',
                     "Expenses:COGS  50.00 CNY", "Liabilities:OwnerLoan"), book="shop") == 0


def test_amend_同样把关写法(named, capsys):
    ident = next(b.ident for b in journal.book_blocks("personal") if "餐饮-午餐" in b.text)
    bad = _txn('2026-09-02 * "食堂" "午饭"', "Expenses:Food:Dining  20.00 CNY", "Assets:Alipay")
    assert edit.cmd_amend("personal", ident, stream=io.StringIO(bad)) == 1
    assert "写法不合规" in capsys.readouterr().out


def test_check_列出全账不合规的分录(named, capsys):
    # 夹具里商店账有一笔对方「供应商」、摘要「主营业务成本-采购」：合规；改出一笔不合规的
    path = named / "personal" / "journal" / "2026-09.beancount"
    path.write_text(path.read_text(encoding="utf-8").replace('"餐饮-午餐"', '"午饭"'), encoding="utf-8")
    assert cli.main(["check"]) == 1
    out = capsys.readouterr().out
    assert "1 笔对方/摘要写法不合规" in out and "personal/journal/2026-09.beancount" in out


def test_check_全部合规时通过(named):
    assert cli.main(["check"]) == 0


def test_没配_naming_不做写法检查(ledger):
    assert config.load().naming is None
    assert _add(_txn('2026-09-23 * "商家" "随便写"', "Expenses:Food:Dining  30.00 CNY", "Assets:Alipay")) == 0


def test_兜底科目写了_note_就能入账(named):
    assert _add('2026-09-23 * "超市" "其他-神秘礼盒"\n  note: "盲盒，分不清是玩具还是零食"\n'
                "  Expenses:Other  9.00 CNY\n  Assets:Alipay") == 0


def test_rules_打印找不到分类时的处理步骤(named, capsys):
    assert cli.main(["rules"]) == 0
    out = capsys.readouterr().out
    assert "找不到分类时" in out and "1. 先查速查词典" in out


def test_退款摘要末尾要加退款(named, capsys):
    # 费用科目省略金额、按其余各条推出是冲回：没写「退款」被拒，写了就过
    bad = _txn('2026-09-23 * "网店" "餐饮-燕麦"', "Assets:Alipay  23.65 CNY", "Expenses:Food:Dining")
    assert _add(bad) == 1
    assert "末尾加「退款」" in capsys.readouterr().out
    assert _add(_txn('2026-09-23 * "网店" "餐饮-燕麦退款"', "Assets:Alipay  23.65 CNY", "Expenses:Food:Dining")) == 0


def test_退款结尾不看括号里的固定标记(named):
    assert _add(_txn('2026-09-23 * "商店" "餐饮-晚餐退款（股东往来）"',
                     "Assets:Wechat  5.00 CNY", "Expenses:Food:Dining  -5.00 CNY")) == 0


def test_商店销售退回也算合规退款(named):
    assert _add(_txn('2026-09-23 * "客户" "销售退回"', "Income:Revenue  20.00 CNY", "Assets:Bank:Main"),
                book="shop") == 0


def test_check_报出没配摘要开头的收支科目(named, capsys):
    path = named / "personal" / "accounts.beancount"
    path.write_text(path.read_text(encoding="utf-8") + "2026-08-31 open Expenses:Travel:Lodging CNY\n",
                    encoding="utf-8")
    assert cli.main(["check"]) == 1
    out = capsys.readouterr().out
    assert "没配摘要开头" in out and "Expenses:Travel:Lodging" in out


def test_rules_打印对照表(named, capsys):
    assert cli.main(["rules", "shop"]) == 0
    out = capsys.readouterr().out
    assert "Income:Revenue" in out and "主营业务收入（ / 销售退回" in out
    assert "经营卡付股东个人消费" in out and "（股东往来）" in out and "personal" not in out


def test_rules_没配_naming_时说明(ledger, capsys):
    assert cli.main(["rules"]) == 0
    assert "没有配置 [naming]" in capsys.readouterr().out


@pytest.mark.parametrize("extra,msg", [
    ('[naming]\nmarkers = "x"\nfoo = 1\n', "不认识的键"),
    ('[naming.prefix.nobook]\n"Expenses:Food" = "餐饮-"\n', "未声明的账本"),
    ('[naming.prefix.personal]\n"Food" = "餐饮-"\n', "科目名不合法"),
    ('[[naming.patterns]]\nbook = "shop"\nwhen = []\npayee = "股东"\n', "when"),
])
def test_naming_配置写错直接报错(ledger, extra, msg):
    with open(ledger / "ledger.toml", "a", encoding="utf-8") as f:
        f.write("\n" + extra)
    with pytest.raises(config.ConfigError, match=msg):
        config.load()


@pytest.mark.parametrize("template", ["personal", "business", "minimal"])
def test_new_book_按模板补上摘要开头(named, template):
    from ledgerlib import books, naming, newbook

    assert newbook.cmd_new_book("extra", template=template) == 0
    assert config.load().naming.prefix["extra"]
    entries, _, _ = books.load_book("extra")
    assert naming.unmapped("extra", entries) == []


def test_没配开头表的账本不算漏配(named):
    from ledgerlib import books, naming

    cfg = named / "ledger.toml"
    text = cfg.read_text(encoding="utf-8")
    head, tail = text.split("[naming.prefix.shop]")
    cfg.write_text(head + tail.split("\n\n", 1)[1], encoding="utf-8")
    assert "shop" not in config.load().naming.prefix
    entries, _, _ = books.load_book("shop")
    assert naming.unmapped("shop", entries) == []
