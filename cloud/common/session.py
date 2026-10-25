"""Session records saved in Firestore, and their decoder.

Field names, order and defaults are unchanged from the retired root `controller_contracts.py`
and `session_store.py`, so sessions saved by earlier runtimes still decode.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import json
from typing import Any


class SessionConflict(RuntimeError):
    pass


class Outcome(str, Enum):
    NOT_TRIED = "NOT_TRIED"
    OBSERVED_NORMAL = "OBSERVED_NORMAL"
    OBSERVED_ABNORMAL = "OBSERVED_ABNORMAL"
    ACTION_COMPLETED_UNRESOLVED = "ACTION_COMPLETED_UNRESOLVED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNCLEAR = "UNCLEAR"
    RESOLVED = "RESOLVED"


@dataclass(frozen=True)
class Fact:
    value: Any
    value_type: str  # BOOLEAN, ENUM, NUMBER
    unit: str | None = None
    confirmed: bool = True


@dataclass(frozen=True)
class StepAttempt:
    attempt_id: str
    step_id: str
    condition_id: str | None
    outcome_enum: Outcome
    observed_details: tuple[tuple[str, Fact], ...]
    supporting_user_turn_id: str
    timestamp: str
    supersedes: str | None = None
    symptom_revision: int = 0
    reason: str | None = None
    applicability_symptoms: tuple[str, ...] = ()


@dataclass(frozen=True)
class DiagnosticSession:
    session_id: str
    manual_id: str
    manual_checksum: str
    bike_variant: str | None
    edition: str | None
    current_symptoms: tuple[str, ...]
    version_lock: str
    generation_lock: str = ""
    attempted_steps: tuple[StepAttempt, ...] = ()
    status: str = "OPEN"
    version: int = 0
    symptom_revision: int = 0
    pending_step_id: str | None = None
    pending_rule_id: str | None = None
    scope_reconfirmation_required: bool = False
    excluded_branches: tuple[str, ...] = ()
    clarification_counts: tuple[tuple[str, int], ...] = ()


def decode(raw):
    d = json.loads(raw)
    attempts = []
    for a in d.pop("attempted_steps"):
        a["outcome_enum"] = Outcome(a["outcome_enum"])
        a["applicability_symptoms"] = tuple(a.get("applicability_symptoms", []))
        a["observed_details"] = tuple((k, Fact(**v)) for k, v in a["observed_details"])
        attempts.append(StepAttempt(**a))
    d["current_symptoms"] = tuple(d["current_symptoms"])
    d["excluded_branches"] = tuple(d.get("excluded_branches", []))
    d["clarification_counts"] = tuple(tuple(x) for x in d["clarification_counts"])
    return DiagnosticSession(**d, attempted_steps=tuple(attempts))
