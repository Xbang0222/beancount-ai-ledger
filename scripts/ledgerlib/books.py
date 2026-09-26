"""账本加载：统一 beancount loader 的调用与错误输出。"""
import os

from . import config

MAX_SHOWN_ERRORS = 10


def load_book(book):
    """加载账本，返回 (entries, errors, options)。"""
    from beancount import loader

    main, _, _ = config.book_paths(book)
    if not os.path.exists(main):
        raise config.ConfigError(f"账本 {book} 的入口文件不存在：{os.path.relpath(main, config.ROOT)}")
    return loader.load_file(main)


def print_errors(book, errors):
    print(f"[FAIL] {book}: {len(errors)} 个错误")
    _print_error_lines(errors)


def _print_error_lines(errors):
    for e in errors[:MAX_SHOWN_ERRORS]:
        print("   -", _describe(e))
    if len(errors) > MAX_SHOWN_ERRORS:
        print(f"   ...另有 {len(errors) - MAX_SHOWN_ERRORS} 个错误未显示")


def _describe(error):
    """错误说明带上文件与行号，方便直接定位到出错的分录。"""
    msg = getattr(error, "message", str(error))
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
        _print_error_lines(errors)
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
