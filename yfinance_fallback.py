"""Yahoo Finance 備援（雲端主機無法連 MOPS 時使用）。"""

from __future__ import annotations

import numpy as np
import pandas as pd
import yfinance as yf

from indicator_calculation import REQUIRED_METRIC_COLUMNS


def _col_year(col: object) -> int | None:
    try:
        return int(pd.Timestamp(col).year)
    except Exception:
        text = str(col)[:4]
        return int(text) if text.isdigit() else None


def _row_value(df: pd.DataFrame, labels: list[str]) -> float | None:
    if df is None or df.empty:
        return None
    index_map = {str(i).strip().lower(): i for i in df.index}
    for label in labels:
        key = label.strip().lower()
        if key in index_map:
            val = df.loc[index_map[key]].iloc[0]
            try:
                f = float(val)
                return f if not np.isnan(f) else None
            except (TypeError, ValueError):
                return None
    return None


def _value_for_year(df: pd.DataFrame, year: int, labels: list[str]) -> float | None:
    if df is None or df.empty:
        return None
    for col in df.columns:
        y = _col_year(col)
        if y == year:
            slice_df = df[[col]]
            return _row_value(slice_df, labels)
    return None


def fetch_metrics_yfinance(security_code: str, years: list[int]) -> pd.DataFrame:
    """由 Yahoo Finance 組出與主 app 相近的年度指標表。"""
    ticker = yf.Ticker(f"{security_code}.TW")
    income = ticker.financials
    balance = ticker.balance_sheet
    cashflow = ticker.cashflow

    records: list[dict[str, float | int]] = []
    for year in sorted(years):
        revenue = _value_for_year(
            income, year, ["Total Revenue", "Operating Revenue"]
        )
        gross = _value_for_year(income, year, ["Gross Profit"])
        operating = _value_for_year(
            income, year, ["Operating Income", "EBIT", "Operating Revenue"]
        )
        net_income = _value_for_year(
            income, year, ["Net Income", "Net Income Common Stockholders"]
        )
        assets = _value_for_year(balance, year, ["Total Assets"])
        liabilities = _value_for_year(
            balance, year, ["Total Liabilties", "Total Liabilities Net Minority Interest"]
        )
        equity = _value_for_year(
            balance, year, ["Stockholders Equity", "Total Equity Gross Minority Interest"]
        )
        current_assets = _value_for_year(balance, year, ["Current Assets"])
        current_liab = _value_for_year(balance, year, ["Current Liabilities"])
        inventories = _value_for_year(balance, year, ["Inventory"])
        op_cf = _value_for_year(
            cashflow, year, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"]
        )
        capex = _value_for_year(
            cashflow,
            year,
            ["Capital Expenditure", "Capital Expenditures"],
        )

        if all(
            v is None
            for v in (revenue, gross, net_income, assets, equity, op_cf)
        ):
            continue

        capex_abs = abs(capex) if capex is not None and not np.isnan(capex) else np.nan
        if capex is None or np.isnan(capex_abs):
            fcf = op_cf if op_cf is not None else np.nan
        else:
            fcf = (op_cf if op_cf is not None else np.nan) - capex_abs

        def pct(num: float | None, den: float | None) -> float:
            if num is None or den is None or den == 0 or np.isnan(num) or np.isnan(den):
                return np.nan
            return float(num) / float(den) * 100

        def ratio(num: float | None, den: float | None) -> float:
            if num is None or den is None or den == 0 or np.isnan(num) or np.isnan(den):
                return np.nan
            return float(num) / float(den)

        quick_assets = (
            (current_assets - inventories)
            if current_assets is not None and inventories is not None
            else np.nan
        )

        records.append(
            {
                "Year": year,
                "EPS_Growth_Rate": np.nan,
                "Gross_Margin": pct(gross, revenue),
                "Operating_Margin": pct(operating, revenue),
                "ROE": pct(net_income, equity),
                "FCF": fcf,
                "Debt_Ratio": pct(liabilities, assets),
                "Current_Ratio": ratio(current_assets, current_liab),
                "Quick_Ratio": ratio(quick_assets, current_liab),
                "RND_Ratio": np.nan,
                "OperatingCashflow": op_cf if op_cf is not None else np.nan,
                "_NetIncome": net_income,
            }
        )

    if not records:
        return pd.DataFrame(columns=REQUIRED_METRIC_COLUMNS)

    metrics = pd.DataFrame(records).sort_values("Year").reset_index(drop=True)
    eps_proxy = metrics.get("_NetIncome")
    if eps_proxy is not None:
        metrics["EPS_Growth_Rate"] = eps_proxy.pct_change(fill_method=None) * 100
    metrics = metrics.drop(columns=["_NetIncome"], errors="ignore")
    metrics = metrics.set_index("Year")
    for col in REQUIRED_METRIC_COLUMNS:
        if col not in metrics.columns:
            metrics[col] = np.nan
    return metrics[REQUIRED_METRIC_COLUMNS]
