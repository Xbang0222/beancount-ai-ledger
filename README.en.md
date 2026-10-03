# beancount-ai-ledger

[简体中文](README.md) | English

[![CI](https://github.com/Xbang0222/beancount-ai-ledger/actions/workflows/ci.yml/badge.svg)](https://github.com/Xbang0222/beancount-ai-ledger/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Xbang0222/beancount-ai-ledger)](https://github.com/Xbang0222/beancount-ai-ledger/releases)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](requirements.txt)
[![License](https://img.shields.io/github/license/Xbang0222/beancount-ai-ledger)](LICENSE)

A [Beancount](https://github.com/beancount/beancount) ledger template that you keep by talking to an AI coding agent.

Tell Claude Code, Codex or a similar agent "lunch 18, paid with WeChat". The agent writes a double-entry transaction following the rules in this repository, a script validates it before it is written, and the change is committed to Git. The ledger is plain text in your own private repository.

[Getting started](#getting-started) · [Commands](#commands) · [Multiple books](#multiple-books) · [FAQ](#faq)

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

## No Git? A chat assistant with cloud storage works too

If you only use an assistant that comes with a cloud computer and a cloud drive (such as Doubao), you can skip GitHub and Git entirely. The ledger lives as a zip file in your own cloud drive.

1. Download the [template zip](https://github.com/Xbang0222/beancount-ai-ledger/archive/refs/heads/main.zip).
2. Send the zip to the assistant and tell it to unzip it, read `AGENTS.md` (the "不用 Git 时" section) and `CATEGORIES.md`, set up your accounts, and save the ledger to a folder in your cloud drive after every change.
3. In later sessions, tell it where the ledger is: "take the newest `ledger-backup` zip from my cloud drive folder and follow its `AGENTS.md`".

The assistant reports the last recorded transaction at the start of each session so you can spot a stale copy, and runs `ledger.py backup` after every change to write a fresh zip back to your drive.

## Commands

Run `python3 scripts/ledger.py <command>`. Add `--root <dir>` to operate on a ledger in another directory.

| Command | Description |
|---|---|
| `doctor` | Check dependencies, each book's state and whether the Git remote is private |
| `check [--no-reconcile]` | Validate every book, and reconcile inter-book balances when mirrors are declared |
| `add <book> [--file FILE]` | Append one entry from stdin or a file; roll back if validation fails |
| `recent <book> [-n N]` | Latest N transactions by date and time (default 10) |
| `summary <book> [YYYY-MM]` | Income and expenses by top-level account |
| `report <book> [YYYY-MM]` | Monthly report: income, expense shares, savings rate (profit margin for business books) |
| `balances <book>` | Account balances |
| `tag <book> <tag> [YYYY-MM]` | Totals and details for one tag |
| `networth [--rate CUR=RATE]` | Consolidated balance sheet with inter-book eliminations and currency conversion |
| `reconcile` | Check that each pair of mirror accounts nets to zero |
| `fmt [--check] [book]` | Normalize journal layout and ordering without changing amounts |
| `books` | List books and mirror accounts |
| `new-book <name> [options]` | Create a book, see [Multiple books](#multiple-books) |
| `backup [-o DIR]` | Pack the whole ledger into one zip, for cloud-drive storage when you do not use Git |

Adding an entry by hand:

```bash
python3 scripts/ledger.py add personal <<'EOF'
2026-09-26 * "面馆" "餐饮-午餐"
  Expenses:Food:Dining  18.00 CNY
  Assets:Wechat
EOF
```

More patterns (split bills, advances, credit card repayment, refunds, deposits, loans, funds, foreign currency) are in [`examples/cookbook.beancount`](examples/cookbook.beancount).

## Multiple books

One book is one accounting entity. Create a new book only when something needs its own profit and loss, or the money isn't entirely yours: a shop, a studio, a shared family pool. To see what a trip cost, use a tag instead: `ledger.py tag personal chengdu`.

```bash
# A shop with business accounts, linked to the personal book
python3 scripts/ledger.py new-book shop --template business --title "My Shop" --link personal

# A shared family book, excluded from your personal net worth
python3 scripts/ledger.py new-book family --template minimal --title "Family" --no-consolidate
```

`--link personal` opens a pair of accounts in each book and registers them as mirrors in `ledger.toml`:

| Situation | Personal book | Shop book |
|---|---|---|
| You pay for the shop from a personal account | `Assets:Receivable:Shop` | `Liabilities:OwnerLoan` |
| Shop money lands in a personal account | `Liabilities:Shop` | `Assets:Receivable:Owner` |

Each mirror pair must sum to zero. Beancount only checks that a single book balances, so a transfer recorded on one side goes unnoticed. `add` prints a hint when an entry touches a mirror account, `reconcile` checks every pair, and `networth` eliminates them when consolidating.

A complete `ledger.toml`:

```toml
[ledger]
timezone = "Asia/Shanghai"      # used for injected times and the future-date check
base_currency = "CNY"           # target currency for networth

[books.personal]                # book name: starts with a lowercase letter
title = "个人账本"
kind = "personal"               # personal: savings rate; business: operating result

[books.shop]
title = "My Shop"
kind = "business"
consolidate = true              # include in networth (default true)
# main = "shop.beancount"       # entry file, default <name>.beancount
# journal = "shop/journal"      # journal directory, default <name>/journal

[[mirrors]]                     # a mirror pair: both sides must sum to zero
name = "personal pays for shop"
currency = "CNY"
accounts = { personal = "Assets:Receivable:Shop", shop = "Liabilities:OwnerLoan" }
```

Misspelled keys, references to undeclared books and accounts used in more than one mirror pair are reported as errors.

## Project layout

```text
.
├── ledger.toml              books, mirrors, timezone, base currency
├── personal.beancount       entry file of the personal book (open it in Fava)
├── personal/
│   ├── accounts.beancount   chart of accounts
│   ├── opening.beancount    opening balances
│   └── journal/             monthly journals, created by add
├── common/                  commodities, exchange rates and prices
├── AGENTS.md                instructions for AI agents
├── CLAUDE.md, GEMINI.md     load AGENTS.md into Claude Code and Gemini CLI
├── CATEGORIES.md            bookkeeping rules
├── STATE.md                 temporary context, such as an ongoing trip
├── docs/GUIDE.md            user guide (Chinese)
├── examples/                entry cookbook and example ledger
├── scripts/                 ledger.py, bootstrap.py and the implementation
└── tests/                   pytest suite
```

## FAQ

**Which agents work?**
Any coding agent that can read files and run commands. Claude Code and Gemini CLI load the rules through `CLAUDE.md` and `GEMINI.md`; Codex, Cursor, GitHub Copilot and others read `AGENTS.md` directly.

**Does it work on Windows?**
Yes, CI runs the full test suite on Windows. Use `python` or `py` instead of `python3`. PowerShell has no heredoc, so save the entry to a UTF-8 file and run `add <book> --file <file>`.

**What about cloud agents such as Claude Code on the web or Codex cloud?**
Each session starts in a fresh environment. Following `AGENTS.md`, the agent runs `bootstrap.py` to install the dependencies before doing anything else.

**Can I use it without an AI agent?**
Yes. Everything is a command-line script.

**What does the GitHub Actions workflow do in my copy?**
In a repository created from the template it only runs `check` on each push, which takes about a minute. Delete `.github/workflows/` if you don't want it.

**Charts?**
Use [Fava](https://github.com/beancount/fava): `pip install fava && fava personal.beancount`, then open http://localhost:5000.

**How do I upgrade to a newer template?**
Pull only the scripts and tests; your ledger data stays untouched:

```bash
git remote add upstream https://github.com/Xbang0222/beancount-ai-ledger.git   # once
git fetch upstream
git checkout upstream/main -- scripts tests requirements.txt requirements-dev.txt
python3 -m pytest tests/ -q && python3 scripts/ledger.py check
git commit -m "chore(script): sync upstream scripts"
```

Merge changes to `AGENTS.md` and `CATEGORIES.md` by hand, using the [changelog](CHANGELOG.md), since you have probably edited them.

## Acknowledgements

The accounting engine is [Beancount](https://github.com/beancount/beancount) by Martin Blais (GPL-2.0). It is installed separately with pip and is not distributed with this repository.
