"""现拉汇率与贵金属价：开源数据集 fawazahmed0/exchange-api（npm 包 @fawazahmed0/currency-api）。

选它是因为云端会话只放行 npm / GitHub / PyPI 等域名；每天北京时间中午前后发布新版，历史每天一版。
覆盖法币、主流加密币（USDT、BTC 等）和金银铂钯。数据集里的 XAU、XAG 是每金衡盎司的价格；
账本里黄金、白银按克记（AU、AG），这里换算成每克。汇率现拉现用，不写入账本。
"""
import io
import json
import tarfile
import urllib.request

REGISTRY = "https://registry.npmjs.org/@fawazahmed0/currency-api"
CDN = "https://cdn.jsdelivr.net/npm/@fawazahmed0/currency-api@{ver}/v1/currencies/{code}.min.json"
SOURCE = "fawazahmed0/exchange-api"
TIMEOUT = 20
TROY_OUNCE_GRAMS = 31.1034768
GRAM_UNITS = {"AU": "xau", "AG": "xag"}   # 按克记的贵金属 → 数据集里按盎司报价的代码

_cache = {}


class RateError(Exception):
    """拉不到汇率。消息面向用户，直接打印即可。"""


class NoRate(RateError):
    """数据集里没有这个代码（基金、股票等），不是网络问题。"""


def _get(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", **(headers or {})})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def _version(day):
    """数据集按日期发版，版本号不补零：2026-02-11 → 2026.2.11；None 为最新版。"""
    return "latest" if day is None else f"{day.year}.{day.month}.{day.day}"


def _table(code, day):
    """{目标币种: 汇率} 与数据日期。先取单个文件，取不到再下整包（npm 源云端也能访问）。"""
    key = (code, day)
    if key in _cache:
        return _cache[key]
    ver = _version(day)
    try:
        data = json.loads(_get(CDN.format(ver=ver, code=code)))
    except Exception:
        meta = json.loads(_get(f"{REGISTRY}/{ver}"))
        with tarfile.open(fileobj=io.BytesIO(_get(meta["dist"]["tarball"])), mode="r:gz") as tar:
            try:
                f = tar.extractfile(f"package/v1/currencies/{code}.min.json")
            except KeyError:
                raise NoRate(f"数据集里没有 {code.upper()}") from None
            data = json.load(f)
    _cache[key] = data[code], data["date"]
    return _cache[key]


def fetch(cur, base, day=None):
    """返回 (汇率, 数据日期)：1 cur = 汇率 base。day 为 date 时取那天的历史汇率。AU、AG 是每克价格。"""
    code = GRAM_UNITS.get(cur.upper(), cur.lower())
    try:
        table, date = _table(code, day)
        rate = table[base.lower()]
    except RateError:
        raise
    except Exception as ex:  # 网络、格式、币种缺失统一报给用户
        raise RateError(f"拉取 {cur.upper()}/{base.upper()} 汇率失败：{ex}") from None
    if cur.upper() in GRAM_UNITS:
        rate /= TROY_OUNCE_GRAMS
    return rate, date
