"""財報區塊：指標圖表（含解說）、風險提醒。"""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from chart_glossary import render_chart_with_help, render_term_panel
from indicator_calculation import REQUIRED_METRIC_COLUMNS
from screening import build_risk_alerts, evaluate_hard_conditions


def _plot_df(metrics_df: pd.DataFrame) -> pd.DataFrame:
    if metrics_df.empty:
        return metrics_df
    plot_df = metrics_df.reset_index()
    if "Year" not in plot_df.columns:
        plot_df = plot_df.rename(columns={plot_df.columns[0]: "Year"})
    return plot_df


def render_financial_charts(metrics_df: pd.DataFrame, *, show_help: bool = True) -> None:
    st.subheader("指標圖表")
    if metrics_df.empty:
        st.info("目前沒有可繪圖資料。")
        return

    plot_df = _plot_df(metrics_df)

    def _eps(col: Any) -> None:
        if plot_df["EPS_Growth_Rate"].dropna().empty:
            col.info("EPS 成長率：無有效資料。")
            return
        col.plotly_chart(
            px.line(plot_df, x="Year", y="EPS_Growth_Rate", markers=True, title="EPS 成長率"),
            width="stretch",
        )

    def _margin(col: Any) -> None:
        if plot_df[["Gross_Margin", "Operating_Margin"]].dropna(how="all").empty:
            col.info("毛利率與營業利益率：無有效資料。")
            return
        col.plotly_chart(
            px.line(
                plot_df,
                x="Year",
                y=["Gross_Margin", "Operating_Margin"],
                markers=True,
                title="毛利率與營業利益率",
            ),
            width="stretch",
        )

    def _roe(col: Any) -> None:
        if plot_df["ROE"].dropna().empty:
            col.info("ROE：無有效資料。")
            return
        col.plotly_chart(
            px.line(plot_df, x="Year", y="ROE", markers=True, title="ROE"),
            width="stretch",
        )

    def _fcf(col: Any) -> None:
        if plot_df["FCF"].dropna().empty:
            col.info("FCF：無有效資料。")
            return
        chart = plot_df.copy()
        chart["FCF_億"] = chart["FCF"] / 1e8
        col.plotly_chart(
            px.bar(chart, x="Year", y="FCF_億", title="自由現金流（億元）"),
            width="stretch",
        )

    if show_help:
        render_chart_with_help("eps_growth", _eps, st, show_help=True)
        render_chart_with_help("margins", _margin, st, show_help=True)
        render_chart_with_help("roe", _roe, st, show_help=True)
        render_chart_with_help("fcf", _fcf, st, show_help=True)
    else:
        c1, c2 = st.columns(2)
        _eps(c1)
        _margin(c1)
        _roe(c2)
        _fcf(c2)


def render_risk_section(metrics_df: pd.DataFrame, is_core: bool, *, show_help: bool = True) -> None:
    st.subheader("風險提醒")
    if show_help:
        render_term_panel("risk", st)
    if metrics_df.empty:
        st.info("沒有可用指標資料，暫時無法評估風險。")
        return

    try:
        risk_result = build_risk_alerts(metrics_df, is_core_asic_ip=is_core)
    except Exception as exc:
        st.error(f"風險評分失敗：{exc}")
        return

    alerts = risk_result.get("alerts", [])
    if isinstance(alerts, list) and alerts:
        for item in alerts:
            if not isinstance(item, tuple) or len(item) != 2:
                continue
            level, message = item
            if level == "error":
                st.error(str(message))
            else:
                st.warning(str(message))
    else:
        st.success("目前未觸發重大風險警示。")

    c1, c2, c3 = st.columns(3)
    c1.metric("risk_score", risk_result.get("risk_score", "N/A"))
    c2.metric("risk_level", risk_result.get("risk_level", "N/A"))
    c3.metric("moat_score", risk_result.get("moat_score", "N/A"))

    try:
        hard_pass, reasons = evaluate_hard_conditions(metrics_df)
        st.write(f"硬性條件檢查：{'通過' if hard_pass else '未通過'}")
        if reasons:
            st.caption("；".join(reasons))
    except Exception:
        pass


def render_metrics_table_raw(metrics_df: pd.DataFrame) -> None:
    st.subheader("關鍵指標（原始數值）")
    if metrics_df.empty:
        st.info("目前沒有可顯示的指標資料。")
        return
    data = metrics_df.copy()
    for col in REQUIRED_METRIC_COLUMNS:
        if col not in data.columns:
            data[col] = pd.NA
    st.dataframe(data[REQUIRED_METRIC_COLUMNS].round(2), width="stretch")
