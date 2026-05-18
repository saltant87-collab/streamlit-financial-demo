"""Project configuration for the Taiwan ASIC/IP/AI dashboard."""

from __future__ import annotations

YEARS: list[int] = [2021, 2022, 2023, 2024, 2025]

STOCK_UNIVERSE: list[dict[str, str]] = [
    {
        "code": "2454",
        "name": "聯發科",
        "role": "AI ASIC / SoC",
        "category": "IC設計",
        "tier": "核心ASIC/IP股",
        "moat_profile": "較適合長期護城河分析",
    },
    {
        "code": "3443",
        "name": "創意",
        "role": "ASIC 設計服務 / NRE / Turnkey",
        "category": "IC設計服務",
        "tier": "核心ASIC/IP股",
        "moat_profile": "較適合長期護城河分析",
    },
    {
        "code": "3661",
        "name": "世芯-KY",
        "role": "ASIC 設計服務 / AI ASIC",
        "category": "IC設計服務",
        "tier": "核心ASIC/IP股",
        "moat_profile": "偏成長驅動，波動較高",
    },
    {
        "code": "3035",
        "name": "智原",
        "role": "ASIC / IP / Turnkey",
        "category": "IC設計服務",
        "tier": "核心ASIC/IP股",
        "moat_profile": "中長期可追蹤",
    },
    {
        "code": "3529",
        "name": "力旺",
        "role": "IP 授權 / 矽智財",
        "category": "IP",
        "tier": "核心ASIC/IP股",
        "moat_profile": "較適合長期護城河分析",
    },
    {
        "code": "6643",
        "name": "M31",
        "role": "IP 授權 / 矽智財",
        "category": "IP",
        "tier": "核心ASIC/IP股",
        "moat_profile": "較適合長期護城河分析",
    },
    {
        "code": "6533",
        "name": "晶心科",
        "role": "CPU IP / RISC-V",
        "category": "IP",
        "tier": "核心ASIC/IP股",
        "moat_profile": "偏題材成長型",
    },
    {
        "code": "8227",
        "name": "巨有科技",
        "role": "ASIC Turnkey / Design Service",
        "category": "IC設計服務",
        "tier": "核心ASIC/IP股",
        "moat_profile": "景氣循環敏感",
    },
    {
        "code": "2330",
        "name": "台積電",
        "role": "晶圓代工 / AI ASIC 供應鏈",
        "category": "晶圓代工",
        "tier": "代工/設備/伺服器相關股",
        "moat_profile": "較適合長期護城河分析",
    },
    {
        "code": "2317",
        "name": "鴻海",
        "role": "AI 伺服器 / ASIC 供應鏈",
        "category": "系統整合",
        "tier": "AI供應鏈相關股",
        "moat_profile": "景氣循環敏感",
    },
    {
        "code": "2382",
        "name": "廣達",
        "role": "AI 伺服器 / 供應鏈",
        "category": "伺服器",
        "tier": "AI供應鏈相關股",
        "moat_profile": "景氣循環敏感",
    },
    {
        "code": "2409",
        "name": "友達",
        "role": "顯示器供應鏈 / 非核心ASIC-IP",
        "category": "面板",
        "tier": "AI供應鏈相關股",
        "moat_profile": "景氣循環敏感",
    },
]

STOCKS: list[str] = [stock["code"] for stock in STOCK_UNIVERSE]
STOCK_NAMES: dict[str, str] = {stock["code"]: stock["name"] for stock in STOCK_UNIVERSE}
STOCK_ROLE_MAP: dict[str, str] = {
    stock["code"]: stock["role"] for stock in STOCK_UNIVERSE
}
