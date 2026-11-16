"""资产负债汇总：账本间往来要抵销，外币要按价格折算，价格缺失或过期要说清楚。"""
from datetime import date
from decimal import Decimal

import pytest

from ledgerlib import networth, quote


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """默认当作数据源里查不到，测试不联网；需要联网取价的用例自己换掉 quote.price。"""
    def nothing(code, base, day=None):
        raise quote.NoRate(code)

    monkeypatch.setattr(quote, "price", nothing)

USD_INCOME = '''
2026-09-10 * "某平台" "其他收入-美元结算"
  time: "10:00"
  Assets:Bank:USD  100.00 USD
  Income:Other
'''
USD_PRICE = "\n2026-09-20 price USD 7.10 CNY\n"


def _append(path, text):
    path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")


def _personal_journal(root):
    return root / "personal" / "journal" / "2026-09.beancount"


def _run(capsys, overrides=None, offline=False):
    assert networth.cmd_networth(overrides, offline=offline) == 0
    return capsys.readouterr().out


def _section(out, title):
    return out.split(title, 1)[1].split("【", 1)[0]


def test_账本间往来被抵销不计入资产负债(ledger, capsys):
    out = _run(capsys)
    assets = _section(out, "【资产】")
    assert "Receivable:Shop" not in assets
    assert "OwnerLoan" not in _section(out, "【负债】")
    eliminated = _section(out, "【已抵销的账本间往来")
    assert "Assets:Receivable:Shop" in eliminated and "Liabilities:OwnerLoan" in eliminated


def test_不参与合并的账本_往来按真实债权列示(ledger, capsys):
    cfg = ledger / "ledger.toml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace(
        'kind = "business"\n', 'kind = "business"\nconsolidate = false\n'), encoding="utf-8")
    out = _run(capsys)
    assert "Assets:Receivable:Shop" in _section(out, "【资产】")
    assert "【未合并的账本】shop" in out


def test_只有一本账时显示单账本标题(solo, capsys):
    out = _run(capsys)
    assert "资产负债 · personal" in out
    assert "已抵销" not in out


def test_外币按账内价格折算并提示非当日价格(ledger, capsys):
    _append(_personal_journal(ledger), USD_INCOME + USD_PRICE)
    out = _run(capsys)
    assert "≈     710.00 CNY" in out
    assert "距今 3 天，非当日价格" in out
    assert "590.00 CNY" in _section(out, "【折合 CNY】")  # -120 + 710


def test_命令行汇率覆盖账内价格(ledger, capsys):
    from decimal import Decimal

    _append(_personal_journal(ledger), USD_INCOME + USD_PRICE)
    out = _run(capsys, {"USD": Decimal("7.5")})
    assert "≈     750.00 CNY" in out
    assert "命令行 --rate" in out


def test_缺少价格时明确提示且不计入折合合计(ledger, capsys):
    _append(_personal_journal(ledger), USD_INCOME)
    out = _run(capsys)
    assert "缺少 USD 的价格" in out
    assert "--rate USD=" in out


def _accounts(root):
    return root / "personal" / "accounts.beancount"


def test_默认联网取价_优先于账内旧价格(ledger, capsys, monkeypatch):
    _append(_personal_journal(ledger), USD_INCOME + USD_PRICE)
    monkeypatch.setattr(quote, "price", lambda code, base, day=None: (Decimal("7.2"), "2026-09-23", "测试源"))
    out = _run(capsys)
    assert "≈     720.00 CNY" in out
    assert "联网取价，测试源" in out


def test_offline不联网只用账内价格(ledger, capsys, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("offline 时不应联网")

    _append(_personal_journal(ledger), USD_INCOME + USD_PRICE)
    monkeypatch.setattr(quote, "price", boom)
    out = _run(capsys, offline=True)
    assert "≈     710.00 CNY" in out


def test_联网失败时提示并改用账内价格(ledger, capsys, monkeypatch):
    def down(code, base, day=None):
        raise quote.RateError("断网")

    _append(_personal_journal(ledger), USD_INCOME + USD_PRICE)
    monkeypatch.setattr(quote, "price", down)
    out = _run(capsys)
    assert "≈     710.00 CNY" in out
    assert "联网取价失败（断网）" in out


def test_标了networth_FALSE的账户单列且不计入净资产(ledger, capsys):
    _append(_accounts(ledger), "2026-08-31 open Assets:Benefit:Pension CNY\n  networth: FALSE\n")
    _append(_personal_journal(ledger), '''
2026-09-10 * "社保局" "社保入账-养老保险"
  time: "10:00"
  Assets:Benefit:Pension  500.00 CNY
  Income:Other
''')
    out = _run(capsys)
    assert "Pension" not in _section(out, "【资产】")
    assert "Assets:Benefit:Pension" in out.split("【不计入净资产", 1)[1]
    assert "Pension" not in _section(out, "【合计】")


GOLD = '''
2026-09-01 * "积存金" "转账-买入积存金"
  time: "10:00"
  Assets:Gold  1000.00 CNY
  Income:Other

2026-09-15 * "积存金" "转账-买入积存金"
  time: "10:00"
  Assets:Gold  900.00 CNY
  Income:Other
'''


def test_按金额记的黄金按每笔当天金价估算克数和现值(ledger, capsys, monkeypatch):
    _append(_accounts(ledger), '2026-08-31 open Assets:Gold CNY\n  estimate: "AU"\n')
    _append(_personal_journal(ledger), GOLD)
    px = {date(2026, 9, 1): Decimal(1000), date(2026, 9, 15): Decimal(900), None: Decimal(800)}
    monkeypatch.setattr(quote, "price", lambda code, base, day=None: (px[day], str(day), "测试金价"))
    out = _run(capsys)
    line = [x for x in out.splitlines() if "Assets:Gold" in x][0]
    assert "约 2.000 AU" in line and "1600.00 CNY" in line   # 1 克 + 1 克，现价 800
    assert "1 AU = 800 CNY" in out


def test_别的账本同名科目标了estimate不影响本账本(ledger, capsys, monkeypatch):
    # 个人账的 Assets:Gold 没标 estimate，商店账开了同名科目并标了、但没有余额：不该去拉金价
    _append(_accounts(ledger), "2026-08-31 open Assets:Gold CNY\n")
    _append(ledger / "shop" / "accounts.beancount", '2026-08-31 open Assets:Gold CNY\n  estimate: "AU"\n')
    _append(_personal_journal(ledger), GOLD)
    asked = []

    def price(code, base, day=None):
        asked.append(code)
        raise quote.NoRate(code)

    monkeypatch.setattr(quote, "price", price)
    out = _run(capsys)
    line = [x for x in out.splitlines() if "Assets:Gold" in x][0]
    assert "1900.00 CNY" in line and "买入成本" not in line
    assert "AU" not in asked


def test_金价查不到时按成本列示并说明(ledger, capsys):
    _append(_accounts(ledger), '2026-08-31 open Assets:Gold CNY\n  estimate: "AU"\n')
    _append(_personal_journal(ledger), GOLD)
    out = _run(capsys)
    assert "估算现值失败" in out


# ---------- 合伙人还没分走的利润：留在账本里，但不是所有者的钱 ----------

DIVIDEND_CONFIG = """
[dividend]
book = "shop"
partners = [
  { name = "本人", payee = "股东", share = 0.75, owner = true },
  { name = "合伙人", share = 0.25, offset = "Assets:Receivable:Partner" },
]
"""
SHOP_EXTRA_ACCOUNTS = """\
2026-08-31 open Assets:Exchange USDT
2026-08-31 open Assets:Receivable:Partner CNY
2026-08-31 open Expenses:Tools USDT
2026-08-31 open Equity:Distributions CNY
"""
# 连同脚手架里的 100 元采购：9 月净利润 1000 CNY − 10 USDT，按 7 折算合计 930，合伙人 25% 应得 232.50
SHOP_SEPT = '''
2026-09-05 * "客户" "主营业务收入"
  time: "10:00"
  Assets:Bank:Main  1100.00 CNY
  Income:Revenue

2026-09-06 * "服务商" "管理费用-服务器"
  time: "10:00"
  Expenses:Tools  10.00 USDT
  Assets:Exchange
'''
PARTNER_PAID = '''
{day} * "合伙人" "利润分配-9月合伙人分红"
  time: "10:00"
  period: "2026-09"
  Equity:Distributions  {amount} CNY
  Assets:Bank:Main
'''
USDT_7 = {"USDT": Decimal("7")}


@pytest.fixture
def partnered(ledger):
    _append(ledger / "ledger.toml", DIVIDEND_CONFIG)
    _append(ledger / "shop" / "accounts.beancount", SHOP_EXTRA_ACCOUNTS)
    _append(ledger / "shop" / "journal" / "2026-09.beancount", SHOP_SEPT)
    return ledger


def _amount(out, title):
    line = next(ln for ln in _section(out, "【折合 CNY").splitlines() if ln.strip().startswith(title))
    return Decimal(line.split()[1])


def _pay_partner(root, amount, day="2026-09-21"):
    _append(root / "shop" / "journal" / "2026-09.beancount", PARTNER_PAID.format(amount=amount, day=day))


def test_合伙人未分利润从净资产里扣(partnered, capsys):
    out = _run(capsys, USDT_7)
    assert _amount(out, "应付合伙人未分利润") == Decimal("-232.50")
    assert _amount(out, "扣后净资产") == _amount(out, "净资产") - Decimal("232.50")
    assert "2026-09 净利润 930.00 × 25% − 已分配 0.00" in out


def test_已分配的部分不再扣(partnered, capsys):
    _pay_partner(partnered, "200.00")
    out = _run(capsys, USDT_7)
    assert _amount(out, "应付合伙人未分利润") == Decimal("-32.50")


def test_预支超过应得时加回(partnered, capsys):
    _pay_partner(partnered, "300.00")
    out = _run(capsys, USDT_7)
    assert _amount(out, "合伙人预支分红超出应得") == Decimal("67.50")
    assert _amount(out, "扣后净资产") == _amount(out, "净资产") + Decimal("67.50")


def test_月后发过分红即结清_不再扣(partnered, capsys):
    _pay_partner(partnered, "200.00", day="2026-10-03")
    assert networth.cmd_networth(USDT_7, today=date(2026, 10, 5)) == 0
    assert "扣后净资产" not in capsys.readouterr().out


def test_月内预发的过了月仍按差额扣(partnered, capsys):
    _pay_partner(partnered, "200.00")   # 9 月 21 日预发：全月利润定下来之前发的，不算结清
    assert networth.cmd_networth(USDT_7, today=date(2026, 10, 5)) == 0
    assert _amount(capsys.readouterr().out, "应付合伙人未分利润") == Decimal("-32.50")


def test_往月没发过分红仍然要扣(partnered, capsys):
    assert networth.cmd_networth(USDT_7, today=date(2026, 10, 5)) == 0
    assert _amount(capsys.readouterr().out, "应付合伙人未分利润") == Decimal("-232.50")


def test_没标所有者时不扣(partnered, capsys):
    cfg = partnered / "ledger.toml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace(", owner = true", ""), encoding="utf-8")
    assert "扣后净资产" not in _run(capsys, USDT_7)


def test_利润币种缺汇率时说明没有扣(partnered, capsys):
    out = _run(capsys)
    assert "算不出合伙人未分利润" in out and "扣后净资产" not in out


def test_分红账本不参与合并时不扣(partnered, capsys):
    cfg = partnered / "ledger.toml"
    cfg.write_text(cfg.read_text(encoding="utf-8").replace(
        'kind = "business"\n', 'kind = "business"\nconsolidate = false\n'), encoding="utf-8")
    assert "扣后净资产" not in _run(capsys, USDT_7)
