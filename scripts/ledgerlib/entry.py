"""分录文本的解析与预处理（不涉及磁盘写入）。"""
import re
from datetime import date, datetime

# 行首日期；用于定位分录所属月份
DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})", re.M)
# 交易首行：日期 + 标志位（* / ! / txn 三种写法都算一笔）
TXN_RE = re.compile(r"^\d{4}-\d{2}-\d{2}[ \t]+([*!]|txn\b)", re.M)
# 已含 time 元数据
TIME_RE = re.compile(r"^[ \t]+time:[ \t]", re.M)
# 手写 time 的取值（HH:MM）
TIME_VAL_RE = re.compile(r'^[ \t]+time:[ \t]*"(\d{1,2}):(\d{2})"', re.M)


def now_local():
    """当前时间（ledger.toml 中配置的时区，默认 Asia/Shanghai）。"""
    from zoneinfo import ZoneInfo

    from . import config

    return datetime.now(ZoneInfo(config.load().timezone))


def future_error(block, now=None):
    """交易日期晚于今天、或当天交易的手写 time 晚于此刻时返回错误说明，否则返回 None。

    账本只记已经发生的事：日期在未来多半是年份/月份写错；手写 time 只应来自用户
    明确报的时间，晚于此刻说明是估的，或把上午当成了晚上。
    """
    if not TXN_RE.search(block):
        return None
    m = DATE_RE.search(block)
    try:
        d = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None  # 非法日期交给 beancount 校验报错
    now = now or now_local()
    if d > now.date():
        return (f"交易日期 {d} 晚于今天 {now.date()}（本次未写入）。"
                "检查年份、月份是否写错；尚未发生的交易不要提前入账。")
    t = TIME_VAL_RE.search(block)
    if t and d == now.date() and (int(t.group(1)), int(t.group(2))) > (now.hour, now.minute):
        return (f'time "{t.group(1)}:{t.group(2)}" 晚于当前时间 {now:%H:%M}（本次未写入）。'
                "time 只能填用户明确报的时间，用户没说就删掉 time 行，由脚本注入录入时刻，不要估。")
    return None


TIME_OK_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
# 可以经 add 写进序时簿的非交易指令；开户、币种声明等属于科目表，不进序时簿
JOURNAL_DIRECTIVES = ("Balance", "Pad", "Price", "Note")


def validate(block):
    """入账前的内容检查，返回错误说明或 None。

    借贷平衡、科目是否开户由 beancount 整本校验把关；这里补它不管的几条口径：
    对方和摘要必须写、time 必须是合法的 HH:MM、序时簿只收交易和余额断言等少数指令。
    语法错误不在这里报，留给整本校验（它会带上文件与行号）。
    """
    from beancount.core import data
    from beancount.parser import parser

    entries, errors, _ = parser.parse_string(block)
    if errors:
        return None
    for e in entries:
        kind = type(e).__name__
        if not isinstance(e, data.Transaction):
            if kind not in JOURNAL_DIRECTIVES:
                return (f"序时簿不收 {kind.lower()} 指令（本次未写入）。"
                        "开户、币种声明请写进对应的 accounts.beancount / commodities.beancount。")
            continue
        if not (e.payee or "").strip() or not (e.narration or "").strip():
            return ('交易首行要同时写对方和摘要两段："对方" "摘要"，都不能为空（本次未写入）。'
                    "写法见 CATEGORIES.md 0.1。")
        t = e.meta.get("time")
        if t is not None and not (isinstance(t, str) and TIME_OK_RE.match(t)):
            return (f'time 应为 24 小时制的 "HH:MM"（如 "09:05"），收到：{t!r}（本次未写入）。'
                    "用户没报具体时间就删掉 time 行，由脚本注入录入时刻。")
    return None


def time_line(block):
    """块中的 time 元数据行（原样返回，含缩进）；没有则返回 None。"""
    for line in block.split("\n"):
        if TIME_RE.match(line):
            return line
    return None


def with_time_line(block, line):
    """把一行现成的 time 元数据插到交易首行之后；块里已有 time 或不是交易时原样返回。"""
    if TIME_RE.search(block):
        return block
    lines = block.split("\n")
    for i, text in enumerate(lines):
        if TXN_RE.match(text):
            lines.insert(i + 1, line)
            return "\n".join(lines)
    return block


def first_date(block):
    """分录中出现的第一个日期，返回 (年, 月) 字符串元组；没有则返回 None。"""
    m = DATE_RE.search(block)
    if not m:
        return None
    return m.group(1), m.group(2)


def count_transactions(block):
    """块中的交易笔数（用于“一次只录一笔”的守卫）。"""
    return len(TXN_RE.findall(block))


def inject_time(block, now=None):
    """交易未含 time 元数据时注入当前时间（配置时区）。

    无论交易日期是否为今天都注入：补记历史账同样带 time（即录入时刻），口径见 CATEGORIES.md 第 7 节。
    用户已手写 time 的不覆盖；余额断言、价格等非交易指令不注入（balance 断言的是当天开始时，time 无意义）。
    """
    if TIME_RE.search(block):
        return block
    lines = block.split("\n")
    # 定位交易首行（而非固定第 2 行）：块首可能有注释行，插错位置会导致语法错误
    header = None
    for i, line in enumerate(lines):
        if TXN_RE.match(line):
            header = i
            break
    if header is None:
        return block
    now = now or now_local()
    lines.insert(header + 1, f'  time: "{now.strftime("%H:%M")}"')
    return "\n".join(lines)


def has_active_include(main_text, rel):
    """只认行首非注释的有效 include；被 ; // # 注释掉的不算生效。"""
    target = f'include "{rel}"'
    for line in main_text.splitlines():
        s = line.strip()
        if s.startswith((";", "//", "#")):
            continue
        if target in s:
            return True
    return False


def touched_accounts(block, accounts):
    """块中以整词出现的科目（用于提示“本笔涉及往来科目，记得记另一边”）。"""
    hits = []
    for acc in accounts:
        if re.search(rf"(?<![\w:]){re.escape(acc)}(?![\w:])", block):
            hits.append(acc)
    return hits


YM_RE = re.compile(r"^(\d{4})-(\d{2})$")


def parse_ym(ym):
    """校验并返回规范化的 YYYY-MM；非法则抛 ValueError。"""
    m = YM_RE.match(ym or "")
    if not m:
        raise ValueError(f"月份格式应为 YYYY-MM，收到：{ym!r}")
    month = int(m.group(2))
    if not 1 <= month <= 12:
        raise ValueError(f"月份应在 01-12 之间，收到：{ym!r}")
    return ym


def entry_ym(d):
    """datetime.date → 'YYYY-MM'。"""
    return f"{d.year:04d}-{d.month:02d}"
