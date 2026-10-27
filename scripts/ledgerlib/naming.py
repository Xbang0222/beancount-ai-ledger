"""对方名称与摘要的写法检查：规则来自 ledger.toml 的 [naming]，没配就不检查。

入账（add）、更正（amend）时拦截不合规的写法，check 时扫一遍全账，
让“摘要怎么写”和借贷平衡一样由脚本把关，而不是只靠每次读文档。
规则只在 ledger.toml 写一份，`ledger.py rules` 把它打印成人能看的对照表。
"""
import re
from decimal import Decimal

from . import config

# 摘要里的括号段：全角（）或半角 ()
PAREN_RE = re.compile(r"[（(]([^（）()]*)[）)]")
# 收支科目的根：这两类科目每个都要配好摘要开头，否则 check 报错
PNL_ROOTS = ("Expenses", "Income")


def _match(account, prefix):
    return account == prefix or account.startswith(prefix + ":")


def _best(account, table):
    """account 命中 table 里最长的那个科目前缀，没有返回 None。"""
    hits = [k for k in table if _match(account, k)]
    return max(hits, key=len) if hits else None


def _signed(txn):
    """各条的带符号金额；入账前省略金额的那条按“其余各条之和取反”补上。"""
    nums = []
    for p in txn.postings:
        num = getattr(p.units, "number", None)
        nums.append(Decimal(num) if isinstance(num, Decimal) else None)
    filled = -sum(n for n in nums if n is not None)
    return [filled if n is None else n for n in nums]


def _main_posting(txn, table):
    """决定摘要开头的科目：命中前缀表的各条里金额绝对值最大的那条。

    返回 (科目, 命中的前缀, 带符号金额) 或 None。
    """
    best = None
    for p, amt in zip(txn.postings, _signed(txn)):
        key = _best(p.account, table)
        if key is not None and (best is None or abs(amt) > abs(best[2])):
            best = (p.account, key, amt)
    return best


def _is_reversal(account, amount):
    """费用记在贷方、或收入记在借方：钱退回来了，属于退款/退回。"""
    return (_match(account, "Expenses") and amount < 0) or (_match(account, "Income") and amount > 0)


def _pattern_of(txn, patterns):
    accounts = [p.account for p in txn.postings]
    for pat in patterns:
        if not any(_match(a, w) for a in accounts for w in pat.when):
            continue
        if all(any(_match(a, x) for x in pat.when + pat.with_) for a in accounts):
            return pat
    return None


def _quote(items):
    return "」或「".join(items)


def problems(book, txn, naming):
    """一笔交易的写法问题清单（中文说明）；没问题返回空列表。"""
    if naming is None or txn.flag == "P":  # beancount 为 pad 自动生成的补差交易，不是人写的
        return []
    payee = (txn.payee or "").strip()
    narr = (txn.narration or "").strip()
    out = []

    if payee in naming.banned_payees:
        out.append(f"对方「{payee}」太空泛：写店名、称呼或业务描述（如「便利店」「AI 会员供应商」）")

    for m in PAREN_RE.finditer(narr):
        if m.group(1) not in naming.markers:
            out.append(f"摘要括号「{m.group(0)}」不是固定标记：补充说明写进 note: 元数据，"
                       "摘要括号里只留固定标记（`ledger.py rules` 可查）")
    bare = PAREN_RE.sub("", narr).strip()
    if bare.count("-") > 1:
        out.append(f"摘要「{narr}」有多段“-”：格式是「大类简称-事项」，只用一个“-”")
    item = bare.split("-", 1)[1].strip() if "-" in bare else ""
    if item in naming.vague_items:
        out.append(f"摘要事项「{item}」太笼统：写清具体是什么东西（如「购物-小米音箱」）")

    pat = _pattern_of(txn, [p for p in naming.patterns if p.book == book])
    if pat is not None:
        bad_payee = payee not in pat.payees
        bad_narr = pat.narrations and not narr.startswith(pat.narrations)
        if bad_payee or bad_narr:
            want = f"对方写「{_quote(pat.payees)}」"
            if pat.narrations:
                want += f"，摘要以「{_quote(pat.narrations)}」开头"
            out.append(f"「{pat.name}」{want}" + (f"：{pat.hint}" if pat.hint else ""))

    if not str((txn.meta or {}).get("note", "")).strip():
        for p in txn.postings:
            if any(_match(p.account, a) for a in naming.note_required):
                out.append(f"记到兜底科目 {p.account} 要写 note: 说明买的是什么、为什么现有分类都对不上，"
                           "方便以后归类或新开科目")
                break

    table = naming.prefix.get(book) or {}
    main = _main_posting(txn, table)
    if main is not None:
        account, key, amount = main
        allowed = table[key]
        if not narr.startswith(allowed):
            out.append(f"科目 {account} 的摘要应以「{_quote(allowed)}」开头"
                       f"（多个收支科目按金额最大的那个定），收到「{narr}」")
        if naming.refund_suffix and _is_reversal(account, amount) and not bare.endswith(naming.refund_suffix):
            out.append(f"这笔是钱退回来（{account} 冲回），摘要末尾加「{_quote(naming.refund_suffix)}」，"
                       "如「餐饮-燕麦退款」；不是退款的差额按规则另记收入或费用")
    return out


def block_error(book, block):
    """入账前检查一笔分录文本的写法，返回错误说明或 None。"""
    naming = config.load().naming
    if naming is None:
        return None
    from beancount.core import data
    from beancount.parser import parser

    entries, errors, _ = parser.parse_string(block)
    if errors:
        return None  # 语法错误留给整本校验
    msgs = []
    for e in entries:
        if isinstance(e, data.Transaction):
            msgs += problems(book, e, naming)
    if not msgs:
        return None
    lines = "\n".join(f"   - {m}" for m in msgs)
    return f"对方/摘要写法不合规（本次未写入），对照表见 `ledger.py rules {book}`：\n{lines}"


def unmapped(book, entries):
    """配了摘要开头表的账本里，开了户却没配开头的收支科目：这些科目的账会漏查，check 时报错逼着补上。"""
    naming = config.load().naming
    if naming is None:
        return []
    from beancount.core.data import Open

    table = naming.prefix.get(book)
    if not table:  # 这本账没配摘要开头表：不做开头检查，也就不算漏配
        return []
    return sorted({e.account for e in entries
                   if isinstance(e, Open) and e.account.startswith(PNL_ROOTS) and _best(e.account, table) is None})


def scan(book, entries):
    """全账扫描：[(交易, [问题...])]，供 check 报告。"""
    naming = config.load().naming
    if naming is None:
        return []
    from .books import transactions

    found = []
    for t in transactions(entries):
        msgs = problems(book, t, naming)
        if msgs:
            found.append((t, msgs))
    return found


def cmd_rules(book=None):
    """把 [naming] 打印成对照表：给人看，也给 AI 入账前查。"""
    from .display import pad

    cfg = config.load()
    naming = cfg.naming
    if naming is None:
        print(f"{config.CONFIG_NAME} 没有配置 [naming]，不做对方/摘要写法检查。")
        return 0
    books = [book] if book else list(cfg.books)
    for b in books:
        table = naming.prefix.get(b) or {}
        print(f"\n===== {b}：摘要开头（按记账科目；多个收支科目按金额最大的那个） =====")
        if not table:
            print("  （未配置）")
        for acc, heads in table.items():
            print(f"  {pad(acc, 28)}{' / '.join(heads)}")
        pats = [p for p in naming.patterns if p.book == b]
        if pats:
            print(f"\n----- {b}：固定场景 -----")
        for p in pats:
            print(f"  {p.name}")
            print(f"    分录只涉及：{' / '.join(p.when + p.with_)}（且含 {' / '.join(p.when)} 之一）")
            print(f"    对方只能写：{' / '.join(p.payees)}")
            if p.narrations:
                print(f"    摘要开头：{' / '.join(p.narrations)}")
            if p.hint:
                print(f"    说明：{p.hint}")
    if naming.fallback:
        print("\n----- 找不到分类时 -----")
        for i, step in enumerate(naming.fallback, 1):
            print(f"  {i}. {step}")
    print("\n----- 通用 -----")
    print("  摘要格式：「大类简称-具体事项」，只用一个“-”，详细情况写进 note:")
    print(f"  括号里只许出现的固定标记：{' '.join(f'（{m}）' for m in naming.markers) or '（无）'}")
    if naming.refund_suffix:
        print(f"  退款/退回（费用冲回、收入冲减）摘要末尾：{' / '.join(naming.refund_suffix)}")
    if naming.banned_payees:
        print(f"  不能当对方的空泛词：{'、'.join(naming.banned_payees)}")
    if naming.vague_items:
        print(f"  不能当事项的笼统词：{'、'.join(naming.vague_items)}")
    return 0
