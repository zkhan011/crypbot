"""Tolerant BingX account-type parsing without reflecting values back to the API."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, Callable
import re


class AccountType(StrEnum):
    SPOT = "spot"
    SWAP = "swap"
    FUND = "fund"
    UNKNOWN = "unknown"
    MISSING = "missing"


@dataclass(frozen=True)
class AccountBalanceView:
    raw_account_type: str | None
    account_type: AccountType
    usdt_balance: Decimal


class AccountTypeParseError(ValueError):
    pass


ACCOUNT_TYPE_ALIASES: dict[str, AccountType] = {
    "sopt": AccountType.SPOT,
    "spot": AccountType.SPOT,
    "swap": AccountType.SWAP,
    "perpetual": AccountType.SWAP,
    "fund": AccountType.FUND,
}


def parse_account_balance(item: Any, unknown_observer: Callable[[str], None] | None = None) -> AccountBalanceView:
    if not isinstance(item, dict):
        raise AccountTypeParseError("account balance item must be an object")
    raw_value = item.get("accountType")
    raw = str(raw_value) if raw_value is not None else None
    normalized = ACCOUNT_TYPE_ALIASES.get(raw.lower(), AccountType.UNKNOWN) if raw is not None else AccountType.MISSING
    if raw is None or not raw.strip():
        normalized = AccountType.MISSING
    elif normalized == AccountType.UNKNOWN and unknown_observer is not None:
        unknown_observer(re.sub(r"[^A-Za-z0-9_-]", "?", raw)[:32])
    try:
        balance = Decimal(str(item.get("usdtBalance", "0")))
    except (InvalidOperation, ValueError) as exc:
        raise AccountTypeParseError("account balance contains an invalid decimal") from exc
    if not balance.is_finite():
        raise AccountTypeParseError("account balance must be finite")
    return AccountBalanceView(raw_account_type=raw, account_type=normalized, usdt_balance=balance)
