"""Validate independent judge coverage and frozen inputs; aggregate without changing verdicts."""
from __future__ import annotations
import collections, datetime, hashlib, json, pathlib, re, statistics
BASE = pathlib.Path(__file__).resolve().parent
ROOT = BASE.parents[1]
PIN_CORPUS = "3ec75b47a0f2f8de5ee90273829d9673bec8c232a1e998bb2558fa9ed45ea7d8"
PIN_FEEDBACK = "ae663a289d0090c3d56fd4ee5826baf3212ec7a1fb2cc5a506427e2d35fede1c"
SHARDS = {
    "original_exp": {*(f"EXP{i:03d}" for i in range(1,51)), "lookup_oil_grade", "lookup_tyre_pressure", "lookup_fan_fuse", "lookup_starter_duration", "lookup_usb_charging", "a_fuse", "a_switches_on", "a_refuel", "a_reconnect", "a_raise_stand", "a_cool_engine"},
    "gen_a": {f"GEN{i:03d}" for i in range(1,51)},
    "gen_b": {f"GEN{i:03d}" for i in range(51,101)},
}
ENUMS = {
    "initial_grounding": {"PASS","PARTIAL","FAIL","NOT_VERIFIABLE"},
    "dialogue_flow": {"PASS","PARTIAL","FAIL","NOT_APPLICABLE","NOT_VERIFIABLE"},
    "feedback_alignment": {"PASS","PARTIAL","FAIL"},
    "overall": {"PASS","REVISE","BLOCKED_SOURCE"},
}
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def canonical_sha(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()
def strings(value):
    if isinstance(value,str): yield value
    elif isinstance(value,dict):
        for item in value.values(): yield from strings(item)
    elif isinstance(value,list):
        for item in value: yield from strings(item)
def counts(records,key): return dict(sorted(collections.Counter(r[key] for r in records).items()))
def group(rid): return "original_11" if not rid.startswith(("EXP","GEN")) else ("expanded_50" if rid.startswith("EXP") else "generated_100")
def main():
    assert sha(BASE/"corpus.json") == PIN_CORPUS, "Frozen corpus changed"
    assert sha(BASE/"subagent_feedback.md") == PIN_FEEDBACK, "Frozen feedback changed"
    corpus=json.loads((BASE/"corpus.json").read_text(encoding="utf-8"))
    for entry in corpus["context"].values():
        assert sha(ROOT/entry["frozen_copy"]) == entry["sha256"], "Frozen context changed"
    assert sha(ROOT/"royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf") == corpus["manual_sha256"], "Source PDF changed"
    cases={r["record_id"]:r for r in corpus["records"]}
    assert len(cases)==len(corpus["records"])==161
    for rid,c in cases.items():
        value=dict(c);stored=value.pop("case_sha256")
        assert canonical_sha(value)==stored, f"Case hash mismatch: {rid}"
    collected=[]; actors=[]; quote_warnings=[]; artifact_hashes={}
    for shard,expected in SHARDS.items():
        path=BASE/shard/"records.json"
        data=json.loads(path.read_text(encoding="utf-8"))
        assert data["corpus_sha256"] == PIN_CORPUS, f"Wrong corpus in {shard}"
        assert data["feedback_sha256"] == PIN_FEEDBACK, f"Wrong feedback in {shard}"
        actor=data["judge_actor"];assert actor;actors.append(actor)
        rows=data["records"]
        assert len(rows)==len(expected) and {r["record_id"] for r in rows}==expected, f"Incomplete shard {shard}"
        assert len({r["record_id"] for r in rows})==len(rows), f"Duplicate cases {shard}"
        for r in rows:
            rid=r["record_id"];c=cases[rid]
            assert r["case_sha256"]==c["case_sha256"], f"Stale case result {rid}"
            for key,allowed in ENUMS.items(): assert r[key] in allowed, f"Invalid {key}: {rid}"
            assert type(r["answer_quality"]) is int and 1<=r["answer_quality"]<=5, f"Invalid score {rid}"
            assert r.get("rationale") and r.get("source_checks"), f"Missing review evidence {rid}"
            assert isinstance(r.get("findings"),list), f"Missing findings array {rid}"
            if r["overall"]!="PASS": assert r["findings"], f"Unexplained negative result {rid}"
            searchable=" ".join(strings(c))
            normalized=re.sub(r"\s+"," ",searchable)
            for index,finding in enumerate(r["findings"]):
                for key in ("severity","affected_scope","quote","consequence","source_or_policy_basis","smallest_fix"):
                    assert finding.get(key), f"Incomplete finding {rid} {index} {key}"
                quote=re.sub(r"\s+"," ",finding["quote"])
                if quote not in normalized:
                    quote_warnings.append({"record_id":rid,"finding_index":index,"quote":finding["quote"]})
            collected.append(dict(r,judge_actor=actor,review_shard=shard))
        for rel in (f"{shard}/records.json",f"{shard}/REPORT.md"):
            artifact_hashes[rel]=sha(BASE/rel)
    assert len(set(actors))==3, "Judges must be distinct agents"
    assert len(collected)==161 and {r["record_id"] for r in collected}==set(cases)
    collected.sort(key=lambda r:list(cases).index(r["record_id"]))
    summary={"cases_reviewed":161,"dimensions":{key:counts(collected,key) for key in ENUMS},
             "answer_quality_distribution":counts(collected,"answer_quality"),
             "mean_answer_quality":round(statistics.mean(r["answer_quality"] for r in collected),3),
             "flow_pass_scope_counts":dict(collections.Counter(r.get("dialogue_flow_scope","STATIC_AUTHORED_CONTEXT") for r in collected if r["dialogue_flow"]=="PASS")),
             "groups":{},"findings_by_scope":dict(collections.Counter(f["affected_scope"] for r in collected for f in r["findings"])),
             "findings_by_severity":dict(collections.Counter(f["severity"] for r in collected for f in r["findings"]))}
    for name in ("original_11","expanded_50","generated_100"):
        rows=[r for r in collected if group(r["record_id"])==name]
        summary["groups"][name]={"case_count":len(rows),"mean_answer_quality":round(statistics.mean(r["answer_quality"] for r in rows),3),
             **{key:counts(rows,key) for key in ENUMS},"answer_quality_distribution":counts(rows,"answer_quality")}
    result={"schema_version":"independent-llm-judge-161-v1","created_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "judges":actors,"corpus_sha256":PIN_CORPUS,"feedback_sha256":PIN_FEEDBACK,"manual_sha256":corpus["manual_sha256"],
        "review_mode":"Independent Codex LLM judge agents; static current responses and full authored case context. No external Gemma call or live rider/controller execution.",
        "approval_effect":"Quality review only; prior release records and approved responses are preserved.",
        "summary":summary,"records":collected,"validation":{"exact_coverage":True,"frozen_context_verified":True,
        "case_hashes_verified":True,"independent_actor_count":3,"quote_match_warnings":quote_warnings},"judge_artifact_hashes":artifact_hashes}
    (BASE/"results.json").write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"summary":summary,"quote_match_warnings":quote_warnings,"results_sha256":sha(BASE/"results.json")},ensure_ascii=False,indent=2))
if __name__=="__main__":main()
