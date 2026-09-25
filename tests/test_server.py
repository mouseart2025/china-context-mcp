# -*- coding: utf-8 -*-
"""china-context-mcp 回归测试：用 FastMCP 客户端真连真调（真联网，不 mock）。

跑法：PYTHONPATH=src pytest -q
"""
import asyncio

from fastmcp import Client
from china_context_mcp.server import mcp, _ID_WEIGHTS, _ID_CHECK


def _mk_id(born: str, seq: str = "002", prefix: str = "110105") -> str:
    """构造校验位正确的号码，用于测非校验位逻辑（如非法出生日期段）。"""
    base = prefix + born + seq
    total = sum(int(base[i]) * _ID_WEIGHTS[i] for i in range(17))
    return base + _ID_CHECK[total % 11]

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
            for want in ("random_poem", "holiday_info", "holiday_summary",
                         "history_today", "idcard_check"):
                assert want in names, f"缺少工具 {want}"
    asyncio.run(_run())


def test_history_today_specific_and_default():
    async def _run():
        async with Client(mcp) as c:
            # 指定日期
            text = _text(await c.call_tool("history_today", {"date": "09-25"}))
            assert "历史上的今天（09-25）" in text and "条" in text
            # 默认今天（不传 date）
            text2 = _text(await c.call_tool("history_today", {}))
            assert "历史上的今天" in text2
            # 非法格式降级
            bad = _text(await c.call_tool("history_today", {"date": "not-a-date"}))
            assert "格式应为" in bad
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


def test_holiday_summary_2026_aggregate():
    """编排层回归：2026 全年聚合结论必须与实测数据逐项一致。

    重点锁住「春节不被农历名拆散」——这是 _merge_holidays 按日期连续而非
    同名合并的原因（同名合并会把春节拆成 除夕/初一/初二…9 个单日区间）。
    """
    async def _run():
        async with Client(mcp) as c:
            text = _text(await c.call_tool("holiday_summary", {"year": 2026}))
            assert "获取失败" not in text, f"摘要调用失败：{text}"
            assert "共 7 个" in text, f"应得 7 个假期区间：{text}"
            assert "合计 33 天" in text, f"全年应休 33 天：{text}"
            assert "春节  02-15 ~ 02-23   9天" in text, f"春节应合并为单区间：{text}"
            assert "【调休补班】共 6 天" in text, f"应有 6 个补班日：{text}"
            for md in ("01-04", "02-14", "02-28", "05-09", "09-20", "10-10"):
                assert md in text, f"缺补班日 {md}：{text}"
            assert "3倍 13 天" in text, f"3 倍工资应为 13 天：{text}"
            assert "2倍 20 天" in text, f"2 倍工资应为 20 天：{text}"
            bad = _text(await c.call_tool("holiday_summary", {"year": 3050}))
            assert "1900" in bad, f"非法年份应被拦截：{bad}"
    asyncio.run(_run())


def test_idcard_check_valid_and_rejects():
    """本地算法回归：不联网、零凭证，校验 GB 11643 MOD 11-2 与各条拒绝路径。"""
    async def _run():
        async with Client(mcp) as c:
            good = _text(await c.call_tool("idcard_check",
                                           {"id_number": "11010519491231002X"}))
            assert "有效" in good, good
            assert "1949-12-31" in good, f"出生日期解析错：{good}"
            assert "北京市" in good, f"省级解析错：{good}"
            assert "女" in good, f"性别解析错：{good}"
            assert "********" in good, "回显必须掩码，避免明文回传"
            bad = _text(await c.call_tool("idcard_check",
                                          {"id_number": "110105194912310021"}))
            assert "不是有效" in bad, f"校验位错误未被拒：{bad}"
            short = _text(await c.call_tool("idcard_check", {"id_number": "1234"}))
            assert "长度应为 18 位" in short, short
            # 校验位正确、但出生日期段非法（13 月）——覆盖非校验位分支
            badate = _text(await c.call_tool("idcard_check",
                                             {"id_number": _mk_id("19491331")}))
            assert "出生日期段非法" in badate, f"非法日期未被捕获：{badate}"
            # 顺序码奇数为男
            male = _text(await c.call_tool("idcard_check",
                                           {"id_number": _mk_id("19900101", seq="001")}))
            assert "男" in male, f"奇数顺序码应为男：{male}"
    asyncio.run(_run())
