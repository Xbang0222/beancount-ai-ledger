"""现拉行情：账本里能折现的东西（外币、加密币、金银、基金、股票）统一在这里取价，折成本位币。

代码约定（也是账本里 commodity 的写法）：
- 外币、加密币：ISO 代码，如 USD、HKD、USDT、BTC；黄金、白银按克：AU、AG（见 fxrate）。
- 场外基金：F + 6 位基金代码，如 F161226，取天天基金公布的单位净值。
- 股票：交易所前缀 + 代码，如 SH600519、SZ000001、BJ430047、HK00700、US.AAPL，取腾讯行情最新价，
  港股、美股的价格再按现拉汇率折成本位币。
都是现拉现用，不写入账本；拉不到时由调用方决定改用账内 price 还是报错。
"""
import json
import re
from datetime import date as _date
from decimal import Decimal

from . import fxrate
from .fxrate import NoRate, RateError

FUND_RE = re.compile(r"^F(\d{6})$")
STOCK_RE = re.compile(r"^(?:(SH|SZ|BJ)(\d{6})|(HK)(\d{5})|(US)\.([A-Z][A-Z0-9.-]*))$")
STOCK_CURRENCY = {"SH": "CNY", "SZ": "CNY", "BJ": "CNY", "HK": "HKD", "US": "USD"}
FUND_URL = ("https://api.fund.eastmoney.com/f10/lsjz?fundCode={code}&pageIndex=1&pageSize=1"
            "&startDate={start}&endDate={end}")
FUND_HEADERS = {"Referer": "https://fundf10.eastmoney.com/"}
STOCK_URL = "https://qt.gtimg.cn/q={code}"


def _fund(code, day):
    """(单位净值, 净值日期)。day 为 None 取最新一期，否则取 day 当天或之前最近一期。"""
    end = (day or _date.today()).isoformat()
    start = "" if day is None else _date.fromordinal(day.toordinal() - 15).isoformat()
    try:
        data = json.loads(fxrate._get(FUND_URL.format(code=code, start=start, end=end), FUND_HEADERS))
        rows = (data.get("Data") or {}).get("LSJZList") or []
    except Exception as ex:
        raise RateError(f"拉取基金 {code} 净值失败：{ex}") from None
    if not rows:
        raise NoRate(f"天天基金查不到基金 {code} 的净值")
    return Decimal(rows[0]["DWJZ"]), rows[0]["FSRQ"]


def _stock(market, code):
    """(最新价, 行情时间)，价格币种见 STOCK_CURRENCY。"""
    sym = market.lower() + code
    try:
        text = fxrate._get(STOCK_URL.format(code=sym)).decode("gbk", "replace")
    except Exception as ex:
        raise RateError(f"拉取股票 {market}{code} 行情失败：{ex}") from None
    fields = text.split('"', 2)[1].split("~") if '"' in text else []
    if len(fields) < 31 or not fields[3]:
        raise NoRate(f"腾讯行情查不到股票 {market}{code}")
    return Decimal(fields[3]), fields[30]


def price(code, base, day=None):
    """1 单位 code 值多少 base：返回 (价格, 数据日期, 来源说明)。

    day 只对汇率、金银和基金有效（取历史价）；股票只有最新价。
    """
    code = code.upper()
    if code == base.upper():
        return Decimal(1), None, ""
    m = FUND_RE.match(code)
    if m:
        nav, d = _fund(m.group(1), day)
        return nav, d, "天天基金单位净值"
    m = STOCK_RE.match(code)
    if m:
        if day is not None:
            raise NoRate(f"股票 {code} 只能取最新价，取不到历史价")
        market, sym = [g for g in m.groups() if g]
        px, when = _stock(market, sym)
        cur = STOCK_CURRENCY[market]
        if cur == base.upper():
            return px, when, "腾讯行情最新价"
        rate, d = fxrate.fetch(cur, base)
        return (px * Decimal(str(rate))), when, f"腾讯行情最新价 {px} {cur}，按 {d} {cur} 汇率折算"
    rate, d = fxrate.fetch(code, base, day)
    unit = "（每克）" if code in fxrate.GRAM_UNITS else ""
    return Decimal(str(rate)), d, f"{fxrate.SOURCE}{unit}"


def cmd_quote(codes, day=None):
    from . import config

    base = config.load().base_currency
    bad = 0
    for code in codes:
        try:
            px, d, src = price(code, base, day)
        except RateError as ex:
            print(f"[FAIL] {code.upper()}：{ex}")
            bad = 1
            continue
        print(f"1 {code.upper()} = {px:.4f} {base}（数据时间 {d}，{src}）")
    return bad
