"""资产负债汇总：把 ledger.toml 中 consolidate = true 的账本合并，抵销账本间往来后看真实家底。

多本账分开记，是为了单独核算（例如店铺的经营利润）；但如果这些账本都归你一个人所有，
看净资产时账本之间的往来只是“左手欠右手”（个人账“应收商店”与商店账“欠股东”），
必须按 [[mirrors]] 成对剔除，否则资产与负债会同时虚增。只有两侧账本都参与合并时才抵销；
一侧不参与合并（consolidate = false）时，那笔往来就是真实的对外债权债务，照常列示。

外币、加密币、金银、基金、股票默认现拉当天价格折算（见 quote）；--rate 币种=汇率 临时覆盖，
--offline 或拉不到时改用账内最新一条 `price <代码> ... <本位币>`。

两种账户元数据（写在 open 指令下面）：
- `networth: FALSE`：退休前取不出来的钱（养老保险、医保个人账户），单独列示，不计入净资产。
- `estimate: "AU"`：按人民币金额记、没记克数的黄金（积存金等），按每笔发生当天的价格折成克数，
  再按今天的价格估算现值。代码写法同 quote，白银写 "AG"，基金写 "F161226"。
"""
from collections import defaultdict
from decimal import Decimal

from . import config, quote
from .books import balances, load_entries
from .config import EPSILON
from .display import pad


def _ledger_rates(entries, base):
    """账内 price：{代码: (价格, 价格日期, 来源说明)}。"""
    from beancount.core import prices

    pm = prices.build_price_map(entries)
    rates = {}
    for cur, quote_cur in pm.forward_pairs:
        if quote_cur != base:
            continue
        d, rate = prices.get_latest_price(pm, (cur, quote_cur))
        if rate is not None:
            rates[cur] = (Decimal(rate), d, "账内价格")
    return rates


class _Live:
    """现拉价格；第一次网络失败后不再重试，提示一次改用账内价格。"""

    def __init__(self, base, enabled):
        self.base, self.enabled, self.failed = base, enabled, None

    def get(self, code, day=None):
        if not self.enabled or self.failed:
            return None
        try:
            return quote.price(code, self.base, day)
        except quote.NoRate:
            return None
        except quote.RateError as ex:
            self.failed = str(ex)
            return None


def _rates(entries, base, currencies, live, overrides=None, alias=None):
    """{代码: (价格, 日期, 来源说明)}；优先级：--rate > 现拉 > 账内 price。本位币恒为 1。"""
    from datetime import date as _date

    known = _ledger_rates(entries, base)
    rates = {base: (Decimal(1), None, "")}
    for cur in sorted(currencies - {base}):
        if cur in (overrides or {}):
            rates[cur] = (Decimal(overrides[cur]), None, "命令行 --rate，未写入账本")
            continue
        code = (alias or {}).get(cur, cur)
        got = live.get(code)
        if got:
            px, d, src = got
            if code != cur:
                src = f"按 {code} 价格，{src}"
            day = _date.fromisoformat(str(d)[:10]) if d and len(str(d)) >= 10 and str(d)[4] == "-" else None
            rates[cur] = (px, day, f"现拉，{src}，数据时间 {d}")
        elif cur in known:
            rates[cur] = known[cur]
    return rates


def _account_meta(entries):
    """{科目: open 指令的元数据}。"""
    from beancount.core import data

    return {e.account: e.meta or {} for e in entries if isinstance(e, data.Open)}


def _estimate(entries, account, code, base, live):
    """按金额记的账户：每笔按当天价格折成数量，返回 (估算数量, 失败原因或 None)。"""
    from beancount.core import data

    qty = Decimal(0)
    for e in entries:
        if not isinstance(e, data.Transaction):
            continue
        for p in e.postings:
            if p.account != account or p.units is None or p.units.currency != base:
                continue
            got = live.get(code, e.date)
            if not got:
                return None, live.failed or f"查不到 {code} 在 {e.date} 的价格"
            qty += Decimal(p.units.number) / got[0]
    return qty, None


def _fmt_rate(r):
    return f"{r:.4f}".rstrip("0").rstrip(".") if r == r.to_integral() or abs(r) < 1000 else f"{r:.2f}"


def cmd_networth(overrides=None, today=None, offline=False):
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
    if today is None:
        from .entry import now_local

        today = now_local().date()

    rows = {"Assets": [], "Liabilities": []}
    locked, eliminated = [], []
    meta = {book: _account_meta(entries) for book, entries in books.items()}
    for book, entries in books.items():
        for acc, curs in sorted(balances(entries, ("Assets:", "Liabilities:")).items()):
            for cur, v in sorted(curs.items()):
                if abs(v) < eps:
                    continue
                if (book, acc, cur) in internal:
                    eliminated.append((book, acc, cur, v))
                elif meta[book].get(acc, {}).get("networth") is False:
                    locked.append((book, acc, cur, v))
                else:
                    rows[acc.split(":")[0]].append((book, acc, cur, v))

    live = _Live(base, not offline)
    held = {cur for kind in rows.values() for _, _, cur, _ in kind}
    estimates = {}   # (book, acc) -> (代码, 数量 或 None, 失败原因)
    for book, entries in books.items():
        for _, acc, cur, _ in rows["Assets"]:
            code = str(meta[book].get(acc, {}).get("estimate", "")).upper()
            if code and cur == base and (book, acc) not in estimates:
                qty, why = _estimate(entries, acc, code, base, live)
                estimates[(book, acc)] = (code, qty, why)
                held.add(code)
    all_entries = [e for entries in books.values() for e in entries]
    rates = _rates(all_entries, base, held, live, overrides, cfg.fx_alias)

    totals = {k: defaultdict(Decimal) for k in rows}
    in_base = {k: Decimal(0) for k in rows}
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
            value = None
            est = estimates.get((book, acc))
            if est and est[1] is not None and est[0] in rates:
                code, qty = est[0], est[1]
                value = qty * rates[code][0]
                line += f"  ≈ {value:>10.2f} {base}（买入成本；约 {qty:.3f} {code}，按每笔当天价格估算）"
            elif est:
                line += f"  （买入成本；估算现值失败：{est[2] or '缺少当天价格'}）"
                value = shown
            elif cur == base:
                value = shown
            elif cur in rates:
                value = shown * rates[cur][0]
                line += f"  ≈ {value:>10.2f} {base}"
            else:
                missing.add(cur)
            if value is not None:
                in_base[kind] += value
            print(line)

    print("\n【合计】")
    net = defaultdict(Decimal)
    for kind, title in (("Assets", "资产"), ("Liabilities", "负债")):
        for cur, v in sorted(totals[kind].items()):
            print(f"  {pad(title + '合计', 20)}{v:>12.2f} {cur}")
            net[cur] += v if kind == "Assets" else -v
    for cur, v in sorted(net.items()):
        print(f"  {pad('净资产', 20)}{v:>12.2f} {cur}")

    print(f"\n【折合 {base}{'，按现价' if estimates else ''}】")
    used = set(net) | {e[0] for e in estimates.values()}
    for cur, (r, d, src) in sorted(rates.items()):
        if cur == base or cur not in used:
            continue
        if d is None or "现拉" in src:
            note = src
        elif d >= today:
            note = f"{d} {src}，当日价格"
        else:
            note = f"{d} {src}，距今 {(today - d).days} 天，非当日价格"
        print(f"  1 {cur} = {_fmt_rate(r)} {base}（{note}）")
    print(f"  {pad('总资产', 20)}{in_base['Assets']:>12.2f} {base}")
    print(f"  {pad('总负债', 20)}{in_base['Liabilities']:>12.2f} {base}")
    print(f"  {pad('净资产', 20)}{in_base['Assets'] - in_base['Liabilities']:>12.2f} {base}")
    if live.failed:
        print(f"  [!] 联网取价失败（{live.failed}），已改用账内价格")
    if missing:
        names = ", ".join(sorted(missing))
        print(f"  [!] 缺少 {names} 的价格，未计入折合合计；请在 common/prices.beancount 补 price，"
              f"或用 --rate {sorted(missing)[0]}=汇率 临时指定")

    if locked:
        print("\n【不计入净资产（退休前取不出来，open 指令标了 networth: FALSE）】")
        for book, acc, cur, v in locked:
            print(f"  {pad(book, bw)}{acc:<36}{v:>12.2f} {cur}")
    if len(books) > 1 or eliminated:
        print("\n【已抵销的账本间往来（不计入上表）】")
        if not eliminated:
            print("  （无）")
        for book, acc, cur, v in eliminated:
            print(f"  {pad(book, bw)}{acc:<36}{v:>12.2f} {cur}")
    if excluded:
        print(f"\n【未合并的账本】{' / '.join(excluded)}（ledger.toml 中 consolidate = false）")
    return 0
