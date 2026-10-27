"""账套配置：从账套根目录的 ledger.toml 读取账本清单、跨账本往来镜像、时区与本位币。

ledger.toml 的写法见 docs/REFERENCE.md「多本账」。每次调用 load() 都重新读取文件
（文件很小），这样测试把 ROOT 指向临时账套、或 new-book 追加了账本后都能立即生效。
"""
import os
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

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

_TOP_KEYS = {"ledger", "books", "mirrors", "dividend", "naming"}
_LEDGER_KEYS = {"timezone", "base_currency", "fx_alias"}
_DIVIDEND_KEYS = {"book", "account", "partners"}
_PARTNER_KEYS = {"name", "payee", "share", "offset"}
_BOOK_KEYS = {"title", "kind", "main", "journal", "consolidate"}
_MIRROR_KEYS = {"name", "currency", "accounts"}
_NAMING_KEYS = {"markers", "banned_payees", "vague_items", "refund_suffix", "note_required", "fallback",
                "prefix", "patterns"}
_PATTERN_KEYS = {"book", "name", "when", "with", "payee", "narration", "hint"}


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
class Partner:
    """利润分配的一方：分得比例，以及可选的抵扣科目（对方欠账本的钱，从应得里扣）。"""
    name: str
    share: Decimal
    offset: str = ""
    payee: str = ""    # 分红分录的对方名称，默认同 name


@dataclass(frozen=True)
class Dividend:
    book: str
    partners: tuple    # Partner 元组，比例合计为 1
    account: str = "Equity:Distributions"   # 记已分配利润的科目


@dataclass(frozen=True)
class Pattern:
    """固定场景的写法：分录出现 when 里的科目、其余科目都在 with 里时，对方与摘要只能按这里写。"""
    book: str
    name: str
    when: tuple        # 出现其中任一科目即可能命中（前缀匹配）
    with_: tuple       # 其余科目只能是这些（前缀匹配）；有别的科目就不算这个场景
    payees: tuple      # 允许的对方名称
    narrations: tuple  # 允许的摘要开头；空表示不限
    hint: str = ""


@dataclass(frozen=True)
class Naming:
    """对方名称与摘要的写法规则（[naming]）。未配置时不做任何写法检查。"""
    markers: tuple        # 摘要括号里允许出现的固定标记
    banned_payees: tuple  # 不许用作对方名称的空泛词
    vague_items: tuple    # 摘要“大类-事项”里不许单独当事项用的笼统词
    refund_suffix: tuple  # 费用冲回、收入冲减（退款/退回）时摘要必须的结尾；空表示不查
    note_required: tuple  # 记到这些科目（兜底科目）时必须写 note: 说明是什么、为什么没有合适分类
    fallback: tuple       # 找不到分类时的处理步骤，rules 原样打印
    prefix: dict          # 账本名 -> {科目前缀: (允许的摘要开头, ...)}
    patterns: tuple       # Pattern 元组


@dataclass(frozen=True)
class Config:
    books: dict        # 账本名 -> Book，保持 ledger.toml 中的书写顺序
    mirrors: tuple     # Mirror 元组
    timezone: str
    base_currency: str
    fx_alias: dict = None       # 折算时视同另一币种取汇率，如 {"USDT": "USD"}
    dividend: Dividend = None   # 按月利润分配；未配置为 None
    naming: Naming = None       # 对方与摘要写法规则；未配置为 None


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

    fx_alias = ledger.get("fx_alias", {})
    if not isinstance(fx_alias, dict) or not all(
            isinstance(k, str) and isinstance(v, str) and CURRENCY_RE.match(k) and CURRENCY_RE.match(v)
            for k, v in fx_alias.items()):
        raise ConfigError(f"[ledger] fx_alias 写成 {{ USDT = \"USD\" }}（大写币种代码），收到：{fx_alias!r}")

    dividend = _parse_dividend(data.get("dividend"), books)
    naming = _parse_naming(data.get("naming"), books)
    return Config(books=books, mirrors=tuple(mirrors), timezone=timezone, base_currency=base,
                  fx_alias=dict(fx_alias), dividend=dividend, naming=naming)


def _str_list(value, where, allow_empty=True):
    """接受一个字符串或字符串数组，统一成元组。"""
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value) \
            or (not allow_empty and not value):
        raise ConfigError(f"{where} 应为非空字符串或字符串数组，收到：{value!r}")
    return tuple(value)


def _account_prefix(value, where):
    if not ACCOUNT_RE.match(value):
        raise ConfigError(f"{where} 科目名不合法：{value!r}")
    return value


def _parse_naming(raw, books):
    if raw is None:
        return None
    where = "[naming]"
    if not isinstance(raw, dict):
        raise ConfigError(f"{where} 应为一个表（table）")
    _no_unknown(raw, _NAMING_KEYS, where)
    prefix = {}
    raw_prefix = raw.get("prefix", {})
    if not isinstance(raw_prefix, dict):
        raise ConfigError(f"{where} prefix 要写成 [naming.prefix.<账本>] 表")
    for book, table in raw_prefix.items():
        pw = f"[naming.prefix.{book}]"
        if book not in books:
            raise ConfigError(f"{pw} 引用了未声明的账本；已声明：{' / '.join(books)}")
        if not isinstance(table, dict):
            raise ConfigError(f"{pw} 应为 科目前缀 = \"摘要开头\" 的表")
        prefix[book] = {_account_prefix(acc, pw): _str_list(v, f"{pw} {acc}", allow_empty=False)
                        for acc, v in table.items()}
    patterns = []
    raw_patterns = raw.get("patterns", [])
    if not isinstance(raw_patterns, list):
        raise ConfigError("patterns 要写成 [[naming.patterns]]（数组表），每个场景一段")
    for i, p in enumerate(raw_patterns, 1):
        pw = f"第 {i} 个 [[naming.patterns]]"
        if not isinstance(p, dict):
            raise ConfigError(f"{pw} 应为一个表（table）")
        _no_unknown(p, _PATTERN_KEYS, pw)
        if p.get("book") not in books:
            raise ConfigError(f"{pw} book 应为已声明的账本，收到：{p.get('book')!r}")
        name = p.get("name") or f"场景{i}"
        when = tuple(_account_prefix(a, pw) for a in _str_list(p.get("when"), f"{pw} when", False))
        with_ = tuple(_account_prefix(a, pw) for a in _str_list(p.get("with", []), f"{pw} with"))
        patterns.append(Pattern(
            book=p["book"], name=str(name), when=when, with_=with_,
            payees=_str_list(p.get("payee"), f"{pw} payee", allow_empty=False),
            narrations=_str_list(p.get("narration", []), f"{pw} narration"),
            hint=str(p.get("hint", ""))))
    return Naming(
        markers=_str_list(raw.get("markers", []), f"{where} markers"),
        banned_payees=_str_list(raw.get("banned_payees", []), f"{where} banned_payees"),
        vague_items=_str_list(raw.get("vague_items", []), f"{where} vague_items"),
        refund_suffix=_str_list(raw.get("refund_suffix", []), f"{where} refund_suffix"),
        note_required=tuple(_account_prefix(a, where) for a in
                            _str_list(raw.get("note_required", []), f"{where} note_required")),
        fallback=_str_list(raw.get("fallback", []), f"{where} fallback"),
        prefix=prefix, patterns=tuple(patterns))


def _parse_dividend(raw, books):
    if raw is None:
        return None
    where = "[dividend]"
    if not isinstance(raw, dict):
        raise ConfigError(f"{where} 应为一个表（table）")
    _no_unknown(raw, _DIVIDEND_KEYS, where)
    book = raw.get("book")
    if book not in books:
        raise ConfigError(f"{where} book 应为已声明的账本，收到：{book!r}；已声明：{' / '.join(books)}")
    raw_partners = raw.get("partners")
    if not isinstance(raw_partners, list) or not raw_partners:
        raise ConfigError(f"{where} partners 至少写一方，如 partners = [{{ name = \"本人\", share = 1 }}]")
    partners = []
    for i, p in enumerate(raw_partners, 1):
        pw = f"{where} 第 {i} 个 partner"
        if not isinstance(p, dict):
            raise ConfigError(f"{pw} 应为一个表（table）")
        _no_unknown(p, _PARTNER_KEYS, pw)
        name = p.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ConfigError(f"{pw} 缺少 name")
        try:
            share = Decimal(str(p.get("share")))
        except InvalidOperation:
            share = None
        if share is None or not share.is_finite() or not 0 < share <= 1:
            raise ConfigError(f"{pw}（{name}）share 应为 0 到 1 之间的比例，如 0.25，收到：{p.get('share')!r}")
        offset = p.get("offset", "")
        if offset and (not isinstance(offset, str) or not ACCOUNT_RE.match(offset)):
            raise ConfigError(f"{pw}（{name}）offset 科目名不合法：{offset!r}")
        payee = p.get("payee", name)
        if not isinstance(payee, str) or not payee.strip():
            raise ConfigError(f"{pw}（{name}）payee 应为分红分录的对方名称")
        partners.append(Partner(name, share, offset, payee))
    total = sum(p.share for p in partners)
    if total != 1:
        raise ConfigError(f"{where} 各方 share 合计应为 1，现在是 {total}")
    account = raw.get("account", "Equity:Distributions")
    if not isinstance(account, str) or not ACCOUNT_RE.match(account):
        raise ConfigError(f"{where} account 科目名不合法：{account!r}")
    return Dividend(book=book, partners=tuple(partners), account=account)


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
