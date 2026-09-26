"""资产负债汇总：把 ledger.toml 中 consolidate = true 的账本合并，抵销账本间往来后看真实家底。

多本账分开记，是为了单独核算（例如店铺的经营利润）；但如果这些账本都归你一个人所有，
看净资产时账本之间的往来只是“左手欠右手”（个人账“应收商店”与商店账“欠股东”），
必须按 [[mirrors]] 成对剔除，否则资产与负债会同时虚增。只有两侧账本都参与合并时才抵销；
一侧不参与合并（consolidate = false）时，那笔往来就是真实的对外债权债务，照常列示。

外币与投资标的按账内最新一条 `price <币种> ... <本位币>` 折算，可用 --rate 币种=汇率 临时覆盖。
"""
from collections import defaultdict
from decimal import Decimal

from . import config
from .books import balances, load_entries
from .config import EPSILON
from .display import pad


def _rates(entries, base, overrides=None):
    """{币种: (汇率, 价格日期或 None, 来源说明)}；本位币恒为 1。"""
    from beancount.core import prices

    pm = prices.build_price_map(entries)
    rates = {base: (Decimal(1), None, "")}
    for cur, quote in pm.forward_pairs:
        if quote != base:
            continue
        d, rate = prices.get_latest_price(pm, (cur, quote))
        if rate is not None:
            rates[cur] = (Decimal(rate), d, "账内价格")
    for cur, rate in (overrides or {}).items():
        rates[cur] = (Decimal(rate), None, "命令行 --rate，未写入账本")
    return rates


def cmd_networth(overrides=None, today=None):
    cfg = config.load()
    base = cfg.base_currency
    members = [b.name for b in cfg.books.values() if b.consolidate]
    excluded = [b.name for b in cfg.books.values() if not b.consolidate]
    if not members:
        print("[FAIL] ledger.toml 里没有参与合并的账本（全部 consolidate = false）。")
        return 1

    books = {}
    for book in members:
        entries = load_entries(book)
        if entries is None:
            return 1
        books[book] = entries

    internal = set()
    for m in cfg.mirrors:
        (lb, la), (rb, ra) = m.sides()
        if lb in books and rb in books:
            internal.add((lb, la, m.currency))
            internal.add((rb, ra, m.currency))

    eps = Decimal(EPSILON)
    rates = _rates([e for entries in books.values() for e in entries], base, overrides)
    if today is None:
        from .entry import now_local

        today = now_local().date()

    rows = {"Assets": [], "Liabilities": []}
    eliminated = []
    for book, entries in books.items():
        for acc, curs in sorted(balances(entries, ("Assets:", "Liabilities:")).items()):
            for cur, v in sorted(curs.items()):
                if abs(v) < eps:
                    continue
                if (book, acc, cur) in internal:
                    eliminated.append((book, acc, cur, v))
                    continue
                rows[acc.split(":")[0]].append((book, acc, cur, v))

    totals = {k: defaultdict(Decimal) for k in rows}
    missing = set()
    bw = max(len(b) for b in books) + 2

    if len(books) > 1:
        print(f"\n===== 合并资产负债（{' + '.join(books)}，已抵销账本间往来） =====")
    else:
        print(f"\n===== 资产负债 · {members[0]} =====")
    for kind, title in (("Assets", "资产"), ("Liabilities", "负债")):
        print(f"\n【{title}】")
        if not rows[kind]:
            print("  （无）")
        for book, acc, cur, v in rows[kind]:
            shown = -v if kind == "Liabilities" else v
            totals[kind][cur] += shown
            line = f"  {pad(book, bw)}{acc:<36}{shown:>12.2f} {cur}"
            if cur != base:
                if cur in rates:
                    line += f"  ≈ {shown * rates[cur][0]:>10.2f} {base}"
                else:
                    missing.add(cur)
            print(line)

    def _in_base(sums):
        return sum((v * rates[c][0] for c, v in sums.items() if c in rates), Decimal(0))

    print("\n【合计】")
    net = defaultdict(Decimal)
    for kind, title in (("Assets", "资产"), ("Liabilities", "负债")):
        for cur, v in sorted(totals[kind].items()):
            print(f"  {pad(title + '合计', 20)}{v:>12.2f} {cur}")
            net[cur] += v if kind == "Assets" else -v
    for cur, v in sorted(net.items()):
        print(f"  {pad('净资产', 20)}{v:>12.2f} {cur}")

    print(f"\n【折合 {base}】")
    for cur, (r, d, src) in sorted(rates.items()):
        if cur == base or cur not in net:
            continue
        if d is None:
            note = src
        elif d >= today:
            note = f"{d} {src}，当日价格"
        else:
            note = f"{d} {src}，距今 {(today - d).days} 天，非当日价格"
        print(f"  汇率 1 {cur} = {r} {base}（{note}）")
    print(f"  {pad('总资产', 20)}{_in_base(totals['Assets']):>12.2f} {base}")
    print(f"  {pad('总负债', 20)}{_in_base(totals['Liabilities']):>12.2f} {base}")
    print(f"  {pad('净资产', 20)}{_in_base(net):>12.2f} {base}")
    if missing:
        names = ", ".join(sorted(missing))
        print(f"  [!] 缺少 {names} 的价格，未计入折合合计；请在 common/prices.beancount 补 price，"
              f"或用 --rate {sorted(missing)[0]}=汇率 临时指定")

    if len(books) > 1 or eliminated:
        print("\n【已抵销的账本间往来（不计入上表）】")
        if not eliminated:
            print("  （无）")
        for book, acc, cur, v in eliminated:
            print(f"  {pad(book, bw)}{acc:<36}{v:>12.2f} {cur}")
    if excluded:
        print(f"\n【未合并的账本】{' / '.join(excluded)}（ledger.toml 中 consolidate = false）")
    return 0
