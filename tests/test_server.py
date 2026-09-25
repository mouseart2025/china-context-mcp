# -*- coding: utf-8 -*-
"""china-context-mcp 回归测试：本地算法真算，外部数据走**离线快照**。

跑法：PYTHONPATH=src pytest -q
真联网冒烟（可选）：LIVE=1 PYTHONPATH=src pytest -q -k live

★ 为什么三路外部依赖全部换成快照（2026-09-25 定）：
  timor.tech 对**机房 IP**（GitHub Actions runner）返回 **403 Forbidden** ——
  不是限流，是直接不放行。于是 CI 的绿/红被押在「上游愿不愿意放行机房 IP」
  这件事上，等于把我们的回归测试交给别人控制。快照只锁**我们自己的**
  解析与聚合逻辑，这部分才是本仓库该负责的正确性。
"""
import asyncio
import json
import os
import pathlib
import re

import pytest
from fastmcp import Client
from china_context_mcp.server import mcp, _ID_WEIGHTS, _ID_CHECK

FIXDIR = pathlib.Path(__file__).parent / "fixtures"
# 2026 全年上游响应快照（39 条，code=0）
TIMOR_YEAR = json.loads((FIXDIR / "timor_2026.json").read_text(encoding="utf-8"))
# 其余三路依赖的快照：info_<date>（6 个日期）、history_09-25、poem_1
BUNDLE = json.loads((FIXDIR / "bundle.json").read_text(encoding="utf-8"))


def _use_fixtures(monkeypatch) -> None:
    """把三路外部依赖换成离线快照；被测对象仍是真实的 MCP 工具函数。"""
    import china_context_mcp.server as srv

    monkeypatch.setattr(srv, "_holiday_year_raw", lambda _y: TIMOR_YEAR)
    monkeypatch.setattr(
        srv, "_holiday_raw",
        lambda d: BUNDLE.get(f"info_{d}") or {"code": 0, "type": {}, "holiday": None})
    monkeypatch.setattr(srv, "_history_raw", lambda _md: BUNDLE["history_09-25"])
    monkeypatch.setattr(srv, "_get", lambda url, **_k: BUNDLE["poem_1"])


def _skip_if_limited(text: str) -> None:
    """上游不放行（403/429）时跳过而非判红：那不是我们代码的错。

    正常路径已走快照，这条只在有人直连上游时兜底。
    """
    if any(k in text for k in ("429", "403", "Too Many Requests", "Forbidden")):
        pytest.skip(f"上游未放行，跳过联网断言：{text[:80]}")


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


def test_history_today_specific_and_default(monkeypatch):
    _use_fixtures(monkeypatch)

    async def _run():
        async with Client(mcp) as c:
            # 指定日期
            text = _text(await c.call_tool("history_today", {"date": "09-25"}))
            _skip_if_limited(text)
            assert "历史上的今天（09-25）" in text and "条" in text
            # 默认今天（不传 date）
            text2 = _text(await c.call_tool("history_today", {}))
            assert "历史上的今天" in text2
            # 非法格式降级
            bad = _text(await c.call_tool("history_today", {"date": "not-a-date"}))
            assert "格式应为" in bad
    asyncio.run(_run())


def test_random_poem_returns_content(monkeypatch):
    _use_fixtures(monkeypatch)

    async def _run():
        async with Client(mcp) as c:
            text = _text(await c.call_tool("random_poem", {}))
            _skip_if_limited(text)
            assert "——" in text
    asyncio.run(_run())


def test_holiday_six_cases(monkeypatch):
    _use_fixtures(monkeypatch)

    async def _run():
        async with Client(mcp) as c:
            for date, (name, work) in CASES.items():
                text = _text(await c.call_tool("holiday_info", {"date": date}))
                _skip_if_limited(text)
                assert "获取失败" not in text, f"{date} 调用失败：{text}"
                if name:
                    assert name in text, f"{date} 应含「{name}」：{text}"
                want = "是否工作日：是" if work else "是否工作日：否"
                assert want in text, f"{date} 应为{'班' if work else '休'}：{text}"
    asyncio.run(_run())


def test_holiday_summary_2026_aggregate(monkeypatch):
    """编排层回归：2026 全年聚合结论必须与**离线快照**逐项一致。

    ★ 为什么改用 fixture：原实现真联网，CI 的稳定性等于押在上游限流策略上 ——
      2026-09-25 上游返回 429 直接把这条打红。聚合是我们自己的代码，
      它的正确性应由快照决定，不由上游可用性决定。

    重点锁住「春节不被农历名拆散」——这是 _merge_holidays 按日期连续而非
    同名合并的原因（同名合并会把春节拆成 除夕/初一/初二…9 个单日区间）。
    """
    _use_fixtures(monkeypatch)

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

            # ★ 回归锁（2026-09-25）：逐日明细必须列出标题宣称的每一个 3 倍日。
            #   旧代码 `if len(items) < 2: continue` 会把「只有 1 天」的倍率组整组跳过，
            #   于是 元旦/清明/端午/中秋 4 个 3 倍日只在标题出现、明细里永远查不到 ——
            #   而这正是本工具存在的理由（「哪几天算 3 倍」）。
            for md in ("01-01", "04-05", "06-19", "09-25"):
                assert f"3倍 1 天：{md}" in text, f"{md} 的 3 倍日未在明细中列出：{text}"

            # ★ 结构性校验：每个区间下方「N倍 M 天」的 M 之和必须等于区间天数。
            #   上一条只覆盖 3 倍；这一条把「明细与标题自相矛盾」整类问题都锁住。
            for blk in re.split(r"\n(?=  · )", text):
                m = re.match(r"  · \S+  \d\d-\d\d ~ \d\d-\d\d   (\d+)天", blk)
                if not m:
                    continue
                want, got = int(m.group(1)), sum(
                    int(x) for x in re.findall(r"(\d+) 天：", blk))
                assert got == want, f"明细 {got} 天与区间 {want} 天不符：{blk.splitlines()[0]}"
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
            # ★ 反向断言：只断言「掩码存在」是不够的 —— 旧版首行就回显了完整号码，
            #   而这条断言照样通过。掩码类需求必须反过来测「明文不存在」。
            assert "11010519491231002X" not in good, "回显不得包含完整号码明文"
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


@pytest.mark.skipif(os.environ.get("LIVE") != "1",
                    reason="真联网冒烟需显式 LIVE=1；默认不跑，避免 CI 押在上游放行上")
def test_live_smoke_upstream_reachable():
    """真联网冒烟：只验「上游还活着、返回结构没变」，不验我们的聚合。

    上游对机房 IP 会 403，故默认不跑 —— 需要确认上游契约时人肉跑一次。
    """
    async def _run():
        async with Client(mcp) as c:
            for tool, args in (("random_poem", {}),
                               ("holiday_info", {"date": "2026-10-01"}),
                               ("history_today", {"date": "09-25"})):
                text = _text(await c.call_tool(tool, args))
                _skip_if_limited(text)
                assert "获取失败" not in text, f"{tool} 上游不可达：{text[:80]}"
    asyncio.run(_run())
