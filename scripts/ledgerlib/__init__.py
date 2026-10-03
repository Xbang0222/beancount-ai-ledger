"""beancount 账套的记账工具库。

入口是 scripts/ledger.py，命令行用法见 cli.EPILOG 或 README。
账本清单、往来镜像、时区与本位币都在账套根目录的 ledger.toml 里声明，代码里不写死任何账本。
"""

__version__ = "0.2.0"
