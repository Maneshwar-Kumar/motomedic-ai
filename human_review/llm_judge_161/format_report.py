"""Render the verified independent LLM quality review as a readable case-level report."""
import collections, datetime, hashlib, json, pathlib
BASE=pathlib.Path(__file__).resolve().parent
ROOT=BASE.parents[1]
def link(path,label): return f"[{label}](<{path.as_posix()}>)"
def clean(value): return str(value).replace("|","\\|").replace("\n"," ")
def count_text(value): return ", ".join(f"{k}: {v}" for k,v in value.items())
def main():
    result=json.loads((BASE/"results.json").read_text(encoding="utf-8"))
    corpus=json.loads((BASE/"corpus.json").read_text(encoding="utf-8"))
    cases={r["record_id"]:r for r in corpus["records"]}
    summary=result["summary"];dimensions=summary["dimensions"]
    lines=["# Independent LLM review of 161 MotoMedic cases", "",
        "Three fresh Codex LLM judge agents reviewed the complete 161-case corpus in disjoint shards (61/50/50), with one independent judge per case. Each used the full agent-feedback Markdown, accepted feedback history, authored branch context, TRD policy and original OEM PDF. Earlier source approval was not taken as a quality pass.", "",
        f"**All 161 cases reviewed.** Overall verdicts: {count_text(dimensions['overall'])}. Mean current-answer quality: {summary['mean_answer_quality']}/5.", "",
        "This is a static content and conversation-design review. Current responses are approved claim text joined in recorded order, or canonical policy responses. No external Gemma request was made, and no live rider conversation, rendered UI or controller transition was executed. Source checks distinguish OEM mechanical facts from product-policy statements. These findings do not silently change the signed release package or responses.", "",
        "## Results", "", "| Dimension | Results |", "| --- | --- |"]
    for key,label in [("initial_grounding","Initial grounding in manual or product policy"),("dialogue_flow","Authored conversation flow"),("feedback_alignment","Alignment with owner feedback"),("overall","Overall quality verdict")]:
        lines.append(f"| {label} | {clean(count_text(dimensions[key]))} |")
    lines += [f"| Current-answer quality, 1–5 | {clean(count_text(summary['answer_quality_distribution']))}; mean {summary['mean_answer_quality']} |", "",
        "PASS in grounding means the judge found support for the current response in its proper source namespace. It does not establish rider applicability or live execution. PARTIAL and FAIL identify content support or scope defects. Flow NOT_APPLICABLE is appropriate for complete terminal lookups; NOT_VERIFIABLE means the authored context does not show enough replies or transitions to assess a conversation. Neither is counted as a flow pass.", "",
        f"Scope of flow PASS ratings: {clean(count_text(summary['flow_pass_scope_counts']))}. Local single-turn clarification passes do not establish complete conditional reply paths. Other flow ratings assess the static authored context; none measures live execution.", "",
        "| Cohort | Cases | Grounding | Answer quality mean | Flow | Overall |", "| --- | ---: | --- | ---: | --- | --- |"]
    for name,group in summary["groups"].items():
        lines.append(f"| {name} | {group['case_count']} | {clean(count_text(group['initial_grounding']))} | {group['mean_answer_quality']} | {clean(count_text(group['dialogue_flow']))} | {clean(count_text(group['overall']))} |")
    lines += ["", "Answer quality scale: 1 unsafe/unusable; 2 major relevance, assumptions or readability problem; 3 substantive improvement needed; 4 useful with minor edits; 5 direct, practical, clear and concise with necessary safety context.", "", "## Findings requiring action", "",
        "Each proposed correction is review feedback. It has not been applied to the source-approved response package. Source defects should be corrected and rechecked before those affected responses are served; a quality pass on other cases does not repair them.", ""]
    actionable=[r for r in result["records"] if r["overall"]!="PASS"]
    actionable.sort(key=lambda r:(0 if r["initial_grounding"]=="FAIL" else 1 if r["initial_grounding"]=="PARTIAL" else 2, r["answer_quality"],r["record_id"]))
    for r in actionable:
        lines += [f"### {r['record_id']} — {r['overall']}", "",
            f"Question: {cases[r['record_id']]['question']}", "",
            f"Grounding {r['initial_grounding']}; answer quality {r['answer_quality']}/5; authored flow {r['dialogue_flow']}; feedback alignment {r['feedback_alignment']}.", "",
            str(r["rationale"]), ""]
        for f in r["findings"]:
            lines += [f"- **{f['severity']} / {f['affected_scope']}**: “{f['quote']}”", "",
                f"  Consequence: {f['consequence']}", "",
                f"  Source or policy: {f['source_or_policy_basis']}", "",
                f"  Smallest correction: {f['smallest_fix']}", ""]
    lines += ["## Verdict for every case", "", "| Case | Grounding | Quality /5 | Authored flow | Feedback | Overall |", "| --- | --- | ---: | --- | --- | --- |"]
    for r in result["records"]:
        lines.append(f"| {r['record_id']} | {r['initial_grounding']} | {r['answer_quality']} | {r['dialogue_flow']} | {r['feedback_alignment']} | {r['overall']} |")
    lines += ["", "## Evidence and reproducibility", "",
        "The coverage validator checked exactly one result for each of the 161 expected cases, three distinct judge agents, per-case hashes, the frozen feedback/context files and the original PDF checksum. It checks review completeness and input identity; semantic conclusions remain LLM judgments rather than measured production accuracy.", "",
        f"Corpus SHA-256: `{result['corpus_sha256']}`.", "",f"Feedback SHA-256: `{result['feedback_sha256']}`.", "", f"Manual SHA-256: `{result['manual_sha256']}`.", "",
        f"Input/quote validation: {clean(result['validation'])}", "",
        link(BASE/"results.json","All verdicts, rationales, source checks and exact findings (JSON)"), "",
        link(BASE/"corpus.json","Frozen complete case/response corpus"), "",
        link(BASE/"subagent_feedback.md","Full agent feedback used by the judges"), "",
        link(BASE/"record_id_verification.md","Accepted feedback history used by the judges"), ""]
    for shard in ("original_exp","gen_a","gen_b"):
        lines += [link(BASE/shard/"REPORT.md",f"Detailed judge report: {shard}"), ""]
    lines += ["The original-eleven judge independently checked 70 original PDF pages visually. Root also rendered and inspected PDF23/PDF29 to confirm the hazard-switch location finding. Per-shard reports and source checks identify the actual pages and rationale for each case. The review evaluates the preserved authored branches; it does not claim that missing transitions have been implemented or tested.", ""]
    (BASE/"REPORT.md").write_text("\n".join(lines),encoding="utf-8")
    files=["corpus.json","rubric.json","subagent_feedback.md","record_id_verification.md","AGENTS.md","03_TRD.txt","source_manifest.json","original_manual_pages.json","aggregate_reviews.py","format_report.py","results.json","REPORT.md"]
    files += [f"{shard}/{name}" for shard in ("original_exp","gen_a","gen_b") for name in ("records.json","REPORT.md")]
    files += sorted(str(p.relative_to(BASE)).replace("\\","/") for p in BASE.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.suffix in {".json",".md",".png",".txt"} and p.name != "manifest.json" and str(p.relative_to(BASE)).replace("\\","/") not in files)
    manifest={"schema_version":"llm-quality-review-manifest-v1","created_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
       "case_count":161,"review_scope":result["review_mode"],"approval_effect":result["approval_effect"],
       "files":{name:hashlib.sha256((BASE/name).read_bytes()).hexdigest() for name in files}}
    (BASE/"manifest.json").write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"report":str(BASE/"REPORT.md"),"manifest":str(BASE/"manifest.json"),"actionable_cases":len(actionable)},indent=2))
if __name__=="__main__":main()
