"""Streamlit Community Cloud 財報分析（對齊本機 8501 主要區塊）."""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from classification import get_stock_meta, is_core_asic_ip_stock
from cloud_sections import render_financial_charts, render_metrics_table_raw, render_risk_section
from config import STOCK_NAMES, YEARS
from data_fetch import fetch_stock_data_auto
from display_format import (
    inject_layout_css,
    metrics_for_display,
    render_source_banner,
    source_banner,
)
from market_depth_analysis import depth_analysis_available, render_depth_section, resolve_stock_name

st.set_page_config(
    page_title="台股財報分析",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_layout_css()

_REPORT_CAP = min(max(YEARS), date.today().year - 1)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_data(symbol: str, years: tuple[int, ...]) -> dict:
    code = symbol.strip()
    year_list = sorted(int(y) for y in years)
    if not code or not year_list:
        return {"ok": False, "error": "請輸入股票代號並選擇至少一個年度。"}
    return fetch_stock_data_auto(code, year_list)


def _is_core_stock(code: str, name: str = "", role: str = "") -> bool:
    try:
        return bool(is_core_asic_ip_stock(code, name, role))
    except Exception:
        return False


st.title("台股財報分析")
st.caption(
    "Cloud 版：財報 · 圖表解說 · 風險提醒 · 技術籌碼 · "
    "完整 MOPS 與進階功能請用本機 `start_hub`（8501）"
)

with st.sidebar:
    st.subheader("年度範圍")
    min_y, max_y = min(YEARS), min(max(YEARS), _REPORT_CAP)
    default_end = max(min_y, max_y)
    default_start = max(min_y, default_end - 3)
    year_start, year_end = st.slider(
        "西元年",
        min_value=min_y,
        max_value=max_y,
        value=(default_start, default_end),
    )
    selected_years = tuple(y for y in YEARS if year_start <= y <= year_end and y <= _REPORT_CAP)

    st.divider()
    show_chart_help = st.checkbox(
        "顯示圖表解說（初學者模式）",
        value=True,
        help="圖表右側顯示白話說明，與本機 8501 相同。",
    )
    load_depth = st.checkbox(
        "載入技術面／籌碼面",
        value=True,
        disabled=not depth_analysis_available(),
    )
    if not depth_analysis_available():
        st.caption("技術籌碼模組未就緒（缺 `modules/stock_report_generator.py`）。")

    st.divider()
    st.markdown(
        "**與本機 8501 差異**\n"
        "- 財報：Cloud 常走 Yahoo 備援\n"
        "- 技術籌碼：TWSE API 在海外可能失敗\n"
        "- 無「全清單篩選」與 HTML 匯出"
    )

def _url_code() -> str:
    try:
        raw = st.query_params.get("code", "")
        if isinstance(raw, list):
            raw = raw[0] if raw else ""
        return str(raw).strip()[:6]
    except Exception:
        return ""


_default_code = _url_code() or "2330"
symbol = st.text_input("股票代號", value=_default_code, max_chars=6).strip().upper()

if not symbol:
    st.warning("請輸入股票代號。")
else:
    try:
        meta = get_stock_meta(symbol)
    except Exception:
        meta = {}
    stock_name = str(meta.get("name") or STOCK_NAMES.get(symbol, "") or resolve_stock_name(symbol))
    is_core = _is_core_stock(symbol, stock_name, str(meta.get("role", "")))

    with st.spinner(f"正在取得 {symbol}（{year_start}–{year_end}）…"):
        result = fetch_stock_data(symbol, selected_years)

    if not result.get("ok"):
        st.error(result.get("error", "無法取得資料"))
        for note in result.get("notes") or []:
            st.caption(note)
    else:
        source_kind = result.get("source_kind", "yahoo")
        banner_text, banner_level = source_banner(source_kind)
        render_source_banner(banner_text, banner_level)
        for note in result.get("notes") or []:
            if "MOPS" in str(note):
                render_source_banner(str(note), "info")

        metrics_raw: pd.DataFrame = result["metrics"]
        table_df = metrics_for_display(metrics_raw)

        st.header("一、財報分析")
        st.caption(f"{stock_name}（`{symbol}`）· {result.get('source_label', '')}")

        tab_summary, tab_charts, tab_risk, tab_raw = st.tabs(
            ["指標表（億元）", "指標圖表", "風險提醒", "原始數值"]
        )

        with tab_summary:
            st.dataframe(table_df, width="stretch", hide_index=True)

        with tab_charts:
            render_financial_charts(metrics_raw, show_help=show_chart_help)

        with tab_risk:
            render_risk_section(metrics_raw, is_core=is_core, show_help=show_chart_help)

        with tab_raw:
            render_metrics_table_raw(metrics_raw)

        if load_depth:
            st.divider()
            st.header("二、技術面與籌碼面")
            render_depth_section(symbol, stock_name=stock_name, show_help=show_chart_help)
