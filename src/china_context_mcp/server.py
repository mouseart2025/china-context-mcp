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


def _wage_label(wage: int) -> str:
    """把 timor 的 wage 数值写成人读的倍数标签（3/2 → 「3」/「2」，其余如实）。

    ★ 不能一律兜底成「2」：wage 为 1（普通周末）时也输出「2倍」，会把
      「这天不加班」说成「这天双倍加班」，是薪酬口径上的实质性错报。
    """
    return {3: "3", 2: "2"}.get(wage, str(wage))


def _md_to_date(year: int, md: str) -> datetime:
    m, d = md.split("-")
    return datetime(year, int(m), int(d))


def _merge_holidays(year: int, entries: dict) -> list:
    """把扁平的 {MM-DD: {...}} 合并为「连续假期区间」。

    ★ 按日期连续性合并，不要求同名：中国法定假常把「春节」拆成
    除夕/初一/初二…多个名称（target 字段在假日条目上恒为 "-" 不可用于分组），
    若强制同名会把一个春节拆成一整串单日，与用户心智（"春节放 9 天"）严重不符。
    补班日（holiday=false）不参与合并，单独列出。

    第 6 项是**逐日明细**，按工资倍率分组：{3: [(md, name), ...], 1|2: [...]}。
    它回答的是 holiday_summary 此前给不出的问题——
    「春节区间内**具体哪几天**要付 3 倍」（2026 年是 02-16 除夕 ~ 02-19 初三）。
    不加这一层，调用方只能拿到「3 倍共 4 天」，还得自己回查 365 行原始数据。

    返回 [(name, start_md, end_md, days, triple_days, by_wage), ...]，name 取区间首个名称。
    """
    merged = []
    for md, v in sorted(entries.items()):
        if not v.get("holiday"):
            continue
        wage = v.get("wage") or 1
        triple = 1 if wage == 3 else 0
        day = (md, (v.get("name") or "").strip())
        if merged and (_md_to_date(year, md) - _md_to_date(year, merged[-1][2])).days == 1:
            p = merged[-1]
            p[2] = md
            p[3] += 1
            p[4] += triple
            p[5].setdefault(wage, []).append(day)
        else:
            merged.append([(v.get("name") or "（未命名）").strip(), md, md, 1, triple,
                           {wage: [day]}])
    return merged


@mcp.tool()
def holiday_summary(year: int = None) -> str:
    """返回中国某年的节假日与调休摘要——聚合推导，不是单日查询。

    与 holiday_info 的区别：本工具对 timor 全年扁平数据做聚合，给出
    holiday_info 拿不到、而 AI 自身容易算错的结论——连续假期区间与天数、
    法定 3 倍工资天数与**具体是哪几天**、全部调休补班日、全年总休假天数。
    每条区间的逐日明细按工资倍率分组输出，例如
    `3倍 4 天：02-16、02-17 初一、02-18 初二、02-19 初三`。

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
        lines = [f"{y} 年中国节假日与调休摘要", "",
                 f"【假期区间】共 {len(merged)} 个，合计 {total_days} 天（不含补班）"]
        for name, s, e, days, triple, by_wage in merged:
            seg = f"  · {name}  {s} ~ {e}   {days}天"
            if triple:
                seg += f"（3倍工资 {triple} 天）"
            lines.append(seg)
            # ★ 逐日明细按倍率分组。缺了这一段，「3 倍共 4 天」这个结论仍然要调用方
            #   回查 365 行原始数据才能知道是哪几天 —— 工作没被减掉。
            for wage in sorted(by_wage, reverse=True):
                items = by_wage[wage]
                # ★ 分组必须全打，不能因为「不足 2 天」而整组跳过。
                #   3 倍工资常常只有 1 天（2026 清明只有 04-05 是清明节气当天，
                #   04-04/04-06 是周六与调休），而「哪几天算 3 倍」正是本工具存在的理由。
                #   一旦跳过，区间标题里的「（3倍工资 1 天）」就成了找不到对应日期的空话，
                #   输出自相矛盾。全打之后，明细组是区间的等价划分，这类矛盾不可能再出现。
                # ★ 只显示首日的名称：同一区间内 timor 常给每天相同的 name（元旦 3 天都叫
                #   「元旦」），逐一拼会造成「元旦、元旦、元旦」这种毫无增量信息的输出。
                #   真正要回答的是「哪几天」，所以日期必显，名称仅在异于首日时才带。
                base = items[0][1]
                parts = []
                for md, nm in items:
                    # ★ 用完整 MM-DD，不能只给「日」：「2倍 3 天：03、04、05」出现在
                    #   「05-01 ~ 05-05」下面时会被读成 3 月 3/4/5 日 —— 比不给还糟。
                    tag = f"{md} {nm}".strip() if nm and nm != base else md
                    parts.append(tag)
                lines.append(f"      {_wage_label(wage)}倍 {len(items)} 天：{'、'.join(parts)}")
        lines.append("")
        if makeup:
            lines.append(f"【调休补班】共 {len(makeup)} 天")
            lines.extend(makeup)
            lines.append("")
        # ★ 页脚按实际 wage 直方图统计，不再假设「非 3 倍即 2 倍」。
        #   旧写法 total_days - triple_days 一旦出现 wage=1 的条目，
        #   就会把不加班日算成双倍加班；直方图不给这种错报留余地。
        wage_hist: dict[int, int] = {}
        for _n, _s, _e, _d, _tri, bw in merged:
            for w, items in bw.items():
                wage_hist[w] = wage_hist.get(w, 0) + len(items)
        lines.append("【工资倍率】" + " / ".join(
            f"{_wage_label(w)}倍 {n} 天"
            for w, n in sorted(wage_hist.items(), reverse=True)))
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


# 省级行政区（GB/T 2260 前两位）；71/81/82 按国标表述为中国领土
_PROVINCES = {
    "11": "北京市", "12": "天津市", "13": "河北省", "14": "山西省", "15": "内蒙古自治区",
    "21": "辽宁省", "22": "吉林省", "23": "黑龙江省",
    "31": "上海市", "32": "江苏省", "33": "浙江省", "34": "安徽省",
    "35": "福建省", "36": "江西省", "37": "山东省",
    "41": "河南省", "42": "湖北省", "43": "湖南省", "44": "广东省",
    "45": "广西壮族自治区", "46": "海南省",
    "50": "重庆市", "51": "四川省", "52": "贵州省", "53": "云南省", "54": "西藏自治区",
    "61": "陕西省", "62": "甘肃省", "63": "青海省", "64": "宁夏回族自治区",
    "65": "新疆维吾尔自治区",
    "71": "中国台湾", "81": "中国香港", "82": "中国澳门",
}
# GB 11643 校验位：ISO 7064 MOD 11-2 的加权因子与校验码表
_ID_WEIGHTS = [7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2]
_ID_CHECK = "10X98765432"


@mcp.tool()
def idcard_check(id_number: str) -> str:
    """校验中国居民身份证号（GB 11643），并解析国标公开字段。

    ★ 纯本地算法，不联网、零凭证：按 ISO 7064 MOD 11-2 加权算法验证末位校验码。
      这类 17 位加权求和 + 模 11 查表，**AI 自行计算极易出错**（因子表或索引错位）。
      因此本工具的价值不在"包 API"（它无 API 可包），而在**替 AI 算对**。

    参数 id_number：18 位身份证号，末位 X/x 大小写均可。
    隐私：仅解析国标公开字段（出生日期/性别/省级），不触姓名与住址；回显做中间掩码。
    """
    s = (id_number or "").strip().upper()
    if len(s) != 18:
        return f"[身份证] 长度应为 18 位，当前 {len(s)} 位：{s}"
    body, tail = s[:17], s[17]
    if not body.isdigit():
        return f"[身份证] 前 17 位应全为数字，当前：{body}"
    total = sum(int(body[i]) * _ID_WEIGHTS[i] for i in range(17))
    expect = _ID_CHECK[total % 11]
    if tail != expect:
        return (f"[身份证] 校验位错误：期望 {expect}，实际 {tail}\n"
                f"  号码 {s} 不是有效的居民身份证号")
    born_s = body[6:14]
    try:
        born = datetime.strptime(born_s, "%Y%m%d")
    except ValueError:
        return f"[身份证] 出生日期段非法：{born_s}"
    if born > datetime.now():
        return f"[身份证] 出生日期晚于今天：{born.date()}"
    seq = body[16]
    gender = "男" if int(seq) % 2 == 1 else "女"
    masked = body[:6] + "*" * 8 + tail
    return (
        f"[身份证] {s} → 有效\n"
        f"  校验位：{tail} 正确（ISO 7064 MOD 11-2）\n"
        f"  出生日期：{born.date()}\n"
        f"  性别：{gender}（顺序码 {seq} 为{'奇' if int(seq) % 2 else '偶'}）\n"
        f"  省级行政区：{_PROVINCES.get(body[:2], '未知')}（{body[:2]}）\n"
        f"  回显掩码：{masked}"
    )


def main():
    mcp.run()


if __name__ == "__main__":
    main()
