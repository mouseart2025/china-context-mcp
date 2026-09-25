# -*- coding: utf-8 -*-
"""法定节假日法规常量层（L1）与 `holiday_info` 三态判别的回归锁。

★ 判据来源纪律（PRD AC-01.8）：本文件的标准答案与日期集合**不取自** `eval/cases.json`
  —— 那是产品方既有资产，用它出题就是自证循环。
  本文件依据：
  - 《全国年节及纪念日放假办法》（**国务院令第 795 号**，2024-11-10 公布、**2025-01-01 施行**）第二条
  - 《中华人民共和国劳动法》第四十四条（法定节假日加班不得以补休替代）

★ 为什么断言写成「属性」而不是「点」
  锁死固定的 2027-01-01 / 05-01 / 10-01 三个日期，只能抓住**今天已知**的错误；
  未来的某次回归若把「无数据」重新压回「否」，只要没碰到这三天就抓不到。
  故这里对 **2027–2035 每个年份 × 全部 6 个公历固定法定日**做属性断言。
"""
import pytest

from china_context_mcp import server as srv
from china_context_mcp.statutory import FIXED_BY_MD, fixed_name, year_fixed_dates

# 《放假办法》第二条规定的公历固定法定节假日（795 号令口径，共 6 天/年）
LAW_FIXED = {
    "01-01": "元旦",
    "05-01": "劳动节",
    "05-02": "劳动节",   # 795 号令新增；施行前劳动节法定假日仅 1 天
    "10-01": "国庆节",
    "10-02": "国庆节",
    "10-03": "国庆节",
}
YEARS = range(2027, 2036)          # 上游目前无数据的年份区间
NON_FIXED = ("06-15", "03-09", "11-20")   # 非公历固定法定日，用作阴性对照


def _no_data_raw(*_a, **_k):
    """上游对该日期返回「无节假日信息」的原始形态。"""
    return {"code": 0, "type": {"type": 0, "name": "周五", "week": 5}, "holiday": None}


# ---------------------------------------------------------------- 常量层本身

def test_statutory_table_matches_the_law():
    """常量表必须与国务院令第 795 号一致，且**必须包含 05-02**。"""
    assert FIXED_BY_MD == LAW_FIXED, "常量表与《放假办法》第二条不符"
    assert "05-02" in FIXED_BY_MD, (
        "05-02 是 795 号令新增的那一天；删除它等于静默退回 2025-01-01 前的旧口径"
    )
    assert len(FIXED_BY_MD) == 6


def test_fixed_name_lookup():
    assert fixed_name("01-01") == "元旦"
    assert fixed_name("05-02") == "劳动节"
    assert fixed_name("10-03") == "国庆节"
    assert fixed_name("06-15") is None


def test_year_fixed_dates_count_and_order():
    for y in YEARS:
        got = year_fixed_dates(y)
        assert len(got) == 6
        assert [g[0][5:] for g in got] == sorted(LAW_FIXED)


# ------------------------------------------------- 态二：无数据年份的固定法定日

def test_no_data_year_fixed_days_are_statutory_holidays(monkeypatch):
    """★ 核心属性断言：无数据年份里，6 个公历固定法定日**不得**被判为「否」。

    这是本次修的那个 P0 的回归锁 —— 修之前 `holiday_info('2027-01-01')`
    会返回「法定假日：否 / 是否工作日：是」。
    """
    monkeypatch.setattr(srv, "_holiday_raw", _no_data_raw)
    monkeypatch.setattr(srv, "_year_has_data", lambda _y: False)

    for y in YEARS:
        for md, nm in LAW_FIXED.items():
            out = srv.holiday_info(f"{y}-{md}")
            assert "法定假日：是" in out, f"{y}-{md} 被判为非法定假日：{out}"
            assert "法定假日：否" not in out, f"{y}-{md} 出现了否定断言：{out}"
            assert nm in out, f"{y}-{md} 未给出法定节假日名称：{out}"


def test_no_data_year_fixed_day_does_not_claim_workday(monkeypatch):
    """固定法定日不得被说成「工作日：是」（那会直接产出违法的排班建议）。"""
    monkeypatch.setattr(srv, "_holiday_raw", _no_data_raw)
    monkeypatch.setattr(srv, "_year_has_data", lambda _y: False)
    for y in (2027, 2028):
        for md in LAW_FIXED:
            out = srv.holiday_info(f"{y}-{md}")
            assert "是否工作日：是" not in out, f"{y}-{md} 被判为工作日：{out}"


# ------------------------------------------------- 态三：无数据年份的未知日

def test_no_data_year_unknown_day_says_unknown(monkeypatch):
    """非固定日 + 无数据 ⇒ 必须是「无法确定」，**绝不能**说「否」。

    理由：调休可能把周末变成工作日、也可能把工作日变成休息日。
    """
    monkeypatch.setattr(srv, "_holiday_raw", _no_data_raw)
    monkeypatch.setattr(srv, "_year_has_data", lambda _y: False)
    for y in (2027, 2028):
        for md in NON_FIXED:
            out = srv.holiday_info(f"{y}-{md}")
            assert "无法确定" in out, f"{y}-{md} 未声明无法确定：{out}"
            assert "法定假日：否" not in out, f"{y}-{md} 出现了否定断言：{out}"


def test_year_lookup_failure_never_asserts_negative(monkeypatch):
    """年份覆盖探测失败（`_year_has_data` 返回 None）时，同样**不许**给否定结论。"""
    monkeypatch.setattr(srv, "_holiday_raw", _no_data_raw)
    monkeypatch.setattr(srv, "_year_has_data", lambda _y: None)
    for md in list(LAW_FIXED) + list(NON_FIXED):
        out = srv.holiday_info(f"2027-{md}")
        assert "法定假日：否" not in out, f"2027-{md} 在降级路径上给出了否定断言：{out}"


# ------------------------------------------- 消除两个工具之间的自相矛盾（AC-01.4）

def test_summary_and_info_agree_on_no_data_year(monkeypatch):
    """同一上游状态下，`holiday_info` 与 `holiday_summary` 不得一个说「是」一个说「没数据」。"""
    monkeypatch.setattr(srv, "_holiday_raw", _no_data_raw)
    monkeypatch.setattr(srv, "_year_has_data", lambda _y: False)
    monkeypatch.setattr(srv, "_holiday_year_raw", lambda _y: {"code": 0, "holiday": {}})

    summary = srv.holiday_summary(2027)
    for md in LAW_FIXED:
        assert md in summary, f"holiday_summary(2027) 未列出固定法定日 {md}"
        assert "法定假日：是" in srv.holiday_info(f"2027-{md}")

    # 未知日两边都不得给出「否」
    for md in NON_FIXED:
        assert "法定假日：否" not in srv.holiday_info(f"2027-{md}")


def test_this_file_does_not_read_eval_cases():
    """判据来源纪律（AC-01.8）：本文件不得**读取**产品方既有题库。

    注意措辞：查的是**读取操作**（open / read_text / Path 指向 cases.json），
    不是字面提及 —— 本文件注释里正当引用了它作为「禁止对象」，字面匹配会自相矛盾。
    """
    import pathlib
    import re

    src = pathlib.Path(__file__).read_text(encoding="utf-8")
    assert not re.search(r"(open|read_text|read_bytes|Path|json\.load)\s*\(.*cases\.json", src), (
        "测试不得 open/read eval/cases.json 作为判据来源（自证循环）"
    )
    # 侧向确认：本文件确实引了权威口径
    assert "795" in src and "放假办法" in src
