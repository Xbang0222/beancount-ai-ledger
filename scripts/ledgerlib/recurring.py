"""周期事项：到日子就该有一笔的账（每周定投、每月房租），算出哪几天还没记。

规则写在 ledger.toml 的 [[recurring]]。这里只负责算和给出现成分录，不替用户入账——
扣款有没有真的发生，脚本不知道；它只保证“该补的那几天”不靠记性。
"""
import calendar
from datetime import timedelta

from .books import transactions

MAX_LISTED = 31   # 一条规则最多列这么多个漏记的日子（只列最近的），免得起算日写早了刷屏


def due_dates(rule, today):
    """从 rule.since 到 today（含）之间按周期应有一笔的日期，升序；rule.skip 列出的日期不算。"""
    out = []
    d = rule.since
    while d <= today:
        if rule.kind == "daily":
            hit = True
        elif rule.kind == "weekday":
            hit = d.weekday() < 5
        elif rule.kind == "weekly":
            hit = d.weekday() == rule.day
        else:  # monthly：当月没有这一天（如 31 号）就取月末
            hit = d.day == min(rule.day, calendar.monthrange(d.year, d.month)[1])
        if hit and d not in rule.skip:
            out.append(d)
        d += timedelta(days=1)
    return out


def missing(rule, entries, today):
    """rule 该有却没记的日期（升序，最多 MAX_LISTED 个最近的）。

    当天有一笔对方或摘要含 rule.match 的交易就算记过。
    """
    done = {t.date for t in transactions(entries)
            if rule.match in (t.narration or "") or rule.match in (t.payee or "")}
    return [d for d in due_dates(rule, today) if d not in done][-MAX_LISTED:]


def render(rule, day):
    """把分录模板里的 {date} 换成 day；没配模板返回空串。"""
    return rule.entry.replace("{date}", day.isoformat())


def pending(cfg, entries_by_book, today):
    """[(Recurring, [漏记日期])]，只含有漏记的规则；entries_by_book 里没有的账本跳过。"""
    out = []
    for rule in cfg.recurring:
        if rule.book not in entries_by_book:
            continue
        days = missing(rule, entries_by_book[rule.book], today)
        if days:
            out.append((rule, days))
    return out
