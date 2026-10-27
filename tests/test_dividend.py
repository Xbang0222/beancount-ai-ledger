"""按月利润分配：外币按汇率折算、按比例拆分、已分配按 period 与 payee 归集、对方欠款从差额里扣。"""
from datetime import datetime
from decimal import Decimal

import pytest

from ledgerlib import config, dividend, fxrate
from ledgerlib.config import ConfigError, parse

DIVIDEND_CONFIG = """
[dividend]
book = "shop"
partners = [
  { name = "本人", payee = "股东", share = 0.75 },
  { name = "合伙人", share = 0.25, offset = "Assets:Receivable:Partner" },
]
"""

EXTRA_ACCOUNTS = """\
2026-08-31 open Assets:Exchange USDT
2026-08-31 open Assets:Receivable:Partner CNY
2026-08-31 open Expenses:Tools USDT
2026-08-31 open Equity:Distributions CNY
"""

SEPT = """
2026-09-05 * "客户" "主营业务收入"
  time: "10:00"
  Assets:Bank:Main  1100.00 CNY
  Income:Revenue

2026-09-06 * "服务商" "管理费用-服务器"
  time: "10:00"
  Expenses:Tools  10.00 USDT
  Assets:Exchange
"""

PAID = """
2026-09-20 * "股东" "利润分配-8月"
  time: "10:00"
  period: "2026-08"
  Equity:Distributions  99.00 CNY
  Assets:Bank:Main

2026-09-21 * "合伙人" "利润分配-9月合伙人分红（多发）"
  time: "10:00"
  period: "2026-09"
  Equity:Distributions  200.00 CNY
  Assets:Receivable:Partner  50.00 CNY
  Assets:Bank:Main
"""


def _append(path, text):
    path.write_text(path.read_text(encoding="utf-8") + text, encoding="utf-8")


@pytest.fixture
def shop(ledger):
    _append(ledger / "ledger.toml", DIVIDEND_CONFIG)
    _append(ledger / "shop" / "accounts.beancount", EXTRA_ACCOUNTS)
    _append(ledger / "shop" / "journal" / "2026-09.beancount", SEPT)
    return ledger


@pytest.fixture
def in_september(monkeypatch):
    """把「今天」定在 9 月，让 9 月算作未结月份。"""
    monkeypatch.setattr(dividend, "now_local", lambda: datetime(2026, 9, 30, 12))


def _run(capsys, ym="2026-09", rates=None):
    assert dividend.cmd_dividend(ym, rates) == 0
    return capsys.readouterr().out


def _line(out, name):
    return next(line for line in out.splitlines() if line.strip().startswith(name))


def test_外币按指定汇率折算后按比例拆分(shop, capsys):
    out = _run(capsys, rates={"USDT": Decimal("7")})
    # 1100 收入 − 100 进货（夹具自带）− 10 USDT × 7 = 930
    assert "930.00 CNY" in _line(out, "合计净利润")
    assert "应得     697.50" in _line(out, "本人")
    assert "应得     232.50" in _line(out, "合伙人")


def test_不给汇率时按别名现拉(shop, capsys, monkeypatch):
    text = (shop / "ledger.toml").read_text(encoding="utf-8")
    (shop / "ledger.toml").write_text(
        text.replace('base_currency = "CNY"', 'base_currency = "CNY"\nfx_alias = { USDT = "USD" }'),
        encoding="utf-8")
    asked = []
    monkeypatch.setattr(fxrate, "fetch", lambda cur, base: asked.append((cur, base)) or (7.123456, "2026-09-30"))
    out = _run(capsys)
    assert asked == [("USD", "CNY")]
    assert "1 USDT = 7.1235 CNY" in out and "按 USD 汇率" in out and "2026-09-30" in out


def test_拉不到汇率时报错提示用rate(shop, capsys, monkeypatch):
    def boom(cur, base):
        raise fxrate.RateError("拉取 USDT/CNY 汇率失败：断网")

    monkeypatch.setattr(fxrate, "fetch", boom)
    assert dividend.cmd_dividend("2026-09", None) == 1
    assert "--rate" in capsys.readouterr().out


def test_已分配按period和payee归集_欠款从差额里扣(shop, capsys, in_september):
    _append(shop / "shop" / "journal" / "2026-09.beancount", PAID)
    out = _run(capsys, rates={"USDT": Decimal("7")})
    me = _line(out, "本人")
    assert "已分配       0.00" in me  # 8 月的分红不算进 9 月
    partner = out.split("合伙人", 1)[1]
    assert "已分配     200.00" in partner and "差额      32.50" in partner
    assert "仍欠 17.50 CNY" in partner


def test_欠款够扣时给出实付(shop, capsys, in_september):
    _append(shop / "shop" / "journal" / "2026-09.beancount", PAID.replace("200.00", "100.00"))
    out = _run(capsys, rates={"USDT": Decimal("7")})
    assert "本次实付 82.50 CNY" in out.split("合伙人", 1)[1]


def test_没配置dividend时报错(ledger):
    with pytest.raises(ConfigError):
        dividend.cmd_dividend("2026-09")


BOOKS = {"books": {"shop": {}}}


@pytest.mark.parametrize("raw, hint", [
    ({"book": "nope", "partners": [{"name": "a", "share": 1}]}, "book"),
    ({"book": "shop", "partners": []}, "partners"),
    ({"book": "shop", "partners": [{"name": "a", "share": 0.5}]}, "合计"),
    ({"book": "shop", "partners": [{"name": "a", "share": "x"}]}, "share"),
    ({"book": "shop", "partners": [{"name": "a", "share": 1, "offset": "bad"}]}, "offset"),
    ({"book": "shop", "partners": [{"name": "a", "share": 1, "pct": 1}]}, "不认识"),
])
def test_dividend配置写错要报错(raw, hint):
    with pytest.raises(ConfigError, match=hint):
        parse({**BOOKS, "dividend": raw})


def test_dividend配置解析(monkeypatch):
    cfg = parse({**BOOKS, "ledger": {"fx_alias": {"USDT": "USD"}},
                 "dividend": {"book": "shop", "partners": [
                     {"name": "本人", "payee": "股东", "share": 0.75},
                     {"name": "合伙人", "share": 0.25, "offset": "Assets:Receivable:Partner"}]}})
    assert cfg.fx_alias == {"USDT": "USD"}
    me, other = cfg.dividend.partners
    assert (me.payee, me.share, other.payee, other.share) == ("股东", Decimal("0.75"), "合伙人", Decimal("0.25"))
    assert cfg.dividend.account == "Equity:Distributions"


def test_fx_alias写错要报错():
    with pytest.raises(ConfigError, match="fx_alias"):
        parse({**BOOKS, "ledger": {"fx_alias": {"usdt": "USD"}}})


def test_config_load读到真实结构(shop):
    assert config.load().dividend.book == "shop"


def test_往月发过分红即结清_不拉汇率不算差额(shop, capsys, monkeypatch):
    _append(shop / "shop" / "journal" / "2026-09.beancount", PAID)
    monkeypatch.setattr(fxrate, "fetch", lambda cur, base: pytest.fail("已结清月份不该拉汇率"))
    out = _run(capsys)
    assert "已结清" in out and "差额" not in out.replace("产生的差额", "")
    assert "已分配     200.00" in _line(out, "合伙人")
    assert "已分配       0.00" in _line(out, "本人")


def test_当月发过分红也照常计算(shop, capsys, in_september):
    _append(shop / "shop" / "journal" / "2026-09.beancount", PAID)
    out = _run(capsys, rates={"USDT": Decimal("7")})
    assert "已结清" not in out and "差额      32.50" in out.split("合伙人", 1)[1]


def test_recalc时往月照常重算(shop, capsys):
    _append(shop / "shop" / "journal" / "2026-09.beancount", PAID)
    assert dividend.cmd_dividend("2026-09", {"USDT": Decimal("7")}, recalc=True) == 0
    out = capsys.readouterr().out
    assert "已结清" not in out and "差额      32.50" in out.split("合伙人", 1)[1]
