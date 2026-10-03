# beancount-ai-ledger

[简体中文](README.md) | English

[![CI](https://github.com/Xbang0222/beancount-ai-ledger/actions/workflows/ci.yml/badge.svg)](https://github.com/Xbang0222/beancount-ai-ledger/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Xbang0222/beancount-ai-ledger)](https://github.com/Xbang0222/beancount-ai-ledger/releases)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](requirements.txt)
[![License](https://img.shields.io/github/license/Xbang0222/beancount-ai-ledger)](LICENSE)

A [Beancount](https://github.com/beancount/beancount) ledger template that you keep by talking to an AI coding agent.

Tell Claude Code, Codex or a similar agent "lunch 18, paid with WeChat". The agent writes a double-entry transaction following the rules in this repository, a script validates it before it is written, and the change is committed to Git. The ledger is plain text in your own private repository.

[Getting started](#getting-started) · [Documentation](#documentation)

> [!NOTE]
> The rules, account templates and user guide are written in Chinese and target users in mainland China (Alipay, WeChat Pay, Huabei and so on). The code is locale-agnostic: timezone and base currency are set in `ledger.toml`, and the account names are English.

## Example

> **You:** noodles for lunch 18, WeChat; taxi home 32, Huabei
>
> **Agent:** Recorded 2 entries: Food 18.00 (WeChat balance); Transport 32.00 (Huabei). No tags.

What ends up in the journal. The `time` metadata is injected by the script at entry time:

```beancount
2026-09-26 * "面馆" "餐饮-午餐"
  time: "12:10"
  Expenses:Food:Dining  18.00 CNY
  Assets:Wechat

2026-09-26 * "网约车" "交通-打车"
  time: "21:47"
  Expenses:Transport:Local  32.00 CNY
  Liabilities:Huabei
```

## Features

- The bookkeeping rules live in [`CATEGORIES.md`](CATEGORIES.md): which account each payment method maps to, which expense account to use, how to write payees, narrations and tags. Edit the file to change how the agent books things.
- New entries never go straight into the journal files. They go through `ledger.py add`: one transaction per call, the time is injected rather than guessed, future dates and times are rejected, and unbalanced entries or unopened accounts are rolled back.
- Starts with a single personal book. Add a shop, a studio or a shared family book with `new-book`. Transfers between books are recorded on both sides and checked by `reconcile`.
- Reports: recent entries, monthly summary, monthly report with savings rate, balances, per-tag totals (for example, the cost of a whole trip), and consolidated net worth with currency and fund conversion.
- Ships `AGENTS.md`, `CLAUDE.md` and `GEMINI.md`, so common coding agents pick up the rules when they open the repository. The `doctor` command reports missing dependencies, uninitialized books and a public Git remote.

## Getting started

You need Python 3.9 or later and Git.

### 1. Create a private repository

Click **Use this template** → **Create a new repository** on this page, choose **Private**, and clone it. With the [GitHub CLI](https://cli.github.com/):

```bash
gh repo create my-ledger --private --template Xbang0222/beancount-ai-ledger --clone
```

> [!WARNING]
> Your ledger contains your income, spending and balances. Keep it in a private repository and don't fork this one: forks of a public repository are public. Don't commit raw bank or Alipay exports; `.gitignore` already excludes `*.csv` and `*.xlsx`.

### 2. Install dependencies

```bash
cd my-ledger
python3 scripts/bootstrap.py
```

The script installs Beancount into `.venv` inside the repository and validates the ledger. After that, run `python3 scripts/ledger.py` as usual; it switches to `.venv` automatically. On Windows use `python` or `py` instead of `python3`.

### 3. Hand it to your agent

Open Claude Code, Codex or another agent in the repository and start with something like:

> Set up my ledger starting today. I have 5000 in my CMB bank account, 1200 in Alipay and 800 in WeChat, and I owe 1500 on my credit card. Default to WeChat when I don't say how I paid.

The agent runs `doctor`, adjusts the chart of accounts and opening balances, validates, and commits. See the [user guide](docs/GUIDE.md) (Chinese) for everyday phrases.

> [!TIP]
> Try the commands on the bundled example ledger without changing anything:
>
> ```bash
> python3 scripts/ledger.py --root examples/demo report personal 2026-09
> python3 scripts/ledger.py --root examples/demo networth
> ```

## Documentation

The detailed documentation is in Chinese.

| Document | Contents |
|---|---|
| [Quick start with Git](docs/QUICKSTART.md) | Private repository, dependencies, first session |
| [Without Git](docs/NO-GIT.md) | For chat assistants with a cloud computer and a cloud drive, such as Doubao: the ledger lives on the cloud computer, with a daily zip backup in your own drive |
| [User guide](docs/GUIDE.md) | What to say to the agent for recording, fixing, querying and reconciling |
| [Commands and configuration](docs/REFERENCE.md) | All `ledger.py` commands, multiple books, `ledger.toml`, project layout |
| [FAQ](docs/FAQ.md) | Supported tools, Windows, cloud agents, upgrading the template |
| [Changelog](CHANGELOG.md) | What changed in each release |

## Acknowledgements

The accounting engine is [Beancount](https://github.com/beancount/beancount) by Martin Blais (GPL-2.0). It is installed separately with pip and is not distributed with this repository.
