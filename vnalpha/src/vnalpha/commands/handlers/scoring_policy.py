from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import date
from typing import Any

from vnalpha.commands.errors import CommandValidationError
from vnalpha.commands.models import CommandResult, ParsedCommand, ResultPanel
from vnalpha.commands.normalizers import normalize_date
from vnalpha.outcomes.models import DEFAULT_HORIZONS
from vnalpha.scoring.policy import PolicyLifecycleStatus
from vnalpha.scoring.policy_decision import (
    DEFAULT_SCORING_POLICY_CONTEXT,
    ScoringPolicyDecision,
)
from vnalpha.scoring.policy_decision_repository import (
    create_scoring_policy_decision,
    get_active_scoring_policy_decision,
    get_previous_scoring_policy_decision,
    get_scoring_policy_decision,
    list_scoring_policy_decisions,
    set_active_scoring_policy_decision_pointer,
)


def handle_scoring_policy(
    parsed: ParsedCommand, *, conn=None, **_kwargs
) -> CommandResult:
    if conn is None:
        return CommandResult(
            status="FAILED",
            title="/scoring-policy",
            summary="No database connection.",
        )

    from vnalpha.warehouse.migrations import run_migrations

    run_migrations(conn=conn)

    if not parsed.positional:
        subcommand = "active"
    else:
        subcommand = str(parsed.positional[0]).strip().lower()

    if subcommand == "active":
        return _active(conn, parsed)
    if subcommand == "list":
        return _list(conn, parsed)
    if subcommand == "create":
        return _create(conn, parsed)
    if subcommand == "set":
        return _set(conn, parsed)
    if subcommand == "rollback":
        return _rollback(conn, parsed)

    raise CommandValidationError(
        "Unsupported /scoring-policy subcommand. "
        "Supported: active, list, create, set, rollback."
    )


def _active(conn, parsed: ParsedCommand) -> CommandResult:
    if parsed.positional[1:] or parsed.filters:
        raise CommandValidationError("/scoring-policy active accepts only --context.")
    _ensure_supported_options(parsed, allowed={"context"})

    context = _context_option(parsed)
    decision = get_active_scoring_policy_decision(conn, policy_context=context)
    if decision is None:
        return CommandResult(
            status="EMPTY_RESULT",
            title="/scoring-policy active",
            summary=(
                f"No active scoring policy decision found for context '{context}'."
            ),
            panels=[
                ResultPanel(
                    title="Active Scoring Policy",
                    content={"policy_context": context},
                )
            ],
        )

    return CommandResult(
        status="SUCCESS",
        title="/scoring-policy active",
        summary=(
            f"Active scoring policy for context '{context}' is "
            f"{decision.policy_id}@{decision.policy_version}."
        ),
        panels=[
            ResultPanel(
                title="Active Scoring Policy",
                content={"policy_context": context, **_decision_payload(decision)},
            )
        ],
    )


def _list(conn, parsed: ParsedCommand) -> CommandResult:
    if parsed.filters:
        raise CommandValidationError("/scoring-policy list does not support filters.")
    if parsed.positional[1:]:
        raise CommandValidationError(
            "/scoring-policy list accepts only --context, --status, --policy-id, "
            "--policy-version."
        )

    _ensure_supported_options(
        parsed,
        allowed={"context", "status", "policy-id", "policy-version"},
    )

    status = None
    raw_status = _string_option(parsed.options.get("status"), name="status")
    if raw_status is not None:
        status = _policy_status(raw_status)

    context = _context_option(parsed)
    decisions = list_scoring_policy_decisions(
        conn,
        policy_id=_string_option(parsed.options.get("policy-id"), name="policy-id"),
        policy_version=_string_option(
            parsed.options.get("policy-version"),
            name="policy-version",
        ),
        status=status,
    )
    active = get_active_scoring_policy_decision(conn, policy_context=context)

    return CommandResult(
        status="SUCCESS",
        title="/scoring-policy list",
        summary=(
            f"Found {len(decisions)} scoring policy decision(s) for context "
            f"'{context}'."
        ),
        panels=[
            ResultPanel(
                title="Scoring Policy Decisions",
                content={
                    "policy_context": context,
                    "active_decision_id": active.decision_id if active else None,
                    "decisions": [
                        _decision_payload(decision) for decision in decisions
                    ],
                },
            )
        ],
    )


def _create(conn, parsed: ParsedCommand) -> CommandResult:
    if parsed.positional[1:] or parsed.filters:
        raise CommandValidationError(
            "Usage: /scoring-policy create --policy-id ID --policy-version VERSION "
            "--policy-hash HASH --status STATUS --effective-date DATE "
            "--reviewer REVIEWER --rationale TEXT [--activate] [--context CONTEXT] "
            "[--decision-cutoff-date DATE] [--evidence-json JSON] "
            "[--limitations-json JSON]"
        )
    _ensure_supported_options(
        parsed,
        allowed={
            "context",
            "policy-id",
            "policy-version",
            "policy-hash",
            "status",
            "effective-date",
            "reviewer",
            "rationale",
            "decision-cutoff-date",
            "evidence-json",
            "limitations-json",
            "activate",
        },
    )

    policy_id = _required_string_option(
        parsed.options.get("policy-id"), name="policy-id"
    )
    policy_version = _required_string_option(
        parsed.options.get("policy-version"), name="policy-version"
    )
    policy_hash = _normalize_policy_hash(
        _required_string_option(parsed.options.get("policy-hash"), name="policy-hash")
    )
    status = _policy_status(
        _required_string_option(parsed.options.get("status"), name="status")
    )
    reviewer = _required_string_option(parsed.options.get("reviewer"), name="reviewer")
    rationale = _required_string_option(
        parsed.options.get("rationale"), name="rationale"
    )
    effective_date = _date_option(
        parsed.options.get("effective-date"), name="effective-date"
    )
    decision_cutoff_date = _optional_date_option(
        parsed.options.get("decision-cutoff-date"),
        name="decision-cutoff-date",
    )
    activate = _bool_option(parsed.options.get("activate"), name="activate")
    evidence_json = _json_option(
        parsed.options.get("evidence-json"),
        name="evidence-json",
        required=status is PolicyLifecycleStatus.ACCEPTED,
    )
    limitations_json = _json_option(
        parsed.options.get("limitations-json"),
        name="limitations-json",
    )

    if status is PolicyLifecycleStatus.ACCEPTED:
        if evidence_json is None:
            raise CommandValidationError(
                "ACCEPTED scoring policy decisions require --evidence-json."
            )
        _assert_accepted_readiness(
            conn,
            policy_id=policy_id,
            policy_version=policy_version,
            policy_hash=policy_hash,
        )

    decision_id = create_scoring_policy_decision(
        conn,
        policy_id=policy_id,
        policy_version=policy_version,
        policy_hash=policy_hash,
        status=status,
        effective_date=effective_date,
        reviewer=reviewer,
        rationale=rationale,
        evidence_json=evidence_json or [],
        limitations_json=limitations_json or [],
        decision_cutoff_date=decision_cutoff_date,
    )

    context = _context_option(parsed)
    activated = False
    if activate:
        set_active_scoring_policy_decision_pointer(
            conn,
            decision_id=decision_id,
            policy_context=context,
            assigned_by=reviewer,
        )
        activated = True

    decision = get_scoring_policy_decision(conn, decision_id)
    active = get_active_scoring_policy_decision(conn, policy_context=context)

    summary = (
        f"Created scoring policy decision {decision_id} for "
        f"{policy_id}@{policy_version} with status {status.value}."
    )
    if activated:
        summary += f" Activated decision for context '{context}'."

    return CommandResult(
        status="SUCCESS",
        title="/scoring-policy create",
        summary=summary,
        panels=[
            ResultPanel(
                title="Scoring Policy Decision",
                content={
                    "policy_context": context,
                    "activated": activated,
                    "decision": _decision_payload(decision),
                    "active_decision": _decision_payload(active),
                },
            )
        ],
    )


def _set(conn, parsed: ParsedCommand) -> CommandResult:
    if parsed.filters:
        raise CommandValidationError("/scoring-policy set does not support filters.")
    _ensure_supported_options(
        parsed,
        allowed={"context", "decision-id", "assigned-by"},
    )

    decision_id: str | None
    if parsed.positional:
        if len(parsed.positional) != 2:
            raise CommandValidationError(
                "Usage: /scoring-policy set --decision-id DECISION_ID "
                "[--context CONTEXT] or /scoring-policy set DECISION_ID."
            )
        decision_id = str(parsed.positional[1]).strip()
    else:
        decision_id = _string_option(
            parsed.options.get("decision-id"),
            name="decision-id",
        )
    if not decision_id:
        raise CommandValidationError(
            "Usage: /scoring-policy set --decision-id DECISION_ID "
            "[--context CONTEXT] or /scoring-policy set DECISION_ID."
        )
    if parsed.positional and parsed.options.get("decision-id") is not None:
        raise CommandValidationError(
            "Provide decision-id either as /scoring-policy set DECISION_ID "
            "or via --decision-id, not both."
        )

    context = _context_option(parsed)
    previous_active = get_active_scoring_policy_decision(
        conn,
        policy_context=context,
    )
    assigned_by = _string_option(parsed.options.get("assigned-by"), name="assigned-by")
    decision = get_scoring_policy_decision(conn, decision_id)
    if decision is None:
        raise CommandValidationError(f"Unknown decision '{decision_id}'.")

    set_active_scoring_policy_decision_pointer(
        conn,
        decision_id=decision.decision_id,
        policy_context=context,
        assigned_by=assigned_by,
    )
    next_active = get_active_scoring_policy_decision(conn, policy_context=context)

    return CommandResult(
        status="SUCCESS",
        title="/scoring-policy set",
        summary=(
            f"Set active scoring policy for context '{context}' to "
            f"{decision.policy_id}@{decision.policy_version}."
        ),
        panels=[
            ResultPanel(
                title="Active Scoring Policy",
                content={
                    "policy_context": context,
                    "previous_active_decision": _decision_payload(previous_active),
                    "active_decision": _decision_payload(next_active),
                    "decision_id": decision.decision_id,
                    "assigned_by": assigned_by,
                },
            )
        ],
    )


def _rollback(conn, parsed: ParsedCommand) -> CommandResult:
    if parsed.positional[1:] or parsed.filters:
        raise CommandValidationError(
            "/scoring-policy rollback does not support positional args or filters."
        )
    _ensure_supported_options(parsed, allowed={"context"})

    context = _context_option(parsed)
    active = get_active_scoring_policy_decision(
        conn,
        policy_context=context,
    )
    if active is None:
        return CommandResult(
            status="EMPTY_RESULT",
            title="/scoring-policy rollback",
            summary=(
                f"No active scoring policy decision found for context '{context}' "
                "to rollback."
            ),
            panels=[
                ResultPanel(
                    title="Active Scoring Policy",
                    content={"policy_context": context},
                )
            ],
        )

    previous = get_previous_scoring_policy_decision(conn, policy_context=context)
    if previous is None:
        return CommandResult(
            status="EMPTY_RESULT",
            title="/scoring-policy rollback",
            summary=(
                f"No previous scoring policy decision found for context '{context}'. "
                "Set at least one explicit decision first."
            ),
            panels=[
                ResultPanel(
                    title="Active Scoring Policy",
                    content={
                        "policy_context": context,
                        "active_decision": _decision_payload(active),
                    },
                )
            ],
        )

    set_active_scoring_policy_decision_pointer(
        conn,
        decision_id=previous.decision_id,
        policy_context=context,
        assigned_by="operator.rollback",
    )
    next_active = get_active_scoring_policy_decision(conn, policy_context=context)

    return CommandResult(
        status="SUCCESS",
        title="/scoring-policy rollback",
        summary=(
            f"Rolled back active scoring policy for context '{context}' to "
            f"{previous.policy_id}@{previous.policy_version}."
        ),
        panels=[
            ResultPanel(
                title="Active Scoring Policy",
                content={
                    "policy_context": context,
                    "previous_active_decision": _decision_payload(active),
                    "active_decision": _decision_payload(next_active),
                    "rollback_from_decision": active.decision_id,
                    "rollback_to_decision": previous.decision_id,
                },
            )
        ],
    )


def _context_option(parsed: ParsedCommand) -> str:
    return (
        _string_option(parsed.options.get("context"), name="context")
        or DEFAULT_SCORING_POLICY_CONTEXT
    )


def _string_option(value: object | None, *, name: str) -> str | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise CommandValidationError(f"--{name} requires a non-empty value.")
    normalized = str(value).strip()
    if not normalized:
        raise CommandValidationError(f"--{name} requires a non-empty value.")
    return normalized


def _required_string_option(value: object | None, *, name: str) -> str:
    resolved = _string_option(value, name=name)
    if resolved is None:
        raise CommandValidationError(f"--{name} is required.")
    return resolved


def _policy_status(value: str) -> PolicyLifecycleStatus:
    try:
        return PolicyLifecycleStatus(str(value).strip().upper())
    except ValueError as exc:
        allowed = ", ".join(s.value for s in PolicyLifecycleStatus)
        raise CommandValidationError(
            f"Unknown policy status '{value}'. Expected one of: {allowed}."
        ) from exc


def _normalize_policy_hash(raw_value: str) -> str:
    value = raw_value.strip().lower()
    if len(value) != 64:
        raise CommandValidationError(
            "--policy-hash must be exactly 64 hexadecimal characters."
        )
    try:
        int(value, 16)
    except ValueError as exc:
        raise CommandValidationError(
            "--policy-hash must contain only hexadecimal characters."
        ) from exc
    return value


def _date_option(
    value: object | None,
    *,
    name: str,
) -> date:
    if value is None:
        raise CommandValidationError(f"--{name} is required.")
    if isinstance(value, bool):
        raise CommandValidationError(f"--{name} requires a non-empty date value.")
    try:
        return date.fromisoformat(normalize_date(str(value)))
    except (TypeError, ValueError) as exc:
        raise CommandValidationError(f"Invalid --{name} value {value!r}.") from exc


def _optional_date_option(
    value: object | None,
    *,
    name: str,
) -> date | None:
    if value is None:
        return None
    if isinstance(value, bool):
        raise CommandValidationError(f"--{name} requires a non-empty date value.")
    try:
        return date.fromisoformat(normalize_date(str(value)))
    except (TypeError, ValueError) as exc:
        raise CommandValidationError(f"Invalid --{name} value {value!r}.") from exc


def _json_option(
    value: object | None,
    *,
    name: str,
    required: bool = False,
) -> str | list | dict[str, Any] | None:
    if value is None:
        if required:
            raise CommandValidationError(f"--{name} is required.")
        return None
    if isinstance(value, bool):
        raise CommandValidationError(f"--{name} requires a JSON value.")
    text = str(value).strip()
    if not text:
        if required:
            raise CommandValidationError(f"--{name} cannot be empty.")
        return None
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CommandValidationError(f"--{name} must be valid JSON.") from exc
    if isinstance(parsed, (dict, list, str, int, float, bool, type(None))):
        return parsed
    raise CommandValidationError(f"--{name} must be a JSON object or list.")


def _bool_option(value: object | None, *, name: str) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    raise CommandValidationError(
        f"--{name} is a boolean flag and cannot accept a value."
    )


def _ensure_supported_options(parsed: ParsedCommand, allowed: set[str]) -> None:
    extras = set(parsed.options) - allowed
    if extras:
        rendered = ", ".join(f"--{option}" for option in sorted(extras))
        raise CommandValidationError(f"Unsupported option: {rendered}.")


def _assert_accepted_readiness(
    conn,
    *,
    policy_id: str,
    policy_version: str,
    policy_hash: str,
) -> None:
    if not _has_matching_shortlist_decision_report(
        conn,
        policy_id=policy_id,
        policy_version=policy_version,
        policy_hash=policy_hash,
    ):
        raise CommandValidationError(
            "ACCEPTED scoring policy decisions require a matching shortlist decision "
            "report."
        )

    missing_horizons = _missing_default_horizons(
        conn,
        policy_id=policy_id,
        policy_version=policy_version,
        policy_hash=policy_hash,
    )
    if missing_horizons:
        raise CommandValidationError(
            "ACCEPTED scoring policy decisions require complete outcomes for horizons: "
            f"{', '.join(str(horizon) for horizon in missing_horizons)}."
        )


def _has_matching_shortlist_decision_report(
    conn,
    *,
    policy_id: str,
    policy_version: str,
    policy_hash: str,
) -> bool:
    rows = conn.execute(
        "SELECT payload_json FROM research_shortlist_decision_report"
    ).fetchall()
    for (payload_json,) in rows:
        if not payload_json:
            continue
        try:
            payload = json.loads(payload_json)
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, Mapping):
            continue
        methodology = payload.get("scoring_policy")
        if not isinstance(methodology, Mapping):
            continue
        if (
            str(methodology.get("scoring_policy_id") or "") == policy_id
            and str(methodology.get("scoring_policy_version") or "") == policy_version
            and str(methodology.get("scoring_policy_hash") or "").lower() == policy_hash
        ):
            return True
    return False


def _missing_default_horizons(
    conn,
    *,
    policy_id: str,
    policy_version: str,
    policy_hash: str,
) -> list[int]:
    rows = conn.execute(
        """
        SELECT DISTINCT horizon_sessions
        FROM candidate_outcome
        WHERE outcome_status = 'COMPLETE'
          AND price_basis = 'RAW_UNADJUSTED'
          AND adjustment_methodology = 'NONE'
          AND action_overlap_status = 'CLEAR'
          AND scoring_policy_id = ?
          AND scoring_policy_version = ?
          AND scoring_policy_hash = ?
        """,
        [policy_id, policy_version, policy_hash],
    ).fetchall()
    seen = {int(row[0]) for row in rows}
    return [horizon for horizon in DEFAULT_HORIZONS if horizon not in seen]


def _decision_payload(decision: ScoringPolicyDecision | None) -> dict[str, Any]:
    if decision is None:
        return {}
    return {
        "decision_id": decision.decision_id,
        "policy_id": decision.policy_id,
        "policy_version": decision.policy_version,
        "policy_hash": decision.policy_hash,
        "status": decision.status.value,
        "effective_date": str(decision.effective_date),
        "decision_cutoff_date": (
            str(decision.decision_cutoff_date)
            if decision.decision_cutoff_date is not None
            else None
        ),
        "reviewer": decision.reviewer,
        "rationale": decision.rationale,
        "evidence_json": decision.evidence_json,
        "limitations_json": decision.limitations_json,
        "reviewed_at": str(decision.reviewed_at),
    }
