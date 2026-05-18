"""Financial screening and risk scoring utilities."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

try:
    from config import STOCK_UNIVERSE
except Exception:
    STOCK_UNIVERSE = []


def _ensure_numeric_series(metrics_df: pd.DataFrame, column: str) -> pd.Series:
    """Return a numeric series for the specified column, or NaN series if missing."""
    if column not in metrics_df.columns:
        return pd.Series(index=metrics_df.index, dtype=float)
    return pd.to_numeric(metrics_df[column], errors="coerce")


def _last_valid(series: pd.Series) -> float:
    """Return the latest non-NaN value from a series."""
    valid = series.dropna()
    if valid.empty:
        return np.nan
    return float(valid.iloc[-1])


def _safe_tail(series: pd.Series, n: int) -> pd.Series:
    """Return the last n non-NaN values."""
    return series.dropna().tail(n)


def _lookup_stock_meta(code: str) -> dict[str, str]:
    """Lookup stock metadata from config.STOCK_UNIVERSE."""
    for stock in STOCK_UNIVERSE:
        if str(stock.get("code", "")) == str(code):
            return {
                "code": str(stock.get("code", code)),
                "name": str(stock.get("name", "")),
                "role": str(stock.get("role", "")),
                "category": str(stock.get("category", "")),
                "tier": str(stock.get("tier", "")),
            }
    return {"code": code, "name": "", "role": "", "category": "", "tier": ""}


def _evaluate_hard_conditions_internal(
    metrics_df: pd.DataFrame,
    is_core_asic_ip: bool = False,
) -> tuple[bool, list[str]]:
    """Evaluate hard conditions with optional core ASIC/IP relaxation."""
    reasons: list[str] = []
    if metrics_df.empty:
        return False, ["缺少指標資料"]

    ocf_series = _ensure_numeric_series(metrics_df, "OperatingCashflow")
    fcf_series = _ensure_numeric_series(metrics_df, "FCF")
    roe_series = _ensure_numeric_series(metrics_df, "ROE")
    debt_series = _ensure_numeric_series(metrics_df, "Debt_Ratio")
    current_ratio_series = _ensure_numeric_series(metrics_df, "Current_Ratio")
    gross_margin_series = _ensure_numeric_series(metrics_df, "Gross_Margin")
    eps_growth_series = _ensure_numeric_series(metrics_df, "EPS_Growth_Rate")

    ocf_tail = _safe_tail(ocf_series, 3)
    if len(ocf_tail) < 2:
        reasons.append("營業現金流資料不足")
    else:
        need_positive_years = 2 if not is_core_asic_ip else 1
        positive_years = int((ocf_tail > 0).sum())
        if positive_years < need_positive_years:
            reasons.append("近3年營業現金流為正年度不足")

    fcf_tail = _safe_tail(fcf_series, 3)
    if len(fcf_tail) < 2:
        reasons.append("自由現金流資料不足")
    else:
        need_positive_years = 2 if not is_core_asic_ip else 1
        positive_years = int((fcf_tail > 0).sum())
        if positive_years < need_positive_years:
            reasons.append("近3年自由現金流為正年度不足")

    latest_roe = _last_valid(roe_series)
    roe_floor = 8.0 if not is_core_asic_ip else 6.0
    if pd.isna(latest_roe):
        reasons.append("缺少 ROE")
    elif latest_roe < roe_floor:
        reasons.append(f"最新年度 ROE 低於門檻({roe_floor:.0f}%)")

    latest_debt = _last_valid(debt_series)
    debt_cap = 70.0 if not is_core_asic_ip else 75.0
    if pd.isna(latest_debt):
        reasons.append("缺少負債比")
    elif latest_debt > debt_cap:
        reasons.append(f"最新年度負債比高於上限({debt_cap:.0f}%)")

    latest_current_ratio = _last_valid(current_ratio_series)
    current_ratio_floor = 1.0 if not is_core_asic_ip else 0.9
    if pd.isna(latest_current_ratio):
        reasons.append("缺少流動比率")
    elif latest_current_ratio < current_ratio_floor:
        reasons.append(f"最新年度流動比率低於下限({current_ratio_floor:.1f})")

    latest_gross_margin = _last_valid(gross_margin_series)
    if pd.isna(latest_gross_margin):
        reasons.append("毛利率缺值，暫無法完整評估")
    elif latest_gross_margin < 15.0:
        reasons.append("最新年度毛利率低於常見下限(15%)")

    eps_tail = _safe_tail(eps_growth_series, 3)
    if len(eps_tail) >= 2 and (eps_tail < 0).all():
        reasons.append("EPS 成長率連續為負")

    return len(reasons) == 0, reasons


def evaluate_hard_conditions(metrics_df: pd.DataFrame) -> tuple[bool, list[str]]:
    """Return whether the stock passes hard conditions and reasons if not."""
    return _evaluate_hard_conditions_internal(metrics_df, is_core_asic_ip=False)


def _compute_moat_adjustment(metrics_df: pd.DataFrame, is_core_asic_ip: bool) -> float:
    """Compute moat score adjustment from key quality signals."""
    gross_margin = _ensure_numeric_series(metrics_df, "Gross_Margin")
    roe = _ensure_numeric_series(metrics_df, "ROE")
    ocf = _ensure_numeric_series(metrics_df, "OperatingCashflow")

    score = 0.0
    gm_avg = _safe_tail(gross_margin, 3).mean()
    roe_avg = _safe_tail(roe, 3).mean()
    ocf_positive_ratio = (_safe_tail(ocf, 3) > 0).mean() if not _safe_tail(ocf, 3).empty else 0.0

    if pd.notna(gm_avg) and gm_avg >= 35:
        score += 12
    elif pd.notna(gm_avg) and gm_avg >= 25:
        score += 6

    if pd.notna(roe_avg) and roe_avg >= 15:
        score += 10
    elif pd.notna(roe_avg) and roe_avg >= 10:
        score += 5

    score += float(ocf_positive_ratio) * 8

    if is_core_asic_ip and pd.notna(gm_avg) and pd.notna(roe_avg) and gm_avg >= 35 and roe_avg >= 15 and ocf_positive_ratio >= 0.67:
        score += 10

    return score


def build_risk_alerts(metrics_df: pd.DataFrame, is_core_asic_ip: bool = False) -> dict[str, Any]:
    """Build risk alerts, risk score, risk level, and moat score."""
    alerts: list[tuple[str, str]] = []
    if metrics_df.empty:
        return {
            "alerts": [("error", "缺少指標資料，無法評估風險")],
            "risk_score": 100,
            "risk_level": "高",
            "moat_score": 0,
        }

    debt_ratio = _ensure_numeric_series(metrics_df, "Debt_Ratio")
    operating_cashflow = _ensure_numeric_series(metrics_df, "OperatingCashflow")
    fcf = _ensure_numeric_series(metrics_df, "FCF")
    roe = _ensure_numeric_series(metrics_df, "ROE")
    gross_margin = _ensure_numeric_series(metrics_df, "Gross_Margin")
    eps_growth = _ensure_numeric_series(metrics_df, "EPS_Growth_Rate")
    rnd_ratio = _ensure_numeric_series(metrics_df, "RND_Ratio")

    risk_score = 0

    latest_debt = _last_valid(debt_ratio)
    if pd.notna(latest_debt) and latest_debt > 70:
        alerts.append(("error", "負債比過高"))
        risk_score += 24

    ocf_tail2 = _safe_tail(operating_cashflow, 2)
    if len(ocf_tail2) == 2 and (ocf_tail2 < 0).all():
        alerts.append(("error", "營業現金流連兩年為負"))
        risk_score += 24

    fcf_tail2 = _safe_tail(fcf, 2)
    if len(fcf_tail2) == 2 and (fcf_tail2 < 0).all():
        alerts.append(("error", "自由現金流連兩年為負"))
        risk_score += 20

    latest_roe = _last_valid(roe)
    ocf_stability = (_safe_tail(operating_cashflow, 3) > 0).mean() if not _safe_tail(operating_cashflow, 3).empty else 0.0
    if pd.notna(latest_roe) and latest_roe >= 15 and ocf_stability < 0.67:
        alerts.append(("warning", "ROE 高但營業現金流不穩定"))
        risk_score += 10

    gm_tail3 = _safe_tail(gross_margin, 3)
    if len(gm_tail3) == 3 and gm_tail3.is_monotonic_decreasing:
        alerts.append(("warning", "毛利率持續下滑"))
        risk_score += 8

    eps_tail3 = _safe_tail(eps_growth, 3)
    if len(eps_tail3) >= 2:
        eps_avg = eps_tail3.mean()
        ocf_tail3 = _safe_tail(operating_cashflow, 3)
        ocf_nonpositive_ratio = (ocf_tail3 <= 0).mean() if len(ocf_tail3) > 0 else 0.0
        if pd.notna(eps_avg) and eps_avg > 15 and ocf_nonpositive_ratio >= 0.34:
            alerts.append(("warning", "EPS 成長率偏高但現金流動能不足"))
            risk_score += 6

    latest_rnd = _last_valid(rnd_ratio)
    if is_core_asic_ip and pd.notna(latest_rnd) and latest_rnd < 6:
        alerts.append(("warning", "核心 ASIC/IP 公司研發費用率偏低"))
        risk_score += 8

    risk_score = int(max(0, min(100, risk_score)))
    if risk_score <= 33:
        risk_level = "低"
    elif risk_score <= 66:
        risk_level = "中"
    else:
        risk_level = "高"

    moat_base = 65 - risk_score * 0.5
    moat_score = moat_base + _compute_moat_adjustment(metrics_df, is_core_asic_ip=is_core_asic_ip)
    moat_score = int(max(0, min(100, round(moat_score))))

    return {
        "alerts": alerts,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "moat_score": moat_score,
    }


def screen_stock_universe(
    all_results: dict[str, pd.DataFrame],
    core_codes: list[str] | set[str] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Screen all stocks and return passed, ranking, and rejected DataFrames."""
    core_set = set(core_codes or [])

    passed_rows: list[dict[str, Any]] = []
    ranking_rows: list[dict[str, Any]] = []
    rejected_rows: list[dict[str, Any]] = []

    for code, metrics_df in all_results.items():
        meta = _lookup_stock_meta(code)
        is_core = str(code) in core_set or meta.get("tier", "") == "核心ASIC/IP股"

        if not isinstance(metrics_df, pd.DataFrame) or metrics_df.empty:
            rejected_rows.append(
                {
                    "code": str(code),
                    "name": meta.get("name", ""),
                    "reason": "缺少有效指標資料",
                }
            )
            continue

        hard_pass, reasons = _evaluate_hard_conditions_internal(metrics_df, is_core_asic_ip=is_core)
        risk = build_risk_alerts(metrics_df, is_core_asic_ip=is_core)

        latest_roe = _last_valid(_ensure_numeric_series(metrics_df, "ROE"))
        latest_fcf = _last_valid(_ensure_numeric_series(metrics_df, "FCF"))
        latest_debt_ratio = _last_valid(_ensure_numeric_series(metrics_df, "Debt_Ratio"))
        latest_ocf = _last_valid(_ensure_numeric_series(metrics_df, "OperatingCashflow"))

        base_row = {
            "code": str(code),
            "name": meta.get("name", ""),
            "role": meta.get("role", ""),
            "risk_score": risk["risk_score"],
            "risk_level": risk["risk_level"],
            "moat_score": risk["moat_score"],
            "latest_roe": latest_roe,
            "latest_fcf": latest_fcf,
            "latest_debt_ratio": latest_debt_ratio,
            "latest_operating_cashflow": latest_ocf,
            "is_core_asic_ip": is_core,
            "hard_pass": hard_pass,
        }

        if hard_pass:
            passed_rows.append(base_row)
            ranking_rows.append(base_row)
        else:
            rejected_rows.append(
                {
                    "code": str(code),
                    "name": meta.get("name", ""),
                    "reason": "；".join(reasons) if reasons else "未通過硬性條件",
                }
            )

    result_df = pd.DataFrame(passed_rows)
    if not result_df.empty:
        result_df = result_df.sort_values(
            by=["moat_score", "risk_score"], ascending=[False, True]
        ).reset_index(drop=True)

    ranking_df = pd.DataFrame(ranking_rows)
    if not ranking_df.empty:
        ranking_df = ranking_df.sort_values(
            by=["moat_score", "risk_score"], ascending=[False, True]
        ).reset_index(drop=True)

    rejected_df = pd.DataFrame(rejected_rows)
    if not rejected_df.empty:
        rejected_df = rejected_df.sort_values(by=["code"]).reset_index(drop=True)

    return result_df, ranking_df, rejected_df
