"""资产负债汇总：账本间往来要抵销，外币要按价格折算，价格缺失或过期要说清楚。"""
from datetime import date
from decimal import Decimal

import pytest

from ledgerlib import networth, quote


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """默认当作数据源里查不到，测试不联网；要现拉价的用例自己换掉 quote.price。"""
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


def test_默认现拉当天价格_优先于账内旧价格(ledger, capsys, monkeypatch):
    _append(_personal_journal(ledger), USD_INCOME + USD_PRICE)
    monkeypatch.setattr(quote, "price", lambda code, base, day=None: (Decimal("7.2"), "2026-09-23", "测试源"))
    out = _run(capsys)
    assert "≈     720.00 CNY" in out
    assert "现拉，测试源" in out


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


def test_金价查不到时按成本列示并说明(ledger, capsys):
    _append(_accounts(ledger), '2026-08-31 open Assets:Gold CNY\n  estimate: "AU"\n')
    _append(_personal_journal(ledger), GOLD)
    out = _run(capsys)
    assert "估算现值失败" in out
