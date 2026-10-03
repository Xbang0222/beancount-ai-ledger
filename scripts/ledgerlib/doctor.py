"""doctor：一次报告运行环境、各账本状态和 Git 仓库是否安全。

给第一次接手仓库的 AI（或人）看：跑一条命令就知道该先装依赖、先建私有仓库，还是先初始化账本。
只有 [FAIL] 会让退出码非零；[WARN] 是需要告诉用户、但不妨碍记账的情况。
"""
import json
import os
import re
import shutil
import subprocess
import sys

from . import __version__, config, env
from .books import load_book
from .query import last_summary

# 公开的模板仓库。用户的真实账目只能放在自己的私有仓库，不能推到这里。
UPSTREAM = "Xbang0222/beancount-ai-ledger"
GITHUB_URL_RE = re.compile(r"github\.com[:/]+([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", re.I)
# CATEGORIES.md 开头的模板提示；初始化时连同第 0 节一起改掉
TEMPLATE_MARK = "这是模板，请改成你自己的"
# 没有 Git 时的两条路：会用 Git 的建私有仓库；只用豆包这类云电脑的改用压缩包加云盘
NO_GIT_TODO = ("在账套目录 git init 并提交，改动才有记录可查。"
               "用户没有远程仓库（如豆包云电脑）：按 AGENTS.md「没有远程仓库时」，"
               "用 python3 scripts/ledger.py backup 把压缩包存进用户的云盘")
NO_REMOTE_TODO = ("用户会用 GitHub：建一个私有远程仓库，git remote add origin <地址> 后推送；"
                  "用户不会用（如豆包云电脑）：按 AGENTS.md「没有远程仓库时」，"
                  "用 python3 scripts/ledger.py backup 把压缩包存进用户的云盘")


class _Report:
    def __init__(self):
        self.fails = 0
        self.todo = []  # [(说明, 是否紧急)]

    def ok(self, msg):
        print(f"[OK] {msg}")

    def warn(self, msg, todo=None, urgent=False):
        print(f"[WARN] {msg}")
        self._add_todo(todo, urgent)

    def fail(self, msg, todo=None):
        self.fails += 1
        print(f"[FAIL] {msg}")
        self._add_todo(todo, urgent=True)

    def _add_todo(self, todo, urgent):
        """紧急的排在前面：先建私有仓库、先修好错误，再初始化账本。"""
        if not todo:
            return
        if urgent:
            self.todo.insert(sum(1 for _, u in self.todo if u), (todo, True))
        else:
            self.todo.append((todo, False))


def _run(cmd, timeout=20):
    """跑外部命令，返回 (退出码, 标准输出)；命令不存在或超时返回 (None, "")。"""
    if not shutil.which(cmd[0]):
        return None, ""
    try:
        p = subprocess.run(cmd, cwd=config.ROOT, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return None, ""
    return p.returncode, p.stdout.strip()


def github_repo(url):
    """从远程地址里取 owner/repo；不是 GitHub 地址返回 None。"""
    m = GITHUB_URL_RE.search(url or "")
    return f"{m.group(1)}/{m.group(2)}" if m else None


def github_visibility(repo):
    """用 gh 查仓库可见性（PUBLIC / PRIVATE / INTERNAL）；没装或没登录 gh 时返回 None。"""
    rc, out = _run(["gh", "repo", "view", repo, "--json", "visibility"], timeout=15)
    if rc != 0:
        return None
    try:
        return json.loads(out).get("visibility")
    except ValueError:
        return None


def _environment(r):
    print("===== 运行环境 =====")
    r.ok(f"Python {sys.version.split()[0]}（{sys.executable}）")
    r.ok(f"beancount {env.beancount_version() or '（版本未知）'}，ledger.py {__version__}")


def _books(r):
    print("\n===== 账本 =====")
    try:
        cfg = config.load()
    except config.ConfigError as ex:
        r.fail(str(ex), "修好 ledger.toml 后再运行 doctor")
        return
    r.ok(f"{config.CONFIG_NAME}：{len(cfg.books)} 本账（{' / '.join(cfg.books)}），"
         f"{len(cfg.mirrors)} 对往来镜像，时区 {cfg.timezone}，本位币 {cfg.base_currency}")

    from beancount.core import data

    for name, book in cfg.books.items():
        try:
            entries, errors, _ = load_book(name)
        except config.ConfigError as ex:
            r.fail(str(ex))
            continue
        if errors:
            r.fail(f"{name}：{len(errors)} 个校验错误",
                   f"运行 python3 scripts/ledger.py check 查看并修复 {name} 的错误")
            continue
        # pad 会生成标志为 P 的补差交易，不算用户记的账
        txns = sum(isinstance(e, data.Transaction) and e.flag != "P" for e in entries)
        checks = sum(isinstance(e, data.Balance) for e in entries)
        pads = sum(isinstance(e, data.Pad) for e in entries)
        r.ok(f"{name}（{book.title}）：校验通过，{last_summary(entries)}，余额断言 {checks} 条")
        if txns == 0 and checks == 0 and pads == 0:
            r.warn(f"{name} 还没有期初余额，也没有任何交易",
                   f"第一次使用：按 AGENTS.md「首次使用」问清用户的账户和余额，初始化 {name}")

    cats = os.path.join(config.ROOT, "CATEGORIES.md")
    if os.path.exists(cats):
        with open(cats, encoding="utf-8") as f:
            if TEMPLATE_MARK in f.read():
                r.warn("CATEGORIES.md 还是模板原样",
                       "初始化时把 CATEGORIES.md 第 0 节的付款渠道对照表改成用户的账户，并删掉开头的模板提示")


def _git(r):
    print("\n===== Git =====")
    if not os.path.isdir(config.ROOT):
        r.fail(f"账套目录不存在：{config.ROOT}")
        return
    rc, inside = _run(["git", "rev-parse", "--is-inside-work-tree"])
    if rc is None:
        r.warn("没有安装 git：改动无法追溯，也没法同步到远程", NO_GIT_TODO)
        return
    if rc != 0 or inside != "true":
        r.warn("账套目录不是 Git 仓库：改动无法追溯", NO_GIT_TODO)
        return
    _, branch = _run(["git", "branch", "--show-current"])
    _, status = _run(["git", "status", "--porcelain"])
    dirty = len([line for line in status.splitlines() if line.strip()])
    r.ok(f"分支 {branch or '（未知）'}，" + (f"{dirty} 个文件有未提交的改动" if dirty else "工作区干净"))

    _hooks(r)

    rc, url = _run(["git", "remote", "get-url", "origin"])
    if rc != 0 or not url:
        r.warn("没有配置远程仓库 origin：账本只存在这台电脑上", NO_REMOTE_TODO)
        return
    repo = github_repo(url)
    if repo and repo.lower() == UPSTREAM.lower():
        r.warn(f"origin 指向公开的模板仓库 {UPSTREAM}：真实账目不能提交到这里",
               "先让用户建自己的私有仓库（GitHub 上 Use this template 并选 Private，不要 Fork），"
               "再 git remote rename origin upstream && git remote add origin <私有仓库地址>", urgent=True)
        return
    visibility = github_visibility(repo) if repo else None
    if visibility == "PUBLIC":
        r.warn(f"远程仓库 {repo} 是公开的，账目所有人都能看到",
               "请用户在 GitHub 仓库 Settings 里改成 Private，改好之前不要推送", urgent=True)
    else:
        note = f"（{visibility}）" if visibility else "（可见性未知：没有可用的 gh 命令，请确认是私有仓库）"
        r.ok(f"origin {url}{note}")


HOOKS_DIR = "scripts/hooks"


def _hooks(r):
    """仓库带了提交前检查脚本却没启用时提醒：不启用的话，校验全靠记得手动跑。"""
    if not os.path.isfile(os.path.join(config.ROOT, HOOKS_DIR, "pre-commit")):
        return
    _, path = _run(["git", "config", "--get", "core.hooksPath"])
    # 相对路径按仓库根目录解析；写成绝对路径或 ./scripts/hooks 同样算启用
    want = os.path.realpath(os.path.join(config.ROOT, HOOKS_DIR))
    if path and os.path.realpath(os.path.join(config.ROOT, path)) == want:
        r.ok("提交前自动检查已启用（check + fmt --check，改脚本时加跑测试）")
    else:
        r.warn("提交前自动检查没有启用", f"运行 git config core.hooksPath {HOOKS_DIR} 启用提交前自动检查")


def cmd_doctor():
    r = _Report()
    _environment(r)
    _books(r)
    _git(r)
    print()
    if r.todo:
        print("下一步：")
        for t, _ in r.todo:
            print(f"  - {t}")
    elif not r.fails:
        print("一切正常，可以开始记账。")
    return 1 if r.fails else 0
