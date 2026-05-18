"""MOPS annual financial statement scraping utilities."""

from __future__ import annotations

from io import StringIO

import pandas as pd
import requests

# Primary host only: mops.twse.com.tw often blocks automated access.
BASE_HOSTS: list[str] = ["https://mopsov.twse.com.tw"]
INCOME_STATEMENT_PATH = "/mops/web/ajax_t163sb04"
BALANCE_SHEET_PATH = "/mops/web/ajax_t163sb05"
CASHFLOW_STATEMENT_PATH = "/mops/web/ajax_t163sb20"

REQUEST_HEADERS: dict[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://mops.twse.com.tw/mops/web/t163sb04",
    "Origin": "https://mops.twse.com.tw",
}


def _roc_year(year: int) -> int:
    """Convert Gregorian year to ROC year."""
    return year - 1911


def _build_payload(security_code: str, year: int, market_type: str) -> dict[str, str]:
    """Build annual statement query payload."""
    return {
        "encodeURIComponent": "1",
        "step": "1",
        "firstin": "1",
        "off": "1",
        "isnew": "false",
        "co_id": security_code,
        "year": str(_roc_year(year)),
        "season": "4",
        "TYPEK": market_type,
    }


def _fetch_tables(session: requests.Session, url: str, payload: dict[str, str]) -> list[pd.DataFrame]:
    """Fetch statement HTML and parse all tables."""
    response = session.post(url, data=payload, timeout=30)
    response.raise_for_status()
    response.encoding = "utf-8"
    if "THE PAGE CANNOT BE ACCESSED" in response.text:
        return []
    try:
        return pd.read_html(StringIO(response.text))
    except ValueError:
        return []


def _normalize_statement_df(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize statement DataFrame and keep original table headers."""
    cleaned = df.copy()
    if isinstance(cleaned.columns, pd.MultiIndex):
        cleaned.columns = [
            "_".join([str(level).strip() for level in col if str(level) != "nan"]).strip("_")
            for col in cleaned.columns
        ]
    cleaned = cleaned.dropna(how="all").dropna(axis=1, how="all")
    cleaned.columns = [str(col).strip() for col in cleaned.columns]
    return cleaned


def _table_contains_security_code(table: pd.DataFrame, security_code: str) -> bool:
    """Return True when the table has a row for the given security code."""
    if table.empty or table.shape[1] < 2:
        return False
    code_series = table.iloc[:, 0].astype(str).str.strip()
    return (code_series == str(security_code).strip()).any()


def _score_table(table: pd.DataFrame, security_code: str, keywords: list[str]) -> int:
    """Score candidate tables; prefer company row + expected column labels."""
    if table.empty:
        return -1

    score = 0
    if _table_contains_security_code(table, security_code):
        score += 1000

    column_text = " ".join(str(col) for col in table.columns)
    for keyword in keywords:
        if keyword in column_text:
            score += 10
        elif keyword in table.astype(str).to_string():
            score += 1

    if table.shape[1] >= 5:
        score += 5
    return score


def _pick_company_row_table(
    tables: list[pd.DataFrame],
    security_code: str,
    keywords: list[str],
) -> pd.DataFrame:
    """Pick the best table and return only the target company's row."""
    best_table = pd.DataFrame()
    best_score = -1

    for table in tables:
        score = _score_table(table=table, security_code=security_code, keywords=keywords)
        if score > best_score:
            best_score = score
            best_table = table

    if best_table.empty or not _table_contains_security_code(best_table, security_code):
        return pd.DataFrame()

    code_col = best_table.columns[0]
    mask = best_table[code_col].astype(str).str.strip() == str(security_code).strip()
    return _normalize_statement_df(best_table.loc[mask].copy())


def _fetch_statement_by_year(
    path: str,
    security_code: str,
    years: list[int],
    keywords: list[str],
) -> dict[int, pd.DataFrame]:
    """Fetch annual statement dict by year with resilient fallback."""
    session = requests.Session()
    session.headers.update(REQUEST_HEADERS)
    result: dict[int, pd.DataFrame] = {}

    for year in years:
        year_df = pd.DataFrame()
        for host in BASE_HOSTS:
            session.headers.update(
                {
                    "Referer": f"{host}/mops/web/t163sb04",
                    "Origin": host,
                }
            )
            url = f"{host}{path}"
            for market_type in ("sii", "otc"):
                payload = _build_payload(security_code=security_code, year=year, market_type=market_type)
                try:
                    tables = _fetch_tables(session=session, url=url, payload=payload)
                    candidate = _pick_company_row_table(
                        tables=tables,
                        security_code=security_code,
                        keywords=keywords,
                    )
                    if not candidate.empty:
                        year_df = candidate
                        break
                except Exception:
                    continue
            if not year_df.empty:
                break
        result[year] = year_df

    return result


def fetch_income_statement(security_code: str, years: list[int]) -> dict[int, pd.DataFrame]:
    """Fetch annual income statement DataFrames by year."""
    keywords = ["營業收入", "營業毛利", "每股盈餘"]
    return _fetch_statement_by_year(
        path=INCOME_STATEMENT_PATH,
        security_code=security_code,
        years=years,
        keywords=keywords,
    )


def fetch_balance_sheet(security_code: str, years: list[int]) -> dict[int, pd.DataFrame]:
    """Fetch annual balance sheet DataFrames by year."""
    keywords = ["資產總計", "負債總計", "權益總計", "流動資產", "股東權益"]
    return _fetch_statement_by_year(
        path=BALANCE_SHEET_PATH,
        security_code=security_code,
        years=years,
        keywords=keywords,
    )


def fetch_cashflow_statement(security_code: str, years: list[int]) -> dict[int, pd.DataFrame]:
    """Fetch annual cashflow statement DataFrames by year."""
    keywords = ["營業活動之淨現金流入", "投資活動之淨現金流入", "籌資活動之淨現金流入"]
    return _fetch_statement_by_year(
        path=CASHFLOW_STATEMENT_PATH,
        security_code=security_code,
        years=years,
        keywords=keywords,
    )
