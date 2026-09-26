"""跨账本往来对账。

beancount 只校验单本账内部平衡；两本账之间的双边镜像登记（如个人垫付商店款：
个人账记“应收商店”、商店账记“欠股东”）无人把关，任何一次“只记了单边”的操作
都不会被 check 发现，差额可以长期潜伏。本模块核对 ledger.toml 中每一对 [[mirrors]]，
两侧余额相加必须为 0。
"""
from decimal import Decimal

from . import config
from .books import balances, load_book, print_errors, transactions
from .config import EPSILON
from .display import pad

RECENT_SHOWN = 5


def _recent_touching(entries, account, limit=RECENT_SHOWN):
    hits = [t for t in transactions(entries)
            if any(p.account == account for p in t.postings)]
    return hits[-limit:]


def mirror_books(cfg):
    """参与往来镜像的账本，按 ledger.toml 中的声明顺序。"""
    used = {b for m in cfg.mirrors for b, _ in m.sides()}
    return [b for b in cfg.books if b in used]


def cmd_reconcile():
    cfg = config.load()
    print("\n===== 跨账套往来对账 =====")
    if not cfg.mirrors:
        print("  （ledger.toml 未声明 [[mirrors]]，没有需要对账的往来科目）")
        return 0

    books = {}
    for book in mirror_books(cfg):
        entries, errors, _ = load_book(book)
        if errors:
            print_errors(book, errors)
            print("[FAIL] 账本存在错误，无法对账，请先修复。")
            return 1
        books[book] = entries
    bals = {book: balances(entries) for book, entries in books.items()}

    eps = Decimal(EPSILON)
    bad = []
    width = max(len(b) for b in books) + 2
    for m in cfg.mirrors:
        (lb, la), (rb, ra) = m.sides()
        lv = bals[lb][la][m.currency]
        rv = bals[rb][ra][m.currency]
        diff = lv + rv
        ok = abs(diff) < eps
        print(f"\n  {m.name}（{m.currency}）")
        print(f"      {pad(lb, width)}{la:<34}{lv:>12.2f}")
        print(f"      {pad(rb, width)}{ra:<34}{rv:>12.2f}   差额 {diff:.2f}  {'OK' if ok else '!!'}")
        if not ok:
            bad.append((m, lv, rv, diff))

    if not bad:
        print(f"\n[OK] {len(cfg.mirrors)} 对往来科目全部镜像一致。")
        return 0

    print(f"\n[FAIL] {len(bad)} 对往来科目不一致：")
    for m, lv, rv, diff in bad:
        (lb, la), (rb, ra) = m.sides()
        print(f"\n  ▸ {m.name}（{m.currency}）差额 {diff:.2f}")
        print(f"      两侧相加应为 0，很可能有一笔只记了单边。最近触及的分录：")
        for book, acc in ((lb, la), (rb, ra)):
            for t in _recent_touching(books[book], acc):
                time_str = (t.meta or {}).get("time", "")
                amt = next((p.units for p in t.postings if p.account == acc), "")
                print(f"        [{book}] {t.date} {time_str} {t.payee or ''} {t.narration or ''}  {amt}")
    return 1
