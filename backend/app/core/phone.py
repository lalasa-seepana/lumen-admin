from __future__ import annotations

import re
from typing import Optional, Tuple


_DIGITS = re.compile(r"\D+")


def normalize_phone_e164(raw: Optional[str], *, default_region: str = "IN") -> Optional[str]:
    """Best-effort E.164 for POC. Returns None when phone is missing or unusable."""
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    digits = _DIGITS.sub("", text)
    if len(digits) < 7 or len(digits) > 15:
        return None
    if text.startswith("+"):
        return f"+{digits}"
    if default_region == "IN":
        if len(digits) == 10:
            return f"+91{digits}"
        if len(digits) == 12 and digits.startswith("91"):
            return f"+{digits}"
        if len(digits) == 11 and digits.startswith("0"):
            return f"+91{digits[1:]}"
    return f"+{digits}"


def phones_match(left: Optional[str], right: Optional[str]) -> bool:
    a = normalize_phone_e164(left)
    b = normalize_phone_e164(right)
    return a is not None and a == b


def describe_phone(raw: Optional[str]) -> Tuple[Optional[str], bool]:
    """Return (e164, is_normalized_ok)."""
    e164 = normalize_phone_e164(raw)
    return e164, e164 is not None
