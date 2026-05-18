"""Streamlit Community Cloud 財報分析（MOPS 真實資料，獨立子專案）."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from config import YEARS
from financial_scraping import (
    fetch_balance_sheet,
    fetch_cashflow_statement,
    fetch_income_statement,
)
from indicator_calculation import compute_full_metrics

st.set_page_config(
    page_title="台股財報分析",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

METRIC_LABELS: dict[str, str] = {
    "EPS_Growth_Rate": "EPS 年成長率 (%)",
    "Gross_Margin": "毛利率 (%)",
    "Operating_Margin": "營業利益率 (%)",
    "ROE": "ROE (%)",
    "FCF": "自由現金流",
    "Debt_Ratio": "負債比 (%)",
    "Current_Ratio": "流動比",
    "Quick_Ratio": "速動比",
    "RND_Ratio": "研發費用率 (%)",
    "OperatingCashflow": "營業現金流",
}


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_data(symbol: str, years: tuple[int, ...]) -> dict:
    """自公開資訊觀測站（MOPS）抓取年度財報並計算指標。"""
    code = symbol.strip()
    year_list = sorted(int(y) for y in years)
    if not code or not year_list:
        return {"ok": False, "error": "請輸入股票代號並選擇至少一個年度。"}

    try:
        income = fetch_income_statement(code, year_list)
        balance = fetch_balance_sheet(code, year_list)
        cashflow = fetch_cashflow_statement(code, year_list)
        metrics = compute_full_metrics(income, balance, cashflow)
    except Exception as exc:
        return {"ok": False, "error": f"抓取或計算失敗：{exc}"}

    if metrics.empty or metrics.dropna(how="all").empty:
        return {
            "ok": False,
            "error": (
                f"未取得 {code} 在 {year_list} 的可用財報。"
                "請確認代號正確（上市櫃四碼），或稍後再試。"
            ),
        }

    metrics = metrics.copy()
    metrics.index.name = "Year"
    display = metrics.rename(columns=METRIC_LABELS)

    return {
        "ok": True,
        "symbol": code,
        "years": year_list,
        "source": "MOPS（mopsov.twse.com.tw）年度季報",
        "metrics": display.reset_index().to_dict(orient="records"),
        "metrics_columns": list(display.reset_index().columns),
    }


st.title("台股財報分析")
st.caption(
    "資料來源：公開資訊觀測站 MOPS · 獨立 Cloud 版 · "
    "本機主專案完整功能請用 `start_hub`（8501）"
)

with st.sidebar:
    st.subheader("年度範圍")
    min_y, max_y = min(YEARS), max(YEARS)
    year_start, year_end = st.slider(
        "西元年",
        min_value=min_y,
        max_value=max_y,
        value=(max(min_y, max_y - 3), max_y),
    )
    selected_years = tuple(y for y in YEARS if year_start <= y <= year_end)

symbol = st.text_input("股票代號", value="2330", max_chars=6).strip().upper()

if not symbol:
    st.warning("請輸入股票代號。")
else:
    with st.spinner(f"正在從 MOPS 取得 {symbol}（{year_start}–{year_end}）…"):
        result = fetch_stock_data(symbol, selected_years)

    if not result.get("ok"):
        st.error(result.get("error", "無法取得資料"))
    else:
        st.success(f"已載入 {result['symbol']} · {result['source']}")
        metrics_df = pd.DataFrame(result["metrics"])

        tab_table, tab_chart = st.tabs(["指標表", "趨勢圖"])

        with tab_table:
            st.dataframe(metrics_df, use_container_width=True, hide_index=True)

        with tab_chart:
            if metrics_df.empty:
                st.info("無可繪圖資料。")
            else:
                chart_df = metrics_df.set_index("Year")
                col1, col2 = st.columns(2)
                with col1:
                    if "EPS 年成長率 (%)" in chart_df.columns:
                        fig = px.line(
                            chart_df.reset_index(),
                            x="Year",
                            y="EPS 年成長率 (%)",
                            markers=True,
                            title="EPS 年成長率",
                        )
                        st.plotly_chart(fig, use_container_width=True)
                    if "毛利率 (%)" in chart_df.columns:
                        fig2 = px.line(
                            chart_df.reset_index(),
                            x="Year",
                            y=["毛利率 (%)", "營業利益率 (%)"],
                            markers=True,
                            title="毛利率 / 營業利益率",
                        )
                        st.plotly_chart(fig2, use_container_width=True)
                with col2:
                    if "ROE (%)" in chart_df.columns:
                        fig3 = px.bar(
                            chart_df.reset_index(),
                            x="Year",
                            y="ROE (%)",
                            title="ROE",
                        )
                        st.plotly_chart(fig3, use_container_width=True)
                    if "自由現金流" in chart_df.columns:
                        fig4 = px.bar(
                            chart_df.reset_index(),
                            x="Year",
                            y="自由現金流",
                            title="自由現金流",
                        )
                        st.plotly_chart(fig4, use_container_width=True)

        with st.expander("原始 JSON（除錯用）"):
            st.json(result)
