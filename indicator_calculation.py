"""Financial indicator calculation module for Taiwan annual statements."""

from __future__ import annotations

from typing import Iterable

import numpy as np
import pandas as pd

REQUIRED_METRIC_COLUMNS: list[str] = [
    "EPS_Growth_Rate",
    "Gross_Margin",
    "Operating_Margin",
    "ROE",
    "FCF",
    "Debt_Ratio",
    "Current_Ratio",
    "Quick_Ratio",
    "RND_Ratio",
    "OperatingCashflow",
]

CANDIDATE_MAP: dict[str, list[str]] = {
    "Revenue": ["營業收入", "營收淨額", "收入合計"],
    "GrossProfit": ["營業毛利", "營業毛利（毛損）", "營業毛利（毛損）淨額"],
    "OperatingIncome": ["營業利益", "營業淨利"],
    "NetIncome": ["稅後淨利", "本期淨利", "本期淨利（淨損）", "本期稅後淨利"],
    "EPS": ["基本每股盈餘", "每股盈餘", "EPS"],
    "RNDExpense": ["研究發展費用", "研發費用", "研究發展支出"],
    "TotalAssets": ["資產總額", "資產總計"],
    "TotalLiabilities": ["負債總額", "負債總計"],
    "CurrentAssets": ["流動資產"],
    "CurrentLiabilities": ["流動負債"],
    "Inventories": ["存貨", "存貨淨額"],
    "Equity": ["股東權益", "權益總額", "權益總計", "母公司業主權益"],
    "OperatingCashflow": [
        "營業活動現金流量",
        "營業活動之淨現金流入（流出）",
        "營業活動之淨現金流入",
        "營業活動之淨現金流出",
    ],
    "Capex": [
        "取得不動產、廠房及設備",
        "購置不動產、廠房及設備",
        "取得不動產、設備",
        "資本支出",
        "投資活動之淨現金流入（流出）",
    ],
}


def _normalize_text(text: object) -> str:
    """Normalize text for robust keyword matching."""
    value = str(text) if text is not None else ""
    value = value.replace("　", "").replace(" ", "").replace("\n", "")
    return value.lower()


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten MultiIndex columns into single-level strings."""
    table = df.copy()
    if isinstance(table.columns, pd.MultiIndex):
        table.columns = [
            "_".join([str(level) for level in col if str(level) != "nan"]).strip("_")
            for col in table.columns
        ]
    table.columns = [str(col).strip() for col in table.columns]
    return table


def _find_first_match(df: pd.DataFrame, candidates: list[str]) -> str | None:
    """Find first matching column name or row-label source column."""
    if df.empty:
        return None

    table = _flatten_columns(df)
    normalized_candidates = [_normalize_text(item) for item in candidates]

    for col in table.columns:
        col_text = _normalize_text(col)
        if any(candidate in col_text for candidate in normalized_candidates):
            return str(col)

    first_col = str(table.columns[0])
    first_col_values = table.iloc[:, 0].astype(str).fillna("")
    for value in first_col_values:
        row_text = _normalize_text(value)
        if any(candidate in row_text for candidate in normalized_candidates):
            return first_col
    return None


def _extract_numeric(series: pd.Series) -> pd.Series:
    """Convert mixed-format text values into numeric values."""
    text_series = series.astype(str).str.strip()
    text_series = text_series.str.replace("−", "-", regex=False)
    text_series = text_series.str.replace("，", ",", regex=False)
    text_series = text_series.str.replace("%", "", regex=False)

    is_negative_parentheses = text_series.str.match(r"^\(.*\)$")
    text_series = text_series.str.replace("(", "", regex=False).str.replace(")", "", regex=False)
    text_series = text_series.str.replace(",", "", regex=False)
    text_series = text_series.str.replace("--", "", regex=False)
    text_series = text_series.str.replace("N/A", "", regex=False)
    text_series = text_series.str.replace(r"[^\d\.\-]", "", regex=True)

    numeric = pd.to_numeric(text_series, errors="coerce")
    numeric = numeric.where(~is_negative_parentheses, -numeric.abs())
    return numeric


def _pick_last_numeric(values: Iterable[object]) -> float | None:
    """Return the last numeric value from an iterable."""
    numeric_series = _extract_numeric(pd.Series(list(values)))
    valid = numeric_series.dropna()
    if valid.empty:
        return None
    return float(valid.iloc[-1])


def _safe_get_value(
    df: pd.DataFrame,
    row_keywords: list[str],
    col_keywords: list[str] | None = None,
) -> float | None:
    """Safely get a value from statement table by row/column keywords."""
    if df.empty:
        return None

    table = _flatten_columns(df).dropna(how="all").dropna(axis=1, how="all")
    if table.empty:
        return None

    first_col_name = str(table.columns[0])
    row_source_col = _find_first_match(table[[first_col_name]], row_keywords)
    if row_source_col is None:
        matched_col = _find_first_match(table, row_keywords)
        if matched_col is None:
            return None
        values = table[matched_col]
        numeric = _extract_numeric(values).dropna()
        return float(numeric.iloc[-1]) if not numeric.empty else None

    row_labels = table[first_col_name].astype(str).fillna("").map(_normalize_text)
    normalized_keywords = [_normalize_text(keyword) for keyword in row_keywords]
    row_mask = row_labels.map(lambda value: any(keyword in value for keyword in normalized_keywords))
    if not row_mask.any():
        return None

    target_row = table.loc[row_mask].iloc[0]

    if col_keywords:
        matched_col = _find_first_match(table, col_keywords)
        if matched_col and matched_col in table.columns:
            value = _extract_numeric(pd.Series([target_row[matched_col]])).iloc[0]
            return None if pd.isna(value) else float(value)

    row_values = target_row.iloc[1:] if len(target_row) > 1 else target_row.iloc[:1]
    return _pick_last_numeric(row_values.tolist())


def _normalize_year_df_dict(
    data: dict[int, pd.DataFrame],
    aligned_years: list[int] | None = None,
) -> dict[int, pd.DataFrame]:
    """Normalize yearly dict keys and align missing years with empty DataFrame."""
    normalized: dict[int, pd.DataFrame] = {}
    for key, value in data.items():
        try:
            year_key = int(key)
        except Exception:
            continue
        normalized[year_key] = value if isinstance(value, pd.DataFrame) else pd.DataFrame()

    if aligned_years is None:
        aligned_years = sorted(normalized.keys())
    return {year: normalized.get(year, pd.DataFrame()) for year in aligned_years}


def _safe_div(numerator: float | None, denominator: float | None, as_percent: bool = True) -> float:
    """Safely divide two scalar values."""
    if numerator is None or denominator is None:
        return np.nan
    if pd.isna(numerator) or pd.isna(denominator) or denominator == 0:
        return np.nan
    value = float(numerator) / float(denominator)
    return value * 100 if as_percent else value


def compute_full_metrics(
    income_dict: dict[int, pd.DataFrame],
    balance_dict: dict[int, pd.DataFrame],
    cashflow_dict: dict[int, pd.DataFrame],
) -> pd.DataFrame:
    """Compute annual financial indicators for app consumption."""
    all_years = sorted(set(income_dict.keys()) | set(balance_dict.keys()) | set(cashflow_dict.keys()))
    if not all_years:
        return pd.DataFrame(columns=REQUIRED_METRIC_COLUMNS, index=pd.Index([], name="Year"))

    income_norm = _normalize_year_df_dict(income_dict, all_years)
    balance_norm = _normalize_year_df_dict(balance_dict, all_years)
    cashflow_norm = _normalize_year_df_dict(cashflow_dict, all_years)

    records: list[dict[str, float | int]] = []
    for year in all_years:
        income_df = income_norm[year]
        balance_df = balance_norm[year]
        cashflow_df = cashflow_norm[year]

        revenue = _safe_get_value(income_df, CANDIDATE_MAP["Revenue"])
        gross_profit = _safe_get_value(income_df, CANDIDATE_MAP["GrossProfit"])
        operating_income = _safe_get_value(income_df, CANDIDATE_MAP["OperatingIncome"])
        net_income = _safe_get_value(income_df, CANDIDATE_MAP["NetIncome"])
        eps = _safe_get_value(income_df, CANDIDATE_MAP["EPS"])
        rnd_expense = _safe_get_value(income_df, CANDIDATE_MAP["RNDExpense"])

        total_assets = _safe_get_value(balance_df, CANDIDATE_MAP["TotalAssets"])
        total_liabilities = _safe_get_value(balance_df, CANDIDATE_MAP["TotalLiabilities"])
        current_assets = _safe_get_value(balance_df, CANDIDATE_MAP["CurrentAssets"])
        current_liabilities = _safe_get_value(balance_df, CANDIDATE_MAP["CurrentLiabilities"])
        inventories = _safe_get_value(balance_df, CANDIDATE_MAP["Inventories"])
        equity = _safe_get_value(balance_df, CANDIDATE_MAP["Equity"])

        operating_cashflow = _safe_get_value(cashflow_df, CANDIDATE_MAP["OperatingCashflow"])
        capex_raw = _safe_get_value(cashflow_df, CANDIDATE_MAP["Capex"])
        capex_abs = abs(capex_raw) if capex_raw is not None and not pd.isna(capex_raw) else np.nan

        if pd.isna(capex_abs):
            fcf = operating_cashflow if operating_cashflow is not None else np.nan
        else:
            fcf = (operating_cashflow if operating_cashflow is not None else np.nan) - capex_abs

        records.append(
            {
                "Year": year,
                "Revenue": revenue,
                "GrossProfit": gross_profit,
                "OperatingIncome": operating_income,
                "NetIncome": net_income,
                "EPS": eps,
                "DebtTotal": total_liabilities,
                "AssetsTotal": total_assets,
                "CurrentAssets": current_assets,
                "CurrentLiabilities": current_liabilities,
                "Inventories": inventories,
                "Equity": equity,
                "RNDExpense": rnd_expense,
                "OperatingCashflow": operating_cashflow,
                "FCF": fcf,
            }
        )

    metrics = pd.DataFrame(records).sort_values("Year").reset_index(drop=True)
    eps_proxy = metrics["EPS"].where(metrics["EPS"].notna(), metrics["NetIncome"])
    metrics["EPS_Growth_Rate"] = eps_proxy.pct_change(fill_method=None) * 100
    metrics["Gross_Margin"] = [
        _safe_div(n, d, as_percent=True) for n, d in zip(metrics["GrossProfit"], metrics["Revenue"])
    ]
    metrics["Operating_Margin"] = [
        _safe_div(n, d, as_percent=True) for n, d in zip(metrics["OperatingIncome"], metrics["Revenue"])
    ]
    metrics["ROE"] = [_safe_div(n, d, as_percent=True) for n, d in zip(metrics["NetIncome"], metrics["Equity"])]
    metrics["Debt_Ratio"] = [
        _safe_div(n, d, as_percent=True) for n, d in zip(metrics["DebtTotal"], metrics["AssetsTotal"])
    ]
    metrics["Current_Ratio"] = [
        _safe_div(n, d, as_percent=False)
        for n, d in zip(metrics["CurrentAssets"], metrics["CurrentLiabilities"])
    ]
    quick_assets = metrics["CurrentAssets"] - metrics["Inventories"]
    metrics["Quick_Ratio"] = [
        _safe_div(n, d, as_percent=False) for n, d in zip(quick_assets, metrics["CurrentLiabilities"])
    ]
    metrics["RND_Ratio"] = [
        _safe_div(n, d, as_percent=True) for n, d in zip(metrics["RNDExpense"], metrics["Revenue"])
    ]

    metrics = metrics.set_index("Year")
    for col in REQUIRED_METRIC_COLUMNS:
        if col not in metrics.columns:
            metrics[col] = np.nan
    return metrics[REQUIRED_METRIC_COLUMNS]


def compute_indicators(
    income_dict: dict[int, pd.DataFrame],
    balance_dict: dict[int, pd.DataFrame],
    cashflow_dict: dict[int, pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return chart-friendly subsets expected by current app flow."""
    full = compute_full_metrics(income_dict, balance_dict, cashflow_dict)
    primary = full[["EPS_Growth_Rate", "Gross_Margin", "Operating_Margin"]]
    roe = full[["ROE"]]
    fcf = full[["FCF"]]
    return primary, roe, fcf
