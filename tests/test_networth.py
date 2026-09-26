"""资产负债汇总：账本间往来要抵销，外币要按价格折算，价格缺失或过期要说清楚。"""
from ledgerlib import networth

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


def _run(capsys, overrides=None):
    assert networth.cmd_networth(overrides) == 0
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
