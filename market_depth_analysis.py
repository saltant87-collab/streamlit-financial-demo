"""Market depth (technical + chip) — Cloud 子專案內建 modules/stock_report_generator。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    import certifi

    _ca = certifi.where()
    for _key in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        if not os.environ.get(_key):
            os.environ[_key] = _ca
except ImportError:
    pass
from typing import Any

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

_MODULE_DIR = Path(__file__).resolve().parent / "modules"
_OVERRIDE_DIR = _MODULE_DIR / "report_overrides"

DEPTH_IMPORT_ERROR: str | None = None
build_report_data = None  # type: ignore[assignment]
load_report_override = None  # type: ignore[assignment]
COMPANY_NAMES: dict[str, str] = {}

if _MODULE_DIR.is_dir():
    mod_path = str(_MODULE_DIR)
    if mod_path not in sys.path:
        sys.path.insert(0, mod_path)
    try:
        from stock_report_generator import (  # type: ignore[import-not-found]
            COMPANY_NAMES as _CN,
            build_report_data as _build,
            load_report_override as _load,
        )

        build_report_data = _build
        load_report_override = _load
        COMPANY_NAMES = _CN
    except Exception as exc:
        DEPTH_IMPORT_ERROR = str(exc)
else:
    DEPTH_IMPORT_ERROR = f"找不到模組目錄：{_MODULE_DIR}"


def depth_analysis_available() -> bool:
    return build_report_data is not None and DEPTH_IMPORT_ERROR is None


def resolve_stock_name(code: str, fallback: str = "") -> str:
    name = COMPANY_NAMES.get(code.strip(), "") or fallback
    return name or code


def fetch_market_depth(code: str) -> dict[str, Any]:
    if build_report_data is None:
        raise RuntimeError(DEPTH_IMPORT_ERROR or "market depth module unavailable")
    return build_report_data(code.strip())


def load_editorial_override(code: str) -> dict[str, Any]:
    if load_report_override is not None:
        return load_report_override(code.strip())
    path = _OVERRIDE_DIR / f"{code.strip()}.json"
    if not path.is_file():
        return {}
    import json

    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _fmt_lots(value: int | float | None) -> str:
    if value is None:
        return "—"
    try:
        v = int(value)
    except (TypeError, ValueError):
        return "—"
    sign = "+" if v > 0 else ""
    return f"{sign}{v:,}"


def _support_levels(data: dict[str, Any]) -> tuple[float, float, float]:
    ma10 = float(data.get("ma10") or 0)
    ma20 = float(data.get("ma20") or 0)
    if ma20 <= 0:
        close = float(data.get("close") or 0)
        ma20 = close
    if ma10 <= 0:
        ma10 = ma20
    return round(ma20 * 0.99, 1), round(ma10 * 1.01, 1), round(ma20 * 0.97, 1)


def render_depth_section(
    code: str,
    stock_name: str = "",
    container: Any | None = None,
    show_help: bool = True,
) -> None:
    import streamlit as st

    ui = container or st

    if not depth_analysis_available():
        ui.warning(
            "技術面／籌碼面模組無法載入。請確認已安裝 "
            "`yfinance`、`pandas`、`requests`、`certifi`，且 repo 內含 `modules/stock_report_generator.py`。"
        )
        if DEPTH_IMPORT_ERROR:
            ui.caption(DEPTH_IMPORT_ERROR)
        return

    ui.caption("資料來源：TWSE 法人／資券 API + Yahoo Finance 日線（海外主機若失敗請改本機 8501）")

    from chart_glossary import TECH_ROW_HINTS, render_chart_with_help, render_term_panel

    if show_help:
        render_term_panel("chip_daily", ui)

    @st.cache_data(show_spinner=False, ttl=1800)
    def _load_depth_bundle(ticker: str) -> tuple[dict[str, Any], dict[str, Any]]:
        return fetch_market_depth(ticker), load_editorial_override(ticker)

    try:
        with ui.spinner(f"抓取 {code} 技術面與籌碼資料中…"):
            data, override = _load_depth_bundle(code)
    except Exception as exc:
        ui.error(f"深度分析資料抓取失敗：{exc}")
        ui.caption("Cloud 上 TWSE API 有時無法連線；完整技術籌碼請用本機 start_hub（8501）。")
        return

    display_name = stock_name or resolve_stock_name(code)
    header = override.get("header") or {}
    subtitle = header.get("subtitle") or ""
    theme = header.get("theme_tagline") or ""

    ui.markdown(f"### {display_name}（`{code}`）· {data.get('date', '')}")
    if subtitle:
        ui.info(subtitle)
    if theme:
        ui.caption(theme)

    pct = float(data.get("pct") or 0)
    c1, c2, c3, c4, c5 = ui.columns(5)
    c1.metric("收盤", f"{data.get('close', 0):.2f}")
    c2.metric("漲跌", f"{data.get('change', 0):+.2f}", f"{pct:+.2f}%")
    c3.metric("成交量", f"{int(data.get('volume') or 0):,} 張")
    c4.metric("MA20", f"{data.get('ma20', 0):.2f}")
    c5.metric("RSI(5)", f"{data.get('rsi5', 0):.1f}")

    t1, t2 = ui.columns(2)
    with t1:
        ui.markdown("**技術指標**")
        if show_help:
            render_term_panel("tech_table", ui)
        names = ["MA5", "MA10", "MA20", "DIF", "MACD", "OSC", "RSI5", "RSI10"]
        tech_df = pd.DataFrame(
            {
                "指標": names,
                "數值": [
                    data.get("ma5"),
                    data.get("ma10"),
                    data.get("ma20"),
                    data.get("dif"),
                    data.get("macd_sig"),
                    data.get("osc"),
                    data.get("rsi5"),
                    data.get("rsi10"),
                ],
                "白話": [TECH_ROW_HINTS.get(n, "—") for n in names] if show_help else ["—"] * len(names),
            }
        )
        perf = {
            "10日": data.get("perf_10d"),
            "20日": data.get("perf_20d"),
            "60日": data.get("perf_60d"),
        }
        ui.dataframe(tech_df, width="stretch", hide_index=True)
        perf_cols = ui.columns(3)
        for col, (label, val) in zip(perf_cols, perf.items()):
            col.metric(label, f"{val:+.2f}%" if val is not None else "—")

    sup_low, sup_high, stop_loss = _support_levels(data)
    with t2:
        ui.markdown("**籌碼與資券（最新交易日）**")
        ui.write(
            f"- 外資：{_fmt_lots(data.get('foreign'))} 張　"
            f"投信：{_fmt_lots(data.get('trust'))} 張　"
            f"自營：{_fmt_lots(data.get('dealer'))} 張"
        )
        ui.write(f"- 三大法人合計：{_fmt_lots(data.get('inst_total'))} 張")
        ui.write(
            f"- 融資餘額：{int(data.get('margin_bal') or 0):,}　"
            f"融券餘額：{int(data.get('short_bal') or 0):,}　"
            f"融資增減：{_fmt_lots(data.get('margin_chg'))}"
        )
        ui.write(
            f"- 支撐參考：{sup_low}～{sup_high} 元　"
            f"停損參考：{stop_loss} 元（依均線推算，非投資建議）"
        )

    conclusions = override.get("conclusions")
    if isinstance(conclusions, list) and conclusions:
        ui.markdown("**核心觀點（手填補充）**")
        for item in conclusions:
            if not isinstance(item, dict):
                continue
            text = str(item.get("text", "")).strip()
            if not text:
                continue
            if item.get("type") == "warn":
                ui.warning(text)
            else:
                ui.success(text)

    kline = data.get("kline") or []
    chip_series = data.get("daily_chip_series") or []

    def _plot_kline(col: Any) -> None:
        col.markdown("**日 K 與均線（近 60 日）**")
        if kline:
            kdf = pd.DataFrame(kline)
            fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.72, 0.28], vertical_spacing=0.04)
            fig.add_trace(
                go.Candlestick(
                    x=kdf["date"],
                    open=kdf["o"],
                    high=kdf["h"],
                    low=kdf["l"],
                    close=kdf["c"],
                    name="K線",
                ),
                row=1,
                col=1,
            )
            for col_name, label, color in [
                ("ma5", "MA5", "#f59e0b"),
                ("ma10", "MA10", "#3b82f6"),
                ("ma20", "MA20", "#a855f7"),
            ]:
                if col_name in kdf.columns and kdf[col_name].notna().any():
                    fig.add_trace(
                        go.Scatter(x=kdf["date"], y=kdf[col_name], name=label, line=dict(width=1.2, color=color)),
                        row=1,
                        col=1,
                    )
            fig.add_trace(
                go.Bar(x=kdf["date"], y=kdf["v"], name="量(張)", marker_color="rgba(100,116,139,0.5)"),
                row=2,
                col=1,
            )
            fig.update_layout(
                height=420,
                margin=dict(l=10, r=10, t=30, b=10),
                xaxis_rangeslider_visible=False,
                legend=dict(orientation="h", y=1.05),
            )
            col.plotly_chart(fig, width="stretch")
        else:
            col.info("K 線資料不足。")

    def _plot_inst(col: Any) -> None:
        col.markdown("**近 10 日三大法人（張）**")
        if chip_series:
            cdf = pd.DataFrame(chip_series)
            fig2 = go.Figure()
            for key, label, color in [
                ("foreign", "外資", "#2563eb"),
                ("trust", "投信", "#16a34a"),
                ("dealer", "自營", "#ea580c"),
            ]:
                if key in cdf.columns:
                    fig2.add_trace(
                        go.Bar(x=cdf["day_label"], y=cdf[key], name=label, marker_color=color),
                    )
            fig2.update_layout(barmode="group", height=420, margin=dict(l=10, r=10, t=30, b=10))
            col.plotly_chart(fig2, width="stretch")
        else:
            col.info("法人序列資料不足。")

    if show_help:
        render_chart_with_help("kline", _plot_kline, ui, show_help=True)
        render_chart_with_help("inst_bar", _plot_inst, ui, show_help=True)
    else:
        c_left, c_right = ui.columns(2)
        _plot_kline(c_left)
        _plot_inst(c_right)

    peers = override.get("peers")
    if isinstance(peers, list) and peers:
        ui.markdown("**同業比較（手填）**")
        rows = []
        for p in peers:
            if not isinstance(p, dict):
                continue
            rows.append(
                {
                    "代號": p.get("code", ""),
                    "名稱": p.get("name", ""),
                    "業務": p.get("biz", ""),
                    "爆發": p.get("burst", ""),
                    "安全": p.get("safe", ""),
                    "基本面": p.get("fund", ""),
                    "策略": p.get("strategy", ""),
                }
            )
        if rows:
            ui.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
