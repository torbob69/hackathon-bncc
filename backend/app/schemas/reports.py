"""
Pydantic v2 schemas for portfolio reporting, data-share grants, and anomaly detection.

CLAUDE.md §3.8 / Phase 15 requirements:
  - ALLOWED_REPORT_FIELDS is the ONLY set of fields a financing partner may ever receive.
    It contains aggregate/summary metrics ONLY — never raw PII, individual rows, NIK, names.
  - GrantScope validates that every requested field is in the allow-list before the grant
    is persisted.  scope_json is never trusted raw at read time — it is re-validated.
  - PortfolioReportOut.metrics is a plain dict keyed by field name; the service layer
    populates ONLY the subset that appears in the grant's scope_json["fields"].
  - AnomalyOut carries structured heuristic findings — read-only, never mutates data.

Money fields use Decimal (never float) per CLAUDE.md §4 fintech convention.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

# ---------------------------------------------------------------------------
# Aggregate field allow-list (CLAUDE.md §3.8 / §8)
# ---------------------------------------------------------------------------

# STRICT allow-list: only aggregate/summary fields may be shared with financing partners.
# PII (names, NIK, addresses, per-farmer rows) is NEVER in this set.
# Adding a field here is the ONLY way to make it grantable — the service layer enforces this.
ALLOWED_REPORT_FIELDS: frozenset[str] = frozenset(
    {
        "gmv",
        "loan_disbursement_volume",
        "active_farmer_count",
        "total_farmer_count",
        "active_farmer_rate",
        "npl_rate",
        "active_loan_count",
        "npl_count",
        "loan_pool_balance",
        "marginal_profit_pool_balance",
    }
)


# ---------------------------------------------------------------------------
# GrantScope — validated field list
# ---------------------------------------------------------------------------


class GrantScope(BaseModel):
    """
    Validated scope for a data-share grant.

    Every field name in *fields* must be present in ALLOWED_REPORT_FIELDS.
    The list must be non-empty.  Duplicate field names are de-duplicated.
    """

    fields: list[str]

    @field_validator("fields", mode="before")
    @classmethod
    def validate_fields(cls, v: Any) -> list[str]:
        if not v:
            raise ValueError("fields list must not be empty")
        if not isinstance(v, list):
            raise ValueError("fields must be a list of strings")
        unique_fields: list[str] = []
        seen: set[str] = set()
        for f in v:
            if not isinstance(f, str):
                raise ValueError(f"Each field must be a string; got {type(f).__name__!r}")
            if f not in ALLOWED_REPORT_FIELDS:
                raise ValueError(
                    f"Field {f!r} is not allowed. Permitted fields: "
                    + str(sorted(ALLOWED_REPORT_FIELDS))
                )
            if f not in seen:
                seen.add(f)
                unique_fields.append(f)
        return unique_fields


# ---------------------------------------------------------------------------
# Grant request / response schemas
# ---------------------------------------------------------------------------


class GrantCreate(BaseModel):
    """
    Admin request body for creating a data-share grant.

    *fields* is validated via GrantScope so any disallowed field name raises a
    422 before the row is written.
    """

    financing_partner_id: int
    fields: list[str]
    date_range_start: date
    date_range_end: date

    @model_validator(mode="after")
    def validate_date_range(self) -> "GrantCreate":
        if self.date_range_end < self.date_range_start:
            raise ValueError("date_range_end must not be before date_range_start")
        return self

    @field_validator("fields", mode="before")
    @classmethod
    def _validate_fields(cls, v: Any) -> list[str]:
        # Delegate to GrantScope for the allow-list check
        scope = GrantScope(fields=v)
        return scope.fields


class GrantOut(BaseModel):
    """Serialisation of a data_share_grants row returned to the admin."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    koperasi_id: int
    financing_partner_id: int
    scope_json: dict[str, Any]
    date_range_start: date
    date_range_end: date
    status: str  # GrantStatus enum value
    created_at: datetime


# ---------------------------------------------------------------------------
# Portfolio report output
# ---------------------------------------------------------------------------


class PortfolioReportOut(BaseModel):
    """
    One per granted koperasi — returned to a financing_partner caller.

    *metrics* contains ONLY the fields listed in the grant's scope_json["fields"],
    filtered to the grant's date range.  The service layer is responsible for
    never including a field that is not in the grant scope.

    Money values (gmv, loan_disbursement_volume, pool balances) are Decimal.
    Rate values (active_farmer_rate, npl_rate) are Decimal fractions in [0, 1].
    Count values (active_farmer_count, etc.) are int.
    """

    koperasi_id: int
    date_range_start: date
    date_range_end: date
    # Plain dict: keys are the granted field names, values are Decimal | int | str.
    # Using Any here because the field set is dynamic and caller-scoped.
    metrics: dict[str, Any]


# ---------------------------------------------------------------------------
# Anomaly detection output
# ---------------------------------------------------------------------------


class AnomalyOut(BaseModel):
    """
    One structured anomaly/fraud-detection finding returned to an admin.

    Fields:
      type        — Short machine-readable label, e.g. "orphan_debit",
                    "pihps_price_deviation", "large_ledger_entry",
                    "rapid_fire_confirms".
      severity    — "low" | "medium" | "high".
      entity_type — The table/domain where the anomaly was found, e.g.
                    "ledger_entries", "harvest_intakes", "audit_log".
      entity_id   — PK of the suspicious row, if applicable.
      detail      — Human-readable explanation of the finding.
      created_at  — Timestamp of the suspicious event, if available.
    """

    type: str
    severity: str
    entity_type: str
    entity_id: int | None = None
    detail: str
    created_at: datetime | None = None
