"""整合 MOPS 與 Yahoo Finance 備援。"""

from __future__ import annotations

import pandas as pd

from financial_scraping import (
    fetch_balance_sheet,
    fetch_cashflow_statement,
    fetch_income_statement,
)
from indicator_calculation import compute_full_metrics
from yfinance_fallback import fetch_metrics_yfinance


def _usable_metrics(metrics: pd.DataFrame) -> pd.DataFrame:
    if metrics.empty:
        return metrics
    return metrics.dropna(how="all")


def _mops_has_any_data(
    income: dict[int, pd.DataFrame],
    balance: dict[int, pd.DataFrame],
    cashflow: dict[int, pd.DataFrame],
) -> bool:
    for bucket in (income, balance, cashflow):
        for df in bucket.values():
            if df is not None and not df.empty:
                return True
    return False


def fetch_stock_data_mops(code: str, year_list: list[int]) -> tuple[pd.DataFrame, str]:
    income = fetch_income_statement(code, year_list)
    balance = fetch_balance_sheet(code, year_list)
    cashflow = fetch_cashflow_statement(code, year_list)
    if not _mops_has_any_data(income, balance, cashflow):
        return pd.DataFrame(), "MOPS 無回應資料"
    metrics = _usable_metrics(compute_full_metrics(income, balance, cashflow))
    if metrics.empty:
        return pd.DataFrame(), "MOPS 有回應但無法解析指標"
    return metrics, "MOPS（mopsov.twse.com.tw）年度財報"


def fetch_stock_data_auto(code: str, year_list: list[int]) -> dict:
    """先 MOPS，失敗則 Yahoo Finance（適合 Streamlit Cloud 美國主機）。"""
    notes: list[str] = []
    try:
        metrics, source = fetch_stock_data_mops(code, year_list)
        if not metrics.empty:
            return {"ok": True, "metrics": metrics, "source": source, "notes": notes}
        notes.append(source)
    except Exception as exc:
        notes.append(f"MOPS 例外：{exc}")

    try:
        yf_metrics = _usable_metrics(fetch_metrics_yfinance(code, year_list))
        if not yf_metrics.empty:
            notes.append("MOPS 無法使用時已改以 Yahoo Finance 備援。")
            return {
                "ok": True,
                "metrics": yf_metrics,
                "source": "Yahoo Finance（yfinance · 2330.TW 等）",
                "notes": notes,
            }
        notes.append("Yahoo Finance 亦無可用年度資料。")
    except Exception as exc:
        notes.append(f"Yahoo Finance 例外：{exc}")

    return {
        "ok": False,
        "error": (
            f"未取得 {code} 在 {year_list} 的可用財報。"
            "請確認為上市櫃四碼；若在本機可、雲端不行，多為 MOPS 限制海外 IP。"
        ),
        "notes": notes,
    }
