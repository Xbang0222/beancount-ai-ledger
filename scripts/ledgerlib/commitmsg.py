"""提交信息检查（commit-msg 钩子调用）：首行 `type: 摘要`，不带括号，改了账本要在摘要里写明是哪本。

改到哪本账按暂存的文件自动判断（`<账本>.beancount` 与账本目录），不靠记；
摘要里要出现的账本称呼取 ledger.toml 的 title（「个人账本」去掉末尾的「本」即「个人账」），不写死。
"""
import os
import re
import subprocess
import sys

from . import config

TYPES = {
    "feat": "登记新业务、补记，脚本新功能",
    "fix": "更正、作废账目，修脚本缺陷",
    "style": "只重排序时簿，余额不变",
    "docs": "文档",
    "refactor": "脚本重构",
    "test": "测试",
    "chore": "依赖、配置、汇率",
}
# 改了账本的提交：只能用这几种 type，摘要以这些动词开头
BOOK_TYPES = ("feat", "fix", "style")
BOOK_VERBS = ("登记", "补记", "更正", "作废", "对账", "重排", "新开", "新建", "初始化")
MAX_HEAD = 80
EXAMPLE = "登记个人账10月28日晚餐支出30.00元，支付宝付款"
HEAD_RE = re.compile(r"^(?P<type>[a-z]+): (?P<summary>\S.*)$")
PAREN_RE = re.compile(r"[()（）]")
# git 自己生成的提交信息不查
SKIP_RE = re.compile(r"^(Merge |Revert |fixup! |squash! |amend! )")


def book_label(book):
    """摘要里称呼这本账的写法：title 末尾的「账本」去掉「本」，如「个人账本」→「个人账」。"""
    title = book.title
    return title[:-1] if title.endswith("账本") else title


def touched_books(files, books):
    """这次改到的账本（保持 ledger.toml 里的顺序）。"""
    out = []
    for b in books:
        root = os.path.dirname(b.journal.rstrip("/")) or b.journal
        if any(f == b.main or f.startswith(root.rstrip("/") + "/") for f in files):
            out.append(b)
    return out


def problems(message, files, books):
    """提交信息的问题清单（中文说明）；没问题返回空列表。files 为空（如 --amend 只改信息）时不核对账本。"""
    lines = [ln for ln in message.splitlines() if not ln.startswith("#")]
    head = next((ln.strip() for ln in lines if ln.strip()), "")
    if not head or SKIP_RE.match(head):
        return []
    m = HEAD_RE.match(head)
    if not m:
        return [f"首行「{head}」不是 `type: 摘要` 格式（英文类型、半角冒号后空一格，不带括号）"]
    out = []
    kind, summary = m.group("type"), m.group("summary")
    if kind not in TYPES:
        out.append(f"类型「{kind}」不认识，只能用：{' / '.join(TYPES)}")
    if PAREN_RE.search(head):
        out.append("首行不用括号：账本名写进摘要，补充说明用逗号接在后面，细节放正文")
    if len(head) > MAX_HEAD:
        out.append(f"首行 {len(head)} 字，超过 {MAX_HEAD} 字：首行只写做了什么，细节放正文")
    hit = touched_books(files, books)
    if hit:
        if kind in TYPES and kind not in BOOK_TYPES:
            out.append(f"改了账本的提交类型只能是 {' / '.join(BOOK_TYPES)}"
                       "（登记补记新开 feat、更正作废对账 fix、重排 style）")
        if not summary.startswith(BOOK_VERBS):
            out.append(f"改了账本的摘要以「{'」「'.join(BOOK_VERBS)}」之一开头，"
                       f"如「{EXAMPLE}」")
        missing = [book_label(b) for b in hit if book_label(b) not in summary]
        if missing:
            out.append(f"这次改到了{'与'.join(book_label(b) for b in hit)}，摘要里要写明：缺「{'」「'.join(missing)}」")
    return out


def _staged_files():
    r = subprocess.run(["git", "diff", "--cached", "--name-only"], cwd=config.ROOT,
                       capture_output=True, text=True, encoding="utf-8")
    return [f for f in r.stdout.splitlines() if f] if r.returncode == 0 else []


def cmd_commit_msg(path):
    with open(path, encoding="utf-8") as f:
        message = f.read()
    books = list(config.load().books.values())
    msgs = problems(message, _staged_files(), books)
    if not msgs:
        return 0
    print("[commit-msg] 提交信息不合规，已拒绝提交：", file=sys.stderr)
    for m in msgs:
        print(f"   - {m}", file=sys.stderr)
    print(f"   规范见 README.md「提交信息规范」，如 feat: {EXAMPLE}", file=sys.stderr)
    return 1
