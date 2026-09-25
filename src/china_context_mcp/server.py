# -*- coding: utf-8 -*-
"""china-context-mcp 服务端：FastMCP + 两个零凭证中文数据源工具。"""
import json
import ssl
import urllib.request
from datetime import datetime

from fastmcp import FastMCP

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/122 Safari/537.36")

mcp = FastMCP("china-context-mcp")


def _get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
        return json.loads(r.read().decode("utf-8"))


def _err(label, e):
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


@mcp.tool()
def holiday_info(date: str) -> str:
    """查询中国某日期的节假日 / 调休 / 是否工作日信息。

    参数 date：YYYY-MM-DD，例如 "2026-10-01"。
    返回：节假日名称、是否法定假日、是否调休补班工作日、工资倍率。
    数据来自 timor.tech（公开、零凭证）。
    """
    try:
        datetime.strptime(date, "%Y-%m-%d")  # 校验格式
    except ValueError:
        return "[节假日] 日期格式应为 YYYY-MM-DD，例如 2026-10-01"
    try:
        d = _get(f"https://timor.tech/api/holiday/info/{date}")
        if d.get("code") != 0:
            return f"[节假日] 接口返回异常：{json.dumps(d, ensure_ascii=False)[:160]}"
        # 非节假日时 timor 返回 holiday: null，必须容错
        h = d.get("holiday") or {}
        t = d.get("type", {}) or {}
        is_holiday = bool(h.get("holiday"))
        # 工作日判据：非法定假日 且 非普通周末（调休补班=需上班）
        wk = datetime.strptime(date, "%Y-%m-%d").weekday()
        is_weekend = wk >= 5
        # timor：普通周末 holiday.holiday=False 且无补班标记；调休补班时 type 仍为非假日
        # 简化判据：法定假日→休息；否则周末→休息；调休补班（type 名含「班」）→上班
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


def main():
    mcp.run()


if __name__ == "__main__":
    main()
