"""对方名称、摘要与 note 的写法检查：规则来自 ledger.toml 的 [naming]，没配就不检查。

入账（add）、更正（amend）时拦截不合规的写法，check 时扫一遍全账，
让“摘要怎么写、note 怎么分栏”和借贷平衡一样由脚本把关，而不是只靠每次读文档。
规则只在 ledger.toml 写一份，`ledger.py rules` 把它打印成人能看的对照表。
"""
import re
from decimal import Decimal

from . import config

# 摘要里的括号段：全角（）或半角 ()
PAREN_RE = re.compile(r"[（(]([^（）()]*)[）)]")
# 收支科目的根：这两类科目每个都要配好摘要开头，否则 check 报错
PNL_ROOTS = ("Expenses", "Income")
# note 中导入来源的备注原文：自「<来源>备注：」起照录，不参加写法检查
NOTE_SOURCE_RE = re.compile(r"(?:^|；)[^；：，。]{0,12}" + config.NOTE_SOURCE_SUFFIX + "：")
FIELD_LABELS = {"payee": "对方", "narration": "摘要", "note": "note"}


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


def _is_reversal(account, amount, two_way=()):
    """费用记在贷方、或收入记在借方：钱退回来了，属于退款/退回。双向科目（如投资盈亏）不算。"""
    if any(_match(account, a) for a in two_way):
        return False
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


def own_note(note):
    """note 里由入账者书写的部分：去掉导入来源的备注原文。"""
    m = NOTE_SOURCE_RE.search(note)
    return note[:m.start()] if m else note


def note_problem(note, labels, limit=0):
    """note 的字数与分栏格式问题（中文说明）；合规、或未配置上限与栏目时返回 None。

    格式：「栏目：内容；栏目：内容」，栏目取自 [naming.note_labels]，按表中顺序，各至多一次；
    末段可以是导入来源的备注原文「<来源>备注：……」，照录，不参加检查，也不计入字数。
    """
    own = own_note(note)
    if not own:
        return None
    if limit and len(own) > limit:
        return f"note 共 {len(own)} 字，超过 {limit} 字上限：只写分录未表达的事实，写短语"
    if not labels:
        return None
    names = [name for name, _ in labels]
    usage = f"每段写「栏目：内容」，段间用「；」，栏目按顺序为 {'、'.join(names)}"
    last = -1
    for seg in own.split("；"):
        head, sep, body = seg.partition("：")
        if not sep or head not in names:
            return f"note 的「{seg}」没有写栏目：{usage}"
        if not body.strip():
            return f"note 的「{head}」栏没有内容：没有可写的就去掉这一栏"
        if "：" in body:
            return f"note 的「{seg}」一段里有两个「：」：一段只属于一个栏目，内容里的并列用「，」"
        i = names.index(head)
        if i == last:
            return f"note 的「{head}」栏出现了两次：同一栏的内容并成一段，用「，」连接"
        if i < last:
            return f"note 的「{head}」栏位置不对：{usage}"
        last = i
    return None


def _applies(f, txn):
    """带条件的禁用写法只在分录带该标签、涉及该科目时检查。"""
    if f.tag and f.tag not in (txn.tags or ()):
        return False
    return not f.account or any(_match(p.account, f.account) for p in txn.postings)


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

    note = str((txn.meta or {}).get("note", "")).strip()
    texts = {"payee": payee, "narration": narr, "note": own_note(note)}
    for f in naming.forbidden:
        if not _applies(f, txn):
            continue
        m = f.regex.search(texts[f.field])
        if m:
            out.append(f"{FIELD_LABELS[f.field]}「{texts[f.field]}」含{f.name}「{m.group(0)}」"
                       + (f"：{f.hint}" if f.hint else ""))

    bad_note = note_problem(note, naming.note_labels, naming.note_max)
    if bad_note:
        out.append(bad_note)

    accounts = [p.account for p in txn.postings]
    for r in naming.required:
        if r.book != book or not any(_match(a, w) for a in accounts for w in r.when):
            continue
        if r.with_ and not any(_match(a, x) for a in accounts for x in r.with_):
            continue
        if not r.regex.search(texts["note"]):
            out.append(f"note 没有写明{r.name}" + (f"：{r.hint}" if r.hint else ""))

    pat = _pattern_of(txn, [p for p in naming.patterns if p.book == book])
    if pat is not None:
        bad_payee = pat.payees and payee not in pat.payees
        bad_narr = pat.narrations and not narr.startswith(pat.narrations)
        if bad_payee or bad_narr:
            want = []
            if pat.payees:
                want.append(f"对方写「{_quote(pat.payees)}」")
            if pat.narrations:
                want.append(f"摘要以「{_quote(pat.narrations)}」开头")
            out.append(f"「{pat.name}」{'，'.join(want)}" + (f"：{pat.hint}" if pat.hint else ""))

    if not note:
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
        reversal = _is_reversal(account, amount, naming.two_way)
        if naming.refund_suffix and reversal and not bare.endswith(naming.refund_suffix):
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
    return f"对方、摘要或 note 的写法不合规（本次未写入），对照表见 `ledger.py rules {book}`：\n{lines}"


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


def heads_of(book, account):
    """这本账里 account 的摘要开头（元组）；没配返回空元组。"""
    naming = config.load().naming
    table = (naming.prefix.get(book) or {}) if naming else {}
    key = _best(account, table)
    return table[key] if key else ()


def print_patterns(naming, book):
    """一本账的固定场景写法。"""
    pats = [p for p in naming.patterns if p.book == book]
    if pats:
        print(f"\n----- {book}：固定场景 -----")
    for p in pats:
        print(f"  {p.name}")
        print(f"    分录只涉及：{' / '.join(p.when + p.with_)}"
              + (f"（且含 {' / '.join(p.when)} 之一）" if p.with_ else ""))
        if p.payees:
            print(f"    对方只能写：{' / '.join(p.payees)}")
        if p.narrations:
            print(f"    摘要开头：{' / '.join(p.narrations)}")
        if p.hint:
            print(f"    说明：{p.hint}")
    reqs = [r for r in naming.required if r.book == book]
    if reqs:
        print(f"\n----- {book}：note 必须写明 -----")
    for r in reqs:
        scope = " / ".join(r.when) + (f"，且涉及 {' / '.join(r.with_)}" if r.with_ else "")
        print(f"  {r.name}")
        print(f"    分录涉及：{scope}")
        if r.hint:
            print(f"    说明：{r.hint}")


def print_general(naming):
    """各本账通用的写法：找不到分类时怎么办、摘要格式、固定标记、不许用的词与不许出现的写法。"""
    if naming.fallback:
        print("\n----- 找不到分类时 -----")
        for i, step in enumerate(naming.fallback, 1):
            print(f"  {i}. {step}")
    print("\n----- 通用 -----")
    print("  摘要格式：「大类简称-具体事项」，只用一个“-”，详细情况写进 note:")
    print(f"  括号里只许出现的固定标记：{' '.join(f'（{m}）' for m in naming.markers) or '（无）'}")
    if naming.refund_suffix:
        print(f"  退款/退回（费用冲回、收入冲减）摘要末尾：{' / '.join(naming.refund_suffix)}")
    if naming.two_way:
        print(f"  双向科目（借贷两个方向均属正常发生额，不按退款检查）：{'、'.join(naming.two_way)}")
    if naming.banned_payees:
        print(f"  不能当对方的空泛词：{'、'.join(naming.banned_payees)}")
    if naming.vague_items:
        print(f"  不能当事项的笼统词：{'、'.join(naming.vague_items)}")
    if naming.note_labels:
        print("  note 格式：「栏目：内容；栏目：内容」，栏目按下列顺序，各至多一次；"
              "分录已表达的信息不写，没有可写的不写 note")
        for name, desc in naming.note_labels:
            print(f"    {name}：{desc}")
        print(f"    <来源>{config.NOTE_SOURCE_SUFFIX}：导入来源的备注原文，照录，写在末段")
    if naming.note_max:
        print(f"  note 不超过 {naming.note_max} 字（不含导入来源的备注原文）")
    for f in naming.forbidden:
        scope = "".join([f"带 #{f.tag} 的分录，" if f.tag else "", f"涉及 {f.account} 的分录，" if f.account else ""])
        label = FIELD_LABELS[f.field] + (" " if f.field == "note" else "")
        print(f"  {scope}{label}不得出现{f.name}" + (f"：{f.hint}" if f.hint else ""))


def cmd_rules(book=None):
    """把 [naming] 打印成对照表：给人看，也给 AI 入账前查。"""
    from .display import pad

    cfg = config.load()
    naming = cfg.naming
    if naming is None:
        print(f"{config.CONFIG_NAME} 没有配置 [naming]，不做对方、摘要与 note 的写法检查。")
        return 0
    books = [book] if book else list(cfg.books)
    for b in books:
        table = naming.prefix.get(b) or {}
        print(f"\n===== {b}：摘要开头（按记账科目；多个收支科目按金额最大的那个） =====")
        if not table:
            print("  （未配置）")
        for acc, heads in table.items():
            print(f"  {pad(acc, 28)}{' / '.join(heads)}")
        print_patterns(naming, b)
    print_general(naming)
    return 0
