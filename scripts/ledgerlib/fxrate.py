"""现拉汇率：开源数据集 fawazahmed0/exchange-api（npm 包 @fawazahmed0/currency-api）。

选它是因为云端会话只放行 npm / GitHub / PyPI 等域名；每天北京时间中午前后发布新版。
汇率现拉现用，不写入账本。
"""
import io
import json
import tarfile
import urllib.request

REGISTRY = "https://registry.npmjs.org/@fawazahmed0/currency-api/latest"
SOURCE = "fawazahmed0/exchange-api"
TIMEOUT = 20


class RateError(Exception):
    """拉不到汇率。消息面向用户，直接打印即可。"""


def _get(url):
    with urllib.request.urlopen(url, timeout=TIMEOUT) as r:
        return r.read()


def fetch(cur, base):
    """返回 (汇率, 数据日期)：1 cur = 汇率 base。"""
    cur, base = cur.lower(), base.lower()
    try:
        tarball = json.loads(_get(REGISTRY))["dist"]["tarball"]
        with tarfile.open(fileobj=io.BytesIO(_get(tarball)), mode="r:gz") as tar:
            f = tar.extractfile(f"package/v1/currencies/{cur}.min.json")
            data = json.load(f)
        return data[cur][base], data["date"]
    except Exception as ex:  # 网络、格式、币种缺失统一报给用户
        raise RateError(f"拉取 {cur.upper()}/{base.upper()} 汇率失败：{ex}") from None
