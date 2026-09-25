# china-context-mcp

把**中文世界的数据源**桥接成 AI 工具。零凭证、免交付、可验证。

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
| `history_today(date?)` | 60s-api.viki.moe | 历史上的今天：某月某日的历史事件列表（标题/年份/简述）；省略 date 用今天 |

## 安装

```bash
cd prod/china-mcp
pip install -e .
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
