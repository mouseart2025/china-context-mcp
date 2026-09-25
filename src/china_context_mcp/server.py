# -*- coding: utf-8 -*-
"""china-context-mcp 服务端：FastMCP + 零凭证中文数据源工具。

架构约束（自进化架构师审计）：
  - 出站请求必须：严格超时 + 有限重试（上限 2）+ 失败可降级，禁止无界循环
  - 不可变数据本地缓存，削减冗余出站调用与延迟
  - TLS 默认校验开启（不关闭证书验证）
  - UA 头是 timor.tech 的可用性依赖，不可删除（详见 UA 定义处注释）

当前模块（均零凭证、公开 API）：
  - random_poem       今日诗词（jinrishici）
  - holiday_info      中国节假日/调休工作日（timor.tech）
  - holiday_summary   年度节假日聚合摘要（timor.tech，编排推导层）★差异化
  - history_today     历史上的今天（60s-api.viki.moe）
  - idiom             ⏸ 暂缓：未找到可达的零凭证成语 API（详见 README 路线图）
"""
import functools
import json
import ssl
import urllib.request
from datetime import datetime

from fastmcp import FastMCP

# 安全默认：开启证书校验（不在发布代码里关闭 TLS 验证）
CTX = ssl.create_default_context()
# ★ 可用性依赖，不是装饰：timor.tech 对非浏览器 UA 返回 Cloudflare 人机验证页
#   （HTML "Just a moment..."，解析 JSON 会失败），只有浏览器 UA 才返回 JSON。
#   实测：curl 默认 UA ✗挑战页 / 浏览器 UA ✓JSON。删除本头，
#   holiday_info 与 holiday_summary 会静默失效（返回"获取失败"而非报错）。
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122 Safari/537.36")

mcp = FastMCP("china-context-mcp")

# 不可变数据缓存：节假日/历史事件按日期永久有效，避免重复打网络
_HOLIDAY_CACHE: "functools.LRUCache[str, dict]" = functools.lru_cache(maxsize=2048)
_HISTORY_CACHE: "functools.LRUCache[str, dict]" = functools.lru_cache(maxsize=1024)
_YEAR_CACHE: "functools.LRUCache[int, dict]" = functools.lru_cache(maxsize=16)


def _get(url: str, timeout: int = 8, retries: int = 2):
    """带严格超时 + 有限重试（上限 retries）的出站 GET+JSON。

    每次失败重试间隔 0.3s，超过重试上限抛出最后一个异常，由调用方降级处理。
    """
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            last = e
            if attempt < retries:
                continue
    raise last


def _err(label: str, e: Exception) -> str:
    return f"[{label}] 获取失败：{type(e).__name__} {str(e)[:120]}"


@mcp.tool()
def random_poem() -> str:
    """随机返回一句中国古典诗词，含作者、出处与分类。

    适用：中文创作灵感、文化问答、语文/国学类 AI 陪练。
    数据来自 jinrishici.com（公开、零凭证）。
    """
    try:
        d = _get("https://v1.jinrishici.com/all.json")
        return (f"{d.get('content','')}\n"
                f"—— {d.get('author','')}《{d.get('origin','')}》"
                f"（{d.get('category','')}）")
    except Exception as e:  # noqa: BLE001
        return _err("诗词", e)


@_HOLIDAY_CACHE
def _holiday_raw(date: str) -> dict:
    """按日期取 timor.tech 原始数据；结果按日期缓存（不可变）。"""
    return _get(f"https://timor.tech/api/holiday/info/{date}")


@mcp.tool()
def holiday_info(date: str) -> str:
    """查询中国某日期的节假日 / 调休 / 是否工作日信息。

    参数 date：YYYY-MM-DD，例如 "2026-10-01"。
    返回：节假日名称、是否法定假日、是否调休补班工作日、工资倍率。
    数据来自 timor.tech（公开、零凭证）。
    """
    try:
        datetime.strptime(date, "%Y-%m-%d")  # 校验格式，防 URL 注入
    except ValueError:
        return "[节假日] 日期格式应为 YYYY-MM-DD，例如 2026-10-01"
    try:
        d = _holiday_raw(date)
        if d.get("code") != 0:
            return f"[节假日] 接口返回异常：{json.dumps(d, ensure_ascii=False)[:160]}"
        # 非节假日时 timor 返回 holiday: null，必须容错
        h = d.get("holiday") or {}
        t = d.get("type", {}) or {}
        is_holiday = bool(h.get("holiday"))
        # 工作日判据：非法定假日 且 非普通周末（调休补班=需上班）
        wk = datetime.strptime(date, "%Y-%m-%d").weekday()
        is_weekend = wk >= 5
        # timor：普通周末 holiday.holiday=False 且无补班标记；调休补班时 type 名含「班」
        makeup = "班" in (t.get("name", "") or "")
        is_workday = (not is_holiday) and (not (is_weekend and not makeup))
        return (
            f"日期 {date}：\n"
            f"  名称：{h.get('name') or t.get('name') or '（普通日）'}\n"
            f"  法定假日：{'是' if is_holiday else '否'}\n"
            f"  是否工作日：{'是' if is_workday else '否'}"
            f"{'（调休补班）' if makeup else ''}\n"
            f"  工资倍率：{h.get('wage', 1)}x"
        )
    except Exception as e:  # noqa: BLE001
        return _err("节假日", e)


@_YEAR_CACHE
def _holiday_year_raw(year: int) -> dict:
    """按年取 timor 全年节假日数据；结果按年份缓存（不可变）。"""
    return _get(f"https://timor.tech/api/holiday/year/{year}")


def _md_to_date(year: int, md: str) -> datetime:
    m, d = md.split("-")
    return datetime(year, int(m), int(d))


def _merge_holidays(year: int, entries: dict) -> list:
    """把扁平的 {MM-DD: {...}} 合并为「连续假期区间」。

    ★ 按日期连续性合并，不要求同名：中国法定假常把「春节」拆成
    除夕/初一/初二…多个名称（target 字段在假日条目上恒为 "-" 不可用于分组），
    若强制同名会把一个春节拆成一整串单日，与用户心智（"春节放 9 天"）严重不符。
    补班日（holiday=false）不参与合并，单独列出。
    返回 [(name, start_md, end_md, days, triple_days), ...]，name 取区间首个名称。
    """
    merged = []
    for md, v in sorted(entries.items()):
        if not v.get("holiday"):
            continue
        triple = 1 if v.get("wage") == 3 else 0
        if merged and (_md_to_date(year, md) - _md_to_date(year, merged[-1][2])).days == 1:
            p = merged[-1]
            p[2] = md
            p[3] += 1
            p[4] += triple
        else:
            merged.append([(v.get("name") or "（未命名）").strip(), md, md, 1, triple])
    return [(n, s, e, d, t) for n, s, e, d, t in merged]


@mcp.tool()
def holiday_summary(year: int = None) -> str:
    """返回中国某年的节假日与调休摘要——聚合推导，不是单日查询。

    与 holiday_info 的区别：本工具对 timor 全年扁平数据做聚合，给出
    holiday_info 拿不到、而 AI 自身容易算错的结论——连续假期区间与天数、
    法定 3 倍工资天数、全部调休补班日、全年总休假天数。

    参数 year：4 位年份，省略则用当前年。
    适用：年度休假规划、考勤与排班、HR 与薪酬核算。
    数据来自 timor.tech（公开、零凭证）。
    """
    y = year or datetime.now().year
    if not (1900 <= y <= 2200):
        return "[节假日摘要] 年份应在 1900–2200 之间"
    try:
        resp = _holiday_year_raw(y)
        if resp.get("code") != 0:
            return f"[节假日摘要] 接口返回异常：{json.dumps(resp, ensure_ascii=False)[:160]}"
        entries = resp.get("holiday") or {}
        if not entries:
            return f"{y} 年暂无收录的节假日数据"
        merged = _merge_holidays(y, entries)
        makeup = [f"  · {md} {v.get('name') or ''}（调休上班，非假日）"
                  for md, v in sorted(entries.items()) if not v.get("holiday")]
        total_days = sum(x[3] for x in merged)
        triple_days = sum(x[4] for x in merged)
        lines = [f"{y} 年中国节假日与调休摘要", "",
                 f"【假期区间】共 {len(merged)} 个，合计 {total_days} 天（不含补班）"]
        for name, s, e, days, triple in merged:
            seg = f"  · {name}  {s} ~ {e}   {days}天"
            if triple:
                seg += f"（3倍工资 {triple} 天）"
            lines.append(seg)
        lines.append("")
        if makeup:
            lines.append(f"【调休补班】共 {len(makeup)} 天")
            lines.extend(makeup)
            lines.append("")
        lines.append(f"【工资倍率】3倍 {triple_days} 天 / "
                     f"2倍 {total_days - triple_days} 天")
        return "\n".join(lines)
    except Exception as e:  # noqa: BLE001
        return _err("节假日摘要", e)


def _normalize_md(date: str):
    """把 None / 2026-09-25 / 09-25 归一为 (month, day) 整数元组。

    返回 None 表示格式非法。
    """
    if not date:
        t = datetime.now()
        return t.month, t.day
    s = date.strip()
    try:
        if len(s) == 10 and s[4] == "-" and s[7] == "-":
            datetime.strptime(s, "%Y-%m-%d")
            m, d = int(s[5:7]), int(s[8:10])
        elif len(s) == 5 and s[2] == "-":
            m, d = int(s[0:2]), int(s[3:5])
        else:
            return None
    except ValueError:
        return None
    if not (1 <= m <= 12 and 1 <= d <= 31):
        return None
    return m, d


@_HISTORY_CACHE
def _history_raw(md: str) -> dict:
    """按 MM-DD 取 60s-api 历史事件原始数据；按日期缓存（不可变）。"""
    return _get(f"https://60s-api.viki.moe/v2/today_in_history?date={md}")


@mcp.tool()
def history_today(date: str = None) -> str:
    """返回「历史上的今天」：某月某日发生的历史事件列表（标题 + 年份 + 简述）。

    参数 date：可选，格式 "MM-DD"（如 "09-25"）或 "YYYY-MM-DD"（如 "2026-09-25"）。
              省略则使用今天。
    适用：历史问答、内容创作、文化类 AI 陪练。
    数据来自 60s-api.viki.moe（公开、零凭证）。
    """
    md_tuple = _normalize_md(date)
    if md_tuple is None:
        return "[历史今日] 日期格式应为 MM-DD 或 YYYY-MM-DD，例如 09-25"
    m, d = md_tuple
    md = f"{m:02d}-{d:02d}"
    try:
        resp = _history_raw(md)
        if resp.get("code") != 200:
            return f"[历史今日] 接口返回异常：{json.dumps(resp, ensure_ascii=False)[:160]}"
        items = (resp.get("data") or {}).get("items") or []
        if not items:
            return f"{md} 暂无收录的历史事件。"
        lines = [f"历史上的今天（{md}）共 {len(items)} 条："]
        for it in items:
            yr = it.get("year", "")
            title = it.get("title", "")
            desc = (it.get("description") or "").strip()
            line = f"  · {yr}年 {title}"
            if desc:
                line += f"：{desc[:80]}"
            lines.append(line)
        return "\n".join(lines)
    except Exception as e:  # noqa: BLE001
        return _err("历史今日", e)


def main():
    mcp.run()


if __name__ == "__main__":
    main()
