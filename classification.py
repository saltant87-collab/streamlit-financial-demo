"""Stock classification module for ASIC/IP/AI themes."""

from __future__ import annotations

try:
    from config import STOCK_UNIVERSE
except Exception:
    STOCK_UNIVERSE: list[dict[str, str]] = []


TIER_NORMALIZATION_MAP: dict[str, str] = {
    "core": "core",
    "核心": "core",
    "核心asic/ip股": "core",
    "核心asicip股": "core",
    "related": "related",
    "ai供應鏈相關股": "related",
    "代工/設備/伺服器相關股": "related",
    "代工設備伺服器相關股": "related",
    "peripheral": "peripheral",
    "周邊": "peripheral",
    "題材型": "peripheral",
    "其他": "peripheral",
}

FALLBACK_CORE_CODES: set[str] = {
    "2454",
    "3443",
    "3661",
    "3035",
    "3529",
    "6643",
    "6533",
    "8227",
}

FALLBACK_RELATED_CODES: set[str] = {"2330", "2317", "2382"}

TAG_KEYWORD_MAP: dict[str, list[str]] = {
    "ASIC": ["asic", "客製化晶片"],
    "IP": [" ip ", "ip授權", "cpu ip", "ip"],
    "矽智財": ["矽智財", "sip", "silicon intellectual property"],
    "IC設計": ["ic設計", "ic design", "晶片設計"],
    "SoC": ["soc", "system on chip"],
    "AI ASIC": ["ai asic", "aiasic"],
    "Design Service": ["設計服務", "design service", "nre"],
    "Turnkey": ["turnkey", "全流程"],
    "CPU IP": ["cpu ip", "處理器ip"],
    "RISC-V": ["risc-v", "riscv"],
    "晶圓代工": ["晶圓代工", "foundry"],
    "AI 伺服器": ["ai伺服器", "ai server", "伺服器"],
    "封裝測試": ["封裝測試", "封測", "osat"],
    "供應鏈": ["供應鏈", "上游", "下游"],
}


def _normalize_text(text: str | None) -> str:
    """Normalize text for robust keyword matching."""
    if text is None:
        return ""
    value = str(text).strip().lower()
    value = value.replace("　", " ").replace("/", " ").replace("-", " ")
    value = " ".join(value.split())
    return value


def _lookup_row_by_code(code: str) -> dict[str, str] | None:
    """Lookup stock row from STOCK_UNIVERSE by code."""
    for row in STOCK_UNIVERSE:
        if str(row.get("code", "")) == str(code):
            return row
    return None


def _normalize_tier(tier: str | None) -> str:
    """Normalize tier text to one of core/related/peripheral."""
    normalized = _normalize_text(tier)
    if normalized in TIER_NORMALIZATION_MAP:
        return TIER_NORMALIZATION_MAP[normalized]
    if "core" in normalized or "核心" in normalized:
        return "core"
    if "related" in normalized or "供應鏈" in normalized or "代工" in normalized:
        return "related"
    return "peripheral"


def _infer_tags_from_text(text: str) -> list[str]:
    """Infer industry tags from normalized text."""
    normalized = f" { _normalize_text(text) } "
    tags: list[str] = []
    for tag, keywords in TAG_KEYWORD_MAP.items():
        for keyword in keywords:
            key = f" { _normalize_text(keyword) } "
            if key.strip() and key in normalized:
                tags.append(tag)
                break
    return tags


def _infer_tier_from_role(role: str | None) -> str:
    """Infer stock tier by role text when tier is missing."""
    role_text = _normalize_text(role)
    if any(token in role_text for token in ["asic", "ip", "矽智財", "turnkey", "risc", "soc"]):
        return "core"
    if any(token in role_text for token in ["供應鏈", "晶圓代工", "伺服器", "封裝", "測試"]):
        return "related"
    return "peripheral"


def get_stock_meta(code: str) -> dict[str, str]:
    """Return stock metadata from config, including normalized tier."""
    row = _lookup_row_by_code(code)
    if row is not None:
        role = str(row.get("role", ""))
        tier = row.get("tier")
        if tier is None or str(tier).strip() == "":
            tier = _infer_tier_from_role(role)
        return {
            "code": str(row.get("code", code)),
            "name": str(row.get("name", "")),
            "role": role,
            "category": str(row.get("category", "")),
            "tier": _normalize_tier(str(tier)),
        }

    if code in FALLBACK_CORE_CODES:
        fallback_tier = "core"
    elif code in FALLBACK_RELATED_CODES:
        fallback_tier = "related"
    else:
        fallback_tier = "peripheral"
    return {"code": code, "name": "", "role": "", "category": "", "tier": fallback_tier}


def match_industry_tags(
    name: str | None,
    role: str | None = None,
    category: str | None = None,
) -> list[str]:
    """Return industry tags for display and filtering."""
    text = " ".join([_normalize_text(name), _normalize_text(role), _normalize_text(category)])
    tags = _infer_tags_from_text(text)
    return sorted(set(tags))


def get_stock_tier(code: str, name: str | None = None, role: str | None = None) -> str:
    """Return the stock tier, such as core / related / peripheral."""
    meta = get_stock_meta(code)
    if meta["tier"] in {"core", "related", "peripheral"}:
        return meta["tier"]

    tags = match_industry_tags(name=name, role=role, category=meta.get("category", ""))
    if {"ASIC", "IP", "矽智財", "AI ASIC", "Design Service", "CPU IP", "RISC-V"} & set(tags):
        return "core"
    if {"晶圓代工", "AI 伺服器", "封裝測試", "供應鏈"} & set(tags):
        return "related"
    return "peripheral"


def is_core_asic_ip_stock(code: str, name: str | None = None, role: str | None = None) -> bool:
    """Return True if the stock is a core ASIC/IP company."""
    tier = get_stock_tier(code, name=name, role=role)
    if tier == "core":
        return True
    if tier == "related":
        return False

    role_text = _normalize_text(role)
    if any(token in role_text for token in ["供應鏈", "晶圓代工", "伺服器", "封裝", "測試"]):
        return False

    tags = match_industry_tags(name=name, role=role, category=get_stock_meta(code).get("category"))
    core_only_tags = {"IP", "矽智財", "Design Service", "Turnkey", "CPU IP", "RISC-V"}
    return bool(core_only_tags & set(tags))


def classify_stock_role(code: str, name: str | None = None, role: str | None = None) -> str:
    """Return a normalized role classification."""
    meta = get_stock_meta(code)
    role_text = role if role is not None and str(role).strip() else meta.get("role", "")
    tier = get_stock_tier(code, name=name or meta.get("name", ""), role=role_text)

    if tier == "core":
        return "核心ASIC/IP公司"
    if tier == "related":
        return "AI供應鏈相關"
    return "周邊/題材型"
