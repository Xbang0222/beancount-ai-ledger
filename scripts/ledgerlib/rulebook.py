"""规则文档的位置。账套自有的核算规则按主题放在 rules/ 目录；旧版布局的规则文件在根目录。

脚本里凡是要指向规则文档的地方都经这里取路径：两种布局都认，文档挪位置只改这一处。
"""
import os

from . import config

RULES_DIR = "rules"
LEGACY = ("CLASSIFY.md", "CATEGORIES.md")
# 检索时排在前面的文件：速查词典、判例、分类表、日常规则；其余按文件名
FIRST = ("dictionary.md", "cases.md", "classification.md", "daily.md")
# 主题 -> (新布局里的写法, 旧布局里的写法)；新布局的文件不存在时退回旧写法
TOPICS = {
    "daily": ("rules/daily.md", "CATEGORIES.md"),
    "books": ("rules/daily.md「账本与往来判定」", "CATEGORIES.md 第 3 节"),
    "mirror": ("rules/daily.md「代垫与代收」", "CATEGORIES.md 第 4 节"),
    "commits": ("docs/COMMITS.md", "AGENTS.md「每次改动后」"),
}


def _exists(rel):
    return os.path.isfile(os.path.join(config.ROOT, *rel.split("/")))


def ref(topic):
    """某个主题该指向哪份文档（给提示信息用）。"""
    new, old = TOPICS[topic]
    return new if _exists(new.split("「")[0]) else old


def files():
    """账套里现有的规则文档（相对账套根目录的路径），按检索顺序排列。"""
    try:
        names = [n for n in os.listdir(os.path.join(config.ROOT, RULES_DIR)) if n.endswith(".md")]
    except OSError:
        names = []
    rank = {n: i for i, n in enumerate(FIRST)}
    found = [f"{RULES_DIR}/{n}" for n in sorted(names, key=lambda n: (rank.get(n, len(FIRST)), n))]
    return found + [n for n in LEGACY if _exists(n)]
