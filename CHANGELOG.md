# 更新日志

本文件记录各版本中用户可感知的改动。格式参照 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.1.0/)，版本号遵循[语义化版本](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 升级说明

- 升级只替换 `scripts`、`tests`、`docs`、`AGENTS.md` 与依赖清单；`rules/`、`STATE.md`、`ledger.toml`、各账本目录属于用户数据，不被覆盖。步骤见 `docs/AI-TASKS.md`「升级工具」。
- 旧布局账本（规则位于根目录的 `CATEGORIES.md`、`CLASSIFY.md`）升级后照常可用：脚本与 `lookup` 同时支持两种布局，新版 `AGENTS.md` 第 6.1 节给出新旧文件的对应关系。迁移到 `rules/` 布局为可选操作，步骤见 `docs/AI-TASKS.md`「旧布局迁移」。
- 下列功能依赖用户数据中的配置，升级后须手动启用：写法检查须将模板 `ledger.toml` 的 `[naming]` 段复制到自己的配置，再执行 `check` 并按提示更正既有分录；新增的科目（见「新增」中的分类条目）须对照模板的 `personal/accounts.beancount` 自行开立，并在 `[naming.prefix.<账本>]` 配置摘要开头；新的分类、标签与估值规则须对照模板 `rules/` 下的对应文件自行合并。
- 写法规则本次有四项须手动合并到自己的 `ledger.toml`：`[naming]` 的 `two_way`；`markers` 中的「股东往来」；三段 `[[naming.forbidden]]`；两段 `[[naming.patterns]]`（自有账户之间的划转、负债的借入与偿还），其中 `when`、`with` 的科目须改为自己账本的结算账户与负债科目。合并后执行 `check`，被拦截的既有分录以 `amend` 更正；确属正常写法被误拦的，在对应 `pattern` 的排除字符中补充，不得删除整条规则。
- 新增的 `rules/import.md`、`rules/reconciliation.md` 须从模板复制；`rules/naming.md` 新增第 4.2、4.3、7 节，`rules/daily.md`、`rules/classification.md`、`rules/dictionary.md`、`rules/cases.md`、`rules/credit.md`、`rules/investment.md` 补充了对方与摘要的写法，须对照模板自行合并。
- 默认科目与大类简称的三项调整只影响新建的账本，已有账本的科目表与 `[naming].prefix` 不被改动，是否跟随由用户决定：`Expenses:Social` 的大类简称由「人情」改为「交际」；`Income:SideJob`「兼职收入-」更名为 `Income:Labor`「劳务收入-」；可退押金由 `Assets:Prepaid:Deposit` 改记 `Assets:Receivable:Other`，`Assets:Prepaid:Deposit` 只用于定金与预付的服务费。跟随时，更名科目须先在 `accounts.beancount` 开立新科目，再以 `amend` 逐笔更正既有分录。
- 已执行过 `git config core.hooksPath scripts/hooks` 的仓库，升级后提交信息检查自动生效。仓库中已有的 `.github/workflows/ci.yml` 不会被删除，可自行决定保留或删除。

### 新增

- 规则文档改为按主题拆分的 `rules/` 目录：`daily.md`（日常入账，每次入账前读取）、`naming.md`、`tags.md`、`classification.md`、`dictionary.md`、`cases.md`、`credit.md`、`investment.md`、`valuation.md`、`shared-books.md`。除 `daily.md` 外均按需读取，单次入账须读取的规则由约 45KB 降至约 9KB。原 `CATEGORIES.md` 的内容全部迁入，根目录不再保留该文件。
- `brief [账本]`：一条命令输出入账所需的现场信息，包括当前日期、星期与时间，`STATE.md` 中生效的临时状态，待补记的周期分录，各账本的可用科目及其中文说明与摘要开头（已停用的科目不列出），写法规则，最近的分录范例。`AGENTS.md` 的作业流程以该命令为第一步。
- `lookup <关键词...>`：按关键词检索规则文档与科目说明，输出命中的分类表行及表头、条款所在的文件与章节、科目表中的说明。
- `pair`：账本之间的往来在两本账同时登记。标准输入分 `[账本名]` 两段，各写一笔；同一把锁内写入两本账、各自校验整本账并判重，再核对每对往来镜像的差额未发生变化；任一步未通过，两本账均还原。
- 周期事项提醒：`ledger.toml` 新增 `[[recurring]]`，支持每日、每周某日、每月某日；到期未登记的日期由 `brief` 与 `doctor` 列出并给出分录。`confirm = false` 表示已约定到期直接补记。脚本只提醒，不自动入账。写法见 `docs/REFERENCE.md`「周期事项」。
- 写法检查：`ledger.toml` 新增 `[naming]`，定义摘要开头与科目的对应关系、括号内的固定标记、空泛对方名、笼统事项词、退款结尾、固定场景。`add`、`pair`、`amend` 拒绝不合规的分录并提示正确写法；`check` 检查全部账目，并报出未配置摘要开头的收支科目；记入 `Expenses:Other` 时必须写 `note:`。`rules [账本]` 输出对照表与找不到分类时的处理步骤。`new-book` 按模板自动追加新账本的摘要开头。写法见 `docs/REFERENCE.md`「写法规则」。
- 入账被拒时的报错改为中文并给出处理方法：科目未开立时列出同一上级下已开立的科目与拼写相近的科目；科目已停用时输出科目表中该科目的中文注释；借贷不平、币种不符、余额断言不符时写明差额。
- 提交信息检查：新增 `scripts/hooks/commit-msg` 钩子与 `ledger.py commit-msg` 命令。首行为 `类型: 摘要`，类型为英文，摘要为书面中文且不带括号；改动账本的提交只能使用 `feat`、`fix`、`style`，摘要以登记、补记、更正、作废、对账、重排、新开、新建、初始化之一开头，并写明所涉账本。`commit-msg --range A..B` 逐条检查范围内已有的提交，可用于自建 CI。规范见 `docs/COMMITS.md`。
- `add`、`amend`、`void` 成功后，本设备未启用提交前自动检查时输出一行提醒。
- `doctor` 新增三项检查：有余额且超过 `[ledger] reconcile_days` 天（新配置项，默认 35，0 为不提醒）未经 `balance` 断言核对的资产负债科目（从未核对的自第一笔发生额起算，账本之间的往来镜像由 `reconcile` 核对，不在此列），仅提醒，不影响退出码；用户仓库中残留的模板项目专用文件（`.github` 下的贡献指南、行为准则、安全策略、Issue 与 PR 模板、发版流程）；`ssh.github.com:443` 形式的远程地址。
- `quote <代码...>`：联网查询价格并折合本位币，支持外币与加密货币（`USD`、`USDT`、`BTC`）、每克黄金与白银（`AU`、`AG`）、场外基金净值（`F161226`）、A 股、港股、美股（`SH600519`、`HK00700`、`US.AAPL`）；`--date` 查询历史价格。
- `networth` 默认按联网取得的当日价格折算，无需手动传入 `--rate`；无法取得价格时给出提示并改用账内 `price`，`--offline` 只使用账内价格。
- 科目元数据 `estimate: "AU"`：只登记了金额的积存金按每笔发生当日的金价折算克数，`networth` 按当日金价估算现值。科目元数据 `networth: FALSE`：养老保险、医保个人账户单独列示，不计入净资产。个人账模板新增 `Assets:Invest:Gold`，两个社保账户默认标注 `networth: FALSE`。
- `dividend YYYY-MM`：合伙店铺按月利润分配。计算当月净利润，外币默认从 fawazahmed0/exchange-api 取得汇率折算，也可用 `--rate` 指定；按 `ledger.toml` 新增的 `[dividend]` 比例拆分。分红分录以 `period: "YYYY-MM"` 标明所属月份，据此归集已分配金额；`offset` 将对方欠款从差额中扣抵。月份结束后登记过该月分红的视为已结清，只列实发金额，`--recalc` 强制重算；月内预发不构成结清。写法见 `docs/REFERENCE.md`「利润分配」。
- `[dividend]` 的 `partners` 新增可选 `owner = true`，标注账本所有者本人。标注后，`networth` 在折合本位币的净资产之后单列其余各方在未结清月份中尚未分配的利润，并给出「扣后净资产」；预支超过应得时加回。
- `[ledger]` 新增可选 `fx_alias`，例如 `{ USDT = "USD" }`，取汇率时按别名币种折算。经营账模板新增 `Equity:Distributions`。
- 分类表补全：对照统计局居民消费支出八大类与常见记账 App 的默认分类，补全各小类的关键词；新增宠物 `Pet`、育儿 `Kids`、居住-装修维修 `Housing:Repair`、运动 `Fitness`、个护 `PersonalCare`、服务 `Service:Professional` 与 `Service:Life`、税费 `Tax`、交通-车辆 `Transport:Vehicle`；收入新增社保公积金个人账户入账 `Income:Benefit:Medical`、`Pension`、`HousingFund`，对应资产 `Assets:Benefit:*`。`rules/classification.md` 附常见记账 App 分类的对照表，`rules/dictionary.md` 提供按物品、按商家或平台、非消费业务三张速查表，`rules/cases.md` 提供典型业务的判例。
- 副业收支科目：有进货成本的个人经营（代购、代充会员、摆摊）收款记 `Income:SideBiz`，进货款记 `Expenses:SideBiz`；没有进货成本的兼职与劳务（软件外包、稿费、讲课费）记 `Income:Labor`。
- 新增文档：`docs/AI-SETUP.md`（第一次接手、账本存放、没有远程仓库时、首次使用、引导新手）、`docs/AI-TASKS.md`（更正与删除、余额核对、导入账单、行程与临时状态、修改规则、升级工具、新建账本、常用查询）、`docs/COMMITS.md`（提交信息规范）、`docs/DEVELOPMENT.md`（环境初始化、模块职责、开发约束）。上述内容原在 `AGENTS.md`。
- 账本存放不再绑定具体的 AI 与存储方式，按用户现有条件选择：有私有 Git 仓库（GitHub、Gitee 等）时每次推送；只有云盘时打包备份；两者均无时本地提交并提醒用户。见 `docs/AI-SETUP.md`「账本存放」。
- 写法检查新增 `two_way`（双向科目）：借贷两个方向均属正常发生额的科目，例如 `Income:Invest:PnL` 的收益与亏损，记在借方时不要求摘要以「退款」结尾。模板 `ledger.toml` 默认将 `Income:Invest:PnL` 列为双向科目；已有账本须将该行复制到自己的 `[naming]`。
- 写法检查新增 `[[naming.forbidden]]`：以正则表达式定义对方或摘要中不得出现的写法，命中即拒绝并给出改法。模板默认配置三条：摘要不得出现具体日期（「12月21日」「19号」「昨天」）、摘要不得出现具体时刻（「20:10」「8点」）、对方不得写营业执照名称或收单机构名称（「有限公司」「个体工商户」「经营部」）。所属期间与编号不在拦截之列，例如「居住-9月房租」「工资收入-9月工资」「交通-地铁1号线」。`rules` 与 `brief` 输出这些规则，`check` 按其扫描全部既有分录。
- `[[naming.patterns]]` 的 `payee` 改为可省略：只限定摘要开头、不限定对方。`payee` 与 `narration` 至少填写一项。
- 模板 `ledger.toml` 默认配置两个固定场景：自有账户之间的划转，摘要以「银行转账-」「银行取现」「银行存现」「现金兑换」开头；负债的借入与偿还，摘要以「偿还」「借款-」「其他应付款-」「信用卡取现」开头。
- 新增 `rules/import.md`（历史流水导入）：规则与来源无关，记账 App 的导出文件、支付宝与微信账单、银行流水、信用卡账单按同一套规则处理，各来源的差异只体现在 `rules/classification.md` 第 5.1 节的分类对照表与 `rules/import.md` 第 2 节的字段对应表。内容包括：导入的分录与日常入账适用同一套归类与写法；备注原文写入 `note:`，摘要改写且不带日期与时刻；未指定账户的收付记默认结算账户；平账记录的判定顺序；期初余额以当前实际余额倒推；导入报告的内容。
- 新增 `rules/reconciliation.md`（余额核对）：差额先查漏记，查不出的经用户确认后，实际多于账面记 `Income:Other`「其他收入-对账差额」，少于账面记 `Expenses:Finance:Fee`「财务费用-对账差额」；原因在查时暂记 `Equity:Adjustment`「余额调整-账实差异」，开账后首次核对前形成且无法查明的暂记余额结转期初权益；余额断言写在确认日的次日。
- `rules/naming.md` 新增三部分：第 4.2 节各科目事项的写法（正餐写餐次，饮品零食写品类，买菜写「买菜」，交通写出行方式或起讫地，按期收支写所属期间）；第 4.3 节不得写入摘要的内容及其去向；第 7 节非收支业务的固定写法，覆盖转账、取现存现、信贷还款、借入借出、垫付与收回、押金、定金、基金与黄金的买卖、期初更正、余额调整。`rules/daily.md`、`rules/credit.md`、`rules/investment.md`、`rules/dictionary.md`、`rules/cases.md` 的对应条款同步补充对方与摘要的写法。
- 新增测试 `tests/test_docs_examples.py`：`examples/demo`、`examples/cookbook.beancount` 以及 `AGENTS.md`、`docs/`、`rules/` 代码块中的分录须通过写法检查，模板根目录与演示账套的通用写法配置须一致。

### 变更

- `AGENTS.md` 重写为作业规程，只保留作业流程、强制约束、回报要求与文档索引，篇幅由 27KB 减至约 11KB。`doctor` 的引导提示改为指向 `docs/AI-SETUP.md` 的对应章节。
- 全部文档统一为规范文体：条款化表述、统一术语、章节编号、表格；出处与解释性旁白从规则正文移除。范围包括 `rules/`、`AGENTS.md`、`docs/` 下各文档、`README.md`、`.github/` 下的贡献指南与表单，以及 `ledger.toml`、科目表、建账模板中的注释。核算口径未变。
- `ledger.py --help` 的命令说明、`brief` 输出的标题与操作提示改用规范措辞；价格来源的标注由「现拉」改为「联网取价」。命令与参数未变。
- `add` 遇到往来镜像科目时拒绝入账，并给出 `pair` 的完整写法与另一本账应使用的科目；补平既有的往来差额时使用 `add --one-sided`。此前仅在入账后提示，须到 `check` 才能发现单边登记。
- 归类改由 AI 决定，不再向用户询问记入哪一类：分类固定为大类与小类两级，不确定时先检索规则文档并参照通行口径，必要时新开科目；仅当金额、日期、资金归属、是否属于借出或代垫等事实缺失时才向用户确认。
- 摘要须写明具体事项，例如「购物-蓝牙耳机」，不得使用「购物-日用品」等笼统表述；详细情况写入 `note:` 元数据。分类表与科目表注释中的「学习」统一为「教育」，摘要示例与 `[naming]` 的摘要开头一致。
- 标签规则改写：一个标签只表达一项含义，例如 `#japan #visa`，不写 `#japanvisa`；标签分地点、交易对象、事项三类；用户说明了时间线的，按时间线推断各笔的发生地点并标注。见 `rules/tags.md`。
- README 重写：补充文档约定、目录结构、记账流程、常用命令、核算要点与数据可靠性说明，中英文结构一致。
- 云盘与本地 `backups/` 均只保留最新一份备份，新备份上传成功后才删除旧备份；改动历史已包含在压缩包内。
- 找不到云盘工具时先查看 `~/vm/resource-loader/bin/`；仍然没有时将压缩包发送在对话中由用户自行保存，并明确说明未存入云盘。
- `doctor` 的「没有远程仓库时」「首次使用」两处提示，仅当账套的文档中确有对应章节时才指向该章节，否则只说明处理方法。
- `scripts/ledger.py` 开头的说明不再另列命令清单，以 `python3 scripts/ledger.py --help` 为准。
- 脚本内部整理，命令用法未变：`books.print_error_lines`、`fxrate.http_get` 改为公开名；`env.run_command` 统一 `doctor`、`backup`、`commitmsg` 中执行外部命令的函数；`journal.rstrip_blank` 取代 `fmt` 中的重复函数；`entry.inject_time` 复用 `with_time_line`。
- 历史流水导入时的平账记录不再原样记入 `Equity:Adjustment`，按下列顺序判定：同一时段内多个账户此增彼减的，改记账户之间的划转、申购或赎回；基金、理财等市值变动账户的差额记 `Income:Invest:PnL`「投资收益-基金估值调整」；查得出业务的按该业务补记；其余并入按当前实际余额倒推的期初余额。`docs/AI-TASKS.md`「导入账单」按此重写，并写明与日常余额核对的区别：导入前的差额无法归属到具体期间，并入期初；导入并登记余额断言之后的差额发生在本期，确认为其他收入或财务费用。
- 余额核对的口径统一：`docs/AI-TASKS.md`、`docs/GUIDE.md` 此前写「经确认后调平」，`rules/naming.md`、`rules/dictionary.md` 写按损益入账，二者不一致。现统一为 `rules/reconciliation.md` 的口径。
- 分类与科目口径的调整，均只影响新建的账本：`Expenses:Social` 的大类简称由「人情」改为「交际」；`Income:SideJob`「兼职收入-」更名为 `Income:Labor`「劳务收入-」；出售自用闲置物品由兼职收入改记 `Income:Other`；可退押金由 `Assets:Prepaid:Deposit` 改记 `Assets:Receivable:Other`，摘要「其他应收款-<事项>押金」，`Assets:Prepaid:Deposit` 只用于定金与预付的服务费；`Expenses:Other` 的范围写明包括丢失、被骗、坏账、赔偿，摘要「其他-<具体事项>」；`Expenses:Transport:Vehicle` 的范围加入购买电瓶车等代步车。
- 文档中的分录范例统一为规范写法：正餐写餐次（「餐饮-午餐」），不再使用「餐饮-牛肉面」等按菜品的写法。`examples/cookbook.beancount` 与 `examples/demo` 的分录全部按 `[naming]` 更正，`examples/demo/ledger.toml` 增加 `[naming]` 配置。

### 移除

- 移除 CI（`.github/workflows/ci.yml`）：推送后不再有云端检查，校验由两级承担，即命令写盘后的整本校验与提交前的钩子（`check`、`fmt --check`、提交信息，修改脚本时另执行 ruff 与 pytest）。每台设备、每个克隆均须启用一次钩子（`git config core.hooksPath scripts/hooks`），`doctor` 检查是否已启用。发版流程 `release.yml` 不受影响，其自身执行测试与校验。

### 修复

- 模板 `ledger.toml` 的 `markers` 缺少「股东往来」：`AGENTS.md` 与 `rules/daily.md` 给出的 `pair` 范例使用「（股东往来）」，按原配置入账会被写法检查拒绝。
- `examples/cookbook.beancount` 与 `examples/demo` 中的多笔分录不符合模板自身的写法规则，例如「工资-1月」「偿还花呗账单」「主营业务收入（支付宝）」；演示账套此前未配置 `[naming]`，`check` 未能发现。
- `fmt` 重排序时簿时持有互斥锁 `store.book_lock`：此前另一会话同时入账时，重排会以读到的旧内容覆盖刚写入的分录。`fmt --check` 只读，不持锁。
- `networth` 估值科目的 `estimate` 元数据按科目所在的账本读取：此前其他账本开立了同名科目并标注 `estimate` 时，本账本未标注的科目也会被按金价估值。
- 取汇率时，CDN 明确返回 404 即报告数据集中没有该代码，不再下载完整数据包确认；查询失败的结果在本次运行内缓存，不重复请求。
- `quote` 取基金最新净值的截止日期按 `ledger.toml` 配置时区的当日计算，不使用系统日期。
- 提交信息检查未通过时的提示改为指向 `docs/COMMITS.md`，此前指向 README 中并不存在的章节。

## [0.4.0] - 2026-10-04

在豆包里实测后调整：云电脑的个人目录换对话、重启都还在，账本不必每次从云盘取回。

### 新增

- `backup --daily`：今天已经备份过就跳过，用于每天存一份。
- `AGENTS.md` 新增「升级工具」：一句"帮我升级记账项目"，只换脚本和文档，账本数据不动。

### 变更

- `AGENTS.md`「没有远程仓库时」分成两种做法：目录能跨对话保留的（如豆包云电脑的个人目录），账本常驻固定目录，云盘每天备份一份，目录丢了自动从云盘恢复；留不住的，仍然每批打包存云盘。
- `backup` 的默认目录 `backups/` 只留最近 3 份。用 `-o` 指定的目录不清理。
- `docs/NO-GIT.md` 按新做法重写：更短的开场白、云盘授权说明、升级和从旧做法搬家的提示词。
- 存云盘一律用带日期的文件名，不覆盖同名文件。

### 修复

- 测试在提交钩子里运行时不再受 `GIT_DIR`、`GIT_INDEX_FILE` 影响。

## [0.3.0] - 2026-10-04

### 新增

- `backup` 把 `.git` 一起打包：账套是 Git 仓库时，压缩包带着完整的提交历史，解压出来能接着提交。有未提交的改动会提醒。
- `doctor` 列出每本账的最后一笔，开始记账前用来核对手上的是不是最新的账本。

### 变更

- `AGENTS.md`「不用 Git 时」改为「没有远程仓库时」：豆包这类云电脑里照常用本地 Git 提交（不需要账号，不联网），推送改为 `backup` 存云盘。开始只需解压加一条命令，每批改动一条命令提交并打包。
- 云盘里只留最近 3 份备份，更早的由 AI 自动删除。`docs/NO-GIT.md` 说明了压缩包大小和嫌慢时的做法。

## [0.2.1] - 2026-10-04

### 变更

- `bootstrap.py` 在官方源装不上依赖、又没指定镜像时，自动换清华镜像再试一次。
- `void` 的提示不再只说"原文在 Git 历史中"，不用 Git 时改查更早的备份。
- 发布流程增加代码规范检查。
- 豆包用户第一次使用不用再下载压缩包：`docs/NO-GIT.md` 的开场白改为让 AI 自己下载项目，并一条一条问用户建账需要的信息。
- `AGENTS.md` 新增「引导新手」：一次只问一件事、不说术语、建好后带用户记第一笔，再教他以后怎么开始、怎么改错、能问什么。

## [0.2.0] - 2026-10-04

### 新增

- `find` / `amend` / `void` 命令：按关键词找到分录的编号，再整笔更正或作废。改账和入账走同一套"写盘、校验整本账、失败还原"，不再需要手动编辑序时簿。
- `add` 的新守卫：拒绝内容相同的重复分录（`--allow-duplicate` 放行）、缺对方或摘要的分录、格式不对的 `time`，以及 `open` 这类科目表指令。
- 提交前自动检查 `scripts/hooks/pre-commit`：账本校验、往来对账、排版检查，改了脚本再跑 ruff 和测试。`doctor` 会提醒启用。
- `backup` 命令：把整个账套打成一个压缩包，输出各账本的交易笔数和最后一笔。账本有错误时不生成压缩包。
- 不用 Git 也能用：`AGENTS.md` 新增「不用 Git 时」一节，账本以压缩包形式存在用户的云盘里，适合豆包这类自带云电脑和云盘的 AI。给用户看的做法和开场白写在 `docs/NO-GIT.md`。

### 变更

- `add` / `amend` 按日期和时间把分录插到序时簿里对应的位置，补记较早的账不再打乱顺序。
- `fmt` 重排时，紧贴分录上方的注释跟着分录走。
- 写盘沿用文件原有的换行符。
- 开发依赖加入 ruff，配置在 `pyproject.toml`；CI 增加代码规范检查。
- 汇率改为现查现用，不再写进账本：算总资产前查当天汇率，用 `networth --rate` 传入；`CATEGORIES.md` 第 5 节给出了云端环境也能访问的取数命令。基金、股票净值仍然用 `price` 记账。
- 有多本账时，回答"我有多少钱"按合并口径列示，不列账本之间的往来。
- `doctor` 发现账套目录不是 Git 仓库时，同时给出建私有仓库和改用云盘两条路。
- README 只保留简介和文档入口，详细内容拆到 `docs/`：`QUICKSTART.md`（用 Git 开始）、`NO-GIT.md`（不用 Git）、`REFERENCE.md`（命令与配置）、`FAQ.md`（常见问题）。英文 README 不再重复命令和配置，改为指向这些文档。

## [0.1.0] - 2026-09-27

首个公开版本。

### 新增

- `scripts/ledger.py` 命令：`doctor`、`check`、`add`、`recent`、`summary`、`report`、`balances`、`tag`、`networth`、`reconcile`、`fmt`、`books`、`new-book`。
- `add` 的入账保护：一次只录一笔，自动注入录入时间，拒绝未来的日期和时间，校验失败整笔回滚；支持余额断言，支持用 `--file` 从文件读取分录。
- 多账本：在 `ledger.toml` 声明账本和往来镜像；`reconcile` 核对往来，`networth` 合并时抵销往来并折算外币。
- `new-book` 提供 personal、business、minimal 三种科目表模板；`--link` 生成往来科目，`--no-consolidate` 用于与他人共有的账本。
- `scripts/bootstrap.py` 把依赖装进仓库的 `.venv`；缺依赖时 `ledger.py` 自动改用 `.venv`。
- 给 AI 用的 `AGENTS.md`、`CLAUDE.md`、`GEMINI.md` 和 `.claude/settings.json`。
- 中英文 README、使用指南、分录范例和示例账本。
- CI：Ubuntu（Python 3.9、3.13）和 Windows（Python 3.12）；用模板建的账本仓库只跑账本校验。

[Unreleased]: https://github.com/Xbang0222/beancount-ai-ledger/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/Xbang0222/beancount-ai-ledger/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/Xbang0222/beancount-ai-ledger/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/Xbang0222/beancount-ai-ledger/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/Xbang0222/beancount-ai-ledger/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Xbang0222/beancount-ai-ledger/releases/tag/v0.1.0
