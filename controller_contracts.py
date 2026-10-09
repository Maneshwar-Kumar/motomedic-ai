"""TRD v0.4 immutable contracts; PDF/model content is never executable policy."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Truth(str, Enum):
    TRUE = "TRUE"
    FALSE = "FALSE"
    UNKNOWN = "UNKNOWN"


class Outcome(str, Enum):
    NOT_TRIED = "NOT_TRIED"
    OBSERVED_NORMAL = "OBSERVED_NORMAL"
    OBSERVED_ABNORMAL = "OBSERVED_ABNORMAL"
    ACTION_COMPLETED_UNRESOLVED = "ACTION_COMPLETED_UNRESOLVED"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    UNCLEAR = "UNCLEAR"
    RESOLVED = "RESOLVED"


class ResponseType(str, Enum):
    SUPPORTED = "SUPPORTED"
    AMBIGUOUS = "AMBIGUOUS"
    UNSUPPORTED = "UNSUPPORTED"
    SAFETY_STOP = "SAFETY_STOP"
    SYSTEM_ERROR = "SYSTEM_ERROR"


@dataclass(frozen=True)
class Fact:
    value: Any
    value_type: str  # BOOLEAN, ENUM, NUMBER
    unit: str | None = None
    confirmed: bool = True


@dataclass(frozen=True)
class ApplicabilityRule:
    rule_id: str
    predicate_type: str
    fact_key: str
    operator: str
    expected_value: Any
    unit: str | None
    origin: str
    source_evidence_ids: tuple[str, ...]
    policy_version: str | None
    clarification_evidence_ids: tuple[str, ...]
    review_status: str
    rule_version: str
    clarification_question: str | None = None
    rider_resolvable: bool = False


@dataclass(frozen=True)
class StepDefinition:
    step_id: str
    manual_checksum: str
    action_evidence_ids: tuple[str, ...]
    parent_procedure_id: str | None
    symptom_tags: tuple[str, ...]
    applicability_rule_ids: tuple[str, ...]
    required_evidence_ids: tuple[str, ...]
    dependency_manifest_version: str
    review_status: str
    rule_version: str
    kind: str = "ACTION"  # ACTION, LOOKUP, SAFETY_STOP
    safety_rule_ids: tuple[str, ...] = ()
    next_step_ids: tuple[str, ...] = ()
    next_step_evidence_ids: tuple[str, ...] = ()
    repeat_rule_ids: tuple[str, ...] = ()
    claims: tuple[dict, ...] = ()
    unresolved_route: str = "CONTINUE_DOCUMENTED"
    unresolved_evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class DependencyManifest:
    step_id: str
    version: str
    manual_checksum: str
    index_id: str
    action_evidence_ids: tuple[str, ...]
    required_evidence_ids: tuple[str, ...]
    review_status: str
    categories: dict[str, tuple[str, ...]] = field(default_factory=dict)


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
    attempted_steps: tuple[StepAttempt, ...] = ()
    status: str = "OPEN"
    version: int = 0
    symptom_revision: int = 0
    pending_step_id: str | None = None
    pending_rule_id: str | None = None
    scope_reconfirmation_required: bool = False
    excluded_branches: tuple[str, ...] = ()
    clarification_counts: tuple[tuple[str, int], ...] = ()

    def active_attempts(self):
        superseded = {a.supersedes for a in self.attempted_steps if a.supersedes}
        return tuple(a for a in self.attempted_steps if a.attempt_id not in superseded)

    def known_observations(self):
        facts = {}
        for attempt in self.active_attempts():
            if attempt.outcome_enum in (Outcome.OBSERVED_NORMAL, Outcome.OBSERVED_ABNORMAL):
                facts.update(attempt.observed_details)
        return facts

    def history(self):
        """Derive superseded_by without rewriting earlier immutable events."""
        by = {a.supersedes: a.attempt_id for a in self.attempted_steps if a.supersedes}
        return tuple((a, by.get(a.attempt_id)) for a in self.attempted_steps)


@dataclass(frozen=True)
class EligibilityDecision:
    step_id: str
    eligibility_status: Truth
    condition_results: tuple[dict, ...]
    reason_codes: tuple[str, ...]
    supporting_evidence_ids: tuple[str, ...]
    rule_version: str
    dependency_manifest_version: str
    session_version: int
    repeat_reason: str | None = None


@dataclass(frozen=True)
class Response:
    type: ResponseType
    natural_language: str
    claim_evidence_map: tuple[dict, ...] = ()
    cited_pages: tuple[dict, ...] = ()
    suggested_step_id: str | None = None
    clarification_question: str | None = None
    escalation_uri: str | None = None
    trace_id: str | None = None
    reason_codes: tuple[str, ...] = ()
    session_status: str = "OPEN"
