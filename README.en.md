# beancount-ai-ledger

[简体中文](README.md) | English

[![Release](https://img.shields.io/github/v/release/Xbang0222/beancount-ai-ledger)](https://github.com/Xbang0222/beancount-ai-ledger/releases)
[![Python](https://img.shields.io/badge/python-3.9%2B-blue)](requirements.txt)
[![License](https://img.shields.io/github/license/Xbang0222/beancount-ai-ledger)](LICENSE)

A plain-text double-entry ledger template built on [Beancount](https://github.com/beancount/beancount), designed for bookkeeping with an AI agent. Describe your spending to Claude Code, Codex or a similar agent in everyday words; the agent turns it into a proper transaction following the rules in this repository, a script validates it before it is written, and the change is saved with Git (or a zip backup in your cloud drive). It starts with one personal book; add separate books for a shop, a studio or a shared family budget as needed.

> [!NOTE]
> The rules, account templates and user guide are written in Chinese and target users in mainland China (Alipay, WeChat Pay, Huabei and so on). The code is locale-agnostic: timezone and base currency are set in `ledger.toml`, and the account names are English.

## Documentation conventions

| Document | Contents | When it is read |
|---|---|---|
| `AGENTS.md` | Operating procedure for the agent: workflow, hard constraints, reporting requirements and a document index. Referenced by `CLAUDE.md` and `GEMINI.md`, so common coding agents load it on opening the repository | At the start of a session |
| `rules/daily.md` | Rules for everyday entries: required fields, which book an entry belongs to, the payment-method-to-account table, cross-book transfers, refunds, timestamps and tags. **Edit it to match your habits**; the agent follows whatever it says | Before every entry |
| Other files under `rules/` | One topic per file: payee and narration style, tags, the category table, a lookup dictionary from items and merchants to accounts, worked cases, and special topics (credit, investments, valuation, shared books). Your own conventions go here too | On demand, via the index in `AGENTS.md` or `ledger.py lookup <keyword>` |
| `STATE.md` | Short-lived context: an ongoing trip, a temporary default payment account | Printed by `ledger.py brief` |
| `docs/AI-SETUP.md`, `docs/AI-TASKS.md` | Ledger setup and storage; handling of corrections, balance checks, statement imports, upgrades and other common requests | On demand, via the index in `AGENTS.md` |
| `docs/COMMITS.md`, `docs/DEVELOPMENT.md` | Commit message convention; development rules | Before committing; when changing scripts |

Long-lived rules go only in `rules/`, one topic per file; short-lived context goes only in `STATE.md`; when rules conflict, `rules/daily.md` prevails.

## Example

> **You:** noodles for lunch 18, WeChat; taxi home 32, Huabei
>
> **Agent:** Recorded 2 entries: Food 18.00 (WeChat balance); Transport 32.00 (Huabei). No tags.

What ends up in the journal (`time` is injected by the script at entry time, never guessed by the agent):

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

## Getting started

Any AI that can read files and run commands will do. Store the ledger wherever you can: a **private Git repository** (GitHub, Gitee, …) is best, otherwise back it up to a cloud drive; the AI picks per `docs/AI-SETUP.md` ("账本存放"). The AI runs the commands below; doing it yourself needs Python 3.9 or later and Git.

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
├── rules/                      # bookkeeping rules, one topic per file; daily.md is read before every entry
├── STATE.md                    # short-lived context
├── AGENTS.md                   # operating procedure for the agent
├── common/                     # commodity declarations and prices
├── personal/
│   ├── accounts.beancount      # chart of accounts
│   ├── opening.beancount       # opening balances
│   └── journal/YYYY-MM.beancount  # monthly journals (appended by the script)
├── scripts/
│   ├── ledger.py               # single entry point: add, amend, void, check, query, reconcile, format
│   ├── bootstrap.py            # environment setup
│   ├── hooks/pre-commit        # pre-commit checks
│   ├── hooks/commit-msg        # commit message format check
│   └── ledgerlib/              # implementation and account templates
├── examples/                   # cookbook of tricky entries and a full demo ledger
├── docs/                       # quick start, user guide, reference, FAQ; agent-facing setup, task, commit and development docs (Chinese)
└── tests/                      # pytest suite (runs on temporary ledgers)
```

## Common commands

The full list is in `python3 scripts/ledger.py --help`; details in [Commands and configuration](docs/REFERENCE.md) (Chinese).

```bash
python3 scripts/ledger.py brief                        # context for booking: date, short-lived context, recurring entries due, usable accounts
python3 scripts/ledger.py lookup catfood               # search rules and account notes by keyword
python3 scripts/ledger.py check                        # validate all books + cross-book reconciliation
python3 scripts/ledger.py recent personal              # last 10 entries, each with an [id]
python3 scripts/ledger.py find personal lunch 18       # search entries by keyword
python3 scripts/ledger.py amend personal <id>          # replace an entry with one read from stdin
python3 scripts/ledger.py void personal <id>           # delete an entry
python3 scripts/ledger.py report personal 2026-09      # monthly income, spending, savings rate
python3 scripts/ledger.py tag personal trip 2026-09    # entries and totals for one tag
python3 scripts/ledger.py networth                     # consolidated balance sheet, currencies/gold/funds/stocks at live prices
python3 scripts/ledger.py quote USD AU F161226         # live FX rate, gold per gram, fund NAV
python3 scripts/ledger.py dividend 2026-09             # monthly profit split for a shop run with partners
python3 scripts/ledger.py new-book shop --template business --link personal   # add a shop book
python3 scripts/ledger.py backup --daily               # zip the whole ledger with Git history
```

## Accounting principles

- **Separate entities**: personal, shop and shared books are kept apart; transfers between them are recorded on both sides, `reconcile` checks each pair sums to zero, and `networth` eliminates them when consolidating.
- **Two-level categories**: expenses are group + subcategory only (e.g. `Expenses:Food:Dining`); who and which trip go into tags (`#trip`, `#family`), and the narration names what was bought.
- **Consumer credit**: spending on a credit card or Huabei creates a liability; repayments reduce it and are not counted as spending again.
- **Refunds and advances**: refunds reduce the original expense; money lent or paid on someone's behalf is a receivable, not spending.
- **Valuation**: base currency CNY by default. When computing total assets, foreign currencies, crypto, gold and silver, funds and stocks are converted at the day's price fetched online, falling back to `price` entries in the ledger; pension and medical-insurance personal accounts cannot be withdrawn and are excluded from net worth.
- **Profit split**: for a shop run with partners, set the shares under `[dividend]` in `ledger.toml` and run `dividend` at the start of each month to get each partner's entitlement, amount already distributed and amount payable.
- **Shop books are for internal management**: if the shop is a registered business, tax filing still follows the applicable accounting standards (an accountant can do it); these journals serve as the source records. Personal-only users can ignore this.

## Reliability

1. **In every command**: `add` / `pair` / `amend` / `void` / `fmt` validate the whole book after writing and restore the files if anything fails.
2. **Before each commit**: the pre-commit hook runs validation, reconciliation and formatting checks, plus ruff and pytest when scripts change; the commit-msg hook checks the commit message format.

There is no cloud check after a push: enable the hooks once on every device and every clone (`git config core.hooksPath scripts/hooks`). `doctor` reports whether they are enabled, and `add` / `amend` / `void` remind you after a successful write.

Entry commands also reject future dates, guessed times, missing payees or narrations, and exact duplicates. All changes are tracked in Git and can be traced, compared and rolled back.

## Documentation

The detailed documentation is in Chinese.

| Document | Contents |
|---|---|
| [Quick start with Git](docs/QUICKSTART.md) | Private repository, dependencies, first session |
| [Without Git](docs/NO-GIT.md) | For chat assistants with a cloud computer and a cloud drive, such as Doubao |
| [User guide](docs/GUIDE.md) | What to say to the agent for recording, fixing, querying and reconciling |
| [Commands and configuration](docs/REFERENCE.md) | All commands, multiple books, profit split, `ledger.toml`, project layout |
| [FAQ](docs/FAQ.md) | Supported tools, Windows, cloud agents, upgrading the template |
| [Changelog](CHANGELOG.md) | What changed in each release |

## Acknowledgements

The accounting engine is [Beancount](https://github.com/beancount/beancount) by Martin Blais (GPL-2.0). It is installed separately with pip and is not distributed with this repository.
