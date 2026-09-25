# -*- coding: utf-8 -*-
"""法定节假日「法规常量层」（L1）——离线、永久有效、与网络无关。

★ 为什么要这一层
`holiday_info` 原先在上游（timor）对某个年份没有数据时，会把「无数据」渲染成
「法定假日：否 / 是否工作日：是」——把**未知**说成了**否**。而元旦（1/1）、
劳动节（5/1、5/2）、国庆（10/1–10/3）是《全国年节及纪念日放假办法》**直接规定的
公历固定日**，与年度调休安排、与年份都无关 —— 无论国办通知发没发，答案都必须是「是」。

这一层就是那个不依赖任何上游、也不依赖农历推算的兜底事实。

★ 为什么不含春节/清明/端午/中秋
它们由农历确定，公历日期逐年浮动。任何「本地推算」都会产出**尚未公布的安排**，
与「无数据就诚实说无数据」的纪律直接冲突（这正是不引入农历库的原因，见 PRD NG-6）。
它们的正确来源是**国务院办公厅年度放假安排通知**，随 R-12 的静态数据源一起落地。

★ 为什么是独立模块 + 独立 JSON 数据文件（PRD AC-01.10）
它是**构建期静态常量**，不是运行期能力；独立出来才能：
  ① 单独与国务院令原文对账（`tests/test_statutory.py`）；
  ② 将来 R-12（全量静态数据源）在**同一份产物上扩展并扣除已建部分**，不从零计价。
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

_DATA = Path(__file__).with_name("statutory_dates.json")


def _load() -> tuple[dict[str, str], dict]:
    raw = json.loads(_DATA.read_text(encoding="utf-8"))
    return ({item["md"]: item["name"] for item in raw["fixed"]}, raw)


FIXED_BY_MD, _RAW = _load()
SOURCE = _RAW["_source"]


def fixed_name(md: str) -> str | None:
    """返回 MM-DD 对应的公历固定法定节假日名称，不是则返回 None。"""
    return FIXED_BY_MD.get(md)


def is_fixed(md: str) -> bool:
    return md in FIXED_BY_MD


def year_fixed_dates(year: int) -> list[tuple[str, str]]:
    """某年份的全部公历固定法定节假日，按日期升序。

    用于上游无数据时给 `holiday_summary` 兜底，避免两个工具一个说「暂无收录」、
    一个说「确定不是节假日」的自相矛盾。
    """
    out = []
    for md in sorted(FIXED_BY_MD):
        m, d = int(md[:2]), int(md[3:5])
        out.append((f"{year:04d}-{md}", FIXED_BY_MD[md], datetime(year, m, d).weekday()))
    return out
