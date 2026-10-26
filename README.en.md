# beancount-ai-ledger

[简体中文](README.md) | English

[![CI](https://github.com/Xbang0222/beancount-ai-ledger/actions/workflows/ci.yml/badge.svg)](https://github.com/Xbang0222/beancount-ai-ledger/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Xbang0222/beancount-ai-ledger)](https://github.com/Xbang0222/beancount-ai-ledger/releases)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](requirements.txt)
[![License](https://img.shields.io/github/license/Xbang0222/beancount-ai-ledger)](LICENSE)

A plain-text double-entry ledger template built on [Beancount](https://github.com/beancount/beancount), designed for bookkeeping with an AI agent. Describe your spending to Claude Code, Codex or a similar agent in everyday words; the agent turns it into a proper transaction following the rules in this repository, a script validates it before it is written, and the change is saved with Git (or a zip backup in your cloud drive). It starts with one personal book; add separate books for a shop, a studio or a shared family budget as needed.

> [!NOTE]
> The rules, account templates and user guide are written in Chinese and target users in mainland China (Alipay, WeChat Pay, Huabei and so on). The code is locale-agnostic: timezone and base currency are set in `ledger.toml`, and the account names are English.

## Files that drive the agent

- `CATEGORIES.md`: the bookkeeping rules — which account each payment method maps to, how expenses are categorized, how payees and narrations are written, loans, credit and investments. **Edit it to match your habits**; the agent follows whatever it says.
- `CLASSIFY.md`: why the categories are what they are, plus "what the user said → how it is booked" examples.
- `STATE.md`: short-lived context such as an ongoing trip or a temporary default payment account; deleted when it no longer applies.
- `AGENTS.md` (referenced by `CLAUDE.md` and `GEMINI.md`): operating rules for the agent, picked up automatically by common coding agents.

## Example

> **You:** noodles for lunch 18, WeChat; taxi home 32, Huabei
>
> **Agent:** Recorded 2 entries: Food 18.00 (WeChat balance); Transport 32.00 (Huabei). No tags.

What ends up in the journal (`time` is injected by the script at entry time, never guessed by the agent):

```beancount
2026-09-26 * "面馆" "餐饮-牛肉面"
  time: "12:10"
  Expenses:Food:Dining  18.00 CNY
  Assets:Wechat

2026-09-26 * "网约车" "交通-打车"
  time: "21:47"
  Expenses:Transport:Local  32.00 CNY
  Liabilities:Huabei
```

## Getting started

You need Python 3.9 or later and Git.

1. **Create a private repository.** Click **Use this template** → **Create a new repository**, choose **Private**, and clone it. With the [GitHub CLI](https://cli.github.com/):

   ```bash
   gh repo create my-ledger --private --template Xbang0222/beancount-ai-ledger --clone
   ```

2. **Install dependencies** into the repository's own `.venv` (the system Python is left alone):

   ```bash
   cd my-ledger
   python3 scripts/bootstrap.py                 # create .venv, install deps, validate the ledger
   git config core.hooksPath scripts/hooks      # enable pre-commit checks (once per clone)
   python3 scripts/ledger.py doctor             # check environment, books and Git remote
   ```

3. **Hand it to your agent.** Open Claude Code, Codex or another agent in the repository and start with something like:

   > Set up my ledger starting today. I have 5000 in my CMB bank account, 1200 in Alipay and 800 in WeChat, and I owe 1500 on my credit card. Default to WeChat when I don't say how I paid.

> [!WARNING]
> Your ledger contains your income, spending and balances. Keep it in a private repository and don't fork this one: forks of a public repository are public. Don't commit raw bank or Alipay exports; `.gitignore` already excludes `*.csv` and `*.xlsx`.

Try the commands on the bundled example ledger without changing anything:

```bash
python3 scripts/ledger.py --root examples/demo report personal 2026-09
python3 scripts/ledger.py --root examples/demo networth
```

## Project layout

```
beancount-ai-ledger/
├── personal.beancount          # entry file of the personal book
├── ledger.toml                 # books, cross-book mirrors, timezone, base currency, profit split
├── CATEGORIES.md               # bookkeeping rules
├── CLASSIFY.md                 # category reasoning and examples
├── STATE.md                    # short-lived context
├── AGENTS.md                   # agent operating rules
├── common/                     # commodity declarations and prices
├── personal/
│   ├── accounts.beancount      # chart of accounts
│   ├── opening.beancount       # opening balances
│   └── journal/YYYY-MM.beancount  # monthly journals (appended by the script)
├── scripts/
│   ├── ledger.py               # single entry point: add, amend, void, check, query, reconcile, format
│   ├── bootstrap.py            # environment setup
│   ├── hooks/pre-commit        # pre-commit checks
│   └── ledgerlib/              # implementation and account templates
├── examples/                   # cookbook of tricky entries and a full demo ledger
├── docs/                       # quick start, user guide, reference, FAQ (Chinese)
└── tests/                      # pytest suite (runs on temporary ledgers)
```

## Common commands

The full list is in `python3 scripts/ledger.py --help`; details in [Commands and configuration](docs/REFERENCE.md) (Chinese).

```bash
python3 scripts/ledger.py check                        # validate all books + cross-book reconciliation
python3 scripts/ledger.py recent personal              # last 10 entries, each with an [id]
python3 scripts/ledger.py find personal lunch 18       # search entries by keyword
python3 scripts/ledger.py amend personal <id>          # replace an entry with one read from stdin
python3 scripts/ledger.py void personal <id>           # delete an entry
python3 scripts/ledger.py report personal 2026-09      # monthly income, spending, savings rate
python3 scripts/ledger.py tag personal trip 2026-09    # entries and totals for one tag
python3 scripts/ledger.py networth                     # consolidated balance sheet, currencies converted
python3 scripts/ledger.py dividend 2026-09             # monthly profit split for a shop run with partners
python3 scripts/ledger.py new-book shop --template business --link personal   # add a shop book
python3 scripts/ledger.py backup --daily               # zip the whole ledger with Git history
```

## Accounting principles

- **Separate entities**: personal, shop and shared books are kept apart; transfers between them are recorded on both sides, `reconcile` checks each pair sums to zero, and `networth` eliminates them when consolidating.
- **Two-level categories**: expenses are group + subcategory only (e.g. `Expenses:Food:Dining`); who and which trip go into tags (`#trip`, `#family`), and the narration names what was bought.
- **Consumer credit**: spending on a credit card or Huabei creates a liability; repayments reduce it and are not counted as spending again.
- **Refunds and advances**: refunds reduce the original expense; money lent or paid on someone's behalf is a receivable, not spending.
- **Multiple currencies**: base currency CNY by default; other currencies are converted with `price` entries or `--rate`, and `dividend` can fetch the day's rate.

## Reliability

1. **In every command**: `add` / `amend` / `void` / `fmt` validate the whole book after writing and restore the files if anything fails.
2. **Before each commit**: the pre-commit hook runs validation, reconciliation and formatting checks, plus ruff and pytest when scripts change.
3. **After each push**: GitHub Actions runs all of the above again.

Entry guards also reject future dates, guessed times, missing payees or narrations, and exact duplicates.

## Documentation

The detailed documentation is in Chinese.

| Document | Contents |
|---|---|
| [Quick start with Git](docs/QUICKSTART.md) | Private repository, dependencies, first session |
| [Cloud AI + private repo](docs/CLOUD-GIT.md) | For chat assistants with a cloud computer (such as Doubao) that save every entry to your private GitHub repository; you only sign in once with a code (recommended) |
| [Without Git](docs/NO-GIT.md) | For chat assistants with a cloud computer and a cloud drive, such as Doubao |
| [User guide](docs/GUIDE.md) | What to say to the agent for recording, fixing, querying and reconciling |
| [Commands and configuration](docs/REFERENCE.md) | All commands, multiple books, profit split, `ledger.toml`, project layout |
| [FAQ](docs/FAQ.md) | Supported tools, Windows, cloud agents, upgrading the template |
| [Changelog](CHANGELOG.md) | What changed in each release |

## Acknowledgements

The accounting engine is [Beancount](https://github.com/beancount/beancount) by Martin Blais (GPL-2.0). It is installed separately with pip and is not distributed with this repository.
