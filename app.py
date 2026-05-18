"""Streamlit Community Cloud 財報分析（MOPS + Yahoo 備援）."""

from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from config import YEARS
from data_fetch import fetch_stock_data_auto

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

# 年度報告通常落後約 1 年；預設不選「可能尚無年報」的最近年
_REPORT_CAP = min(max(YEARS), date.today().year - 1)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_stock_data(symbol: str, years: tuple[int, ...]) -> dict:
    code = symbol.strip()
    year_list = sorted(int(y) for y in years)
    if not code or not year_list:
        return {"ok": False, "error": "請輸入股票代號並選擇至少一個年度。"}
    return fetch_stock_data_auto(code, year_list)


def _package_result(raw: dict) -> dict:
    if not raw.get("ok"):
        return raw
    metrics = raw["metrics"].copy()
    metrics.index.name = "Year"
    display = metrics.rename(columns=METRIC_LABELS)
    out = {
        "ok": True,
        "symbol": raw.get("symbol", ""),
        "source": raw["source"],
        "metrics": display.reset_index().to_dict(orient="records"),
        "notes": raw.get("notes") or [],
    }
    return out


st.title("台股財報分析")
st.caption(
    "優先 MOPS · 雲端連線失敗時改 Yahoo Finance · "
    "本機完整版請用 `start_hub`（8501）"
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
    st.caption(f"建議查詢至 {_REPORT_CAP} 年（年報通常尚未含更新年度）")

symbol = st.text_input("股票代號", value="2330", max_chars=6).strip().upper()

if not symbol:
    st.warning("請輸入股票代號。")
else:
    with st.spinner(f"正在取得 {symbol}（{year_start}–{year_end}）…"):
        raw = fetch_stock_data(symbol, selected_years)
        raw["symbol"] = symbol
        result = _package_result(raw)

    if not result.get("ok"):
        st.error(result.get("error", "無法取得資料"))
        for note in result.get("notes") or []:
            st.caption(note)
    else:
        st.success(f"已載入 {symbol} · {result['source']}")
        for note in result.get("notes") or []:
            st.info(note)
        metrics_df = pd.DataFrame(result["metrics"])

        tab_table, tab_chart = st.tabs(["指標表", "趨勢圖"])

        with tab_table:
            st.dataframe(metrics_df, width="stretch", hide_index=True)

        with tab_chart:
            if metrics_df.empty:
                st.info("無可繪圖資料。")
            else:
                chart_df = metrics_df.set_index("Year")
                col1, col2 = st.columns(2)
                with col1:
                    if "EPS 年成長率 (%)" in chart_df.columns:
                        st.plotly_chart(
                            px.line(
                                chart_df.reset_index(),
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
                                chart_df.reset_index(),
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
                            px.bar(chart_df.reset_index(), x="Year", y="ROE (%)", title="ROE"),
                            width="stretch",
                        )
                    if "自由現金流" in chart_df.columns:
                        st.plotly_chart(
                            px.bar(
                                chart_df.reset_index(),
                                x="Year",
                                y="自由現金流",
                                title="自由現金流",
                            ),
                            width="stretch",
                        )

        with st.expander("原始 JSON（除錯用）"):
            st.json(result)
