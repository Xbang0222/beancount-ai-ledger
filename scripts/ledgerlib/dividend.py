"""按月利润分配：算出指定月份的净利润（外币按汇率折成本位币），按 ledger.toml [dividend] 的比例拆分。

外币汇率默认现拉（见 fxrate），也可用 --rate 指定；fx_alias 里的币种按别名取汇率（如 USDT 视同 USD）。
分红分录用 `period: "YYYY-MM"` 元数据标明属于哪个月的利润，按对方名称（payee）归到各方，
算出「应得 − 已分配 = 还差多少」：发完分红后又补记了当月收支，差额会自动显出来。
配了 offset 的一方，再把该科目当前余额（对方欠账本的钱，如多发的分红）从差额里扣掉，得出本次实付。
"""
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from . import config, fxrate
from .books import balances, load_entries, transactions
from .display import pad
from .entry import entry_ym, now_local

CENT = Decimal("0.01")
RATE_PLACES = Decimal("0.0001")


def _money(v):
    return v.quantize(CENT, rounding=ROUND_HALF_UP)


def month_profit(entries, ym):
    """{币种: 当月净利润}（收入 − 支出）。"""
    net = defaultdict(Decimal)
    for txn in transactions(entries):
        if entry_ym(txn.date) != ym:
            continue
        for p in txn.postings:
            if p.units is not None and p.account.startswith(("Income:", "Expenses:")):
                net[p.units.currency] -= Decimal(p.units.number)
    return dict(net)


def distributed(entries, account, ym):
    """{对方名称: 已分配金额}：account 科目上 period 为 ym 的分录，按 payee 汇总。"""
    paid = defaultdict(Decimal)
    for txn in transactions(entries):
        if str((txn.meta or {}).get("period", "")) != ym:
            continue
        for p in txn.postings:
            if p.account == account and p.units is not None:
                paid[txn.payee or ""] += Decimal(p.units.number)
    return dict(paid)


def _resolve_rates(currencies, cfg, overrides):
    """{币种: (汇率, 说明)}；拉不到时抛 fxrate.RateError。"""
    rates = {}
    for cur in currencies:
        if cur == cfg.base_currency:
            continue
        if cur in overrides:
            rates[cur] = (Decimal(overrides[cur]), "命令行 --rate")
            continue
        quote = (cfg.fx_alias or {}).get(cur, cur)
        rate, day = fxrate.fetch(quote, cfg.base_currency)
        alias = f"按 {quote} 汇率，" if quote != cur else ""
        rates[cur] = (Decimal(str(rate)).quantize(RATE_PLACES, rounding=ROUND_HALF_UP),
                      f"{alias}数据日期 {day}，来源 {fxrate.SOURCE}")
    return rates


def cmd_dividend(ym, overrides=None):
    cfg = config.load()
    if cfg.dividend is None:
        raise config.ConfigError("ledger.toml 没有配置 [dividend]（利润分配的账本与各方比例）。")
    book = cfg.dividend.book
    base = cfg.base_currency
    entries = load_entries(book)
    if entries is None:
        return 1

    profit = month_profit(entries, ym)
    try:
        rates = _resolve_rates(profit, cfg, overrides or {})
    except fxrate.RateError as ex:
        print(f"[FAIL] {ex}。请查到当天汇率后用 --rate 币种=汇率 指定。")
        return 1

    print(f"\n===== {book} · {ym} · 利润分配 =====")
    total = Decimal(0)
    for cur in sorted(profit, key=lambda c: (c != base, c)):
        v = profit[cur]
        if cur == base:
            total += v
            print(f"  {pad('净利润（' + cur + '）', 24)}{v:>12.2f} {cur}")
        else:
            r, note = rates[cur]
            total += v * r
            print(f"  {pad('净利润（' + cur + '）', 24)}{v:>12.2f} {cur}  × {r} = {_money(v * r):.2f} {base}")
            print(f"  {'':24}汇率 1 {cur} = {r} {base}（{note}）")
    total = _money(total)
    print(f"  {pad('合计净利润', 24)}{total:>12.2f} {base}")
    if ym >= entry_ym(now_local().date()):
        print("  [!] 本月还没结束，数字会随后续入账变化，月初再算定稿。")

    bals = balances(entries)
    paid = distributed(entries, cfg.dividend.account, ym)
    print(f"\n【分配】（已分配 = {cfg.dividend.account} 上 period: \"{ym}\" 的分录）")
    for p in cfg.dividend.partners:
        due = _money(total * p.share)
        done = paid.get(p.payee, Decimal(0))
        line = (f"  {pad(p.name, 10)}{p.share * 100:>5.0f}%   应得 {due:>10.2f}"
                f"   已分配 {done:>10.2f}   差额 {due - done:>10.2f} {base}")
        if p.offset:
            owed = bals.get(p.offset, {}).get(base, Decimal(0))
            if owed:
                pay = due - done - owed
                line += f"\n  {'':16}扣 {p.offset} 余额 {owed:.2f}："
                line += (f"本次实付 {pay:.2f} {base}" if pay >= 0
                         else f"差额不够扣，仍欠 {-pay:.2f} {base}，留到下次分红再扣")
        print(line)
    return 0
