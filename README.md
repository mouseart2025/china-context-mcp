# china-context-mcp

把**中文世界的数据源**桥接成 AI 工具。零凭证、免交付、可验证。

🔎 已收录进官方 MCP Registry：`io.github.mouseart2025/china-context-mcp` —— [查看详情](https://registry.modelcontextprotocol.io/v0.1/servers/io.github.mouseart2025/china-context-mcp/versions/latest)

## 为什么做这个

给 AI 提供工具/服务/资源，是未来需求的重要方向。但调研发现一个结构性缺口：

- 国际服务（GitHub / Slack / Notion…）的 MCP server 覆盖中位数约 **1554** 个仓库；
- 中国服务（微信 / 支付宝 / 飞书 / 抖音…）的 MCP 覆盖中位数仅 **88** 个——差 **17.7×**。
  （数据：GitHub Search `「<服务> mcp」 in:name,description`，2026-09-25）

缺口只在「广义中国服务→AI」这一层成立。本仓库是这条「桥接层」方向的**最小可验证载体**：
先把**零凭证、公开 API、对中文 AI 真有用、且没被官方垄断**的数据源接进来。

> ⚠️ 支付宝「支付 MCP」已被官方于 2025-04-15 发布，故本项目**不重复造支付类 MCP**，只接官方未覆盖的真空数据源。

## 当前模块（均零凭证）

| 工具 | 数据源 | 用途 |
|---|---|---|
| `random_poem` | jinrishici.com | 随机一句中国古典诗词（作者/出处/分类），用于中文创作、文化问答、国学陪练 |
| `holiday_info(date)` | timor.tech | 查询中国某日期是否为法定节假日、调休补班工作日、工资倍率 |
| `holiday_summary(year?)` | timor.tech | **年度聚合摘要**：连续假期区间与天数、法定 3 倍工资天数、调休补班清单、全年总休假天数。省略 year 用当年 |
| `history_today(date?)` | 60s-api.viki.moe | 历史上的今天：某月某日的历史事件列表（标题/年份/简述）；省略 date 用今天 |
| `idcard_check(id)` | **本地算法（不联网）** | 中国身份证号校验 + 解析：按 ISO 7064 MOD 11-2 验证校验位，输出出生日期、性别、省级行政区，回显做掩码 |

### `holiday_summary` 为什么是差异化的一层

timor 的两个接口都只给**扁平数据**：`holiday_info` 一次一天，`holiday/year` 一次给全年条目。但它们**给不出**下面这些结论——而这些恰恰是最容易算错的：

```
2026 年中国节假日与调休摘要

【假期区间】共 7 个，合计 33 天（不含补班）
  · 元旦  01-01 ~ 01-03   3天（3倍工资 1 天）
  · 春节  02-15 ~ 02-23   9天（3倍工资 4 天）
  · 清明节  04-04 ~ 04-06   3天（3倍工资 1 天）
  · 劳动节  05-01 ~ 05-05   5天（3倍工资 2 天）
  · 端午节  06-19 ~ 06-21   3天（3倍工资 1 天）
  · 中秋节  09-25 ~ 09-27   3天（3倍工资 1 天）
  · 国庆节  10-01 ~ 10-07   7天（3倍工资 3 天）

【调休补班】共 6 天
  · 01-04 元旦后补班（调休上班，非假日）
  · 02-14 春节前补班（调休上班，非假日）
  · 02-28 春节后补班（调休上班，非假日）
  · 05-09 劳动节后补班（调休上班，非假日）
  · 09-20 中秋节前补班（调休上班，非假日）
  · 10-10 国庆节后补班（调休上班，非假日）

【工资倍率】3倍 13 天 / 2倍 20 天
```

**一处必须记住的坑**：合并假期区间要按**日期连续性**，不能按名称。中国法定假常把「春节」拆成 除夕/初一/初二…（且假日条目的 `target` 字段恒为 `-`，无法用于分组），按同名合并会把春节拆成 9 个单日区间，与「春节放 9 天」的用户心智严重不符。

### 外部交叉验证（2026-09-25）

年度聚合的正确性不靠自测自说，已逐项对过公开口径：

| 口径 | 本项目输出 | 第三方来源 |
|---|---|---|
| 2026 全年放假天数合计 | **33 天** | 国务院办公厅《关于 2026 年部分节假日安排的通知》 |
| 其中 3 倍工资天数（法定节假日） | **13 天** | 济南市人民政府12345问答、腾讯新闻（引劳动法第 44 条）、工人日报 |
| 其中 2 倍工资天数（休息日） | **20 天** | 同上（= 33 − 13，官方口径一致） |
| 调休补班（须上班）日 | **6 天**：1/4、2/14、2/28、5/9、9/20、10/10 | China Briefing《China Public Holiday Schedule 2026》同表 |

这四组数字每年都被地方政府与媒体重算发布一遍，说明它同时具备两个属性：
**唯一正确答案的确定性问题** ＋ **每年重做一次的手工劳动**。
AI 直接给出确定答案，正落在工具的价值区间——这是本项目「编排层而非转述层」最实在的一处。

### `idcard_check` 为什么值得单独一提

这是本项目**唯一不依赖第三方 API** 的模块——纯本地算法，永远可用，不会被上游关停或 Cloudflare 拦截。

价值不在"算法稀缺"（Python 有现成库），而在于 **AI 自己做 17 位加权求和 + 模 11 查表极容易算错**：加权因子表错位、索引偏移、X 大小写处理，任何一个小错都会导致校验结论颠倒。把这件事从"AI 现场算"改成"AI 调用一次拿到确定答案"，价值是实打实的。

```
[idcard] 11010519491231002X → 有效
  校验位：X 正确（ISO 7064 MOD 11-2）
  出生日期：1949-12-31
  性别：女（顺序码 2 为偶）
  省级行政区：北京市（11）
  回显掩码：110105********X
```

**隐私边界**：只解析国标公开字段，不触姓名、住址等隐私项；回显中间掩码，避免明文回传。

## 已收录进官方 MCP Registry

- 名称：`io.github.mouseart2025/china-context-mcp`
- 状态：`active` / `isLatest=true`（2026-09-25 上线）
- 声明文件：仓库根目录 `server.json`；改动后执行 `mcp-publisher publish` 重新发布
- 注意：`description` 有 **100 字符硬上限**，超了会返回 422

### 和 Registry 上其他「中国服务」的关系

同一批检索（Registry `search=china`，2026-09-25，命中 38 条）里已经有一批人真在做中国侧 MCP。
把位置摆清楚，比假装没有对手有用：

| 服务 | 定位 | 与本项目的关系 |
|---|---|---|
| `com.ainetcafe/netcafe-china` | 远程 HTTP：中国大陆可达性、调休 holidays、身份证/手机号校验 | **功能有重叠**。但它是把号码 POST 到 `ainetcafe.com` 的远端服务；本项目的 `idcard_check` 全程在本地进程内算完，号码不出机器。校验一个身份证还要过一遍别人的服务器，这层差别是隐私级别的 |
| `io.github.pipeworx-io/china-*` | 中国金融数据家族（LPR / A股 / 海关 / 外汇 / 空气质量…），均零凭证 | 走远程 gateway；本项目走本地 stdio，数据面是「节日 / 史 / 诗词 / 证件」这类生活与文化语境，不抢同一批用户 |
| `io.github.bg7iuy/china-phone` | 手机号归属（工信部号段数据） | 不同号码体系，无冲突 |

> ❗**修正一条此前的判断**：本项目早期做过一轮「天气 / 空气质量 MCP 真空」扫描，GitHub Search 结论是 0 个仓库。
> 但 Registry 里其实已有 `cn.pianam.mcp/weather-mcp-china` 与 `io.github.pipeworx-io/china-air-quality`——
> **只扫 GitHub Search 会漏掉已落地的实现，真空判据必须同时看 Registry。**

## 安装

未发布 PyPI，从 GitHub 装：

```bash
git clone https://github.com/mouseart2025/china-context-mcp.git
cd china-context-mcp
pip install -e .
```

若用 `uv`，一行即可（推荐，自动解依赖）：

```bash
uvx --from git+https://github.com/mouseart2025/china-context-mcp china-context-mcp
```

依赖：`mcp`、`fastmcp`（Python ≥ 3.10）。

## 接入 AI 客户端（stdio）

在 Claude Desktop / Cursor / 任意支持 MCP 的客户端配置：

```json
{
  "mcpServers": {
    "china-context": {
      "command": "china-context-mcp"
    }
  }
}
```

或指向模块：

```json
{
  "mcpServers": {
    "china-context": {
      "command": "python",
      "args": ["-m", "china_context_mcp"]
    }
  }
}
```

## 本地验证

```bash
python -m china_context_mcp   # 启动 stdio 服务，由 MCP 客户端连接
```

## 路线图（真空待接数据源，按稀缺度）

- [x] 历史上的今天（零凭证，已接 60s-api.viki.moe）
- [ ] 空气质量 / 天气（中国，公开源多需 key，待找零凭证源）
- [ ] 成语词典（零凭证）⏸ **暂缓**：已实测 muxiaoguo/oick/oioweb/aa1/codelife/xxapi/qqsuu 等候选，**均无可达的零凭证源**（404 / 隧道拦截 / 空端点），不建立在未验证源上
- [ ] 中国大学 / 专业库（零凭证）

## 许可

MIT
