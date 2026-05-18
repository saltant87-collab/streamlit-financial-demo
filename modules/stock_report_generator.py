"""
台股深度分析報告自動生成器
=============================
安裝依賴：pip install yfinance pandas requests
用法：
    python stock_report_generator.py 6770
    python stock_report_generator.py 2408
    python stock_report_generator.py 3037

手填報告正文（選用）：
    於「模組/report_overrides/<股票代號>.json」填入標語／結論／同業／表格等，
    產報時會自動合併。參見同目錄之 report_overrides/範本.json、6770.json。
"""

import os
import sys
import json
import math
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

# yfinance 1.x 走 curl_cffi；macOS 若未設 CA 會出現 curl (60) SSL 錯誤
def _ensure_ssl_ca_bundle() -> None:
    try:
        import certifi

        ca = certifi.where()
        for key in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
            if not os.environ.get(key):
                os.environ[key] = ca
    except ImportError:
        pass


_ensure_ssl_ca_bundle()

import requests
import pandas as pd

try:
    import certifi
except ImportError:
    certifi = None  # type: ignore[assignment]

try:
    import yfinance as yf
except ImportError:
    print("請先安裝：pip install yfinance pandas requests certifi")
    sys.exit(1)

_HTTP_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"}

import html as _htmlstdlib

SCRIPT_DIR = Path(__file__).resolve().parent


def load_report_override(ticker_code: str) -> dict:
    """讀取同層級 report_overrides/<代號>.json；不存在或錯誤則為空 dict。"""
    path = SCRIPT_DIR / "report_overrides" / f"{ticker_code.strip()}.json"
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] 無法讀取 {path.name}: {e}")
        return {}


def _esc(s: str) -> str:
    return _htmlstdlib.escape(str(s), quote=False)


def _stars_markup(burst: int) -> str:
    n = max(0, min(5, int(burst)))
    full = "★" * n
    empty_ch = '<span style="opacity:.32">★</span>'
    empty = empty_ch * (5 - n)
    return full + empty


def build_override_html(
    extra: Optional[dict],
    data: dict,
    gen_time: str,
) -> dict:
    """由手填 JSON 產出要塞進版型的大段 HTML／預設字串。"""
    code = data["code"]
    if not extra:
        extra = {}
    h = extra.get("header") or {}

    hdr_sub = h.get("subtitle")
    if not hdr_sub:
        hdr_sub = "自動生成深度分析報告 · 資料來源：TWSE + Yahoo Finance"
    else:
        hdr_sub = _esc(hdr_sub)

    theme_badge = h.get("theme_tagline") or "技術面 + 籌碼面 + 進場策略 一次整合"
    theme_badge = _esc(theme_badge)

    trophy_label = h.get("trophy_label") or "深度分析"
    trophy_label = _esc(trophy_label)

    # ── 左欄：核心結論／持股敘述 ──
    left_parts: list[str] = []
    conclusions = extra.get("conclusions")
    if isinstance(conclusions, list) and conclusions:
        rows = []
        for item in conclusions:
            if not isinstance(item, dict):
                continue
            kind = item.get("type", "tick")
            text = item.get("text", "")
            if not text.strip():
                continue
            txt = _esc(text.strip())
            if kind == "warn":
                rows.append(
                    f'<li><span class="ed-warn">⚠</span><span>{txt}</span></li>'
                )
            else:
                rows.append(
                    f'<li><span class="ed-tick">✓</span><span>{txt}</span></li>'
                )
        if rows:
            left_parts.append(
                '<div class="card editorial-card"><div class="ct">核心結論</div>'
                f'<ul class="ed-conclusion">{"".join(rows)}</ul></div>'
            )

    hod = extra.get("holdings")
    if isinstance(hod, dict) and (hod.get("foreign_ratio") or hod.get(
            "trust_ratio")):
        fr = hod.get("foreign_ratio", "—")
        tr = hod.get("trust_ratio", "—")
        note_raw = hod.get("note_raw")
        nh = hod.get("note_html")
        nt = hod.get("note") or ""
        if nh and note_raw:
            note_block = str(nh)
        elif nh and not note_raw:
            note_block = f"<div>{_esc(str(nh))}</div>"
        elif nt.strip():
            note_block = f"<div>{_esc(nt.strip())}</div>"
        else:
            note_block = ""
        left_parts.append(
            '<div class="card editorial-card"><div class="ct">法人持股變化（手填／公告摘要）</div>'
            '<div class="ed-inst-row"><span style="color:var(--dim)">外資持股比率</span>'
            f'<span class="ratio-val">{fr if hod.get("foreign_raw") else _esc(fr)}</span></div>'
            '<div class="ed-inst-row"><span style="color:var(--dim)">投信持股比率</span>'
            f'<span class="ratio-val">{tr if hod.get("trust_raw") else _esc(tr)}</span></div>'
            f"{note_block}</div>"
        )

    block_left_editorial = "\n".join(left_parts)

    # ── 右欄：同業對照（插在股價表現下方）──
    peers = extra.get("peers") or []
    peer_html_parts: list[str] = []
    if isinstance(peers, list) and peers:
        peer_html_parts.append(
            '<div class="card editorial-card"><div class="ct">🏆 與同業比較（手填）</div>'
            '<div class="peer-grid">'
        )
        for p in peers:
            if not isinstance(p, dict):
                continue
            pc_cd = _esc(str(p.get("code", "")))
            hl = p.get("highlight") or (str(p.get("code")) == str(code))
            hi = " peer-hi" if hl else ""
            nm = _esc(str(p.get("name", "")))
            biz = _esc(str(p.get("biz", "")))
            b = int(p.get("burst", 3) or 3)
            s = int(p.get("safe", 3) or 3)
            f = int(p.get("fund", 3) or 3)
            st = _esc(str(p.get("strategy", "—")))
            fund_stars = int(p.get("fund", 3) or 3)
            peer_html_parts.append(
                f'<div class="peer-card{hi}">'
                f'<div class="peer-nm">{nm}</div>'
                f'<div class="peer-cd">{pc_cd}</div>'
                f'<div class="peer-biz">{biz}</div>'
                '<div class="peer-kv"><span class="plab">爆發力</span>'
                f'<span class="starline">{_stars_markup(b)}</span></div>'
                '<div class="peer-kv"><span class="plab">安全性</span>'
                f'<span class="starline">{_stars_markup(s)}</span></div>'
                '<div class="peer-kv"><span class="plab">法人動能</span>'
                f'<span class="starline">{_stars_markup(fund_stars)}</span></div>'
                f'<div class="peer-st">{st}</div></div>'
            )
        peer_html_parts.append("</div></div>")
    block_peer_below_perf = "".join(peer_html_parts)

    # ── 主格下方：排行／目標／籌碼／總結（手填）──
    tails: list[str] = []

    rk = extra.get("ranking")
    if isinstance(rk, dict) and rk.get("rows"):
        title = _esc(rk.get("title", "投信近10日買超排行（手填）"))
        heads = rk.get("headers") or [
            "排名", "股票", "當日買超(張)", "累計(張)", "估金額(億)",
        ]
        ths = "".join(f"<th>{_esc(str(x))}</th>" for x in heads)
        body_rows = []
        for row in rk["rows"]:
            if not isinstance(row, (list, tuple)):
                continue
            cells = "".join(f"<td>{_esc(str(c))}</td>" for c in row)
            row_hl = any(str(code) in str(c) for c in row)
            trc = " class=\"hl\"" if row_hl else ""
            body_rows.append(f"<tr{trc}>{cells}</tr>")
        if body_rows:
            tails.append(
                '<div class="card editorial-card">'
                f'<div class="ct">{title}</div>'
                f'<table><thead><tr>{ths}</tr></thead><tbody>'
                f'{"".join(body_rows)}</tbody></table>'
                '<div class="ed-foot">欄位與單位以你維護的資料為準。</div>'
                "</div>"
            )

    tgt = extra.get("targets") if isinstance(extra.get("targets"), dict) else {}
    obs_list = extra.get("observations") if isinstance(
        extra.get("observations"), list
    ) else []

    tgt_card = ""
    if tgt.get("cons") or tgt.get("mid") or tgt.get("bull"):
        tgt_card = (
            '<div class="card editorial-card"><div class="ct">波段目標價（手填）</div>'
            '<div class="tg-grid">'
            f'<div class="tg-box"><div class="tg-t">保守</div>'
            f'<div class="tg-p">{_esc(str(tgt.get("cons", "—")))}</div></div>'
            f'<div class="tg-box tg-mid"><div class="tg-t">中性</div>'
            f'<div class="tg-p">{_esc(str(tgt.get("mid", "—")))}</div></div>'
            f'<div class="tg-box tg-bull"><div class="tg-t">強勢</div>'
            f'<div class="tg-p">{_esc(str(tgt.get("bull", "—")))}</div></div>'
            "</div></div>"
        )

    obs_card = ""
    olis = []
    for i, o in enumerate(obs_list, 1):
        if not str(o).strip():
            continue
        olis.append(
            f'<li><span class="obs-n">{i}</span>'
            f"<span>{_esc(str(o).strip())}</span></li>"
        )
    if olis:
        obs_card = (
            '<div class="card editorial-card"><div class="ct">關鍵觀察重點</div>'
            f'<ul class="ed-obs">{"".join(olis)}</ul></div>'
        )

    if tgt_card and obs_card:
        tails.append(f'<div class="tail-grid2">{tgt_card}{obs_card}</div>')
    elif tgt_card or obs_card:
        tails.append(tgt_card or obs_card)

    cs = extra.get("chips_10d_summary")
    if isinstance(cs, dict) and any(
        cs.get(k) for k in ("foreign", "trust", "dealer")
    ):
        def _span(lab: str, val: str, sub: str) -> str:
            v_disp = val if cs.get("raw_values") else _esc(str(val))
            return (
                f'<div class="cs-box"><div class="cs-t">{_esc(lab)}</div>'
                f'<div class="cs-v">{v_disp}</div>'
                f'<div class="cs-s">{_esc(str(sub))}</div></div>'
            )

        tails.append(
            '<div class="card editorial-card"><div class="ct">近10日籌碼總結（手填）</div>'
            '<div class="cs-row">'
            f'{_span("外資", cs.get("foreign","—"), cs.get("foreign_note",""))}'
            f'{_span("投信", cs.get("trust","—"), cs.get("trust_note",""))}'
            f'{_span("自營", cs.get("dealer","—"), cs.get("dealer_note",""))}'
            "</div>"
            f'<div class="ed-foot">{_esc(str(cs.get("hint", "")))}</div></div>'
        )

    sum_risk = extra.get("summary_risk")
    if isinstance(sum_risk, dict) and (
        sum_risk.get("summary")
        or sum_risk.get("summary_html")
        or sum_risk.get("risks")
    ):
        sp = sum_risk.get("summary", "") or ""
        summary_card = ""
        if sum_risk.get("summary_raw") and sum_risk.get("summary_html"):
            summary_card = (
                f'<div class="card editorial-card">{sum_risk["summary_html"]}</div>'
            )
        elif sp.strip():
            if sum_risk.get("summary_raw"):
                summary_card = (
                    f'<div class="card editorial-card">{sp}</div>'
                )
            else:
                summary_card = (
                    '<div class="card editorial-card">'
                    f'<div class="ct">總結</div>'
                    f'<div class="ed-sum">{_esc(sp.strip())}</div>'
                    "</div>"
                )
        risk_items = sum_risk.get("risks") or []
        rlis = []
        if isinstance(risk_items, list):
            for it in risk_items:
                if not str(it).strip():
                    continue
                rlis.append(
                    '<li><span class="ed-rb">•</span>'
                    f"<span>{_esc(str(it).strip())}</span></li>"
                )
        risk_html = ""
        if rlis:
            risk_html = (
                '<div class="ed-riskbox"><div class="ed-rt">⚠ 風險提醒</div>'
                f'<ul class="ed-rlist">{"".join(rlis)}</ul></div>'
            )
        if summary_card and risk_html:
            tails.append(
                f'<div class="tail-grid2">{summary_card}{risk_html}</div>'
            )
        else:
            tails.append(summary_card or risk_html)

    block_after_main = "\n".join(tails)

    footer_bar = extra.get("footer_bar")
    if not footer_bar:
        footer_bar = "★ 自動化股票分析報告 · 僅供參考，不構成投資建議 ★"
    else:
        footer_bar = _esc(str(footer_bar))

    fn = (extra.get("footer_source_note") or "").strip()
    if fn:
        footer_hint = (
            "資料來源：台灣證券交易所 TWSE + Yahoo Finance | "
            f"{_esc(fn)} | 報告生成時間：{gen_time}"
        )
    else:
        footer_hint = (
            "資料來源：台灣證券交易所 TWSE + Yahoo Finance | "
            f"報告生成時間：{gen_time}"
        )

    return {
        "hdr_sub": hdr_sub,
        "theme_badge": theme_badge,
        "trophy_label": trophy_label,
        "block_left_editorial": block_left_editorial,
        "block_peer_below_perf": block_peer_below_perf,
        "block_after_main": block_after_main,
        "footer_bar": footer_bar,
        "footer_hint": footer_hint,
    }


# ════════════════════════════════════════════════
#  1. 資料抓取層
# ════════════════════════════════════════════════

def _requests_verify() -> Union[bool, str]:
    if certifi is not None:
        return certifi.where()
    return True


def _fetch_price_data_chart_api(ticker_code: str, period: str = "6mo") -> pd.DataFrame:
    """Yahoo Chart API 備援（requests + certifi，避開 curl_cffi SSL 問題）。"""
    symbol = f"{ticker_code}.TW"
    url = (
        "https://query1.finance.yahoo.com/v8/finance/chart/"
        f"{symbol}?interval=1d&range={period}"
    )
    r = requests.get(url, timeout=30, headers=_HTTP_HEADERS, verify=_requests_verify())
    r.raise_for_status()
    payload = r.json()
    results = (payload.get("chart") or {}).get("result") or []
    if not results:
        raise RuntimeError(f"Yahoo Chart API 無資料：{symbol}")
    block = results[0]
    ts = block.get("timestamp") or []
    quote = ((block.get("indicators") or {}).get("quote") or [{}])[0]
    if not ts or not quote:
        raise RuntimeError(f"Yahoo Chart API 欄位不足：{symbol}")

    df = pd.DataFrame(
        {
            "Open": quote.get("open"),
            "High": quote.get("high"),
            "Low": quote.get("low"),
            "Close": quote.get("close"),
            "Volume": quote.get("volume"),
        },
        index=pd.to_datetime(ts, unit="s"),
    )
    df.index = df.index.tz_localize(None)
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    if df.empty:
        raise RuntimeError(f"Yahoo Chart API 回傳空表：{symbol}")
    return df


def fetch_price_data(ticker_code: str, period: str = "6mo") -> pd.DataFrame:
    """抓取歷史股價：優先 yfinance，SSL 失敗時改 Yahoo Chart API。"""
    symbol = f"{ticker_code}.TW"
    last_err: Optional[Exception] = None
    try:
        tk = yf.Ticker(symbol)
        df = tk.history(period=period)
        if df is not None and not df.empty:
            df.index = df.index.tz_localize(None)
            df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
            if not df.empty:
                return df
    except Exception as exc:
        last_err = exc
        print(f"[WARN] yfinance 失敗 ({symbol})，改走 Yahoo Chart API：{exc}")

    try:
        return _fetch_price_data_chart_api(ticker_code, period)
    except Exception as exc:
        if last_err is not None:
            raise RuntimeError(f"{last_err}; 備援亦失敗：{exc}") from exc
        raise


def fetch_twse_institution(date_str: str) -> dict:
    """
    從台灣證交所 Open API 抓取三大法人
    date_str 格式：YYYYMMDD
    回傳：{stock_code: {foreign, trust, dealer, total}}
    """
    url = (
        "https://www.twse.com.tw/rwd/zh/fund/T86"
        f"?date={date_str}&selectType=ALL&response=json"
    )
    try:
        r = requests.get(
            url, timeout=10, headers=_HTTP_HEADERS, verify=_requests_verify()
        )
        data = r.json()
        result = {}
        if data.get("stat") == "OK":
            for row in data.get("data", []):
                code = row[0].strip()
                # 欄位：代號,名稱,外資買,外資賣,外資淨,投信買,投信賣,投信淨,
                #        自營買,自營賣,自營淨,自營避險買,自營避險賣,自營避險淨,三大法人
                def to_int(s):
                    try:
                        return int(s.replace(",", ""))
                    except Exception:
                        return 0
                result[code] = {
                    "foreign": to_int(row[4]),
                    "trust":   to_int(row[7]),
                    "dealer":  to_int(row[10]),
                    "total":   to_int(row[14]),
                }
        return result
    except Exception as e:
        print(f"[WARN] 三大法人 API 失敗: {e}")
        return {}


def fetch_twse_margin(ticker_code: str, date_str: str) -> Optional[dict]:
    """
    從證交所抓取融資融券餘額；無資料或非交易日回傳 None。
    """
    url = (
        "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN"
        f"?date={date_str}&selectType=ALL&response=json"
    )
    try:
        r = requests.get(
            url, timeout=10, headers=_HTTP_HEADERS, verify=_requests_verify()
        )
        data = r.json()
        if data.get("stat") != "OK" or not data.get("data"):
            return None
        for row in data.get("data", []):
            if row[0].strip() == ticker_code:
                def to_int(s):
                    try:
                        return int(s.replace(",", ""))
                    except Exception:
                        return 0
                return {
                    "margin_balance": to_int(row[6]),   # 融資餘額
                    "short_balance":  to_int(row[12]),  # 融券餘額
                    "margin_change":  to_int(row[5]),   # 融資增減
                    "short_change":   to_int(row[11]),  # 融券增減
                }
        return None
    except Exception as e:
        print(f"[WARN] 融資融券 API 失敗 ({date_str}): {e}")
        return None


def fetch_company_info(ticker_code: str) -> dict:
    """用 yfinance 抓公司基本資料"""
    tk = yf.Ticker(f"{ticker_code}.TW")
    try:
        info = tk.fast_info
        return {
            "name":       tk.info.get("longName", f"股票{ticker_code}"),
            "market_cap": getattr(info, "market_cap", 0),
            "shares":     getattr(info, "shares", 0),
        }
    except Exception:
        return {"name": f"股票{ticker_code}", "market_cap": 0, "shares": 0}


def build_daily_chip_series(
    ticker_code: str,
    df: pd.DataFrame,
    need: int = 10,
    max_scan: int = 50,
) -> list[dict]:
    """
    自最近往回掃描，收集 need 個「同日有資券 + 法人表」的有效交易日，
    回傳由舊→新時間序，供多日圖表使用。
    """
    raw: list[dict] = []
    tail = df.index[-max_scan:] if len(df.index) >= max_scan else df.index
    for ts in reversed(list(tail)):
        if len(raw) >= need:
            break
        ds = ts.strftime("%Y%m%d")
        margin = fetch_twse_margin(ticker_code, ds)
        inst_all = fetch_twse_institution(ds)
        inst = inst_all.get(ticker_code)
        if margin is None or inst is None:
            continue
        raw.append({
            "date":       ds,
            "day_label": f"{ds[4:6]}/{ds[6:]}",
            "close":      round(float(df.loc[ts, "Close"]), 2),
            "financing":  margin["margin_balance"],
            "short_sell": margin["short_balance"],
            "margin_chg": margin["margin_change"],
            "short_chg":  margin["short_change"],
            "foreign":    inst["foreign"],
            "trust":      inst["trust"],
            "dealer":     inst["dealer"],
            "inst_total": inst["total"],
        })
        time.sleep(0.1)
    raw.reverse()
    return raw


# ════════════════════════════════════════════════
#  2. 技術指標計算層
# ════════════════════════════════════════════════

def calc_ma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


def calc_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def calc_macd(series: pd.Series,
              fast=12, slow=26, signal=9) -> tuple[pd.Series, pd.Series, pd.Series]:
    ema_fast = calc_ema(series, fast)
    ema_slow = calc_ema(series, slow)
    dif = ema_fast - ema_slow
    macd_sig = calc_ema(dif, signal)
    osc = dif - macd_sig
    return dif, macd_sig, osc


def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss.replace(0, float("inf"))
    return 100 - (100 / (1 + rs))


def calc_performance(close: pd.Series) -> dict:
    latest = close.iloc[-1]
    def pct(n):
        if len(close) > n:
            old = close.iloc[-(n + 1)]
            return round((latest - old) / old * 100, 2)
        return None
    return {
        "d10": pct(10),
        "d20": pct(20),
        "d60": pct(60),
    }


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["MA5"]   = calc_ma(df["Close"], 5)
    df["MA10"]  = calc_ma(df["Close"], 10)
    df["MA20"]  = calc_ma(df["Close"], 20)
    df["DIF"], df["MACD"], df["OSC"] = calc_macd(df["Close"])
    df["RSI5"]  = calc_rsi(df["Close"], 5)
    df["RSI10"] = calc_rsi(df["Close"], 10)
    return df


# ════════════════════════════════════════════════
#  3. 資料打包
# ════════════════════════════════════════════════

def build_report_data(ticker_code: str, target_date: str = None) -> dict:
    """整合所有資料，回傳報告用 dict"""
    print(f"[1/5] 抓取 {ticker_code} 歷史股價...")
    df = fetch_price_data(ticker_code)
    df = add_indicators(df)

    if target_date:
        ts = pd.Timestamp(target_date)
        df = df[df.index <= ts]

    last = df.iloc[-1]
    prev = df.iloc[-2]
    date_str_api = df.index[-1].strftime("%Y%m%d")
    date_display = df.index[-1].strftime("%Y/%m/%d")

    volume_zhang = int(last["Volume"]) // 1000

    close = float(last["Close"])
    change = round(close - float(prev["Close"]), 2)
    pct = round(change / float(prev["Close"]) * 100, 2)
    limit_up = round(float(prev["Close"]) * 1.1, 1)
    limit_down = round(float(prev["Close"]) * 0.9, 1)

    print(f"[2/5] 回看近十日法人／資券（TWSE API，請稍候）...")
    daily_series = build_daily_chip_series(
        ticker_code, df, need=10, max_scan=55
    )

    print(f"[3/5] 抓取三大法人（{date_str_api}）...")
    inst_all = fetch_twse_institution(date_str_api)
    inst = inst_all.get(
        ticker_code,
        {"foreign": 0, "trust": 0, "dealer": 0, "total": 0},
    )

    margin = fetch_twse_margin(ticker_code, date_str_api)
    if (
        margin is None
        and daily_series
        and daily_series[-1]["date"] == date_str_api
    ):
        lz = daily_series[-1]
        margin = {
            "margin_balance": lz["financing"],
            "short_balance": lz["short_sell"],
            "margin_change": lz["margin_chg"],
            "short_change": lz["short_chg"],
        }
    if margin is None:
        margin = {
            "margin_balance": 0,
            "short_balance": 0,
            "margin_change": 0,
            "short_change": 0,
        }

    print(f"[4/5] 計算技術指標...")
    perf = calc_performance(df["Close"])

    cum_inst_total_10 = (
        sum(d["inst_total"] for d in daily_series) if daily_series else 0
    )

    denom_pie = abs(inst["foreign"]) + abs(inst["trust"]) + abs(inst["dealer"])
    if denom_pie < 1e-9:
        pie_f = pie_t = pie_d = 33.33
    else:
        pie_f = round(abs(inst["foreign"]) / denom_pie * 100, 1)
        pie_t = round(abs(inst["trust"]) / denom_pie * 100, 1)
        pie_d = round(100.0 - pie_f - pie_t, 1)

    if volume_zhang > 0:
        main_vol_ratio_pct = round(
            abs(inst["total"]) / volume_zhang * 100, 2
        )
    else:
        main_vol_ratio_pct = 0.0

    chip_days_n = len(daily_series)

    # K 線資料（最近 60 根）
    recent = df.tail(60)
    kline_data = [
        {
            "o": round(float(r["Open"]), 1),
            "h": round(float(r["High"]), 1),
            "l": round(float(r["Low"]),  1),
            "c": round(float(r["Close"]), 1),
            "v": int(r["Volume"]) // 1000,
            "ma5":  round(float(r["MA5"]),  1) if not math.isnan(r["MA5"])  else None,
            "ma10": round(float(r["MA10"]), 1) if not math.isnan(r["MA10"]) else None,
            "ma20": round(float(r["MA20"]), 1) if not math.isnan(r["MA20"]) else None,
            "dif":  round(float(r["DIF"]),  2) if not math.isnan(r["DIF"])  else None,
            "macd": round(float(r["MACD"]), 2) if not math.isnan(r["MACD"]) else None,
            "osc":  round(float(r["OSC"]),  2) if not math.isnan(r["OSC"])  else None,
            "rsi5":  round(float(r["RSI5"]),  1) if not math.isnan(r["RSI5"])  else None,
            "rsi10": round(float(r["RSI10"]), 1) if not math.isnan(r["RSI10"]) else None,
            "date": r.name.strftime("%m/%d"),
        }
        for _, r in recent.iterrows()
    ]

    print(f"[5/5] 完成。")
    return {
        "code":               ticker_code,
        "date":               date_display,
        "close":              close,
        "change":             change,
        "pct":                pct,
        "high":               round(float(last["High"]), 1),
        "low":                round(float(last["Low"]), 1),
        "limit_up":           limit_up,
        "limit_down":         limit_down,
        "avg":                round(
            (float(last["High"]) + float(last["Low"]) + close) / 3, 1
        ),
        "volume":             volume_zhang,
        "ma5":                round(float(last["MA5"]), 2),
        "ma10":               round(float(last["MA10"]), 2),
        "ma20":               round(float(last["MA20"]), 2),
        "dif":                round(float(last["DIF"]), 2),
        "macd_sig":           round(float(last["MACD"]), 2),
        "osc":                round(float(last["OSC"]), 2),
        "rsi5":               round(float(last["RSI5"]), 1),
        "rsi10":              round(float(last["RSI10"]), 1),
        "foreign":            inst["foreign"],
        "trust":              inst["trust"],
        "dealer":             inst["dealer"],
        "inst_total":         inst["total"],
        "margin_bal":         margin["margin_balance"],
        "short_bal":          margin["short_balance"],
        "margin_chg":         margin["margin_change"],
        "short_chg":          margin["short_change"],
        "perf_10d":           perf["d10"],
        "perf_20d":           perf["d20"],
        "perf_60d":           perf["d60"],
        "kline":              kline_data,
        "daily_chip_series":  daily_series,
        "cum_inst_total_10":  cum_inst_total_10,
        "main_vol_ratio_pct": main_vol_ratio_pct,
        "pie_f":              pie_f,
        "pie_t":              pie_t,
        "pie_d":              pie_d,
        "chip_days_n":        chip_days_n,
    }


# ════════════════════════════════════════════════
#  4. HTML 生成層
# ════════════════════════════════════════════════

def fmt_num(n, plus=True) -> str:
    if n is None:
        return "N/A"
    sign = "+" if (plus and n > 0) else ""
    return f"{sign}{n:,}"


def color_cls(n) -> str:
    if n is None:
        return ""
    return "pos" if n > 0 else ("neg" if n < 0 else "neutral")


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{code} 深度分析 {date}</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;500;700;900&display=swap');
:root{{
  --gold:#d4a017;--gold-l:#f0c040;--gold-d:#a07010;
  --red:#e84040;--green:#00c853;--blue:#2196f3;--orange:#ff6d00;
  --bg:#0a0d12;--card:#111820;--card2:#0f1520;--border:#2a3545;
  --txt:#e8e8e8;--dim:#8899aa;
}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:'Noto Sans TC',sans-serif;background:var(--bg);color:var(--txt);
      width:1000px;margin:0 auto;padding:12px;font-size:13px}}
.card{{background:var(--card);border:1px solid var(--border);border-radius:8px;padding:10px 12px}}
.ct{{font-size:13px;font-weight:700;color:var(--gold-l);margin-bottom:8px;
     display:flex;align-items:center;gap:6px}}
.ct::before{{content:'';display:inline-block;width:4px;height:14px;
             background:var(--gold);border-radius:2px;flex-shrink:0}}
.pos{{color:var(--red)}} .neg{{color:var(--green)}} .neutral{{color:#aaa}}
.r{{color:var(--red)}} .g{{color:var(--green)}}
.hdr{{background:linear-gradient(135deg,#0d1820,#1a2535,#0d1820);
      border:1px solid var(--gold-d);border-radius:10px;padding:14px 18px;
      margin-bottom:8px;display:flex;justify-content:space-between;align-items:center;
      position:relative;overflow:hidden}}
.hdr-title{{font-size:30px;font-weight:900;color:#fff;letter-spacing:1px}}
.hdr-title span{{color:var(--gold-l)}}
.hdr-sub{{font-size:12px;color:#aabbcc;margin-top:4px;letter-spacing:1px}}
.theme-badge{{display:inline-block;background:linear-gradient(90deg,#d4a017,#f0c040,#d4a017);
              color:#000;font-weight:900;font-size:13px;padding:4px 14px;border-radius:4px;
              margin-top:8px;letter-spacing:1px}}
.date-badge{{position:absolute;top:8px;right:14px;background:rgba(212,160,23,.15);
             border:1px solid var(--gold-d);color:var(--gold-l);font-size:12px;
             padding:2px 10px;border-radius:4px;font-weight:700}}
.price-box{{background:linear-gradient(135deg,#1a2030,#0d1520);border:2px solid var(--gold-d);
            border-radius:8px;padding:10px 16px}}
.price-main{{font-size:38px;font-weight:900;letter-spacing:1px}}
.price-grid{{display:grid;grid-template-columns:1fr 1fr;gap:4px 14px;
             margin-top:8px;font-size:11px;color:var(--dim)}}
.price-grid span{{color:var(--txt)}}
.main-grid{{display:grid;grid-template-columns:320px 1fr;gap:8px;margin-bottom:8px}}
.left-col,.right-col{{display:flex;flex-direction:column;gap:8px}}
.irow{{display:flex;justify-content:space-between;align-items:center;
       padding:5px 0;border-bottom:1px solid rgba(255,255,255,.05);font-size:12px}}
.irow:last-child{{border-bottom:none}}
.itotal{{margin-top:6px;padding:6px 0;border-top:1px solid var(--gold-d);
         display:flex;justify-content:space-between;font-weight:700}}
table{{width:100%;border-collapse:collapse;font-size:11px}}
th{{background:#1a2535;color:var(--gold-l);padding:5px 6px;
    text-align:center;border:1px solid var(--border);font-weight:700}}
td{{padding:4px 6px;text-align:center;border:1px solid rgba(42,53,69,.5);color:var(--txt)}}
tr:nth-child(even) td{{background:rgba(255,255,255,.02)}}
tr.hl td{{background:rgba(212,160,23,.1);color:var(--gold-l);font-weight:700}}
tr.hl td:first-child{{border-left:2px solid var(--gold)}}
.stat-box{{text-align:center;padding:6px;background:var(--card2);
           border:1px solid var(--border);border-radius:6px}}
.stat-val{{font-size:20px;font-weight:900;color:var(--red)}}
.footer-bar{{text-align:center;margin-top:10px;padding:10px;
             border:1px solid var(--gold-d);border-radius:6px;
             background:linear-gradient(90deg,#0d1820,#1a2535,#0d1820);
             font-size:15px;font-weight:900;letter-spacing:3px;
             color:var(--gold-l);text-shadow:0 0 12px rgba(212,160,23,.4)}}
canvas{{display:block}}
.ma5{{color:#ffeb3b}} .ma10{{color:#4fc3f7}} .ma20{{color:#f06292}}
.two-col-grid{{display:grid;grid-template-columns:1fr 1fr;gap:8px}}
.margin-legend{{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:4px;font-size:10px;color:var(--dim)}}
.margin-legend .dot{{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:3px}}
.fund-flow-wrap{{display:flex;align-items:center;gap:10px;min-height:96px}}
.pie-container{{position:relative;width:94px;height:94px;flex-shrink:0}}
.pie-label{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;
            text-align:center;font-size:9px;line-height:1.25;color:var(--dim);pointer-events:none}}
.fund-stats{{flex:1;font-size:10px;line-height:1.35}}
.fund-row{{display:flex;justify-content:space-between}}
.fund-out{{color:var(--dim)}}
.fund-in{{color:var(--red);font-weight:700}}
.ct-small{{margin-bottom:0}}
.k-foot{{display:flex;justify-content:space-between;font-size:10px;color:var(--dim);margin-top:2px;padding:0 2px}}
.editorial-card .ed-foot{{font-size:9px;color:var(--dim);margin-top:4px;line-height:1.35}}
.ed-conclusion{{list-style:none;font-size:12px;line-height:1.55;margin:0;padding:0}}
.ed-conclusion li{{display:flex;gap:6px;padding:4px 0;border-bottom:1px solid rgba(255,255,255,.06)}}
.ed-tick{{color:var(--green);flex-shrink:0;font-size:13px}}
.ed-warn{{color:var(--orange);flex-shrink:0;font-size:13px}}
.ed-inst-row{{display:flex;justify-content:space-between;padding:6px 0;font-size:12px;border-bottom:1px solid rgba(255,255,255,.06)}}
.ratio-val{{font-weight:700;color:var(--txt)}}
.peer-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:6px}}
.peer-card{{background:var(--card2);border:1px solid var(--border);border-radius:6px;padding:6px 8px;font-size:10px}}
.peer-hi{{border-color:var(--gold-d);box-shadow:inset 0 0 0 1px rgba(212,160,23,.22)}}
.peer-nm{{font-weight:900;color:var(--txt);font-size:12px}}
.peer-cd{{font-size:10px;color:var(--gold-l);margin:2px 0}}
.peer-biz{{color:var(--dim);margin-bottom:4px;line-height:1.3}}
.peer-kv{{display:flex;justify-content:space-between;margin:3px 0}}
.plab{{color:var(--dim)}}
.starline{{font-size:11px;color:var(--gold-l);letter-spacing:1px}}
.peer-st{{margin-top:4px;text-align:center;font-size:11px;color:var(--gold-l);padding:4px;background:rgba(255,255,255,.03);border-radius:4px}}
.tail-grid2{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:8px}}
@media(max-width:1020px){{
  .peer-grid{{grid-template-columns:repeat(2,1fr)}}
}}
.tg-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:4px}}
.tg-box{{text-align:center;padding:8px 6px;background:rgba(255,255,255,.04);border:1px solid var(--border);border-radius:6px}}
.tg-mid{{background:rgba(212,160,23,.06);border-color:var(--gold-d)}}
.tg-bull{{background:rgba(232,64,64,.06);border-color:rgba(232,64,64,.35)}}
.tg-t{{font-size:11px;color:var(--gold-l);font-weight:700;margin-bottom:3px}}
.tg-p{{font-size:13px;font-weight:900;color:var(--txt)}}
.ed-obs{{list-style:none;margin:4px 0 0;padding:0;font-size:12px}}
.ed-obs li{{display:flex;gap:6px;margin:5px 0}}
.obs-n{{display:inline-flex;align-items:center;justify-content:center;width:17px;height:17px;background:var(--gold);color:#111;font-size:11px;font-weight:900;border-radius:50%;flex-shrink:0}}
.cs-row{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:4px}}
.cs-box{{background:rgba(255,255,255,.03);padding:8px;text-align:center;border-radius:6px;font-size:11px;border:1px solid var(--border)}}
.cs-t{{color:var(--dim)}}
.cs-v{{font-size:17px;font-weight:900;color:var(--gold-l);margin:4px 0}}
.cs-s{{font-size:10px;color:var(--dim)}}
.ed-sum{{font-size:12px;line-height:1.75;color:#ccdde8;margin-top:2px}}
.ed-riskbox{{background:rgba(232,64,64,.08);border:1px solid rgba(232,64,64,.25);border-radius:6px;padding:8px 10px;font-size:11px}}
.ed-rt{{color:var(--red);font-weight:700;margin-bottom:4px}}
.ed-rlist{{list-style:none;padding:0;margin:0;color:#cdb6b6}}
.ed-rlist li{{display:flex;gap:5px;margin:3px 0}}
.ed-rb{{color:var(--red);flex-shrink:0;margin-top:1px}}
</style>
</head>
<body>

<!-- HEADER -->
<div class="hdr">
  <div class="date-badge">{date}</div>
  <div>
    <div class="hdr-title">{name} <span>({code})</span></div>
    <div class="hdr-sub">{hdr_sub}</div>
    <div class="theme-badge">{theme_badge}</div>
  </div>
  <div>🏆<div style="text-align:center;font-size:11px;color:var(--gold-l);font-weight:700">{trophy_label}</div></div>
  <div>
    <div class="price-box">
      <div class="price-main {price_cls}">{close:.2f}</div>
      <div style="font-size:15px;" class="{price_cls}">{chg_tri} {change:+.2f} ({pct:+.2f}%)</div>
      <div class="price-grid">
        <div>最高 <span class="r">{high}</span></div>
        <div>最低 <span class="g">{low}</span></div>
        <div>漲停 <span class="r">{limit_up}</span></div>
        <div>跌停 <span class="g">{limit_down}</span></div>
        <div>均價 <span>{avg}</span></div>
        <div>成交量 <span>{volume:,}張</span></div>
      </div>
    </div>
  </div>
</div>

<!-- MAIN GRID -->
<div class="main-grid">
  <div class="left-col">

    <!-- K-LINE -->
    <div class="card">
      <div style="display:flex;justify-content:space-between;margin-bottom:4px">
        <div class="ct" style="margin-bottom:0">K線走勢圖（日線）</div>
        <div style="font-size:11px;line-height:1.6">
          <div class="ma5">MA5 &nbsp;{ma5} {ma5_arrow}</div>
          <div class="ma10">MA10 {ma10} {ma10_arrow}</div>
          <div class="ma20">MA20 {ma20} {ma20_arrow}</div>
        </div>
      </div>
      <canvas id="kc" width="296" height="160"></canvas>
      <div style="font-size:10px;color:var(--dim);text-align:right;margin-top:2px">成交量 {volume:,} 張</div>
      <div style="font-size:11px;margin-top:6px">
        <span style="color:#ccc">MACD</span>
        <span style="color:#ff9800"> DIF {dif} {dif_arrow}</span>
        <span style="color:#4fc3f7"> MACD {macd_sig} {macd_arrow}</span>
        <span style="color:#f48fb1"> OSC {osc} {osc_arrow}</span>
      </div>
      <canvas id="mc" width="296" height="54"></canvas>
      <div style="font-size:11px;margin-top:4px">
        <span style="color:#ccc">RSI</span>
        <span style="color:#ffeb3b"> RSI(5) {rsi5} {rsi5_arrow}</span>
        <span style="color:#80cbc4"> RSI(10) {rsi10} {rsi10_arrow}</span>
      </div>
      <canvas id="rc" width="296" height="47"></canvas>
      <div class="k-foot">{kline_dates_html}</div>
    </div>

    {block_left_editorial}

  </div><!-- /left -->

  <div class="right-col">

    <!-- PERFORMANCE -->
    <div class="card">
      <div class="ct">股價表現</div>
      <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px">
        <div class="stat-box">
          <div style="font-size:10px;color:var(--dim)">10日漲幅</div>
          <div class="stat-val">{perf_10d:+.1f}%</div>
        </div>
        <div class="stat-box">
          <div style="font-size:10px;color:var(--dim)">20日漲幅</div>
          <div class="stat-val">{perf_20d:+.1f}%</div>
        </div>
        <div class="stat-box">
          <div style="font-size:10px;color:var(--dim)">60日漲幅</div>
          <div class="stat-val">{perf_60d:+.1f}%</div>
        </div>
      </div>
    </div>

    {block_peer_below_perf}

    <!-- INSTITUTIONS + KEY CHIPS -->
    <div class="two-col-grid">
      <div class="card">
        <div class="ct">三大法人（{inst_date_dd}）</div>
        <div class="irow"><span style="color:var(--dim)">外資</span><span class="{f_cls}" style="font-weight:700">{f_val} 張</span></div>
        <div class="irow"><span style="color:var(--dim)">投信</span><span class="{t_cls}" style="font-weight:700">{t_val} 張</span></div>
        <div class="irow"><span style="color:var(--dim)">自營商</span><span class="{d_cls}" style="font-weight:700">{d_val} 張</span></div>
        <div class="itotal">
          <span style="color:var(--dim)">合計</span>
          <span class="{tot_cls}" style="font-weight:700">{tot_val} 張</span>
        </div>
      </div>
      <div class="card">
        <div class="ct">籌碼速覽（{inst_date_dd}）</div>
        <div class="irow"><span style="color:var(--dim)">法人累計 ({chip_sessions}日)</span><span style="color:var(--gold-l);font-weight:700">{cum_inst_txt} 張</span></div>
        <div class="irow"><span style="color:var(--dim)">法人成交比※</span><span style="color:var(--gold-l);font-weight:700">{main_vol_ratio_pct:.2f}%</span></div>
        <div class="irow"><span style="color:var(--dim)">融資增減</span><span class="{mc_cls}" style="font-weight:700">{mc_val} 張</span></div>
        <div class="irow"><span style="color:var(--dim)">融資餘額</span><span style="color:var(--blue);font-weight:700">{margin_bal:,} 張</span></div>
        <div style="font-size:9px;color:var(--dim);margin-top:4px;line-height:1.3">※ 當日三大法人｜淨張數 ÷ 當日總成交量（張），粗估集中度。</div>
      </div>
    </div>

    <!-- TRIPLE MARGIN + PIE -->
    <div class="two-col-grid">
      <div class="card">
        <div class="ct ct-small">資券餘額與股價（{chip_sessions}個交易日）</div>
        <div class="margin-legend">
          <span><span class="dot" style="background:#1e90ff"></span>融資餘額</span>
          <span><span class="dot" style="background:#e84040"></span>融券餘額</span>
          <span><span class="dot" style="background:#ffd700"></span>收盤價（對照）</span>
        </div>
        <canvas id="marginChart" width="294" height="108"></canvas>
      </div>
      <div class="card">
        <div class="ct ct-small">三大法人力道構成（單日·絕對淨張數）</div>
        <div style="font-size:9px;color:var(--dim);margin:-2px 0 4px;line-height:1.35">
          外資／投信／自營各自淨張數<strong>絕對值</strong>占比（非券商分點之大戶／散戶）。</div>
        <div class="fund-flow-wrap">
          <div class="pie-container">
            <canvas id="pieChart" width="94" height="94"></canvas>
            <div class="pie-label">力道<br/>結構</div>
          </div>
          <div class="fund-stats">
            <div class="fund-row"><span style="color:#4fc3f7;font-weight:700">外資</span><span style="color:var(--txt)">{pie_f:.1f}%</span></div>
            <div class="fund-row"><span style="color:#ffd700;font-weight:700">投信</span><span style="color:var(--txt)">{pie_t:.1f}%</span></div>
            <div class="fund-row"><span style="color:#ff9800;font-weight:700">自營</span><span style="color:var(--txt)">{pie_d:.1f}%</span></div>
            <div style="margin-top:6px;padding:4px;background:rgba(212,160,23,.06);border:1px solid var(--gold-d);border-radius:4px;text-align:center;font-size:10px;color:var(--gold-l);">
              法人合計 {tot_val} 張</div>
          </div>
        </div>
      </div>
    </div>

    <!-- DAILY INSTITUTION BARS -->
    <div class="card">
      <div class="ct ct-small">法人買賣超（單日張數｜最近 {chip_sessions} 日）</div>
      <canvas id="instDayChart" width="638" height="88"></canvas>
    </div>

    <!-- STRATEGY -->
    <div class="card">
      <div class="ct">⚡ 自動操作策略建議</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;font-size:11px">
        <div style="background:rgba(0,200,83,.08);border:1px solid rgba(0,200,83,.3);border-radius:6px;padding:8px;text-align:center">
          <div style="color:var(--green);font-weight:700">最佳支撐買進區</div>
          <div style="font-size:18px;font-weight:900;color:var(--green);margin-top:4px">{sup_low:.1f} ～ {sup_high:.1f} 元</div>
          <div style="color:#888;margin-top:3px">MA10 ~ MA20 附近</div>
        </div>
        <div style="background:rgba(232,64,64,.08);border:1px solid rgba(232,64,64,.3);border-radius:6px;padding:8px;text-align:center">
          <div style="color:var(--red);font-weight:700">停損參考</div>
          <div style="font-size:18px;font-weight:900;color:var(--red);margin-top:4px">{stop_loss:.1f} 元 以下</div>
          <div style="color:#888;margin-top:3px">MA20 跌破視為轉弱</div>
        </div>
      </div>
    </div>

  </div><!-- /right -->
</div>

{block_after_main}

<!-- FOOTER -->
<div class="footer-bar">{footer_bar}</div>
<div class="ed-footer-note" style="text-align:center;font-size:10px;color:#445566;margin-top:6px">{footer_hint}</div>

<script>
const KDATA = {kdata_json};
const CHIP_DAYS = {chip_series_json};

(function(){{
  // ── K-LINE ──
  const kc=document.getElementById('kc'), ctx=kc.getContext('2d');
  const W=kc.width,H=kc.height,PL=6,PR=4,PT=6,PB=14;
  const IW=W-PL-PR,IH=H-PT-PB;
  const N=KDATA.length;
  if(N>=2){{
  ctx.fillStyle='#0a1018'; ctx.fillRect(0,0,W,H);
  const prices=KDATA.flatMap(d=>[d.h,d.l]);
  const pMin=Math.min(...prices)*0.98, pMax=Math.max(...prices)*1.01;
  const pR=pMax-pMin;
  const kX=i=>PL+(i+.5)*(IW/N);
  const kY=v=>PT+IH-(v-pMin)/pR*IH;
  for(let i=0;i<=4;i++){{
    const y=PT+i*IH/4;
    ctx.strokeStyle='rgba(255,255,255,.04)';ctx.lineWidth=.5;
    ctx.beginPath();ctx.moveTo(PL,y);ctx.lineTo(W-PR,y);ctx.stroke();
    const v=pMax-(pMax-pMin)*i/4;
    ctx.fillStyle='#445566';ctx.font='9px sans-serif';ctx.textAlign='right';
    ctx.fillText(v.toFixed(1),W-PR,y+3);
  }}
  [['ma20','#f06292'],['ma10','#4fc3f7'],['ma5','#ffeb3b']].forEach(([k,col])=>{{
    ctx.strokeStyle=col;ctx.lineWidth=1;ctx.beginPath();
    let s=false;
    KDATA.forEach((d,i)=>{{
      if(d[k]===null)return;
      if(!s){{ctx.moveTo(kX(i),kY(d[k]));s=true;}}
      else ctx.lineTo(kX(i),kY(d[k]));
    }});
    ctx.stroke();
  }});
  const cw=Math.max(2,IW/N*.6);
  KDATA.forEach((d,i)=>{{
    const up=d.c>=d.o;
    const col=up?'#e84040':'#00c853';
    ctx.strokeStyle=col;ctx.fillStyle=col;ctx.lineWidth=.8;
    ctx.beginPath();ctx.moveTo(kX(i),kY(d.h));ctx.lineTo(kX(i),kY(d.l));ctx.stroke();
    const by=kY(Math.max(d.o,d.c)),bh=Math.max(1,Math.abs(kY(d.o)-kY(d.c)));
    ctx.fillRect(kX(i)-cw/2,by,cw,bh);
  }});

  // ── MACD ──
  const mc=document.getElementById('mc'),mctx=mc.getContext('2d');
  const MW=mc.width,MH=mc.height;
  mctx.fillStyle='#0a1018';mctx.fillRect(0,0,MW,MH);
  const difs=KDATA.map(d=>d.dif||0);
  const macds=KDATA.map(d=>d.macd||0);
  const oscs=KDATA.map(d=>d.osc||0);
  const oscAbs=oscs.map(v=>Math.abs(v));
  const mmax=(Math.max(1e-9,...difs.map(Math.abs),...macds.map(Math.abs),...oscAbs))*1.2;
  const mX=i=>(i+.5)*MW/N;
  const mY=v=>MH/2-(v/mmax)*(MH/2);
  const obW=MW/N*.7;
  oscs.forEach((v,i)=>{{
    mctx.fillStyle=v>=0?'rgba(232,64,64,.6)':'rgba(0,200,83,.6)';
    const y=v>=0?mY(v):MH/2;const h=Math.max(1,Math.abs(mY(v)-MH/2));
    mctx.fillRect(mX(i)-obW/2,y,obW,h);
  }});
  [[difs,'#ff9800'],[macds,'#4fc3f7']].forEach(([arr,col])=>{{
    mctx.strokeStyle=col;mctx.lineWidth=1;mctx.beginPath();
    arr.forEach((v,i)=>i===0?mctx.moveTo(mX(i),mY(v)):mctx.lineTo(mX(i),mY(v)));
    mctx.stroke();
  }});

  // ── RSI ──
  const rc=document.getElementById('rc'),rctx=rc.getContext('2d');
  const RW=rc.width,RH=rc.height;
  rctx.fillStyle='#0a1018';rctx.fillRect(0,0,RW,RH);
  const rX=i=>(i+.5)*RW/N;
  const rY=v=>RH-(v/100)*RH;
  [70,50,30].forEach(lv=>{{
    rctx.strokeStyle='rgba(255,255,255,.06)';rctx.lineWidth=.5;
    rctx.beginPath();rctx.moveTo(0,rY(lv));rctx.lineTo(RW,rY(lv));rctx.stroke();
  }});
  [[KDATA.map(d=>d.rsi5||50),'#ffeb3b'],[KDATA.map(d=>d.rsi10||50),'#80cbc4']].forEach(([arr,col])=>{{
    rctx.strokeStyle=col;rctx.lineWidth=1;rctx.beginPath();
    arr.forEach((v,i)=>i===0?rctx.moveTo(rX(i),rY(v)):rctx.lineTo(rX(i),rY(v)));
    rctx.stroke();
  }});
  }}else{{
    ctx.fillStyle='#0a1018';ctx.fillRect(0,0,W,H);ctx.fillStyle='#667788';ctx.font='11px sans-serif';ctx.fillText('K線資料不足',W/3,H/3);
    const mz=document.getElementById('mc'),mr=document.getElementById('rc');
    [['mc',mz],['rc',mr]].forEach(([_,el])=>{{const ct=el.getContext('2d');ct.fillStyle='#0a1018';ct.fillRect(0,0,el.width,el.height);}});
  }}

  // ── 資券＋價／三線圖 ── (同期力積電範本版型)
  const mgc=document.getElementById('marginChart'),mgctx=mgc.getContext('2d');
  const MgW=mgc.width,MgH=mgc.height,mgPad={{l:10,r:12,t:8,b:17}};
  mgctx.fillStyle='#0a1018';mgctx.fillRect(0,0,MgW,MgH);
  const DM=CHIP_DAYS.length;
  if(DM<1){{
    mgctx.fillStyle='#667788';mgctx.font='11px sans-serif';mgctx.textAlign='center';
    mgctx.fillText('未取得多日資券序列',MgW/2,MgH/2);}}
  else{{
    const mginW=MgW-mgPad.l-mgPad.r,mginH=MgH-mgPad.t-mgPad.b;
    const fin=CHIP_DAYS.map(d=>d.financing),shr=CHIP_DAYS.map(d=>d.short_sell),pr=CHIP_DAYS.map(d=>d.close);
    const fMin=Math.min(...fin)*0.997,fMax=Math.max(...fin)*1.003;
    const sMin=Math.min(...shr)*0.99,sMax=Math.max(...shr)*1.015;
    const pMin=Math.min(...pr)*0.993,pMax=Math.max(...pr)*1.01;
    function xAt(i){{return mgPad.l+(DM<=1?mginW/2:i*mginW/Math.max(DM-1,1));}}
    function yFin(v){{return mgPad.t+mginH-(v-fMin)/Math.max(fMax-fMin,1e-6)*mginH;}}
    function yShr(v){{return mgPad.t+mginH-(v-sMin)/Math.max(sMax-sMin,1e-6)*mginH;}}
    function yPr(v){{return mgPad.t+mginH-(v-pMin)/Math.max(pMax-pMin,1e-6)*mginH;}}
    mgctx.strokeStyle='rgba(255,255,255,.05)';mgctx.lineWidth=0.5;
    mgctx.strokeRect(mgPad.l,mgPad.t,mginW,mginH);
    mgctx.strokeStyle='#1e90ff';mgctx.lineWidth=1.35;mgctx.beginPath();
    fin.forEach((v,i)=>i===0?mgctx.moveTo(xAt(i),yFin(v)):mgctx.lineTo(xAt(i),yFin(v)));
    mgctx.stroke();
    mgctx.strokeStyle='#e84040';mgctx.lineWidth=1.35;mgctx.beginPath();
    shr.forEach((v,i)=>i===0?mgctx.moveTo(xAt(i),yShr(v)):mgctx.lineTo(xAt(i),yShr(v)));
    mgctx.stroke();
    mgctx.strokeStyle='#ffd700';mgctx.lineWidth=1.55;mgctx.beginPath();
    pr.forEach((v,i)=>i===0?mgctx.moveTo(xAt(i),yPr(v)):mgctx.lineTo(xAt(i),yPr(v)));
    mgctx.stroke();
    mgctx.fillStyle='#445566';mgctx.font='8px sans-serif';mgctx.textAlign='center';
    CHIP_DAYS.forEach((d,i)=>mgctx.fillText(d.day_label,xAt(i),MgH-3));
  }}

  // ── 法人單日分組長條 ──
  const ic=document.getElementById('instDayChart'),ictx=ic.getContext('2d');
  const Iw=ic.width,Ih=ic.height,icPad={{l:8,r:12,t:10,b:18}};
  ictx.fillStyle='#0a1018';ictx.fillRect(0,0,Iw,Ih);
  if(DM<1){{
    ictx.fillStyle='#667788';ictx.font='11px sans-serif';ictx.textAlign='center';
    ictx.fillText('未取得法人多日序列',Iw/2,Ih/2);}}
  else{{
    let maxA=1000;
    CHIP_DAYS.forEach(d=>{{
      maxA=Math.max(maxA,Math.abs(d.foreign),Math.abs(d.trust),Math.abs(d.dealer));
    }});
    const innerW=Iw-icPad.l-icPad.r, innerH=Ih-icPad.t-icPad.b, midy=icPad.t+innerH/2;
    ictx.strokeStyle='rgba(255,255,255,.06)';ictx.lineWidth=0.5;
    ictx.beginPath();ictx.moveTo(icPad.l,midy);ictx.lineTo(Iw-icPad.r,midy);ictx.stroke();
    function ix(i){{return icPad.l+(DM<=1?innerW/2:i*innerW/Math.max(DM-1,1));}}
    const bw=Math.max(2,Math.min(11, innerW/Math.max(DM*5,14)));
    const gap=bw>0 ? Math.max(0.75,bw*0.18) : 0;
    const cluster=bw*3+gap*2;
    [['foreign','#4fc3f7'],['trust','#ffd700'],['dealer','#ff9800']].forEach(([fld,col],j)=>{{
      ictx.fillStyle=col+'cc';
      CHIP_DAYS.forEach((d,i)=>{{
        const v=d[fld], h=(Math.abs(v)/maxA)*(innerH/2-6);
        const ox=ix(i)-cluster/2;
        const xc=ox+j*(bw+gap);
        if(v>=0){{ictx.fillRect(xc,midy-h,bw,h);}}
        else{{ictx.fillRect(xc,midy,bw,h);}}
      }});
    }});
    ictx.fillStyle='#445566';ictx.font='8px sans-serif';ictx.textAlign='center';
    CHIP_DAYS.forEach((d,i)=>ictx.fillText(d.day_label,ix(i),Ih-3));
    [['外資','#4fc3f7'],['投信','#ffd700'],['自營','#ff9800']].forEach(([l,c],k)=>{{
      ictx.fillStyle=c;ictx.fillRect(4+k*54,4,10,10);
      ictx.fillStyle='#aaa';ictx.font='9px sans-serif';ictx.textAlign='left';
      ictx.fillText(l,18+k*54,13);
    }});
  }}

  // ── 力道甜甜圈 ──（三大法人｜絕對淨張數占比）
  const PF={pie_pf_fr}, PT={pie_pt_fr}, PD={pie_pd_fr};
  const pel=document.getElementById('pieChart'),pctx=pel.getContext('2d');
  const pCvW=pel.width,pCvH=pel.height,cx=pCvW/2,cy=pCvH/2,rad=40;
  pctx.fillStyle='#0a1018';pctx.fillRect(0,0,pCvW,pCvH);
  const segs=[
    {{pct:PF,col:'#4fc3f7'}},
    {{pct:PT,col:'#ffd700'}},
    {{pct:PD,col:'#ff9800'}}];
  let ang=-Math.PI/2;
  segs.forEach(s=>{{
    const a=s.pct*Math.PI*2;if(a<1e-6)return;
    pctx.beginPath();pctx.moveTo(cx,cy);
    pctx.arc(cx,cy,rad,ang,ang+a);pctx.closePath();
    pctx.fillStyle=s.col;pctx.fill();ang+=a;
  }});
  pctx.beginPath();pctx.arc(cx,cy,25,0,Math.PI*2);
  pctx.fillStyle='#111820';pctx.fill();
}})();
</script>
</body>
</html>
"""


def generate_html(
    data: dict,
    name: str = "",
    override: Optional[dict] = None,
) -> str:
    close = data["close"]
    ma10 = data["ma10"]
    ma20 = data["ma20"]

    def tri_pair(cur, prv):
        if cur is None or prv is None:
            return ""
        return "↑" if cur >= prv else "↓"

    kl = data["kline"]
    kl2 = kl[-2:]
    prv, cur = (kl2[0], kl2[-1]) if len(kl2) >= 2 else ({}, {})
    ma5_arrow = tri_pair(cur.get("ma5"), prv.get("ma5"))
    ma10_arrow = tri_pair(cur.get("ma10"), prv.get("ma10"))
    ma20_arrow = tri_pair(cur.get("ma20"), prv.get("ma20"))
    dif_arrow = tri_pair(cur.get("dif"), prv.get("dif"))
    macd_arrow = tri_pair(cur.get("macd"), prv.get("macd"))
    osc_arrow = tri_pair(cur.get("osc"), prv.get("osc"))
    rsi5_arrow = tri_pair(cur.get("rsi5"), prv.get("rsi5"))
    rsi10_arrow = tri_pair(cur.get("rsi10"), prv.get("rsi10"))

    ktail = kl[-8:] if len(kl) >= 8 else kl
    kline_dates_html = "".join(f"<span>{d['date']}</span>" for d in ktail)

    dates = data["date"].split("/")  # YYYY/MM/DD
    inst_date_dd = f"{dates[1]}/{dates[2]}" if len(dates) >= 3 else data["date"]

    chip_n = data.get("chip_days_n") or 0
    chip_sessions = str(chip_n) if chip_n else "—"

    pie_pf_fr = round(data["pie_f"] / 100.0, 6)
    pie_pt_fr = round(data["pie_t"] / 100.0, 6)
    pie_pd_fr = round(data["pie_d"] / 100.0, 6)

    cum_inst_txt = fmt_num(data["cum_inst_total_10"])

    # 支撐位與停損
    sup_low = round(ma20 * 0.99, 1)
    sup_high = round(ma10 * 1.01, 1)
    stop_loss = round(ma20 * 0.97, 1)

    f = data["foreign"]
    t = data["trust"]
    d = data["dealer"]
    tot = data["inst_total"]
    mc = data["margin_chg"]

    chg_tri = "▲" if data["change"] >= 0 else "▼"

    gen_time = datetime.now().strftime("%Y/%m/%d %H:%M")
    editorial = build_override_html(override or {}, data, gen_time)

    html = HTML_TEMPLATE.format(
        code=data["code"],
        name=name or data["code"],
        date=data["date"],
        close=close,
        change=data["change"],
        pct=data["pct"],
        high=data["high"],
        low=data["low"],
        limit_up=data["limit_up"],
        limit_down=data["limit_down"],
        avg=data["avg"],
        volume=data["volume"],
        ma5=data["ma5"],
        ma10=data["ma10"],
        ma20=data["ma20"],
        dif=data["dif"],
        macd_sig=data["macd_sig"],
        osc=data["osc"],
        rsi5=data["rsi5"],
        rsi10=data["rsi10"],
        ma5_arrow=ma5_arrow,
        ma10_arrow=ma10_arrow,
        ma20_arrow=ma20_arrow,
        dif_arrow=dif_arrow,
        macd_arrow=macd_arrow,
        osc_arrow=osc_arrow,
        rsi5_arrow=rsi5_arrow,
        rsi10_arrow=rsi10_arrow,
        price_cls="pos" if data["change"] >= 0 else "neg",
        chg_tri=chg_tri,
        f_val=fmt_num(f),
        t_val=fmt_num(t),
        d_val=fmt_num(d),
        tot_val=fmt_num(tot),
        f_cls=color_cls(f),
        t_cls=color_cls(t),
        d_cls=color_cls(d),
        tot_cls=color_cls(tot),
        margin_bal=data["margin_bal"],
        short_bal=data["short_bal"],
        mc_val=fmt_num(mc),
        mc_cls=color_cls(mc),
        perf_10d=data["perf_10d"] or 0,
        perf_20d=data["perf_20d"] or 0,
        perf_60d=data["perf_60d"] or 0,
        sup_low=sup_low,
        sup_high=sup_high,
        stop_loss=stop_loss,
        kdata_json=json.dumps(data["kline"], ensure_ascii=False),
        chip_series_json=json.dumps(
            data.get("daily_chip_series") or [], ensure_ascii=False
        ),
        cum_inst_txt=cum_inst_txt,
        main_vol_ratio_pct=data["main_vol_ratio_pct"],
        pie_f=data["pie_f"],
        pie_t=data["pie_t"],
        pie_d=data["pie_d"],
        pie_pf_fr=pie_pf_fr,
        pie_pt_fr=pie_pt_fr,
        pie_pd_fr=pie_pd_fr,
        inst_date_dd=inst_date_dd,
        chip_sessions=chip_sessions,
        kline_dates_html=kline_dates_html,
        **editorial,
    )
    return html


# ════════════════════════════════════════════════
#  5. 主程式入口
# ════════════════════════════════════════════════

# 公司名稱對照表（可自行擴充）
COMPANY_NAMES = {
    "6770": "力積電",
    "2408": "南亞科",
    "3037": "欣興",
    "2330": "台積電",
    "2303": "聯電",
    "2344": "華邦電",
    "2337": "旺宏",
}


def main():
    if len(sys.argv) < 2:
        print("用法: python stock_report_generator.py <股票代號>")
        print("範例: python stock_report_generator.py 6770")
        sys.exit(1)

    ticker_code = sys.argv[1].strip()
    target_date = sys.argv[2] if len(sys.argv) > 2 else None
    name = COMPANY_NAMES.get(ticker_code, ticker_code)

    print(f"\n{'='*50}")
    print(f"  台股深度分析報告生成器")
    print(f"  目標股票：{name}（{ticker_code}）")
    print(f"{'='*50}\n")

    data = build_report_data(ticker_code, target_date)
    extra = load_report_override(ticker_code)
    if extra:
        print(f"📎 已載入手填補充 → report_overrides/{ticker_code}.json")
    html = generate_html(data, name, override=extra)

    out_dir = Path("reports")
    out_dir.mkdir(exist_ok=True)
    date_str = data["date"].replace("/", "")
    out_path = out_dir / f"{ticker_code}_{name}_深度分析_{date_str}.html"
    out_path.write_text(html, encoding="utf-8")

    print(f"\n✅ 報告已生成：{out_path}")
    print(f"   股票：{name}（{ticker_code}）")
    print(f"   日期：{data['date']}")
    print(f"   收盤：{data['close']:.2f} ({data['pct']:+.2f}%)")
    print(f"   三大法人：外資{fmt_num(data['foreign'])} 投信{fmt_num(data['trust'])} 自營{fmt_num(data['dealer'])}")


if __name__ == "__main__":
    main()
