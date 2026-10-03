"""账套配置：从账套根目录的 ledger.toml 读取账本清单、跨账本往来镜像、时区与本位币。

ledger.toml 的写法见 docs/REFERENCE.md「多本账」。每次调用 load() 都重新读取文件
（文件很小），这样测试把 ROOT 指向临时账套、或 new-book 追加了账本后都能立即生效。
"""
import os
import re
from dataclasses import dataclass

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - Python 3.9 / 3.10
    import tomli as tomllib

# 账套根目录（ledger.toml 所在目录）。可用环境变量 LEDGER_ROOT 或命令行 --root 覆盖；
# 测试会把它指向 tmp_path 里的临时账套，避免触碰真实账本。
ROOT = os.environ.get(
    "LEDGER_ROOT",
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
)

CONFIG_NAME = "ledger.toml"

# 标签汇总时归入“往来/资金移动”而非收支的科目前缀（带方向，不计入收支合计）
MOVE_PREFIX = ("Assets:Receivable", "Assets:Prepaid", "Liabilities:")

# 金额显示与比较的容差：小于半分即视为 0
EPSILON = "0.005"

# personal：个人/家庭账，月报计算储蓄率；business：经营账（店铺、公司），月报看经营结余
KINDS = ("personal", "business")

BOOK_NAME_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
ACCOUNT_RE = re.compile(r"^(Assets|Liabilities|Equity|Income|Expenses)(:[^:\s]+)+$")
CURRENCY_RE = re.compile(r"^[A-Z][A-Z0-9'._-]{0,22}[A-Z0-9]$")

_TOP_KEYS = {"ledger", "books", "mirrors"}
_LEDGER_KEYS = {"timezone", "base_currency"}
_BOOK_KEYS = {"title", "kind", "main", "journal", "consolidate"}
_MIRROR_KEYS = {"name", "currency", "accounts"}


class ConfigError(Exception):
    """ledger.toml 缺失或写法有误。消息面向用户，直接打印即可。"""


@dataclass(frozen=True)
class Book:
    name: str
    title: str
    kind: str
    main: str          # 入口文件，相对 ROOT
    journal: str       # 序时簿目录，相对 ROOT
    consolidate: bool  # 是否并入 networth 合并资产负债


@dataclass(frozen=True)
class Mirror:
    """一对镜像往来科目：同一笔业务在两本账各记一边，两侧余额相加必须为 0。"""
    name: str
    currency: str
    left_book: str
    left_account: str
    right_book: str
    right_account: str

    def sides(self):
        return ((self.left_book, self.left_account), (self.right_book, self.right_account))


@dataclass(frozen=True)
class Config:
    books: dict        # 账本名 -> Book，保持 ledger.toml 中的书写顺序
    mirrors: tuple     # Mirror 元组
    timezone: str
    base_currency: str


def config_path():
    return os.path.join(ROOT, CONFIG_NAME)


def load():
    """读取并校验 ledger.toml，返回 Config；有问题抛 ConfigError。"""
    path = config_path()
    if not os.path.exists(path):
        raise ConfigError(
            f"找不到 {CONFIG_NAME}（账套根目录：{ROOT}）。"
            "请在账套根目录运行，或用 --root 指定账套目录；"
            "全新账套可运行 `python3 scripts/ledger.py new-book personal` 自动生成。")
    with open(path, "rb") as f:
        try:
            data = tomllib.load(f)
        except tomllib.TOMLDecodeError as ex:
            raise ConfigError(f"{CONFIG_NAME} 不是合法的 TOML：{ex}") from None
    return parse(data)


def parse(data):
    _no_unknown(data, _TOP_KEYS, CONFIG_NAME)

    ledger = data.get("ledger", {})
    _no_unknown(ledger, _LEDGER_KEYS, "[ledger]")
    timezone = ledger.get("timezone", "Asia/Shanghai")
    _check_timezone(timezone)
    base = ledger.get("base_currency", "CNY")
    if not isinstance(base, str) or not CURRENCY_RE.match(base):
        raise ConfigError(f"[ledger] base_currency 应为大写币种代码（如 CNY），收到：{base!r}")

    raw_books = data.get("books")
    if not isinstance(raw_books, dict) or not raw_books:
        raise ConfigError(f"{CONFIG_NAME} 至少要声明一个账本，例如：\n\n[books.personal]\ntitle = \"个人账本\"")
    books = {}
    for name, raw in raw_books.items():
        where = f"[books.{name}]"
        if not BOOK_NAME_RE.match(name):
            raise ConfigError(f"账本名 {name!r} 不合法：只能用小写字母开头的小写字母、数字、- 和 _")
        if not isinstance(raw, dict):
            raise ConfigError(f"{where} 应为一个表（table）")
        _no_unknown(raw, _BOOK_KEYS, where)
        kind = raw.get("kind", "personal")
        if kind not in KINDS:
            raise ConfigError(f"{where} kind 只能是 {' / '.join(KINDS)}，收到：{kind!r}")
        consolidate = raw.get("consolidate", True)
        if not isinstance(consolidate, bool):
            raise ConfigError(f"{where} consolidate 只能是 true 或 false")
        books[name] = Book(
            name=name,
            title=str(raw.get("title", name)),
            kind=kind,
            main=_rel_path(raw.get("main", f"{name}.beancount"), where, "main"),
            journal=_rel_path(raw.get("journal", f"{name}/journal"), where, "journal"),
            consolidate=consolidate,
        )

    raw_mirrors = data.get("mirrors", [])
    if not isinstance(raw_mirrors, list):
        raise ConfigError("mirrors 要写成 [[mirrors]]（数组表），每对往来科目一段")
    mirrors = []
    seen = set()
    for i, raw in enumerate(raw_mirrors, 1):
        where = f"第 {i} 个 [[mirrors]]"
        if not isinstance(raw, dict):
            raise ConfigError(f"{where} 应为一个表（table）")
        _no_unknown(raw, _MIRROR_KEYS, where)
        name = raw.get("name")
        currency = raw.get("currency")
        accounts = raw.get("accounts")
        if not name or not isinstance(name, str):
            raise ConfigError(f"{where} 缺少 name（业务说明，如 \"个人垫付商店款\"）")
        if not isinstance(currency, str) or not CURRENCY_RE.match(currency):
            raise ConfigError(f"{where}（{name}）currency 应为大写币种代码，收到：{currency!r}")
        if not isinstance(accounts, dict) or len(accounts) != 2:
            raise ConfigError(
                f"{where}（{name}）accounts 要恰好写两本账，"
                "如 accounts = { personal = \"Assets:Receivable:Shop\", shop = \"Liabilities:OwnerLoan\" }")
        sides = list(accounts.items())
        for book, account in sides:
            if book not in books:
                raise ConfigError(f"{where}（{name}）引用了未声明的账本 {book!r}；已声明：{' / '.join(books)}")
            if not isinstance(account, str) or not ACCOUNT_RE.match(account):
                raise ConfigError(f"{where}（{name}）{book} 侧科目名不合法：{account!r}")
            key = (book, account, currency)
            if key in seen:
                raise ConfigError(f"{where}（{name}）{book} 侧科目 {account}（{currency}）重复出现在多个镜像里")
            seen.add(key)
        (lb, la), (rb, ra) = sides
        mirrors.append(Mirror(name, currency, lb, la, rb, ra))

    return Config(books=books, mirrors=tuple(mirrors), timezone=timezone, base_currency=base)


def _no_unknown(table, allowed, where):
    """拼错的键（如 [[mirror]]、kinds）会被 TOML 静默接受，这里直接报错，避免对账被悄悄关掉。"""
    unknown = sorted(set(table) - allowed)
    if unknown:
        raise ConfigError(f"{where} 有不认识的键：{', '.join(unknown)}；可用的键：{', '.join(sorted(allowed))}")


def _rel_path(value, where, key):
    if not isinstance(value, str) or not value or os.path.isabs(value):
        raise ConfigError(f"{where} {key} 应为相对账套根目录的路径，收到：{value!r}")
    return value.replace("\\", "/").rstrip("/")


def _check_timezone(name):
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, TypeError):
        raise ConfigError(
            f"[ledger] timezone 无法识别：{name!r}。请用 IANA 时区名（如 Asia/Shanghai）；"
            "Windows 需先 pip install tzdata（requirements.txt 已包含）。") from None


def get_book(name):
    """按名称取账本定义；未声明时抛 ConfigError 并列出可选账本。"""
    cfg = load()
    if name not in cfg.books:
        raise ConfigError(f"未知账本 {name!r}；ledger.toml 中已声明：{' / '.join(cfg.books)}")
    return cfg.books[name]


def book_paths(book):
    """返回 (入口文件绝对路径, 序时簿目录绝对路径, 序时簿目录相对路径)。"""
    b = get_book(book)
    return (
        os.path.join(ROOT, b.main),
        os.path.join(ROOT, b.journal),
        b.journal,
    )
