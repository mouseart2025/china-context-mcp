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
| `holiday_summary(year?)` | timor.tech | **年度聚合摘要**：连续假期区间与天数、法定 3 倍工资天数**及具体是哪几天**、调休补班清单、全年总休假天数。省略 year 用当年 |
| `history_today(date?)` | 60s-api.viki.moe | 历史上的今天：某月某日的历史事件列表（标题/年份/简述）；省略 date 用今天 |
| `idcard_check(id)` | **本地算法（不联网）** | 中国身份证号校验 + 解析：按 ISO 7064 MOD 11-2 验证校验位，输出出生日期、性别、省级行政区，回显做掩码 |

### `holiday_summary` 为什么是差异化的一层

timor 的两个接口都只给**扁平数据**：`holiday_info` 一次一天，`holiday/year` 一次给全年条目。但它们**给不出**下面这些结论——而这些恰恰是最容易算错的：

```
2026 年中国节假日与调休摘要

【假期区间】共 7 个，合计 33 天（不含补班）
  · 元旦  01-01 ~ 01-03   3天（3倍工资 1 天）
      3倍 1 天：01-01
      2倍 2 天：01-02、01-03
  · 春节  02-15 ~ 02-23   9天（3倍工资 4 天）
      3倍 4 天：02-16、02-17 初一、02-18 初二、02-19 初三
      2倍 5 天：02-15、02-20 初四、02-21 初五、02-22 初六、02-23 初七
  · 清明节  04-04 ~ 04-06   3天（3倍工资 1 天）
      3倍 1 天：04-05
      2倍 2 天：04-04、04-06
  · 劳动节  05-01 ~ 05-05   5天（3倍工资 2 天）
      3倍 2 天：05-01、05-02
      2倍 3 天：05-03、05-04、05-05
  · 端午节  06-19 ~ 06-21   3天（3倍工资 1 天）
      3倍 1 天：06-19
      2倍 2 天：06-20、06-21
  · 中秋节  09-25 ~ 09-27   3天（3倍工资 1 天）
      3倍 1 天：09-25
      2倍 2 天：09-26、09-27
  · 国庆节  10-01 ~ 10-07   7天（3倍工资 3 天）
      3倍 3 天：10-01、10-02、10-03
      2倍 4 天：10-04、10-05、10-06、10-07

【调休补班】共 6 天
  · 01-04 元旦后补班（调休上班，非假日）
  · 02-14 春节前补班（调休上班，非假日）
  · 02-28 春节后补班（调休上班，非假日）
  · 05-09 劳动节后补班（调休上班，非假日）
  · 09-20 中秋节前补班（调休上班，非假日）
  · 10-10 国庆节后补班（调休上班，非假日）

【工资倍率】3倍 13 天 / 2倍 20 天
```

**逐日明细为什么一眼就要看全**：3 倍工资在多数小长假里**只有 1 天**（2026 年元旦 01-01、清明 04-05、端午 06-19、中秋 09-25 才是法定节假当日，其余是周末或调休）。任何「不足 2 天就省略」的省流写法，都会让区间标题里的「（3倍工资 1 天）」变成查不到对应日期的空话。**明细组是区间的等价划分，两者必须逐日对齐**——回归测试用结构断言锁死了这一点。

另外，「2026 年清明节的 3 倍是哪天」这个问题有个易错点：国务院通知写的是「4 月 4 日至 6 日放假」，但**清明节气当天是 4 月 5 日**（2026-04-05 02:39 交节），所以 3 倍工资落在 04-05，不是区间首日 04-04。只看「起止日期」会答错。

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

## 发行面（收录 ≠ 能用，两件事都要看）

**一、被收录并不等于别人能连上。** 2026-09-25 抽样了 Registry 上 40 个带远程端点的服务：
可连且能出工具 **7 个（27%）**，19 个被站点主人拒绝（Cloudflare 1010），14 个因与本网络出口同形错误而无法判定。
Registry 的 `remotes[].url` 是提交者自己填的，没有任何存活校验。收录只是把地址写进一份名单。

**二、目录面：逐条实测（2026-09-25 下午，带阳性/阴性对照）。**

| 站点 | 实测结果 | 判定依据 |
|---|---|---|
| **Glama** | **已收录**：`glama.ai/mcp/servers/mouseart2025/china-context-mcp`，可见 4 个工具（`history_today` / `holiday_info` / `holiday_summary` / `random_poem`），并带 Glama 自评 **A** 的 score badge | 直接 GET 详情页；对照一个假 slug 返回 404 |
| Smithery | 命中仅在 `{"q":"?q=china-context-mcp"}` 里 | 页面**查询串自回显** |
| PulseMCP | 命中仅在 `<input value="…">` 里 | **搜索框自回显** |
| mcp.so | **未收录**；加急发布标 **$39 one-time**，免费走人工 review | `mcp.so/submit` 页原文；未登录态下表单 POST 只回到同一 SPA 页，**拿不到任何提交回执** |
| LobeHub | **未收录**；条目页对已收录项返回 200、对未收录项返回 500 | 阳性对照 `upstash-context7` = 200；org 下只有 `mcp-hello-world`，无公开列表仓库，找不到自提交入口 |

> 这里推翻了先前「Glama / LobeHub 均为 SPA，HTML 里判不出」的说法：
> **Glama 用双段 slug `owner/repo`**（不是单段 `china-context-mcp`），所以先前那轮扫到了一个 SPA 外壳页；
> LobeHub 的条目页是服务端渲染的，200/500 本身就是可用的收录判别器。

> **一个意外收获**：我们从未向 Glama 提交过。它是在官方 Registry 发布后
> 由 Glama 自己的爬虫抓过去的 —— 说明 **Registry 的链接会外溢到第三方目录**，提交 Registry 是有复利的动作。

**三、已做、仍在自动生效的发行动作**（无需人工，爬虫会自己抓）：
- 仓库 topics 已设为 `mcp-server` / `model-context-protocol` / `china` / `holiday` / `idcard` / `python`
- 仓库根目录已放 `smithery.yaml` 与 `.mcp.json` —— Smithery 的 scanner 两者都要有，**只有 `smithery.yaml` 会校验失败**
- 官方 Registry 已发布，`status=active`；`glama.json` 已加在根目录，格式经 Glama 自家
  `https://glama.ai/mcp/schemas/server.json` 校验通过（认领凭证，见下）

**四、已自动提交的收录申请**（2026-09-25）：

| 目标 | 形态 | 状态 |
|---|---|---|
| [punkpeye/awesome-mcp-servers](https://github.com/punkpeye/awesome-mcp-servers)（95.5k★） | PR [#15083](https://github.com/punkpeye/awesome-mcp-servers/pull/15083)，插入 Data Platforms 段字母序位 | 已开，标题带 `🤖🤖🤖` 走 CONTRIBUTING 里的 **agent 快通道** |
| [TensorBlock/awesome-mcp-servers](https://github.com/TensorBlock/awesome-mcp-servers)（864★，当日有更新） | issue [#2669](https://github.com/TensorBlock/awesome-mcp-servers/issues/2669)，走其 `add-mcp-server` 表单，目标分类 Data Analysis & Business Intelligence | 已开，等待其机器人转 PR |
| Glama 认领 | 仓库根 `glama.json` → `{"maintainers":["mouseart2025"]}` | 已就位，下次同步生效 |

> 前一条「仍需人工的：Glama 认领、mcp.so / LobeHub 表单提交」**作废**。
> Glama 那条其实只要一个 JSON 文件；mcp.so 的免费路径要先登录；LobeHub 压根没有自提交入口。

**五、仍未打通的**：mcp.so（付费或登录态）、LobeHub（无入口，只能等其运营收录或由人去提 PR）。
这两家规则不同、没有统一入口，且都不影响可运行性 —— 收录只影响被发现的概率。

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
