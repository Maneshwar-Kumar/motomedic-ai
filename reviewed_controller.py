"""Deterministic TRD v0.4 eligibility, immutable transitions and final routing."""
from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime, timezone
import math
import uuid

from controller_contracts import (DiagnosticSession, EligibilityDecision, Fact, Outcome,
                                  Response, ResponseType, StepAttempt, Truth)
from evidence_registry import POLICY_VERSION


def compare(rule, fact):
    if fact is None or not fact.confirmed or fact.value_type != rule.predicate_type:
        return Truth.UNKNOWN
    value, expected = fact.value, rule.expected_value
    if rule.predicate_type == "BOOLEAN":
        valid = type(value) is bool and type(expected) is bool and rule.operator in ("EQ", "NE")
    elif rule.predicate_type == "ENUM":
        valid = isinstance(value, str) and isinstance(expected, str) and rule.operator in ("EQ", "NE")
    else:
        valid = (type(value) in (int, float) and type(expected) in (int, float) and
                 math.isfinite(value) and math.isfinite(expected) and
                 rule.unit is not None and fact.unit == rule.unit)
    if not valid:
        return Truth.UNKNOWN
    result = {"EQ": lambda: value == expected, "NE": lambda: value != expected,
              "LT": lambda: value < expected, "LE": lambda: value <= expected,
              "GT": lambda: value > expected, "GE": lambda: value >= expected}[rule.operator]()
    return Truth.TRUE if result else Truth.FALSE


def start_session(registry, symptoms, variant=None, edition=None):
    if registry.source.get("applicability_policy", {}).get("rider_edition_selection_required") is False:
        edition = registry.source.get("edition") if edition is None else edition
    return DiagnosticSession(uuid.uuid4().hex, registry.source["manual_id"], registry.checksum,
                             variant, edition, tuple(symptoms), registry.lock)


def append_attempt(session, step_id, outcome, turn_id, *, condition_id=None, facts=(),
                   supersedes=None, reason=None, applicability_symptoms=()):
    outcome = Outcome(outcome)
    if not turn_id or any(a.supporting_user_turn_id == turn_id for a in session.attempted_steps):
        raise ValueError("Missing or duplicate turn id")
    if facts and outcome not in (Outcome.OBSERVED_NORMAL, Outcome.OBSERVED_ABNORMAL):
        raise ValueError("Unresolved, unclear and not-applicable feedback cannot create observation facts")
    if supersedes and supersedes not in {a.attempt_id for a in session.active_attempts()}:
        raise ValueError("Correction must supersede an active attempt")
    event = StepAttempt(uuid.uuid4().hex, step_id, condition_id, outcome, tuple(facts), turn_id,
                        datetime.now(timezone.utc).isoformat(), supersedes,
                        session.symptom_revision, reason, tuple(applicability_symptoms))
    status = "CUSTOMER_REPORTED_RESOLVED" if outcome == Outcome.RESOLVED else "OPEN"
    return replace(session, attempted_steps=session.attempted_steps + (event,),
                   version=session.version + 1, status=status,
                   pending_step_id=None, pending_rule_id=None)


def update_symptoms(session, symptoms):
    symptoms = tuple(sorted(set(symptoms)))
    if set(symptoms) == set(session.current_symptoms):
        return session
    return replace(session, current_symptoms=symptoms, symptom_revision=session.symptom_revision + 1,
                   version=session.version + 1, pending_step_id=None, pending_rule_id=None, status="OPEN")


class ReviewedController:
    def __init__(self, registry, retriever, semantic_verifier=None):
        self.registry, self.retriever, self.verifier = registry, retriever, semantic_verifier
        self.last_retrieval_trace = None
        self.audience = "engineering"
        if retriever.manifest["index_id"] != registry.index_id or retriever.manifest["source_sha256"].lower() != registry.checksum.lower():
            raise ValueError("Controller index mismatch")
        # The overlay preserves original object content and the immutable index files.
        self.retriever.evidence = registry.reviewed_evidence()
        self.retriever.reviewed_scope = registry.source if registry.source_ready() else None

    def for_end_user(self, response):
        display = self.registry.source.get("display_policy", {})
        citations = tuple({k: v for k, v in page.items() if k != "evidence_uri"}
                          for page in response.cited_pages)
        if display.get("end_user_excerpts") is False:
            # Verbatim warning excerpts are engineering review outputs only.
            if any(c.get("verbatim_warning") or c.get("presentation_mode") != "REVIEWED_PARAPHRASE" for c in response.claim_evidence_map):
                return replace(response, type=response.type if response.type == ResponseType.SAFETY_STOP else ResponseType.UNSUPPORTED,
                               natural_language="This request requires a safety stop. Kindly write to Royal Enfield at support@royalenfield.com" if response.type == ResponseType.SAFETY_STOP else "I could not verify an approved answer for display. Kindly write to Royal Enfield at support@royalenfield.com",
                               claim_evidence_map=(), cited_pages=(), suggested_step_id=None,
                               reason_codes=response.reason_codes + ("END_USER_EXCERPT_DISPLAY_PROHIBITED",))
        return replace(response, cited_pages=citations,
                       claim_evidence_map=tuple({"claim_id": c["claim_id"], "evidence_ids": c["evidence_ids"]}
                                                for c in response.claim_evidence_map))

    def scope_status(self, session):
        r = self.registry
        if session.version_lock != r.lock:
            return "VERSION_RECONFIRM_REQUIRED"
        if session.manual_checksum != r.checksum or session.manual_id != r.source["manual_id"]:
            return "SOURCE_MISMATCH"
        if not r.source_ready():
            return "SOURCE_METADATA_REVIEW_REQUIRED"
        if session.scope_reconfirmation_required or session.bike_variant is None or session.edition is None:
            return "UNCONFIRMED"
        if session.bike_variant != r.source["variant"] or session.edition != r.source["edition"]:
            return "MISMATCH"
        return "CONFIRMED"

    def eligible(self, session, sid):
        r, s = self.registry, self.registry.step(sid)
        reasons, results, repeat = [], [], None
        scope = self.scope_status(session)
        if scope not in ("CONFIRMED", "UNCONFIRMED"):
            reasons.append(scope)
        if not r.step_ready(sid):
            reasons.append("SOURCE_REVIEW_REQUIRED")
        if not set(s.symptom_tags) & set(session.current_symptoms):
            reasons.append("IRRELEVANT_SYMPTOM")
        facts = session.known_observations()
        # Product-policy attempt facts describe history only, never component health.
        for prior_sid in r.candidate["steps"]:
            facts["attempted:" + prior_sid] = Fact(any(
                a.step_id == prior_sid and a.condition_id is None and
                a.outcome_enum not in (Outcome.NOT_TRIED, Outcome.UNCLEAR)
                for a in session.active_attempts()), "BOOLEAN")
        for rid in s.applicability_rule_ids + s.safety_rule_ids:
            rule = r.rule(rid)
            truth = compare(rule, facts.get(rule.fact_key)) if rule.review_status == "APPROVED" else Truth.UNKNOWN
            safety = rid in s.safety_rule_ids
            results.append({"rule_id": rid, "result": truth.value, "safety": safety,
                            "supporting_evidence_ids": list(rule.source_evidence_ids), "rule_version": rule.rule_version})
            if rule.review_status != "APPROVED":
                reasons.append("RULE_REVIEW_REQUIRED")
            elif (safety and truth == Truth.TRUE) or (not safety and truth == Truth.FALSE):
                reasons.append("SAFETY_PROHIBITS_STEP" if safety else "CONDITION_FALSE")
        attempts = [a for a in session.active_attempts() if a.step_id == sid and a.condition_id is None]
        completed = [a for a in attempts if a.outcome_enum not in (Outcome.NOT_TRIED, Outcome.UNCLEAR)]
        if completed and s.kind == "ACTION":
            last = completed[-1]
            relevant_keys = {r.rule(rid).fact_key for rid in s.applicability_rule_ids}
            last_index = session.attempted_steps.index(last)
            corrections = [a for a in session.attempted_steps[last_index+1:]
                           if a.supersedes and a.condition_id and relevant_keys & dict(a.observed_details).keys()]
            if corrections:
                repeat = "A relevant observation was corrected; eligibility was re-evaluated."
            elif last.symptom_revision < session.symptom_revision and set(last.applicability_symptoms) != set(s.symptom_tags) & set(session.current_symptoms):
                repeat = "The reported symptoms changed; applicability was re-evaluated."
            elif any(r.rule(rid).origin == "MANUAL" and compare(r.rule(rid), facts.get(r.rule(rid).fact_key)) == Truth.TRUE for rid in s.repeat_rule_ids):
                repeat = "The reviewed manual repeat condition is satisfied."
            else:
                reasons.append("ALREADY_ATTEMPTED")
        if reasons:
            truth = Truth.FALSE
        elif scope == "UNCONFIRMED" or any(x["result"] == "UNKNOWN" for x in results):
            truth = Truth.UNKNOWN
        else:
            truth = Truth.TRUE
        return EligibilityDecision(sid, truth, tuple(results), tuple(dict.fromkeys(reasons)),
                                   s.action_evidence_ids, s.rule_version,
                                   s.dependency_manifest_version, session.version, repeat)

    def feedback(self, session, outcome, turn_id, *, fact=None):
        if not session.pending_step_id:
            raise ValueError("No issued step or question awaits feedback")
        rid = session.pending_rule_id
        if rid:
            rule = self.registry.rule(rid)
            if outcome in (Outcome.OBSERVED_NORMAL, Outcome.OBSERVED_ABNORMAL):
                if fact is None or compare(rule, fact) == Truth.UNKNOWN:
                    raise ValueError("Observation requires a valid confirmed typed fact")
                facts = ((rule.fact_key, fact),)
            elif outcome == Outcome.UNCLEAR:
                facts = ()
            else:
                raise ValueError("A question accepts a typed observation or UNCLEAR")
        else:
            if fact is not None:
                raise ValueError("Action feedback does not imply an inspection result")
            facts = ()
        previous = next((a for a in reversed(session.active_attempts())
                         if a.step_id == session.pending_step_id and a.condition_id == rid and
                         a.outcome_enum == Outcome.NOT_TRIED), None)
        updated = append_attempt(session, session.pending_step_id, outcome, turn_id, condition_id=rid,
                                 facts=facts, supersedes=previous.attempt_id if previous else None,
                                 applicability_symptoms=previous.applicability_symptoms if previous else ())
        if outcome == Outcome.NOT_APPLICABLE:
            updated = replace(updated, scope_reconfirmation_required=True)
        return updated

    def correct(self, session, attempt_id, fact, turn_id):
        old = next((a for a in session.active_attempts() if a.attempt_id == attempt_id), None)
        if not old or not old.condition_id or old.outcome_enum not in (Outcome.OBSERVED_NORMAL, Outcome.OBSERVED_ABNORMAL):
            raise ValueError("Only explicit observations may be corrected with a fact")
        rule = self.registry.rule(old.condition_id)
        if compare(rule, fact) == Truth.UNKNOWN:
            raise ValueError("Invalid correction fact")
        if dict(old.observed_details).get(rule.fact_key) == fact:
            raise ValueError("A correction must change the recorded observation")
        return append_attempt(session, old.step_id, old.outcome_enum, turn_id,
                              condition_id=old.condition_id, facts=((rule.fact_key, fact),),
                              supersedes=old.attempt_id, reason="RIDER_CORRECTION")

    def response(self, kind, text, session, **kwargs):
        wording = (self.registry.source.get("oem_service_route") or {}).get("wording")
        if kind in ("UNSUPPORTED", "SAFETY_STOP") and wording and self.registry.support_uri() and wording not in text:
            text += " " + wording
        return Response(ResponseType(kind), text, escalation_uri=self.registry.support_uri(),
                        trace_id=uuid.uuid4().hex, session_status=session.status, **kwargs)

    def render(self, session, sid, bundle=None, *, safety=False):
        r, s = self.registry, self.registry.step(sid)
        if not r.step_ready(sid) or not s.claims:
            return self.response("UNSUPPORTED", "I could not verify reviewed evidence for this request.", session,
                                 reason_codes=("SOURCE_REVIEW_REQUIRED",))
        if bundle is not None:
            if bundle.get("manual_checksum") != r.checksum or bundle.get("index_id") != r.index_id:
                return self.response("SYSTEM_ERROR", "I am temporarily unable to verify the source.", session,
                                     reason_codes=("INVALID_BUNDLE_IDENTITY",))
            if bundle.get("conflicts") or bundle.get("source_review_required") or not bundle.get("coverage_established"):
                return self.response("UNSUPPORTED", "I could not verify complete applicable evidence.", session,
                                     reason_codes=("INCOMPLETE_EVIDENCE",))
            if bundle.get("retrieval_action") != "CONTINUE_GATES":
                return self.response("UNSUPPORTED", "I could not resolve the applicable evidence ordering.", session,
                                     reason_codes=("RANKING_UNRESOLVED",))
        claims, pages = [], []
        claim_ids = [c.get("claim_id") for c in s.claims]
        if len(claim_ids) != len(set(claim_ids)):
            return self.response("SYSTEM_ERROR", "I am temporarily unable to validate claims.", session,
                                 reason_codes=("DUPLICATE_CLAIM_ID",))
        dep = r.candidate["dependencies"][sid]
        mandatory_text = set(dep.get("categories", {}).get("warnings", [])) | set(dep.get("categories", {}).get("prerequisites", []))
        claimed = {eid for c in s.claims for eid in c.get("evidence_ids", [])}
        if not mandatory_text <= claimed:
            return self.response("SYSTEM_ERROR", "I am temporarily unable to validate required warnings and conditions.", session,
                                 reason_codes=("MANDATORY_WARNING_OR_CONDITION_OMITTED",))
        required = set(s.required_evidence_ids)
        attached = set(bundle["attached_evidence_ids"]) if bundle else required
        for claim in s.claims:
            ids = set(claim.get("evidence_ids", []))
            if not claim.get("claim_id") or not claim.get("text") or not ids or not ids <= required & attached:
                return self.response("SYSTEM_ERROR", "I am temporarily unable to validate citations.", session,
                                     reason_codes=("INVALID_CLAIM_CITATION",))
            claims.append(dict(claim))
            for eid in sorted(ids):
                for prov in r.evidence[eid]["provenance"]:
                    page = prov.get("page_no", prov.get("pdf_page"))
                    if type(page) is not int or not 1 <= page <= r.source["pdf_pages"]:
                        return self.response("SYSTEM_ERROR", "I am temporarily unable to validate citations.", session,
                                             reason_codes=("INVALID_SOURCE_PAGE",))
                    pages.append({"evidence_id": eid, "manual_checksum": r.checksum,
                                  "index_id": r.index_id, "pdf_page": page,
                                  "pdf_page_index": page - 1, "bbox": prov.get("bbox"),
                                  "evidence_uri": f"/evidence/{r.index_id}/{eid}"})
        # For a known safety stop, independently reviewed verbatim source warning claims
        # remain available without an optional model, even during a retrieval outage.
        exact_warning = safety and all(c.get("verbatim_warning") is True and any(
            c["text"] == r.evidence[eid].get("raw_object", {}).get("text") for eid in c["evidence_ids"])
            for c in claims)
        if not exact_warning:
            if self.verifier is None:
                return self.response("SYSTEM_ERROR", "I am temporarily unable to validate claim support.", session,
                                     reason_codes=("SEMANTIC_VERIFIER_UNAVAILABLE",))
            try:
                result = self.verifier(s, tuple(claims), {eid: r.evidence[eid] for eid in required})
                valid = isinstance(result, dict) and set(result) == {c["claim_id"] for c in claims} and all(v is True for v in result.values())
            except Exception:
                valid = False
            if not valid:
                return self.response("SYSTEM_ERROR", "I am temporarily unable to validate claim support.", session,
                                     reason_codes=("CLAIM_VALIDATION_FAILED",))
        # Every required object is cited, including warnings and table/figure context.
        for eid in sorted(required):
            for prov in r.evidence[eid]["provenance"]:
                page = prov.get("page_no", prov.get("pdf_page"))
                if type(page) is not int or not 1 <= page <= r.source["pdf_pages"]:
                    return self.response("SYSTEM_ERROR", "I am temporarily unable to validate source context.", session,
                                         reason_codes=("INVALID_SOURCE_PAGE",))
                ref = {"evidence_id": eid, "manual_checksum": r.checksum, "index_id": r.index_id,
                       "pdf_page": page, "pdf_page_index": page - 1, "bbox": prov.get("bbox"),
                       "evidence_uri": f"/evidence/{r.index_id}/{eid}"}
                if ref not in pages:
                    pages.append(ref)
        response = self.response("SAFETY_STOP" if safety else "SUPPORTED", " ".join(c["text"] for c in claims), session,
                             claim_evidence_map=tuple(claims), cited_pages=tuple(pages),
                             suggested_step_id=sid if s.kind == "ACTION" else None)
        return self.for_end_user(response) if self.audience == "end_user" else response

    def next(self, session, query, *, system_failure=False, unsupported_request=False):
        r = self.registry
        self.last_retrieval_trace = None
        decisions = [self.eligible(session, sid) for sid in sorted(r.candidate["steps"])]
        excluded = tuple(d.step_id for d in decisions if "CONDITION_FALSE" in d.reason_codes or "SAFETY_PROHIBITS_STEP" in d.reason_codes)
        if excluded != session.excluded_branches:
            session = replace(session, excluded_branches=excluded, version=session.version + 1)
        # Evaluate known applicable reviewed stops before ordinary errors or advice.
        stops = [d for d in decisions if d.eligibility_status == Truth.TRUE and r.step(d.step_id).kind == "SAFETY_STOP"]
        for stop in stops:
            response = self.render(session, stop.step_id, safety=True)
            if response.type == ResponseType.SAFETY_STOP:
                return session, response, decisions
        if system_failure:
            return session, self.response("SYSTEM_ERROR", "I am temporarily unable to verify the manual evidence.", session,
                                          reason_codes=("REQUIRED_COMPONENT_FAILURE",)), decisions
        if session.status == "CUSTOMER_REPORTED_RESOLVED":
            return session, self.response("SUPPORTED", "You reported that the symptom is resolved. The repair and cause have not been mechanically verified.", session), decisions
        scope = self.scope_status(session)
        if scope == "UNCONFIRMED":
            question = "Which exact bike variant and manual edition have you selected?"
            return session, self.response("AMBIGUOUS", question, session, clarification_question=question,
                                          reason_codes=("CONFIRM_VARIANT",)), decisions
        if scope != "CONFIRMED" or unsupported_request:
            reason = scope if scope != "CONFIRMED" else "UNSUPPORTED_REQUEST"
            return session, self.response("UNSUPPORTED", "I could not verify an applicable procedure. Source confirmation or review is required.", session,
                                          reason_codes=(reason,)), decisions
        completed_actions = [a for a in session.active_attempts() if a.condition_id is None and a.outcome_enum == Outcome.ACTION_COMPLETED_UNRESOLVED]
        if completed_actions:
            prior = r.step(completed_actions[-1].step_id)
            if r.step_ready(prior.step_id) and prior.unresolved_route == "ESCALATE":
                return session, self.response("UNSUPPORTED", "The documented check remains unresolved and calls for authorised service support.", session,
                                              reason_codes=("DOCUMENTED_ESCALATION_AFTER_UNRESOLVED_ACTION",)), decisions
        latest_actions = {}
        for attempt in session.active_attempts():
            if attempt.condition_id is None:
                latest_actions[attempt.step_id] = attempt
        for sid, attempt in latest_actions.items():
            if attempt.outcome_enum != Outcome.UNCLEAR or not r.step_ready(sid):
                continue
            count_key = "outcome:" + sid
            counts = dict(session.clarification_counts)
            if counts.get(count_key, 0) >= 2:
                return session, self.response("UNSUPPORTED", "I could not verify the outcome of the documented check.", session,
                                              reason_codes=("UNRESOLVED_OUTCOME_UNCERTAINTY",)), decisions
            counts[count_key] = counts.get(count_key, 0) + 1
            question = "Which outcome applies to the documented step: not tried, completed but unresolved, or resolved?"
            session = replace(session, pending_step_id=sid, pending_rule_id=None,
                              clarification_counts=tuple(sorted(counts.items())), version=session.version + 1)
            return session, self.response("AMBIGUOUS", question, session, clarification_question=question,
                                          reason_codes=("UNCLEAR_ACTION_OUTCOME",)), decisions
        eligible = [d for d in decisions if d.eligibility_status == Truth.TRUE and r.step(d.step_id).kind != "SAFETY_STOP"]
        # Prefer only source-reviewed explicit OEM NEXT_STEP links. Otherwise stable product ordering.
        completed = [a.step_id for a in session.active_attempts() if a.outcome_enum == Outcome.ACTION_COMPLETED_UNRESOLVED]
        preferred = r.step(completed[-1]).next_step_ids if completed else ()
        eligible.sort(key=lambda d: (d.step_id not in preferred, d.step_id))
        if eligible:
            d = eligible[0]
            try:
                bundle = self.retriever.search(query, dependency_manifest=r.retrieval_manifest(d.step_id),
                                               step_id=d.step_id, applicability_status="CONFIRMED",
                                               scope={"source_sha256": r.checksum, "manual_id": session.manual_id,
                                                      "variant": session.bike_variant, "edition": session.edition,
                                                      "language": r.source["language"], "motorcycle": r.source["motorcycle"]})
                self.last_retrieval_trace = bundle.get("retrieval_policy")
            except Exception as exc:
                self.last_retrieval_trace = getattr(exc, "telemetry", {"final_action": "SYSTEM_ERROR", "error_class": type(exc).__name__})
                return session, self.response("SYSTEM_ERROR", "I am temporarily unable to verify the manual evidence.", session,
                                              reason_codes=("RETRIEVAL_FAILURE",)), decisions
            response = self.render(session, d.step_id, bundle)
            if response.type == ResponseType.SUPPORTED and r.step(d.step_id).kind == "ACTION":
                if d.repeat_reason:
                    response = replace(response, natural_language=d.repeat_reason + " " + response.natural_language)
                pending = any(a.step_id == d.step_id and a.condition_id is None and a.outcome_enum == Outcome.NOT_TRIED for a in session.active_attempts())
                if not pending:
                    session = append_attempt(session, d.step_id, Outcome.NOT_TRIED, "issued:" + response.trace_id,
                                             reason=d.repeat_reason, applicability_symptoms=tuple(sorted(set(r.step(d.step_id).symptom_tags) & set(session.current_symptoms))))
                session = replace(session, pending_step_id=d.step_id)
            return session, response, decisions
        for d in decisions:
            if d.eligibility_status != Truth.UNKNOWN:
                continue
            for condition in d.condition_results:
                rule = r.rule(condition["rule_id"])
                if condition["result"] != "UNKNOWN" or not rule.rider_resolvable:
                    continue
                count = dict(session.clarification_counts).get(rule.rule_id, 0)
                if count >= 2:
                    continue
                if not all(r.evidence_ready(eid) for eid in rule.clarification_evidence_ids):
                    continue
                question = rule.clarification_question
                response = self.response("AMBIGUOUS", question, session, clarification_question=question,
                                         reason_codes=("UNKNOWN_OBSERVATION",))
                counts = dict(session.clarification_counts)
                counts[rule.rule_id] = count + 1
                session = append_attempt(session, d.step_id, Outcome.NOT_TRIED, "question:" + response.trace_id, condition_id=rule.rule_id)
                session = replace(session, pending_step_id=d.step_id, pending_rule_id=rule.rule_id,
                                  clarification_counts=tuple(sorted(counts.items())))
                return session, response, decisions
        gaps = any("SOURCE_REVIEW_REQUIRED" in d.reason_codes for d in decisions
                   if "IRRELEVANT_SYMPTOM" not in d.reason_codes)
        reason = "SOURCE_REVIEW_REQUIRED" if gaps else "DOCUMENTED_PATHS_EXHAUSTED"
        return session, self.response("UNSUPPORTED", "I could not verify another applicable documented step. Please use OEM or authorised service support.", session,
                                      reason_codes=(reason,)), decisions
