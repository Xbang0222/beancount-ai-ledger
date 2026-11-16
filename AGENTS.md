# 记账作业规程

本仓库是 [Beancount](https://github.com/beancount/beancount) 纯文本复式账本，不是普通代码仓库。任何改动都直接作用于用户的真实账目。本规程适用于所有 AI 工具，各条均为强制要求。

Windows 环境将命令中的 `python3` 替换为 `python` 或 `py`。

## 1 作业流程

### 1.1 准备

```bash
git pull --ff-only                    # 仅在配置了远程仓库时执行
python3 scripts/ledger.py brief       # 输出入账所需的现场信息
```

- `brief` 输出：当前日期、星期与时间；`STATE.md` 中生效的临时状态；待补记的周期分录；各账本的可用科目；对方与摘要的写法；最近的分录范例。只能使用输出中列出的科目。
- 「该补的周期分录」非空时，先按其提示处理（部分须先向用户确认，部分直接补记），再处理用户当次的请求。
- 「当前临时状态」中生效的默认标签、临时默认结算账户，适用于当次分录。
- 通读 `rules/daily.md`。其余规则文件按第 6 节索引按需读取，不必通读。
- 科目归类或业务处理不确定时，执行 `python3 scripts/ledger.py lookup <关键词>`，按输出的科目和文件处理。
- 命令退出码为 3 表示缺少依赖：执行 `python3 scripts/bootstrap.py` 后重试。不得使用 `--break-system-packages` 向系统 Python 安装依赖。
- 首次接手本仓库，或 `brief` 报告账本有错时：执行 `python3 scripts/ledger.py doctor`，按 `docs/AI-SETUP.md`「第一次接手」处理其列出的问题。
- 没有远程仓库时按第 3 节执行。

`ledger.py` 的退出码：0 成功；1 校验未通过或输入有误；2 命令参数或 `ledger.toml` 有误；3 缺少依赖或 Python 版本过低。

### 1.2 入账

只涉及一本账的分录使用 `add`，一次一笔，分录由标准输入传入：

```bash
python3 scripts/ledger.py add personal <<'EOF'
2026-09-26 * "面馆" "餐饮-午餐"
  Expenses:Food:Dining  18.00 CNY
  Assets:Wechat
EOF
```

- `personal` 为 `ledger.toml` 中的账本名，`brief` 会列出全部账本。标签写在首行末尾，例如 `"餐饮-午餐" #trip #chengdu`。
- 不支持 heredoc 的终端（如 Windows PowerShell）：将分录写入 UTF-8 编码的 `entry.tmp`（已被 `.gitignore` 忽略），再执行 `python scripts/ledger.py add personal --file entry.tmp`。不得在 PowerShell 中以管道传入分录，中文会损坏。
- `add` 注入 `time`、写入 `<账本>/journal/YYYY-MM.beancount`、追加 include 并校验整本账；未通过即整笔还原。

账本之间的往来（以个人账户为店铺付款、店铺款项进入个人账户）使用 `pair`，两本账同时登记，每段对应一本账：

```bash
python3 scripts/ledger.py pair <<'EOF'
[personal]
2026-09-26 * "商店" "代垫商店采购款-某供应商（股东往来）"
  Assets:Receivable:Shop  200.00 CNY
  Assets:Wechat
[shop]
2026-09-26 * "某供应商" "主营业务成本-采购"
  Expenses:COGS  200.00 CNY
  Liabilities:OwnerLoan
EOF
```

更正与作废：

```bash
python3 scripts/ledger.py find personal <关键词...>      # 查找分录，行首为 [编号]
python3 scripts/ledger.py amend personal <编号>          # 更正：以标准输入的新分录整笔替换
python3 scripts/ledger.py void personal <编号>           # 作废：删除该笔，原文保留在 Git 历史
```

更多范例见 `rules/daily.md` 第 10 节与 `examples/cookbook.beancount`；更正与作废的完整流程见 `docs/AI-TASKS.md`「更正与删除」。

### 1.3 校验与提交

```bash
python3 scripts/ledger.py check          # 全部账本校验，有往来镜像时一并对账
python3 scripts/ledger.py fmt --check    # 序时簿排版；未通过时执行 ledger.py fmt
git status                               # 核对变更清单
git add -A && git commit -m '<类型: 摘要>'
```

- 每次改动后立即提交。配置了远程仓库的立即推送，账本以远程为准；没有远程仓库的按第 3 节备份。
- 一项业务一个提交，往来的两边属于同一项业务。
- 提交信息首行为 `类型: 摘要`，规范见 `docs/COMMITS.md`。涉及账本的提交只能使用 `feat` / `fix` / `style`，摘要以登记、补记、更正、作废、对账、重排之一开头并写明所涉账本，首行不得使用括号。例如：
  - `feat: 登记个人账10月28日午餐支出18.00元，微信付款`
  - `feat: 登记个人账与商店账10月28日代垫进货款200.00元，微信付款`
- 启用了提交钩子的仓库在提交时自动执行上述校验与提交信息检查。推送后没有云端检查，钩子是唯一的关口；入账命令提示钩子未启用时，先执行 `git config core.hooksPath scripts/hooks` 再提交。
- 修改 `scripts/` 或 `tests/` 时按 `docs/DEVELOPMENT.md` 执行。

## 2 强制约束

1. **不得手工编辑序时簿**（`<账本>/journal/*.beancount`）。入账使用 `add` / `pair`，更正使用 `amend` / `void`；这些命令写盘后校验整本账，未通过即还原。
2. **命令拒绝时按提示修改后重新提交，不得绕过。** 报错为中文，说明问题所在以及应使用的科目或写法。
3. **一次只录入一笔。** 多笔分多次录入，每笔入账后先完成校验与提交，再录入下一笔；`pair` 为两本账各一笔。
4. **对方与摘要必填并符合规范。** 规则由 `ledger.toml` 的 `[naming]` 校验，对照表见 `brief` 输出，补充规定见 `rules/naming.md`。摘要不写交易日期与时刻，细节写入 `note:`；批量导入的分录同样适用。
5. **不得估算时间。** 用户未给出具体时间时不写 `time` 行，由脚本注入录入时刻；无法判断上午或下午时先向用户确认。日期晚于当日、当日 `time` 晚于当前时间均会被拒绝。
6. **账本之间的往来必须在两本账同时登记**，使用 `pair`；`add` 遇到往来科目会拒绝。更正或作废往来分录时同步处理另一本账，并执行 `python3 scripts/ledger.py reconcile` 确认每对镜像科目合计为 0。`add --one-sided` 仅用于补平既有的往来差额。
7. **重复入账会被拒绝。** 日期、对方、摘要、各科目金额均相同的分录不得再次入账；确属两笔独立交易时使用 `--allow-duplicate`。不确定上一笔是否成功时，先执行 `ledger.py recent <账本>`。
8. **序时簿只接受交易和余额断言。** `open` 等科目表指令写入 `<账本>/accounts.beancount`，该文件可直接编辑。
9. **不得使用未开立的科目。** 先从 `brief` 列出的科目中选择；确需新科目时，按原有格式在 `accounts.beancount` 中 `open` 并附中文注释，与该笔分录一并提交，并在回报中告知用户。
10. **归类由 AI 决定，不得询问用户。** 按 `rules/classification.md` 归类，必要时新开科目并更新分类表；无法判断时暂记 `Expenses:Other` 并在回报中说明。仅当事实缺失时向用户确认：金额、日期、所属账本、业务性质（消费、借出或代垫）。业务性质不明时先确认，不得直接费用化。

## 3 没有远程仓库时

适用于用户不使用 GitHub、没有远程仓库的环境，例如豆包等云电脑。Git 照常在本地使用，无需账号与联网。相关操作全部由 AI 完成，不得要求用户学习或操作 Git。

账本常驻于个人目录（如 `~/AI记账/ledger`）时：

```bash
python3 scripts/bootstrap.py && python3 scripts/ledger.py doctor    # 每次开始：自检，并向用户报告 doctor 列出的最后一笔
```

```bash
git add -A && git commit -q -m "feat: 登记个人账10月28日午餐支出18.00元、打车支出32.00元" && python3 scripts/ledger.py backup --daily    # 每批改动后：提交并备份
```

- `backup --daily` 在当日首次执行时生成 `backups/ledger-backup-*.zip`。生成后须上传到用户云盘的备份文件夹并告知用户；上传未成功时须明确说明。
- 下列情形先读 `docs/AI-SETUP.md`「没有远程仓库时」再操作：找不到账本目录（不得自行新建）、每次对话均为全新环境、首次建账、云盘备份的保留与清理、找不到云盘工具、授权过期。

## 4 回报用户

- 使用用户所用的语言回复。
- 入账后以一句话回报：一级大类、金额、结算账户、标签。对用户可使用口语；写入账本的对方与摘要使用书面会计语言。
- 用户询问资产或余额，且多本账均归其一人所有时，采用合并口径（`networth`）：只列示实际资金和对外的债权债务；账本之间的往来科目不列示。口径见 `rules/valuation.md` 第 5 节。

## 5 隐私

账本属于用户的隐私数据。未经用户明确要求，不得将账本内容、余额、交易明细发送给任何外部服务，包括搜索引擎、粘贴站与第三方 API。

## 6 文档索引

| 情形 | 读取 |
|---|---|
| 每次入账 | `rules/daily.md`（必读） |
| 对方与摘要的写法；被写法检查拒绝；转账、还款、借贷、投资等非收支业务的固定写法 | `rules/naming.md` |
| 行程、交易对象、专项事务的标签 | `rules/tags.md` |
| 科目归类 | `ledger.py lookup <关键词>`；`rules/classification.md`（分类表与归类步骤）、`rules/dictionary.md`（速查词典）、`rules/cases.md`（判例） |
| 分期、贷款 | `rules/credit.md` |
| 基金、股票、黄金、白银 | `rules/investment.md` |
| 外币与各类资产折算、价格查询、净资产口径、报告资产 | `rules/valuation.md` |
| 与他人共有的账本 | `rules/shared-books.md` |
| 首次接手、`doctor` 报告问题、远程仓库为公开 | `docs/AI-SETUP.md`「第一次接手」 |
| 账本存放位置与同步方式、没有远程仓库 | `docs/AI-SETUP.md`「账本存放」「没有远程仓库时」 |
| 账本未初始化、用户要求建账、用户不熟悉记账 | `docs/AI-SETUP.md`「首次使用」「引导新手」 |
| 更正与作废 | `docs/AI-TASKS.md`「更正与删除」 |
| 用户报告账户余额、余额与账面不符 | `docs/AI-TASKS.md`「余额核对」，`rules/reconciliation.md` |
| 导入历史流水：记账 App 导出文件、支付宝与微信账单、银行流水 | `docs/AI-TASKS.md`「导入账单」，`rules/import.md` |
| 行程、临时默认账户等临时状态 | `docs/AI-TASKS.md`「行程与临时状态」，登记于 `STATE.md` |
| 用户要求修改分类或规则 | `docs/AI-TASKS.md`「修改规则」 |
| 升级本项目的脚本 | `docs/AI-TASKS.md`「升级工具」 |
| 新建账本 | `docs/AI-TASKS.md`「新建账本」 |
| 用户询问支出或资产 | `docs/AI-TASKS.md`「常用查询」 |
| 周期事项提醒的配置 | `docs/REFERENCE.md`「周期事项」 |
| 提交信息 | `docs/COMMITS.md` |
| 修改 `scripts/` 或 `tests/` | `docs/DEVELOPMENT.md` |
| 命令与参数 | `python3 scripts/ledger.py --help`，`docs/REFERENCE.md` |

文档分工：长期规则只写入 `rules/`，一个主题一个文件，用户自定的少见口径在对应主题文件中追加或新建文件并在上表登记；临时上下文只写入 `STATE.md`；机器可校验的写法规则只在 `ledger.toml` 的 `[naming]` 定义。规则冲突时以 `rules/daily.md` 为准，写法以 `[naming]` 为准。

### 6.1 旧布局账本

没有 `rules/` 目录、规则文件位于仓库根目录的账本属于旧布局，规则继续有效，按下表对应；`ledger.py lookup` 同样检索这些文件。

| 新布局 | 旧布局 |
|---|---|
| `rules/daily.md`、`rules/naming.md`、`rules/tags.md`、`rules/classification.md` 的分类表 | `CATEGORIES.md` |
| `rules/dictionary.md`、`rules/cases.md`、`rules/classification.md` 的分类依据 | `CLASSIFY.md` |
| `rules/credit.md`、`rules/investment.md`、`rules/valuation.md`、`rules/shared-books.md` | `CATEGORIES.md` 第 4、5 节 |
| `rules/import.md`、`rules/reconciliation.md` | `docs/AI-TASKS.md`「导入账单」「余额核对」 |

旧布局迁移为新布局的步骤见 `docs/AI-TASKS.md`「旧布局迁移」，须经用户同意后执行。
