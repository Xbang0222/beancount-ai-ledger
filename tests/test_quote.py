"""现拉行情：按代码分派到汇率、基金、股票数据源，金银按克换算；全程替换网络请求，不联网。"""
import json
from datetime import date
from decimal import Decimal

import pytest

from ledgerlib import fxrate, quote


@pytest.fixture
def web(monkeypatch):
    """把网络请求换成按网址关键字返回的假数据；记录请求过的网址。"""
    pages, asked = {}, []
    fxrate._cache.clear()

    def get(url, headers=None):
        asked.append(url)
        for key, body in pages.items():
            if key in url:
                return body if isinstance(body, bytes) else json.dumps(body).encode()
        raise OSError("not found")

    monkeypatch.setattr(fxrate, "_get", get)
    yield pages, asked
    fxrate._cache.clear()


def test_金价按克换算(web):
    pages, _ = web
    pages["xau.min.json"] = {"date": "2026-10-25", "xau": {"cny": 31.1034768 * 850}}
    px, d, src = quote.price("AU", "CNY")
    assert round(px, 6) == 850 and d == "2026-10-25" and "每克" in src


def test_历史汇率按不补零的版本号取(web):
    pages, asked = web
    pages["@2026.2.1/"] = {"date": "2026-02-01", "usd": {"cny": 7.0}}
    assert quote.price("USD", "CNY", date(2026, 2, 1))[0] == Decimal("7.0")
    assert "@2026.2.1/v1/currencies/usd.min.json" in asked[0]


def test_同一币种同一天只请求一次(web):
    pages, asked = web
    pages["usd.min.json"] = {"date": "2026-10-25", "usd": {"cny": 7.0}}
    quote.price("USD", "CNY")
    quote.price("USD", "CNY")
    assert len(asked) == 1


def test_基金取天天基金单位净值(web):
    pages, _ = web
    pages["fundCode=161226"] = {"Data": {"LSJZList": [{"FSRQ": "2026-10-23", "DWJZ": "1.4947"}]}}
    assert quote.price("F161226", "CNY")[:2] == (Decimal("1.4947"), "2026-10-23")


def test_查不到的基金报NoRate(web):
    pages, _ = web
    pages["fundCode=999999"] = {"Data": {"LSJZList": []}}
    with pytest.raises(quote.NoRate):
        quote.price("F999999", "CNY")


def test_港股按港币汇率折成人民币(web):
    pages, _ = web
    fields = ["100", "腾讯控股", "00700", "400.00"] + ["0"] * 26 + ["2026/10/26 14:00:00"]
    pages["q=hk00700"] = ('v_hk00700="' + "~".join(fields) + '";').encode("gbk")
    pages["hkd.min.json"] = {"date": "2026-10-25", "hkd": {"cny": 0.85}}
    px, when, src = quote.price("HK00700", "CNY")
    assert px == Decimal("340.0000") and when == "2026/10/26 14:00:00" and "HKD" in src


@pytest.mark.parametrize("code", ["USD", "USDT", "USDC"])
def test_US开头的币种不当成美股(web, code):
    pages, asked = web
    pages[f"{code.lower()}.min.json"] = {"date": "2026-10-25", code.lower(): {"cny": 7.0}}
    quote.price(code, "CNY")
    assert "gtimg" not in asked[0]


def test_股票不支持历史价(web):
    with pytest.raises(quote.NoRate):
        quote.price("SH600519", "CNY", date(2026, 2, 1))
