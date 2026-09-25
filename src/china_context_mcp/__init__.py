"""china-context-mcp：把中文世界的数据源桥接成 AI 工具。

首版模块（均零凭证、公开 API）：
  - 今日诗词 jinrishici：随机一句中国古典诗词（作者/出处/分类）
  - 中国节假日 timor.tech：某日期是否为法定节假日、调休工作日、倍率

设计原则（见 06-测试成本趋零-v0.1.md）：
  - 免交付：第 100 个使用者与第 1 个力气一样
  - 零凭证：不依赖任何商户 key / 登录态
  - 可验证：开源放出后看 star / issue / 外部使用
"""
from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    # ★ 版本单一来源：不再在仓库里手写第二份版本号（此前 __init__ 写 0.1.0、
    #   pyproject 写 0.1.1、server.json 写 0.1.1，三处漂移）。
    __version__ = _pkg_version("china-context-mcp")
except PackageNotFoundError:
    __version__ = "0.1.3"
