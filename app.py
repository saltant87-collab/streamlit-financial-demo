"""Streamlit Community Cloud 財報分析範例（獨立子專案，非主專案 app）."""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="財報分析範例",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(ttl=3600)
def fetch_stock_data(symbol: str) -> dict | None:
    """取得股票財報相關資料（範例 placeholder）。"""
    # TODO: 接上真實財報資料來源（例如 MOPS、yfinance 或內部 API）
    _ = symbol
    return None


st.title("台股財報分析範例")
st.caption("獨立 Community Cloud 示範 · 資料來源尚未接上 · 本機請用 **8502**（主專案財報用 8501）")

symbol = st.text_input("股票代號", value="2330", max_chars=6).strip().upper()

if not symbol:
    st.warning("請輸入股票代號。")
else:
    with st.spinner(f"正在取得 {symbol} 的資料…"):
        data = fetch_stock_data(symbol)

    if data is None:
        st.error("目前是範例 API，之後要換成真實財報資料來源")
        st.info(
            f"已輸入代號：**{symbol}**。請在 `fetch_stock_data()` 內實作真實抓取邏輯。"
        )
    else:
        st.success(f"已取得 {symbol} 的資料")
        st.json(data)
