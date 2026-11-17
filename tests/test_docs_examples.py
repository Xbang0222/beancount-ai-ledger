"""文档与范例中的分录必须通过写法检查：规则改了而范例没跟着改时，在这里失败。

检查四处：演示账套本身、examples/cookbook.beancount、AGENTS.md 与 docs/、rules/ 中代码块里的分录、
rules/naming.md 的 note 栏目表。前两处以 examples/demo 的 [naming] 为准，没有演示账套的仓库跳过；
文档代码块在有演示账套时以其 [naming] 为准，否则以根目录 ledger.toml 的 [naming] 为准；
note 栏目表始终与根目录 ledger.toml 的 [naming.note_labels] 对照。
"""
import glob
import os
import re
import subprocess
import sys

import pytest
from beancount.core import data
from beancount.parser import parser

from ledgerlib import config, naming

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(REPO, "examples", "demo")
DEMO_TOML = os.path.join(DEMO, "ledger.toml")
COOKBOOK = os.path.join(REPO, "examples", "cookbook.beancount")
IS_TEMPLATE = os.path.exists(os.path.join(REPO, ".github", "workflows", "release.yml"))

# 通用写法配置：演示账套与根目录的 ledger.toml 必须一致
SHARED_KEYS = ("markers", "banned_payees", "refund_suffix", "two_way", "note_required", "vague_items", "forbidden",
               "note_labels", "note_max")

HEAD = re.compile(r'^\s*(?:;\s*)?\d{4}-\d{2}-\d{2} [*!] "')
FENCE = re.compile(r"^\s*```")
# 切换账本的行：pair 的段首 `[shop]`，或范例上方的注释 `; shop：……`
BOOK = re.compile(r"^\s*(?:\[(\w+)\]\s*|;\s*([a-z][a-z0-9_]*)[：:].*)$")
ROOT_TOML = os.path.join(REPO, "ledger.toml")
NAMING_MD = os.path.join(REPO, "rules", "naming.md")
LABEL_ROW = re.compile(r"^\|\s*\d+\s*\|\s*([^|\s]+)\s*\|")


def _toml(path):
    with open(path, "rb") as f:
        return config.tomllib.load(f)


def _demo_naming():
    if not os.path.exists(DEMO_TOML):
        pytest.skip("本仓库没有 examples/demo")
    rules = config.parse(_toml(DEMO_TOML)).naming
    if rules is None:
        pytest.skip("examples/demo 未配置 [naming]")
    return rules


def _problems(book, text, rules):
    entries, errors, _ = parser.parse_string(text)
    assert not errors, f"范例分录无法解析：{errors}\n{text}"
    out = []
    for e in entries:
        if isinstance(e, data.Transaction):
            out += [f'{e.date} "{e.payee}" "{e.narration}"：{m}' for m in naming.problems(book, e, rules)]
    return out


def _doc_blocks(path):
    """Markdown 代码块里的分录：[(账本, 分录文本)]。`[shop]` 之类的段首行切换账本，代码块结束后恢复为 personal。"""
    with open(path, encoding="utf-8") as f:
        lines = f.read().split("\n")
    found, inside, book, current = [], False, "personal", None
    for line in lines:
        if FENCE.match(line):
            inside, book = not inside, "personal"
            if current:
                found.append(current)
                current = None
            continue
        if not inside:
            continue
        m = BOOK.match(line)
        if m:
            book = m.group(1) or m.group(2)
            continue
        if HEAD.match(line):
            if current:
                found.append(current)
            current = (book, line.strip() + "\n")
        elif current and line.startswith(" ") and line.strip():
            current = (current[0], current[1] + "  " + line.strip() + "\n")
        elif current:
            found.append(current)
            current = None
    return found


def _doc_files():
    files = [os.path.join(REPO, "AGENTS.md"), os.path.join(REPO, "README.md")]
    files += sorted(glob.glob(os.path.join(REPO, "docs", "*.md")))
    files += sorted(glob.glob(os.path.join(REPO, "rules", "*.md")))
    return [f for f in files if os.path.exists(f)]


def test_演示账套通过校验与写法检查():
    _demo_naming()
    env = {k: v for k, v in os.environ.items() if k != "LEDGER_ROOT"}
    p = subprocess.run([sys.executable, os.path.join(REPO, "scripts", "ledger.py"), "--root", DEMO, "check"],
                       capture_output=True, text=True, env=env)
    assert p.returncode == 0, p.stdout + p.stderr


def test_范例集的分录符合写法规则():
    rules = _demo_naming()
    with open(COOKBOOK, encoding="utf-8") as f:
        assert _problems("personal", f.read(), rules) == []


def _doc_naming():
    """文档范例所依据的写法规则：有演示账套用演示账套的，否则用根目录 ledger.toml 的。"""
    path = DEMO_TOML if os.path.exists(DEMO_TOML) else ROOT_TOML
    rules = config.parse(_toml(path)).naming if os.path.exists(path) else None
    if rules is None:
        pytest.skip("未配置 [naming]")
    return rules


def test_文档代码块中的分录符合写法规则():
    rules = _doc_naming()
    bad, seen = [], 0
    for path in _doc_files():
        for book, text in _doc_blocks(path):
            if text.lstrip().startswith(";"):  # 注释掉的示意分录
                text = "\n".join(line.lstrip().removeprefix(";") for line in text.split("\n"))
            seen += 1
            for msg in _problems(book, text, rules):
                bad.append(f"{os.path.relpath(path, REPO)}：{msg}")
    assert seen, "没有在文档中找到任何分录范例，解析规则可能已失效"
    assert bad == []


@pytest.mark.skipif(not IS_TEMPLATE, reason="仅模板仓库要求根配置与演示账套一致")
def test_根配置与演示账套的通用写法规则一致():
    _demo_naming()
    root, demo = _toml(os.path.join(REPO, "ledger.toml"))["naming"], _toml(DEMO_TOML)["naming"]
    for key in SHARED_KEYS:
        assert root.get(key) == demo.get(key), f"[naming].{key} 在 ledger.toml 与 examples/demo/ledger.toml 中不一致"
    assert root["prefix"]["personal"] == demo["prefix"]["personal"]


def test_规范文档的_note_栏目表与配置一致():
    if not (os.path.exists(ROOT_TOML) and os.path.exists(NAMING_MD)):
        pytest.skip("本仓库没有 ledger.toml 或 rules/naming.md")
    rules = config.parse(_toml(ROOT_TOML)).naming
    if rules is None or not rules.note_labels:
        pytest.skip("未配置 [naming.note_labels]")
    with open(NAMING_MD, encoding="utf-8") as f:
        text = f.read()
    start = text.find("### 5.2")
    assert start >= 0, "rules/naming.md 缺少第 5.2 节（note 的格式）"
    section = text[start:text.find("\n### ", start + 1)]
    documented = [m.group(1) for line in section.split("\n") if (m := LABEL_ROW.match(line))]
    assert documented == [name for name, _ in rules.note_labels], \
        "rules/naming.md 第 5.2 节的栏目表与 ledger.toml 的 [naming.note_labels] 不一致"
