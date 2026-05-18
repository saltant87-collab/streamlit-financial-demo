"""顯示用：金額統一為新台幣「元」、表格格式化、來源說明文案。"""

from __future__ import annotations

import re

import pandas as pd
import streamlit as st

from indicator_calculation import REQUIRED_METRIC_COLUMNS

MONEY_COLUMNS = ("FCF", "OperatingCashflow")
PCT_COLUMNS = (
    "EPS_Growth_Rate",
    "Gross_Margin",
    "Operating_Margin",
    "ROE",
    "Debt_Ratio",
    "RND_Ratio",
)
RATIO_COLUMNS = ("Current_Ratio", "Quick_Ratio")

METRIC_LABELS: dict[str, str] = {
    "EPS_Growth_Rate": "EPS 年成長率 (%)",
    "Gross_Margin": "毛利率 (%)",
    "Operating_Margin": "營業利益率 (%)",
    "ROE": "ROE (%)",
    "FCF": "自由現金流（億元）",
    "Debt_Ratio": "負債比 (%)",
    "Current_Ratio": "流動比",
    "Quick_Ratio": "速動比",
    "RND_Ratio": "研發費用率 (%)",
    "OperatingCashflow": "營業現金流（億元）",
}


def normalize_money_to_ntd(metrics: pd.DataFrame, source_kind: str) -> pd.DataFrame:
    """MOPS 抓取值多為千元；Yahoo 多為元。統一成新台幣「元」供比較與顯示。"""
    if metrics.empty:
        return metrics
    out = metrics.copy()
    if source_kind == "mops":
        for col in MONEY_COLUMNS:
            if col in out.columns:
                out[col] = out[col] * 1000.0
    return out


def format_ntd_yi(value: object) -> str:
    """元 → 億元字串（與台股習慣一致）。"""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return "—"
    if pd.isna(num):
        return "—"
    return f"{num / 1e8:,.2f}"


def format_pct(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return "—"
    if pd.isna(num):
        return "—"
    return f"{num:.2f}"


def format_ratio(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    try:
        num = float(value)
    except (TypeError, ValueError):
        return "—"
    if pd.isna(num):
        return "—"
    return f"{num:.2f}"


def metrics_for_display(metrics: pd.DataFrame) -> pd.DataFrame:
    """數值表 → 易讀字串表（圖表仍用原始數值）。"""
    if metrics.empty:
        return metrics
    out = metrics.copy()
    out.index.name = "Year"
    out = out.reset_index()
    for col in PCT_COLUMNS:
        if col in out.columns:
            out[METRIC_LABELS[col]] = out[col].map(format_pct)
            out = out.drop(columns=[col])
    for col in RATIO_COLUMNS:
        if col in out.columns:
            out[METRIC_LABELS[col]] = out[col].map(format_ratio)
            out = out.drop(columns=[col])
    for col in MONEY_COLUMNS:
        if col in out.columns:
            out[METRIC_LABELS[col]] = out[col].map(format_ntd_yi)
            out = out.drop(columns=[col])
    if "Year" not in out.columns and out.index.name == "Year":
        out = out.reset_index()
    return out


def source_banner(source_kind: str) -> tuple[str, str]:
    """回傳 (訊息, streamlit 語意：success | warning | info)。"""
    if source_kind == "mops":
        return (
            "**資料來源：MOPS（公開資訊觀測站）** — 與本機 `start_hub` / 8501 相同口徑；"
            "金額已統一顯示為**新台幣億元**（MOPS 千元 ×1000 換算）。",
            "success",
        )
    return (
        "**資料來源：Yahoo Finance 備援** — 與本機 MOPS **數字可能不同**（會計年度、預估年、單位皆可能差異）。"
        "若要以**台股年報為準**，請在 Mac 執行 `start_hub.command` 後開 **8501** 完整版。"
        "本頁金額欄已統一為**新台幣億元**僅供對照參考。",
        "warning",
    )


def chart_column_map() -> dict[str, str]:
    """圖表用欄位（數值、未格式化）。"""
    return {METRIC_LABELS[k]: k for k in METRIC_LABELS}


def _md_bold_to_html(text: str) -> str:
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)


def render_source_banner(text: str, level: str) -> None:
    """左對齊、貼齊主內容區左緣的來源說明（取代置中的 st.warning）。"""
    styles = {
        "warning": ("#fffbeb", "#78350f", "#f59e0b"),
        "success": ("#ecfdf5", "#065f46", "#10b981"),
        "info": ("#eff6ff", "#1e3a8a", "#3b82f6"),
    }
    bg, color, border = styles.get(level, styles["info"])
    html = _md_bold_to_html(text)
    st.markdown(
        f'<div class="fin-source-banner" style="background:{bg};color:{color};'
        f"border-left:4px solid {border};padding:12px 16px;margin:0 0 12px 0;"
        f"border-radius:6px;text-align:left;width:100%;max-width:100%;"
        f'box-sizing:border-box;font-size:0.95rem;line-height:1.6;">{html}</div>',
        unsafe_allow_html=True,
    )


def inject_layout_css() -> None:
    """主區提示框靠左、不置中。"""
    st.markdown(
        """
<style>
  div[data-testid="stAlert"] {
    width: 100% !important;
    max-width: 100% !important;
    margin-left: 0 !important;
    margin-right: 0 !important;
  }
  div[data-testid="stAlert"] > div {
    justify-content: flex-start !important;
    text-align: left !important;
  }
  .fin-source-banner {
    display: block;
    text-align: left !important;
  }
</style>
        """,
        unsafe_allow_html=True,
    )
