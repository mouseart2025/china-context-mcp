# -*- coding: utf-8 -*-
"""china-context-mcp 回归测试：用 FastMCP 客户端真连真调（真联网，不 mock）。

跑法：PYTHONPATH=src pytest -q
"""
import asyncio

from fastmcp import Client
from china_context_mcp.server import mcp

CASES = {
    "2026-10-01": ("国庆节", False),   # 法定假日 → 休
    "2026-09-27": ("中秋节", False),   # 中秋假日 → 休
    "2026-09-28": (None, True),        # 普通周一 → 班
    "2026-09-20": ("补班", True),      # 中秋前补班(周日) → 班
    "2026-10-10": ("补班", True),      # 国庆后补班(周六) → 班
    "2026-10-11": (None, False),       # 普通周日 → 休
}


def _text(result):
    data = getattr(result, "data", None) or str(result)
    return data[0].text if isinstance(data, list) else str(data)


def test_tools_registered():
    async def _run():
        async with Client(mcp) as c:
            names = [t.name for t in await c.list_tools()]
            assert "random_poem" in names and "holiday_info" in names
    asyncio.run(_run())


def test_random_poem_returns_content():
    async def _run():
        async with Client(mcp) as c:
            text = _text(await c.call_tool("random_poem", {}))
            assert "——" in text
    asyncio.run(_run())


def test_holiday_six_cases():
    async def _run():
        async with Client(mcp) as c:
            for date, (name, work) in CASES.items():
                text = _text(await c.call_tool("holiday_info", {"date": date}))
                assert "获取失败" not in text, f"{date} 调用失败：{text}"
                if name:
                    assert name in text, f"{date} 应含「{name}」：{text}"
                want = "是否工作日：是" if work else "是否工作日：否"
                assert want in text, f"{date} 应为{'班' if work else '休'}：{text}"
    asyncio.run(_run())
