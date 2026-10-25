"""Versioned decisions for bounded retrieval recovery; no answer authorization."""
from dataclasses import asdict, dataclass
import math


@dataclass(frozen=True)
class RetrievalPolicy:
    version: str = "conditional-rerank-v1"
    calibration_status: str = "PROVISIONAL_UNCALIBRATED"
    candidate_limit: int = 20
    expanded_candidate_limit: int = 40
    maximum_dependency_ids: int = 256
    maximum_rerank_pairs: int = 100
    disagreement_top_k: int = 3
    minimum_section_overlap: float = 0.5
    maximum_relative_rrf_margin: float = 0.05

    def __post_init__(self):
        if not (1 <= self.candidate_limit <= self.expanded_candidate_limit <= 50):
            raise ValueError("Candidate limits must be between 1 and 50")
        if not 1 <= self.disagreement_top_k <= self.candidate_limit:
            raise ValueError("Invalid disagreement depth")
        if not 1 <= self.maximum_dependency_ids <= 256 or not 1 <= self.maximum_rerank_pairs <= 100:
            raise ValueError("Invalid evidence or cross-encoder work bound")
        for value in (self.minimum_section_overlap, self.maximum_relative_rrf_margin):
            if not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError("Ranking thresholds must be finite fractions")

    def to_dict(self):
        return asdict(self)


def ranking_signals(dense_sections, sparse_sections, fused_sections, policy):
    """Compare distinct sections so sibling chunks do not create false ambiguity."""
    def distinct(values):
        return list(dict.fromkeys(values))[:policy.disagreement_top_k]
    dense = distinct(dense_sections)
    sparse = distinct(sparse_sections)
    overlap = len(set(dense) & set(sparse)) / max(1, min(len(dense), len(sparse))) if sparse else None
    margin = None
    if len(fused_sections) >= 2 and fused_sections[0][1] > 0:
        margin = (fused_sections[0][1] - fused_sections[1][1]) / fused_sections[0][1]
    reasons = []
    if overlap is not None and overlap < policy.minimum_section_overlap:
        reasons.append("DENSE_SPARSE_DISAGREEMENT")
    if margin is not None and margin <= policy.maximum_relative_rrf_margin:
        reasons.append("COMPETING_SECTION_RANKS")
    return {"dense_sparse_section_overlap": overlap, "relative_rrf_section_margin": margin,
            "uncertainty_reasons": reasons, "ranking_uncertain": bool(reasons)}


def next_retrieval_action(bundle, signals, *, recovered=False, reranked=False, gate_status=None):
    """Trusted gate status comes from the controller, never from user/model text."""
    if gate_status not in (None, "SAFETY_STOP", "SYSTEM_ERROR", "UNSUPPORTED", "AMBIGUOUS"):
        raise ValueError("Invalid controller gate status")
    if gate_status:
        return gate_status
    if bundle["dependency_review_status"] != "APPROVED" or bundle["source_review_required"]:
        return "SOURCE_REVIEW_REQUIRED"
    if bundle["applicability_status"] == "MISMATCH":
        return "UNSUPPORTED"
    if bundle["applicability_status"] != "CONFIRMED":
        return "AMBIGUOUS"
    if bundle["conflicts"]:
        return "SOURCE_REVIEW_REQUIRED"
    if bundle["missing_evidence_ids"]:
        return "UNSUPPORTED" if recovered else "RECOVER_DEPENDENCIES"
    if not bundle["coverage_established"]:
        return "SOURCE_REVIEW_REQUIRED"
    if signals["ranking_uncertain"] and not reranked:
        return "RERANK_CANDIDATES"
    return "CONTINUE_GATES"
