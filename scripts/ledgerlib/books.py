"""账本加载：统一 beancount loader 的调用与错误输出。"""
import os
import re

from . import config

MAX_SHOWN_ERRORS = 10


def load_book(book):
    """加载账本，返回 (entries, errors, options)。"""
    from beancount import loader

    main, _, _ = config.book_paths(book)
    if not os.path.exists(main):
        raise config.ConfigError(f"账本 {book} 的入口文件不存在：{os.path.relpath(main, config.ROOT)}")
    return loader.load_file(main)


def print_errors(book, errors, entries=None):
    print(f"[FAIL] {book}: {len(errors)} 个错误")
    print_error_lines(errors, entries)


def print_error_lines(errors, entries=None):
    """逐条打印校验错误；给了 entries（同一次加载出的指令）时，科目类错误会附上可用科目和科目表备注。"""
    chart = Chart(entries) if entries is not None else None
    for e in errors[:MAX_SHOWN_ERRORS]:
        print("   -", _describe(e, chart))
    if len(errors) > MAX_SHOWN_ERRORS:
        print(f"   ...另有 {len(errors) - MAX_SHOWN_ERRORS} 个错误未显示")


class Chart:
    """科目表速查：哪些科目开着、各收什么币种、open 行尾的中文备注。"""

    def __init__(self, entries):
        from beancount.core.data import Close, Open

        self.opens = {e.account: e for e in entries if isinstance(e, Open)}
        closed = {e.account for e in entries if isinstance(e, Close)}
        self.active = sorted(a for a in self.opens if a not in closed)

    def note(self, account):
        """open 行尾 `;` 后面的备注（科目表里写的中文说明）；没有返回空串。"""
        meta = getattr(self.opens.get(account), "meta", None) or {}
        try:
            with open(meta.get("filename", ""), encoding="utf-8") as f:
                line = f.read().split("\n")[meta.get("lineno", 0) - 1]
        except (OSError, IndexError):
            return ""
        return line.split(";", 1)[1].strip() if ";" in line else ""

    def similar(self, account, limit=6):
        """同一上级下开着的科目；一个都没有时退而找拼写相近的。最多 limit 个。"""
        import difflib

        parent = account.rsplit(":", 1)[0]
        found = [a for a in self.active if a.startswith(parent + ":")]
        if not found:
            found = difflib.get_close_matches(account, self.active, n=limit, cutoff=0.6)
        return found[:limit]


_UNKNOWN_RE = re.compile(r"Invalid reference to unknown account '([^']+)'")
_INACTIVE_RE = re.compile(r"Invalid reference to inactive account '([^']+)'")
_CURRENCY_RE = re.compile(r"Invalid currency (\S+) for account '([^']+)'")
_UNBALANCED_RE = re.compile(r"Transaction does not balance: \((.+?)\)")
_BALANCE_RE = re.compile(r"Balance failed for '([^']+)': expected (.+?) != accumulated (.+?) \((.+?)\)")


def explain(msg, chart=None):
    """把 beancount 常见的英文报错换成中文说明，并写明下一步怎么改；认不出的原样返回。"""
    m = _UNKNOWN_RE.search(msg)
    if m:
        account = m.group(1)
        out = f"科目 {account} 没有开立，不能用。"
        near = chart.similar(account) if chart else []
        if near:
            out += f"已开的相近科目：{'、'.join(near)}。"
        return out + "可用科目看 ledger.py brief <账本>；确需新科目，先在 <账本>/accounts.beancount 里 open 再录"
    m = _INACTIVE_RE.search(msg)
    if m:
        account = m.group(1)
        note = chart.note(account) if chart else ""
        tail = f"科目表备注：{note}" if note else ""
        return f"科目 {account} 在这笔分录的日期已停用（或还没开立），不能再记。{tail}"
    m = _CURRENCY_RE.search(msg)
    if m:
        currency, account = m.groups()
        allowed = getattr(chart.opens.get(account), "currencies", None) if chart else None
        only = f"，只收 {' / '.join(allowed)}" if allowed else ""
        return f"科目 {account} 不收 {currency}{only}：换成对应币种的科目"
    m = _UNBALANCED_RE.search(msg)
    if m:
        return f"借贷不平，差额 {m.group(1)}：各条金额相加必须为 0（可以留一条不写金额，由它自动补齐）"
    m = _BALANCE_RE.search(msg)
    if m:
        account, expected, actual, gap = m.groups()
        gap = gap.replace("too much", "账面多了").replace("too little", "账面少了")
        return f"余额断言不符：{account} 断言 {expected}，账面 {actual}（{gap}）。先查明差额并记平，再写断言"
    return msg


def _describe(error, chart=None):
    """错误说明带上文件与行号，方便直接定位到出错的分录。"""
    msg = explain(getattr(error, "message", str(error)), chart)
    meta = getattr(error, "source", None) or {}
    filename, lineno = meta.get("filename"), meta.get("lineno")
    if filename and not str(filename).startswith("<"):
        try:
            where = os.path.relpath(filename, config.ROOT).replace(os.sep, "/")
        except ValueError:  # Windows 上跨盘符无法取相对路径
            where = filename
        return f"{where}:{lineno}  {msg}" if lineno else f"{where}  {msg}"
    return msg


def load_entries(book):
    """查询类命令统一入口：账本存在加载错误时直接报错并返回 None，不静默出报告。"""
    entries, errors, _ = load_book(book)
    if errors:
        print(f"[FAIL] {book} 账本存在 {len(errors)} 个错误，请先运行 check 修复后再查询：")
        print_error_lines(errors, entries)
        return None
    return entries


def transactions(entries):
    """从 entries 中筛出交易。"""
    from beancount.core.data import Transaction

    return [e for e in entries if isinstance(e, Transaction)]


def balances(entries, prefixes=None):
    """各科目按币种累计的余额：{科目: {币种: Decimal}}；prefixes 可限定科目前缀。"""
    from collections import defaultdict
    from decimal import Decimal

    bals = defaultdict(lambda: defaultdict(Decimal))
    for txn in transactions(entries):
        for p in txn.postings:
            if p.units is None:
                continue
            if prefixes and not p.account.startswith(prefixes):
                continue
            bals[p.account][p.units.currency] += Decimal(p.units.number)
    return bals
