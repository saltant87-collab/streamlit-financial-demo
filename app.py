"""Streamlit Community Cloud 財報分析（MOPS + Yahoo 備援）."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from config import YEARS
from data_fetch import fetch_stock_data_auto
from display_format import METRIC_LABELS, metrics_for_display, source_banner

st.set_page_config(
    page_title="台股財報分析",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

_REPORT_CAP = min(max(YEARS), date.today().year - 1)

# 圖表用（數值、元；金額以億元顯示於軸標題）
CHART_MONEY_YI = {
    "FCF": "自由現金流（億元）",
    "OperatingCashflow": "營業現金流（億元）",
}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_data(symbol: str, years: tuple[int, ...]) -> dict:
    code = symbol.strip()
    year_list = sorted(int(y) for y in years)
    if not code or not year_list:
        return {"ok": False, "error": "請輸入股票代號並選擇至少一個年度。"}
    return fetch_stock_data_auto(code, year_list)


def _metrics_to_chart_df(metrics: pd.DataFrame) -> pd.DataFrame:
    """指標表（元）→ 圖表用（億元）。"""
    chart = metrics.copy()
    chart.index.name = "Year"
    chart = chart.reset_index()
    for col, label in CHART_MONEY_YI.items():
        if col in chart.columns:
            chart[label] = chart[col] / 1e8
    chart = chart.rename(columns={k: v for k, v in METRIC_LABELS.items() if k not in CHART_MONEY_YI})
    return chart


st.title("台股財報分析")
st.caption("Cloud 精簡版 · 金額統一顯示為新台幣億元 · 完整 MOPS 版請用本機 `start_hub`（8501）")

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
    st.caption(f"建議查詢至 {_REPORT_CAP} 年（正式年報年度）")
    st.divider()
    st.markdown(
        "**與本機差異說明**\n"
        "- 本機 **8501**：MOPS 完整儀表板\n"
        "- 本頁 **Cloud**：海外主機常只能 Yahoo 備援\n"
        "- **百分比**兩邊可對照；**金額**以本頁「億元」欄為準"
    )

symbol = st.text_input("股票代號", value="2330", max_chars=6).strip().upper()

if not symbol:
    st.warning("請輸入股票代號。")
else:
    with st.spinner(f"正在取得 {symbol}（{year_start}–{year_end}）…"):
        result = fetch_stock_data(symbol, selected_years)
        result["symbol"] = symbol

    if not result.get("ok"):
        st.error(result.get("error", "無法取得資料"))
        for note in result.get("notes") or []:
            st.caption(note)
    else:
        source_kind = result.get("source_kind", "yahoo")
        banner_text, banner_level = source_banner(source_kind)
        if banner_level == "success":
            st.success(banner_text)
        else:
            st.warning(banner_text)

        st.caption(result.get("source_label", ""))
        for note in result.get("notes") or []:
            if "MOPS 無法使用" in note or "無回應" in note:
                st.info(note)

        metrics_raw: pd.DataFrame = result["metrics"]
        table_df = metrics_for_display(metrics_raw)
        chart_df = _metrics_to_chart_df(metrics_raw)

        tab_table, tab_chart = st.tabs(["指標表", "趨勢圖"])

        with tab_table:
            st.caption("比率為 % 或倍；金額欄為新台幣億元（小數點後兩位）。")
            st.dataframe(table_df, width="stretch", hide_index=True)

        with tab_chart:
            if chart_df.empty:
                st.info("無可繪圖資料。")
            else:
                col1, col2 = st.columns(2)
                with col1:
                    if "EPS 年成長率 (%)" in chart_df.columns:
                        st.plotly_chart(
                            px.line(
                                chart_df,
                                x="Year",
                                y="EPS 年成長率 (%)",
                                markers=True,
                                title="EPS 年成長率",
                            ),
                            width="stretch",
                        )
                    if "毛利率 (%)" in chart_df.columns:
                        st.plotly_chart(
                            px.line(
                                chart_df,
                                x="Year",
                                y=["毛利率 (%)", "營業利益率 (%)"],
                                markers=True,
                                title="毛利率 / 營業利益率",
                            ),
                            width="stretch",
                        )
                with col2:
                    if "ROE (%)" in chart_df.columns:
                        st.plotly_chart(
                            px.bar(chart_df, x="Year", y="ROE (%)", title="ROE"),
                            width="stretch",
                        )
                    fcf_col = CHART_MONEY_YI["FCF"]
                    if fcf_col in chart_df.columns:
                        st.plotly_chart(
                            px.bar(chart_df, x="Year", y=fcf_col, title=fcf_col),
                            width="stretch",
                        )

        with st.expander("原始數值（元 · 除錯用）"):
            st.dataframe(
                metrics_raw.reset_index(),
                width="stretch",
                hide_index=True,
            )
