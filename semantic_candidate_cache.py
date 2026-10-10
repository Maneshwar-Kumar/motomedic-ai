"""Ephemeral semantic candidate cache. Exact authority, never cosine, permits reuse.

Entries hold source-reviewed wording only. No raw rider query or persistent media.
Fresh retrieval/eligibility gates precede lookup; B/C still verify a cached draft.
"""
from collections import OrderedDict
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import threading
import time
import numpy as np

FEATURE_VERSION = "grounded-concurrent-cache-stream-v1"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode("utf-8")).hexdigest()


def binding(controller, session, allowed, architecture, config, embedding_revision, prompt_hash):
    # Drop per-session IDs/timestamps while retaining typed history and corrections.
    attempts = [{"step_id": a.step_id, "condition_id": a.condition_id,
                 "outcome": a.outcome_enum.value,
                 "details": [(k, asdict(v)) for k,v in a.observed_details],
                 "symptom_revision": a.symptom_revision,
                 "applicability_symptoms": a.applicability_symptoms}
                for a in session.active_attempts()]
    state = {k: getattr(session, k) for k in ("manual_id", "manual_checksum", "bike_variant",
             "edition", "current_symptoms", "version_lock", "generation_lock", "version",
             "status", "symptom_revision", "pending_step_id", "pending_rule_id",
             "scope_reconfirmation_required", "excluded_branches", "clarification_counts")}
    state["attempts"] = attempts
    return digest({"feature_version": FEATURE_VERSION, "registry_lock": controller.registry.lock,
        "index_id": controller.registry.index_id, "generation_config": config.versions(),
        "embedding_revision": embedding_revision, "prompt_hash": prompt_hash,
        "architecture": architecture, "typed_state": state, "allowed_envelope": allowed})


def reviewed_texts(allowed, texts):
    return (type(texts) is list and len(texts) == len(allowed["claims"]) and
            all(type(t) is str and t in c["wording"] for t,c in zip(texts,allowed["claims"])))


class SemanticCandidateCache:
    def __init__(self, *, embedding_revision, threshold=0.95, ttl_seconds=300,
                 max_entries=64, clock=time.monotonic):
        if (type(embedding_revision) is not str or not embedding_revision or
                not 0 < threshold <= 1 or not 0 < ttl_seconds <= 3600 or
                type(max_entries) is not int or not 1 <= max_entries <= 1024):
            raise ValueError("Invalid bounded cache configuration")
        self.embedding_revision, self.threshold = embedding_revision, threshold
        self.ttl, self.capacity, self.clock = ttl_seconds, max_entries, clock
        self.lock, self.entries = threading.Lock(), OrderedDict()

    def _vector(self, vector):
        result = np.array(vector, dtype=float, copy=True)
        if result.ndim != 1 or not 1 <= result.size <= 4096 or not np.isfinite(result).all():
            raise ValueError("Invalid cache embedding")
        norm = np.linalg.norm(result)
        if not np.isfinite(norm) or norm <= 0: raise ValueError("Invalid cache embedding")
        return result / norm

    def _expire(self):
        now = self.clock()
        for key in list(self.entries):
            if self.entries[key]["expires"] <= now: del self.entries[key]

    def lookup(self, vector, authority, allowed, *, bypass=False):
        if bypass: return None, "BYPASS"
        query = self._vector(vector)
        with self.lock:
            self._expire()
            candidates = []
            for key, row in self.entries.items():
                if row["vector"].shape == query.shape:
                    score = float(row["vector"] @ query)
                    if score >= self.threshold: candidates.append((score, key, row))
            # Similarity locates candidates. Exact binding/content checks grant reuse.
            for score, key, row in sorted(candidates, key=lambda x: (-x[0], x[1])):
                if (row["authority"] == authority and row["content_hash"] == digest(row["texts"])
                        and reviewed_texts(allowed, row["texts"])):
                    self.entries.move_to_end(key)
                    return deepcopy(row["texts"]), "EXACT_AUTHORITY_VALIDATED_CANDIDATE_HIT"
            return None, "MISS"

    def put(self, vector, authority, allowed, texts):
        if not reviewed_texts(allowed, texts): return "UNREVIEWED_PARAPHRASE_NOT_CACHED"
        stored = deepcopy(texts)
        normalized = self._vector(vector)
        key = digest([authority, normalized.tolist(), stored])
        with self.lock:
            self._expire()
            self.entries[key] = {"authority": authority, "vector": normalized,
                "texts": stored, "content_hash": digest(stored), "expires": self.clock() + self.ttl}
            self.entries.move_to_end(key)
            while len(self.entries) > self.capacity: self.entries.popitem(last=False)
        return "REVIEWED_WORDING_CANDIDATE_STORED"

    def clear(self):
        with self.lock: self.entries.clear()
