"""Small deterministic, source-linked diagnostic dialogue prototype.

Run `python diagnose.py chat "The engine will not start"` for an interactive demo,
or `python diagnose.py validate` to check the atomic golden dialogue paths.
This is a scripted prototype, not a free-form mechanical diagnosis service.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path


ROOT = Path(__file__).resolve().parent
FLOW_PATH = ROOT / "diagnosis_flow.json"
GOLD_PATH = ROOT / "golden_dialogues.json"
CARDS_PATH = ROOT / "golden_qa.json"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def classify_initial(text: str) -> str:
    s = text.lower()
    if "abs" in s and any(term in s for term in ("bypass", "disable", "ignore")):
        return "abs_bypass_request"
    if "abs" in s and any(term in s for term in ("lamp", "light", "indicator")):
        return "abs_indicator"
    if any(term in s for term in ("won't start", "will not start", "does not start", "not starting", "no start", "can't start")):
        return "no_start"
    if "horn" in s and any(term in s for term in ("weak", "faint", "quiet")):
        return "weak_horn_or_dim_lights_only"
    if "lights" in s and "dim" in s:
        return "weak_horn_or_dim_lights_only"
    if "first gear" in s and any(term in s for term in ("stop", "cut", "off", "stall")):
        return "first_gear_stall"
    if any(term in s for term in ("misfire", "runs erratically", "run erratically")):
        return "misfire"
    if "poor pickup" in s or "poor acceleration" in s:
        return "poor_pickup"
    raise ValueError("No supported diagnostic flow matches this symptom")


def normalize_reply(reply: str, node_type: str) -> str:
    s = reply.strip().lower()
    if node_type == "question":
        if s in {"yes", "y", "true", "it is", "i did", "they are"}:
            return "yes"
        if s in {"no", "n", "false", "it is not", "i did not", "they are not"}:
            return "no"
        if s in {"unknown", "unsure", "not sure", "can't tell", "cannot tell", "i don't know"}:
            return "unknown"
    else:
        if s in {"fixed", "resolved", "yes", "it starts", "works now"}:
            return "fixed"
        if s in {"still", "unresolved", "no", "didn't fix it", "does not start", "still failing"}:
            return "still"
        if s in {"unknown", "unsure", "not sure", "can't tell", "cannot tell"}:
            return "unknown"
    raise ValueError("Reply with yes/no/unsure for a question, or fixed/still/unsure after an action")


@dataclass
class Session:
    flow: dict
    intent: str
    initial_user: str
    current: str
    answers: list[str] = field(default_factory=list)
    uncertain_on_node: int = 0
    attempted_actions: list[str] = field(default_factory=list)

    @classmethod
    def start(cls, flow: dict, initial_user: str, intent: str | None = None) -> "Session":
        selected = intent or classify_initial(initial_user)
        if selected not in flow["entry_nodes"]:
            raise ValueError(f"Unsupported intent: {selected}")
        session = cls(flow, selected, initial_user, flow["entry_nodes"][selected])
        if selected == "no_start" and re.search(r"(weak|faint|quiet)\s+horn|horn\s+(?:is\s+)?(?:weak|faint|quiet)|dim\s+lights|lights\s+(?:are\s+)?dim", initial_user.lower()):
            session.answers.append("yes")
            session.current = flow["nodes"]["q_electrical_clue"]["yes"]
        return session

    def output(self) -> dict:
        node = self.flow["nodes"][self.current]
        return {
            "node_id": self.current,
            "type": node["type"],
            "route": node.get("route", "CLARIFY" if node["type"] == "question" else "ACTION_WAIT_FEEDBACK"),
            "text": node["text"],
            "source_pages": node.get("source_pages", []),
            "attempted_actions": list(self.attempted_actions),
        }

    def reply(self, raw_reply: str) -> dict:
        node = self.flow["nodes"][self.current]
        if node["type"] == "terminal":
            raise ValueError("This dialogue path has ended")
        answer = normalize_reply(raw_reply, node["type"])
        if answer == "unknown":
            self.uncertain_on_node += 1
            if self.uncertain_on_node >= 2:
                self.answers.append("unknown_twice")
                self.current = "t_abs_unclear" if self.intent == "abs_indicator" else "t_cannot_verify"
                return self.output()
            result = self.output()
            result["text"] = "I cannot choose a documented branch without that observation. If you can check safely: " + node["text"]
            return result
        self.uncertain_on_node = 0
        self.answers.append(answer)
        if node["type"] == "question":
            self.current = node[answer]
        else:
            self.attempted_actions.append(self.current)
            self.current = node["resolved" if answer == "fixed" else "unresolved"]
        return self.output()


def cache_key(flow: dict, intent: str, answers: list[str], variant_key: str = "prototype_manual_scope") -> str:
    payload = {
        "manual_sha256": flow["source_sha256"].lower(),
        "flow_id": flow["flow_id"],
        "policy_version": "evidence_gate_v1",
        "variant_key": variant_key,
        "intent": intent,
        "typed_answers": answers,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def validate_dialogues(flow: dict, dialogues: dict, cards: dict) -> None:
    if flow["source_sha256"].lower() != dialogues["source_sha256"].lower():
        raise ValueError("Flow and dialogue data use different manual checksums")
    if flow["source_sha256"].lower() != cards["source_sha256"].lower():
        raise ValueError("Flow and answer cards use different manual checksums")
    card_ids = {card["id"] for card in cards["cases"]}
    seen = set()
    for case in dialogues["cases"]:
        if case["id"] in seen:
            raise ValueError(f"Duplicate dialogue ID: {case['id']}")
        seen.add(case["id"])
        if case["mode"] == "diagnostic":
            if classify_initial(case["initial_user"]) != case["intent"]:
                raise ValueError(f"{case['id']}: initial symptom routes to a different intent")
            session = Session.start(flow, case["initial_user"], case["intent"])
            for answer in case["answers"]:
                session.reply(answer)
            if session.current != case["expected_node"]:
                raise ValueError(f"{case['id']}: expected {case['expected_node']}, got {session.current}")
        elif case["mode"] == "lookup":
            if case["reference_card"] not in card_ids:
                raise ValueError(f"{case['id']}: missing reference card")
        else:
            raise ValueError(f"{case['id']}: unsupported mode")
    print(f"Validated {len(dialogues['cases'])} atomic dialogue and lookup goldens")


def export_dialogues(flow: dict, dialogues: dict, cards: dict, destination: Path) -> None:
    card_by_id = {card["id"]: card for card in cards["cases"]}
    pages = {json.loads(line)["id"]: json.loads(line) for line in (ROOT / "provisional_index" / "pages.jsonl").read_text(encoding="utf-8").splitlines()}

    def citation_line(refs: list[str]) -> str:
        citations = []
        for ref in refs:
            page = pages[ref]
            pdf_page = page["pdf_page"]
            citations.append(
                f"[PDF page {pdf_page} (printed {page['printed_page']}, `{ref}`)]"
                f"(royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page={pdf_page})"
            )
        return "**Source:** " + "; ".join(citations)

    lines = [
        "# Atomic diagnostic golden cases",
        "",
        "These are provisional scripted cases grounded in the owner's manual. Symptom cases start with an atomic report and record each diagnostic turn. Exact paths may be cached after independent approval. Direct specification lookups need no diagnostic questions when the question is already precise.",
        "",
    ]
    for case in dialogues["cases"]:
        lines.extend([f"## {case['id']} — {case['mode'].title()}", "", f"**Rider:** {case['initial_user']}", ""])
        if case["mode"] == "diagnostic":
            session = Session.start(flow, case["initial_user"], case["intent"])
            for answer in case["answers"]:
                out = session.output()
                lines.append(f"**Assistant ({out['route']}):** {out['text']}")
                if out["source_pages"]:
                    lines.append(citation_line(out["source_pages"]))
                lines.append("")
                lines.append(f"**Rider:** {answer}")
                lines.append("")
                session.reply(answer)
            out = session.output()
            lines.append(f"**Assistant ({out['route']}):** {out['text']}")
            if out["source_pages"]:
                lines.append(citation_line(out["source_pages"]))
        else:
            card = card_by_id[case["reference_card"]]
            lines.append(f"**Assistant ({card['expected_route']}):** {card['gold_answer']}")
            refs = [ref["evidence_page_id"] for ref in card["citations"]]
            if refs:
                lines.append(citation_line(refs))
        lines.extend(["", "---", ""])
    destination.write_text("\n".join(lines), encoding="utf-8")
    print(f"Exported {len(dialogues['cases'])} atomic cases to {destination}")


def build_cache(flow: dict, dialogues: dict, cards: dict, destination: Path) -> None:
    card_by_id = {card["id"]: card for card in cards["cases"]}
    entries: dict[str, dict] = {}
    for case in dialogues["cases"]:
        if case["mode"] == "diagnostic":
            session = Session.start(flow, case["initial_user"], case["intent"])
            for answer in [None, *case["answers"]]:
                if answer is not None:
                    session.reply(answer)
                result = session.output()
                key = cache_key(flow, session.intent, session.answers)
                candidate = {"key": key, "intent": session.intent, "typed_answers": list(session.answers), "response": result}
                if key in entries and entries[key]["response"] != candidate["response"]:
                    raise ValueError(f"Conflicting cache responses for {key}")
                entries[key] = candidate
        else:
            card = card_by_id[case["reference_card"]]
            normalized = " ".join(case["initial_user"].lower().split())
            key = cache_key(flow, "lookup:" + normalized, [])
            entries[key] = {
                "key": key,
                "intent": "lookup:" + normalized,
                "typed_answers": [],
                "response": {
                    "node_id": card["id"], "type": "terminal", "route": card["expected_route"],
                    "text": card["gold_answer"],
                    "source_pages": [ref["evidence_page_id"] for ref in card["citations"]],
                },
            }
    artifact = {
        "manual_sha256": flow["source_sha256"],
        "flow_id": flow["flow_id"],
        "variant_key": "prototype_manual_scope",
        "review_status": "draft_disabled_for_release",
        "lookup_policy": "Exact intent and typed-answer sequence only; no similarity match",
        "entries": sorted(entries.values(), key=lambda entry: entry["key"]),
    }
    destination.write_text(json.dumps(artifact, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Built {len(entries)} exact-prefix cache entries at {destination}")


def lookup_cache(
    flow: dict,
    cache: dict,
    intent: str,
    answers: list[str],
    manual_sha256: str,
    variant_key: str,
    allow_draft: bool = False,
) -> dict | None:
    if cache["manual_sha256"].lower() != manual_sha256.lower():
        return None
    if cache["flow_id"] != flow["flow_id"] or cache["variant_key"] != variant_key:
        return None
    if cache["review_status"] != "approved" and not allow_draft:
        return None
    key = cache_key(flow, intent, answers, variant_key)
    return next((entry["response"] for entry in cache["entries"] if entry["key"] == key), None)


class ReviewedService:
    """Hosted service boundary; never executes the provisional dialogue/cache path.

    The caller supplies a trusted store and registry, never rider-authored gate inputs.
    A private hosted worker can use SQLite; a multi-worker UI needs managed storage.
    """
    def __init__(self, registry, retriever, store, semantic_verifier=None, audience="end_user", trace_sink=None,
                 response_generator=None):
        if audience not in ("engineering", "end_user"):
            raise ValueError("Invalid audience")
        self.audience = audience
        self.trace_sink = trace_sink
        self.last_trace = None
        self.controller = retriever.reviewed_controller(registry, semantic_verifier)
        from constrained_generator import ConstrainedGenerator
        self.controller.response_generator = response_generator or ConstrainedGenerator()
        self.controller.audience = audience
        self.store = store

    def start(self, intent, variant=None, edition=None):
        from reviewed_controller import start_session
        from dataclasses import replace
        session = start_session(self.controller.registry, [intent], variant, edition)
        session = replace(session, generation_lock=self.controller.response_generator.config.lock)
        self.store.save(session)
        return session

    def turn(self, session_id, query, **kwargs):
        from dataclasses import asdict, replace
        import time
        from evidence_registry import POLICY_VERSION, content_hash
        started = time.perf_counter()
        session = self.store.load(session_id)
        updated, response, decisions = self.controller.next(session, query, **kwargs)
        if updated.version == session.version:
            updated = replace(updated, version=updated.version + 1)
        self.store.save(updated, expected_version=session.version)
        self.last_trace = {"trace_id": response.trace_id, "session_hash": content_hash(session_id),
                           "manual_checksum": session.manual_checksum, "index_id": self.controller.registry.index_id,
                           "registry_lock": session.version_lock, "controller_version": POLICY_VERSION,
                           "session_version_before": session.version, "session_version_after": updated.version,
                           "eligibility": [asdict(d) for d in decisions],
                           "retrieval": self.controller.last_retrieval_trace,
                           "generation_lock": session.generation_lock,
                           "generation_validation": self.controller.response_generator.last_trace,
                           "response_type": response.type.value, "reason_codes": response.reason_codes,
                           "confirmed_input_ttfo_seconds": time.perf_counter() - started,
                           "estimated_cost": None, "raw_input_or_media_recorded": False}
        if self.trace_sink:
            self.trace_sink(self.last_trace)
        return updated, response, decisions

    def feedback(self, session_id, outcome, turn_id, **kwargs):
        session = self.store.load(session_id)
        updated = self.controller.feedback(session, outcome, turn_id, **kwargs)
        self.store.save(updated, expected_version=session.version)
        return updated

    def correct(self, session_id, attempt_id, fact, turn_id):
        session = self.store.load(session_id)
        updated = self.controller.correct(session, attempt_id, fact, turn_id)
        self.store.save(updated, expected_version=session.version)
        return updated


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    chat = sub.add_parser("chat")
    chat.add_argument("initial_user")
    sub.add_parser("validate")
    sub.add_parser("export")
    sub.add_parser("build-cache")
    cache_lookup = sub.add_parser("cache-lookup")
    cache_lookup.add_argument("--intent", required=True)
    cache_lookup.add_argument("--answers", nargs="*", default=[])
    cache_lookup.add_argument("--variant-key", default="prototype_manual_scope")
    cache_lookup.add_argument("--manual-sha256", default=None)
    cache_lookup.add_argument("--allow-draft", action="store_true")
    args = parser.parse_args()
    flow = load_json(FLOW_PATH)
    dialogues = load_json(GOLD_PATH)
    cards = load_json(CARDS_PATH)
    if args.command == "chat":
        session = Session.start(flow, args.initial_user)
        while True:
            out = session.output()
            print(f"\n{out['route']}: {out['text']}")
            if out["source_pages"]:
                print("Source pages:", ", ".join(out["source_pages"]))
            if out["type"] == "terminal":
                break
            session.reply(input("You: "))
    elif args.command == "validate":
        validate_dialogues(flow, dialogues, cards)
    elif args.command == "export":
        export_dialogues(flow, dialogues, cards, ROOT / "golden_dialogues.md")
    elif args.command == "build-cache":
        build_cache(flow, dialogues, cards, ROOT / "provisional_golden_cache.json")
    else:
        cache = load_json(ROOT / "provisional_golden_cache.json")
        result = lookup_cache(
            flow, cache, args.intent, args.answers,
            args.manual_sha256 or flow["source_sha256"], args.variant_key, args.allow_draft,
        )
        print(json.dumps({"cache_hit": result is not None, "response": result}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
