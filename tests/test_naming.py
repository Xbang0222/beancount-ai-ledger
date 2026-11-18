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
    # 这里只测写法：往来分录单边入账的拦截由 test_add / test_pair 覆盖，一律放行
    return add.cmd_add(book, stream=io.StringIO(block), one_sided=True)


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
    assert "1 笔对方、摘要或 note 的写法不合规" in out and "personal/journal/2026-09.beancount" in out


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


def test_双向科目借方发生额不按退款检查(ledger):
    # 投资盈亏一类科目亏损时记在借方，属于正常发生额，不要求摘要以「退款」结尾
    with open(ledger / "ledger.toml", "a", encoding="utf-8") as f:
        f.write(NAMING.replace('refund_suffix = ["退款", "退回"]\n',
                               'refund_suffix = ["退款", "退回"]\ntwo_way = ["Income:Other"]\n'))
    assert config.load().naming.two_way == ("Income:Other",)
    assert _add(_txn('2026-09-23 * "基金" "其他收入-基金浮亏"', "Income:Other  12.30 CNY", "Assets:Alipay")) == 0


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


FORBIDDEN = """
[[naming.forbidden]]
name = "具体日期"
pattern = '\\d{1,2}月\\d{1,2}[日号]|(?<!\\d)\\d{1,2}号(?![线楼电汽])|昨天'
hint = "所属期间可以保留，其余日期信息写入 note:"

[[naming.forbidden]]
name = "具体时刻"
pattern = '(?<!\\d)\\d{1,2}[:：]\\d{2}(?!\\d)|(?<!\\d)\\d{1,2}点(?![券卡])'
hint = "交易时刻写入 time: 元数据"

[[naming.forbidden]]
field = "payee"
name = "注册全称"
pattern = '有限公司|个体工商户|收单'
hint = "对方写店名简称或业务描述"

[[naming.patterns]]
book = "personal"
name = "自有账户之间的划转"
when = ["Assets:Alipay", "Assets:Wechat"]
narration = ["银行转账-", "银行取现"]
hint = "对方写转出机构"
"""


@pytest.fixture
def strict(named):
    with open(named / "ledger.toml", "a", encoding="utf-8") as f:
        f.write(FORBIDDEN)
    return named


@pytest.mark.parametrize("head,expect", [
    ('2026-09-23 * "客运站" "餐饮-9月21日成都到重庆"', "含具体日期「9月21日」"),
    ('2026-09-23 * "客运站" "餐饮-19号21点30成都到重庆"', "含具体日期「19号」"),
    ('2026-09-23 * "客运站" "餐饮-19号21点30成都到重庆"', "含具体时刻「21点」"),
    ('2026-09-23 * "客运站" "餐饮-重庆到成都20:10"', "含具体时刻「20:10」"),
    ('2026-09-23 * "食堂" "餐饮-昨天午餐"', "含具体日期「昨天」"),
    ('2026-09-23 * "成都某某餐饮管理有限公司" "餐饮-午餐"', "对方「成都某某餐饮管理有限公司」含注册全称「有限公司」"),
])
def test_摘要夹带日期时刻与对方写注册全称被拒(strict, capsys, head, expect):
    path = strict / "personal" / "journal" / "2026-09.beancount"
    before = path.read_bytes()
    assert _add(_txn(head, "Expenses:Food:Dining  30.00 CNY", "Assets:Alipay")) == 1
    out = capsys.readouterr().out
    assert "写法不合规" in out and expect in out
    assert path.read_bytes() == before


@pytest.mark.parametrize("payee,narr", [
    ("房东", "餐饮-9月伙食费"),          # 所属期间不是具体日期
    ("地铁", "餐饮-1号线站内便当"),      # 线路编号
    ("便利店", "餐饮-5号电池赠饮"),      # 型号
    ("加油站", "餐饮-92号汽油赠水"),
    ("游戏平台", "餐饮-60点券兑换饮料"),
    ("保险公司", "餐饮-午餐"),           # 「公司」不等于注册全称
    ("食堂", "餐饮-2026年9月餐费"),
])
def test_期间编号型号不被日期时刻规则误拦(strict, payee, narr):
    assert _add(_txn(f'2026-09-23 * "{payee}" "{narr}"', "Expenses:Food:Dining  30.00 CNY", "Assets:Alipay")) == 0


def test_check_按禁止写法扫描既有分录(strict, capsys):
    path = strict / "personal" / "journal" / "2026-09.beancount"
    path.write_text(path.read_text(encoding="utf-8").replace('"餐饮-午餐"', '"餐饮-2号午餐"'), encoding="utf-8")
    assert cli.main(["check"]) == 1
    assert "含具体日期「2号」" in capsys.readouterr().out


def test_rules_打印禁止写法(strict, capsys):
    assert cli.main(["rules", "personal"]) == 0
    out = capsys.readouterr().out
    assert "摘要不得出现具体日期：所属期间可以保留" in out
    assert "对方不得出现注册全称：对方写店名简称或业务描述" in out


def test_固定场景可以只限定摘要开头(strict, capsys):
    legs = ("Assets:Alipay  100.00 CNY", "Assets:Wechat")
    assert _add(_txn('2026-09-23 * "微信" "微信提现到支付宝"', *legs)) == 1
    out = capsys.readouterr().out
    assert "「自有账户之间的划转」摘要以「银行转账-」或「银行取现」开头：对方写转出机构" in out
    assert "对方写「" not in out
    # 对方不限：写哪家机构都可以
    assert _add(_txn('2026-09-23 * "微信" "银行转账-微信转支付宝"', *legs)) == 0
    assert cli.main(["rules", "personal"]) == 0
    out = capsys.readouterr().out
    assert "自有账户之间的划转" in out and "对方只能写" not in out.split("自有账户之间的划转")[1]


@pytest.mark.parametrize("extra,msg", [
    ('[naming]\nmarkers = "x"\nfoo = 1\n', "不认识的键"),
    ('[naming.prefix.nobook]\n"Expenses:Food" = "餐饮-"\n', "未声明的账本"),
    ('[naming.prefix.personal]\n"Food" = "餐饮-"\n', "科目名不合法"),
    ('[[naming.patterns]]\nbook = "shop"\nwhen = []\npayee = "股东"\n', "when"),
    ('[[naming.patterns]]\nbook = "shop"\nwhen = ["Liabilities:OwnerLoan"]\n', "payee（允许的对方）或 narration"),
    ('[[naming.forbidden]]\nname = "日期"\npattern = "(未闭合"\n', "不是合法的正则表达式"),
    ('[[naming.forbidden]]\npattern = "x"\n', "缺少 name"),
    ('[[naming.forbidden]]\nname = "日期"\n', "缺少 pattern"),
    ('[[naming.forbidden]]\nname = "日期"\npattern = "x"\nfield = "tags"\n', "field 应为"),
    ('[[naming.forbidden]]\nname = "日期"\npattern = "x"\nwhere = "摘要"\n', "不认识的键"),
    ('[naming]\nforbidden = "x"\n', "数组表"),
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


NOTE_RULES = """
[[naming.forbidden]]
field = "note"
name = "口语"
pattern = '一起|帮人'
hint = "note 写书面短语"

[[naming.forbidden]]
field = "note"
name = "句号或段末标点"
pattern = '。|[，；、：]$'
hint = "note 写短语，不加句号，段末不加标点"

[[naming.forbidden]]
field = "note"
tag = "friend"
name = "标签已表达的交易对象"
pattern = '与朋友(用餐|共同消费)'
hint = "交易对象由标签表达"

[[naming.forbidden]]
field = "note"
account = "Assets:Wechat"
name = "分录已表达的结算账户"
pattern = '微信(零钱)?(支付|付款)'
hint = "结算账户由分录表达"
"""


@pytest.fixture
def tidy(named):
    with open(named / "ledger.toml", "a", encoding="utf-8") as f:
        f.write(NOTE_RULES)
    return named


def _noted(note, head='2026-09-23 * "餐馆" "餐饮-晚餐"', pay="Assets:Alipay"):
    return _txn(head, f'note: "{note}"', "Expenses:Food:Dining  30.00 CNY", pay)


@pytest.mark.parametrize("note,head,pay,expect", [
    ("和朋友一起吃的火锅", '2026-09-23 * "餐馆" "餐饮-晚餐"', "Assets:Alipay", "含口语「一起」"),
    ("火鸡面。", '2026-09-23 * "餐馆" "餐饮-晚餐"', "Assets:Alipay", "含句号或段末标点「。」"),
    ("火鸡面，", '2026-09-23 * "餐馆" "餐饮-晚餐"', "Assets:Alipay", "含句号或段末标点「，」"),
    ("与朋友用餐", '2026-09-23 * "餐馆" "餐饮-晚餐" #friend', "Assets:Alipay", "含标签已表达的交易对象"),
    ("火鸡面；微信零钱支付", '2026-09-23 * "餐馆" "餐饮-晚餐"', "Assets:Wechat", "含分录已表达的结算账户"),
])
def test_note_口语句号与重复信息被拒(tidy, capsys, note, head, pay, expect):
    path = tidy / "personal" / "journal" / "2026-09.beancount"
    before = path.read_bytes()
    assert _add(_noted(note, head, pay)) == 1
    out = capsys.readouterr().out
    assert "写法不合规" in out and expect in out
    assert path.read_bytes() == before


@pytest.mark.parametrize("note,head,pay", [
    ("火鸡面；经营卡代付", '2026-09-23 * "餐馆" "餐饮-晚餐"', "Assets:Alipay"),
    ("与朋友用餐", '2026-09-23 * "餐馆" "餐饮-晚餐"', "Assets:Alipay"),            # 没带标签，不算重复
    ("微信零钱支付", '2026-09-23 * "餐馆" "餐饮-晚餐"', "Assets:Alipay"),          # 分录不涉及微信，不算重复
    ("账单备注：和朋友一起吃的。微信支付", '2026-09-23 * "餐馆" "餐饮-晚餐" #friend', "Assets:Wechat"),
    ("按微信零钱处理；账单备注：一起吃。", '2026-09-23 * "餐馆" "餐饮-晚餐"', "Assets:Alipay"),
])
def test_note_条件不满足与来源备注原文不受限(tidy, note, head, pay):
    assert _add(_noted(note, head, pay)) == 0


def test_note_规则写进_rules_对照表(tidy, capsys):
    assert cli.main(["rules"]) == 0
    out = capsys.readouterr().out
    assert "带 #friend 的分录，note 不得出现标签已表达的交易对象" in out
    assert "涉及 Assets:Wechat 的分录，note 不得出现分录已表达的结算账户" in out


NOTE_LABELS = """
[naming.note_labels]
"明细" = "交易的具体内容"
"支付" = "分录无法表达的支付情况"
"核对" = "余额核对的数字"
"依据" = "推定与缺失信息的说明"
"""


@pytest.fixture
def labeled(named):
    # note_labels 是 [naming] 的子表：写在文件末尾的其他表之后同样归属 [naming]
    with open(named / "ledger.toml", "a", encoding="utf-8") as f:
        f.write(NOTE_LABELS)
    return named


@pytest.mark.parametrize("note,expect", [
    ("火鸡面", "没有写栏目"),
    ("明细：火鸡面；经营卡代付", "没有写栏目"),
    ("备忘：火鸡面", "没有写栏目"),
    ("明细：", "栏没有内容"),
    ("明细：火鸡面；明细：加蛋", "出现了两次"),
    ("支付：经营卡代付；明细：火鸡面", "位置不对"),
    ("支付：分3笔：6+5+8", "有两个「：」"),
])
def test_note_分栏格式不合规被拒(labeled, capsys, note, expect):
    path = labeled / "personal" / "journal" / "2026-09.beancount"
    before = path.read_bytes()
    assert _add(_noted(note)) == 1
    out = capsys.readouterr().out
    assert "写法不合规" in out and expect in out
    assert path.read_bytes() == before


@pytest.mark.parametrize("note", [
    "明细：火鸡面",
    "明细：火鸡面；支付：经营卡代付，分3笔6+5+8",
    "核对：实际8.42，账面0.52；依据：时间未报",
    "账单备注：和朋友一起吃的。没有栏目；也不检查",
    "依据：付款账户未指定，按微信零钱记；账单备注：9月21日成都到重庆",
])
def test_note_分栏格式合规与来源备注原文(labeled, note):
    assert _add(_noted(note)) == 0


def test_note_未配置栏目时不查分栏格式(named):
    assert _add(_noted("火鸡面")) == 0


def test_note_栏目写进_rules_对照表(labeled, capsys):
    assert cli.main(["rules"]) == 0
    out = capsys.readouterr().out
    assert "note 格式：「栏目：内容；栏目：内容」" in out
    assert "明细：交易的具体内容" in out and "<来源>备注：导入来源的备注原文" in out


@pytest.mark.parametrize("body,expect", [
    ('note_labels = ["明细"]\n', "应为 栏目名"),
    ('[naming.note_labels]\n"明 细" = "x"\n', "不能含标点或空格"),
    ('[naming.note_labels]\n"账单备注" = "x"\n', "留给导入来源的备注原文"),
    ('[naming.note_labels]\n"明细" = 1\n', "说明应为字符串"),
])
def test_note_labels_配置写错时报错(tmp_path, body, expect):
    raw = config.tomllib.loads(body if body.startswith("[") else "[naming]\n" + body)
    with pytest.raises(config.ConfigError) as e:
        config.parse({"books": {"personal": {}}, **raw})
    assert expect in str(e.value)


def test_note_超过字数上限被拒且来源备注原文不计(named, capsys):
    with open(named / "ledger.toml", encoding="utf-8") as f:
        text = f.read()
    with open(named / "ledger.toml", "w", encoding="utf-8") as f:
        f.write(text.replace("[naming]\n", "[naming]\nnote_max = 10\n", 1))
    assert _add(_noted("火鸡面加蛋加肠加辣加葱花")) == 1
    assert "note 共 12 字，超过 10 字上限" in capsys.readouterr().out
    assert _add(_noted("火鸡面；账单备注：这一段是导入来源的原文，再长也不计入字数")) == 0
    assert cli.main(["rules"]) == 0
    assert "note 不超过 10 字（不含导入来源的备注原文）" in capsys.readouterr().out


@pytest.mark.parametrize("value", ['"60"', "-1", "true", "1.5"])
def test_note_max_配置写错时报错(value):
    raw = config.tomllib.loads(f"[naming]\nnote_max = {value}\n")
    with pytest.raises(config.ConfigError) as e:
        config.parse({"books": {"personal": {}}, **raw})
    assert "note_max 应为不小于 0 的整数" in str(e.value)


NOTE_REQUIRED = """
[[naming.required]]
book = "personal"
name = "代付或代收的账户"
when = ["Assets:Receivable:Shop", "Liabilities:Shop"]
with = ["Expenses", "Income"]
pattern = '结算：'
hint = "在「结算」栏写明账户"
"""


@pytest.fixture
def must(named):
    with open(named / "ledger.toml", "a", encoding="utf-8") as f:
        f.write(NOTE_REQUIRED)
    return named


def test_note_必写内容缺失被拒且不落盘(must, capsys):
    path = must / "personal" / "journal" / "2026-09.beancount"
    before = path.read_bytes()
    bare = _txn('2026-09-23 * "餐馆" "餐饮-晚餐"', "Expenses:Food:Dining  30.00 CNY", "Assets:Receivable:Shop")
    assert _add(bare) == 1
    out = capsys.readouterr().out
    assert "note 没有写明代付或代收的账户：在「结算」栏写明账户" in out
    assert _add(_noted("明细：火鸡面", pay="Assets:Receivable:Shop")) == 1
    assert path.read_bytes() == before


def test_note_必写内容写明即可入账且不涉及的分录不受限(must):
    assert _add(_noted("结算：经营卡代付", pay="Assets:Receivable:Shop")) == 0
    assert _add(_txn('2026-09-23 * "餐馆" "餐饮-晚餐"', "Expenses:Food:Dining  30.00 CNY", "Assets:Alipay")) == 0
    # 只涉及往来科目与资产科目的分录不属于收支，不要求写明
    assert _add(_txn('2026-09-23 * "商店" "代垫商店采购款（股东往来）"',
                     "Assets:Receivable:Shop  30.00 CNY", "Assets:Alipay")) == 0


def test_note_必写内容写进_rules_对照表(must, capsys):
    assert cli.main(["rules"]) == 0
    out = capsys.readouterr().out
    assert "note 必须写明" in out and "代付或代收的账户" in out


@pytest.mark.parametrize("body,expect", [
    ('required = "结算"\n', "数组表"),
    ('[[naming.required]]\nbook = "nope"\n', "已声明的账本"),
    ('[[naming.required]]\nbook = "personal"\n', "缺少 name"),
    ('[[naming.required]]\nbook = "personal"\nname = "x"\nwhen = ["Assets:Receivable:Shop"]\n', "缺少 pattern"),
    ('[[naming.required]]\nbook = "personal"\nname = "x"\nwhen = ["Assets:Receivable:Shop"]\npattern = "("\n',
     "不是合法的正则表达式"),
    ('[[naming.required]]\nbook = "personal"\nname = "x"\nwhen = ["Assets:Receivable:Shop"]\npattern = "x"\n'
     'extra = 1\n', "不认识的键"),
])
def test_naming_required_配置写错时报错(body, expect):
    raw = config.tomllib.loads(body if body.startswith("[") else "[naming]\n" + body)
    with pytest.raises(config.ConfigError) as e:
        config.parse({"books": {"personal": {}}, **raw})
    assert expect in str(e.value)
