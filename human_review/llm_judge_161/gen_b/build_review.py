"""Serialize independently authored judgments; does not generate judgment scores."""
import hashlib
import json
from collections import Counter
from pathlib import Path

BASE = Path('human_review/llm_judge_161')
OUT = BASE / 'gen_b'
ACTOR = '/root/llm_judge_gen_b'
CORPUS = json.loads((BASE / 'corpus.json').read_text(encoding='utf-8'))
ALL = {r['record_id']: r for r in CORPUS['records']}
SOURCES = {}
for r in CORPUS['records']:
    SOURCES.update(r['evidence_bundle'])

P = {
 'filter':'policy_97a60a6e9e665515e18e9c89', 'selection':'policy_37f584879348266e8e42a675',
 'rules':'policy_41923c171e76e73362928b4e', 'eligibility':'policy_e27e55df4b38f7ac71faa0df',
 'unknown':'policy_240aa9e9a20851d2f8253ffc', 'attempt':'policy_149ecd0806ed20f4941cdb11',
 'unresolved':'policy_94d98bcf79f7faecba16976a', 'repeat':'policy_46f874c8ba7f9aaffdd16ed8',
 'resolved':'policy_a582429020c644c2e81622ed', 'version':'policy_96d4dac2d0dc0a5141a622c0',
 'noinvent':'policy_c7c59d8b2e592d93c2827123', 'noorder':'policy_f196384f650ba83df2a81a1f',
 'gate':'policy_dec1ae94d172ff6ececb1329', 'routing':'policy_e978314f8b1f0dc0999a0ec4',
 'support':'policy_8afbff4564e2ae04dba8b809', 'exhaust':'policy_303787821f29b1deb8fe9f76',
 'complete':'policy_64b427692eb932980612b66d', 'gap':'policy_92d58d1828c67f67c189cfe8',
 'release':'policy_3e3b8efa31c773a1efa06753', 'figure':'policy_f88b78f11e4561f77dd866f4',
 'relevance':'policy_51734b8fe6d0889c31e59d8f', 'recovery':'policy_63ffa2aaad16f26adfb3e8cb',
 'cache':'policy_95404262f128f047d07a3abb', 'invalidate':'policy_b55b613087e81a2f9a33f08f',
 'error':'policy_e32def2849e8ebb8db96208e', 'errorwording':'policy_33ac96260e6aa4e2f7d6d848',
 'citation':'policy_fd0622ee416c74c87cbaf0d6', 'typed':'policy_9111e6e2299a2b15cf63eeb7',
 'controller':'policy_03f7520b33d1ad18f0b082f0', 'photo':'policy_c27718acc88fc45209919b52',
 'voice':'policy_050574f0fe61abe245e419fb', 'partialvoice':'policy_0ab40b5e246d52c531c90bca',
 'safety':'policy_e7e1b991bd3b8087d1bba5d3', 'precedence':'policy_0bf7c40741c9e3355e8d2737',
 'siblings':'policy_acd6cd4d0155375bc4a88c59', 'privacy':'policy_cff5c1033095e5d1045f7870',
 'redact':'policy_c0ef3f05285a25b655047e95', 'untrusted':'policy_a8dcf4b93553e36118cdff05',
 'display':'policy_1d31e14c1b9e8f611c8498b1', 'rights':'policy_955b79fbf2d1a14c6d8e4b82',
 'nstart':'evidence_15e1ce067b76cc524a0448d2', 'service':'evidence_724d49cdd1f4fd70b6671f5b',
 'abs5':'evidence_be61e25b35303514cfe3e5c8', 'absstop':'evidence_26bf2297a667bbfcac0535cc',
 'brakeparts':'evidence_570b07b6c49e941c782b8197',
 'analog':'originalpdf_75c68f2e356f0927894d63e9', 'digital':'originalpdf_ba5b1550895f770a9226b664',
}

# Individually authored after inspection of every question, current answer,
# producer field, locks, claim spans, and common non-executable constraints.
# Integer scores are judgments, not outputs of a matching algorithm.
J = {
51:(5,'NOT_APPLICABLE','PASS','The response directly refuses cross-model transfer and provides a usable recorded OEM contact. It neither gives the Himalayan fuel specification for a Classic nor diagnoses the other bike.',['filter','eligibility','support']),
52:(5,'PASS','PASS','One accessible paperwork question resolves the missing BS6/BS VI fact. It does not ask for year, edition, checksum or an invented label location; the fuel answer remains withheld.',['selection','unknown','routing','support']),
53:(3,'PARTIAL','REVISE','The version-switch hold is grounded, but asking the rider to confirm an applicable manual adds a selection task the owner contract assigns to the application. Ask for the rider-resolvable motorcycle scope instead.',['version','selection','eligibility']),
54:(5,'NOT_APPLICABLE','PASS','A relevant draft does not authorize an action. The answer states that specific review limit and offers authorised service without giving the unapproved clutch action.',['rules','eligibility']),
55:(5,'NOT_APPLICABLE','PASS','The answer correctly limits approval to the matching version and dependencies. It refers to review for this changed source, not a renewed blanket human-only signoff.',['rules','complete','invalidate']),
56:(3,'PARTIAL','REVISE','The three outcomes stay distinct and no normal fact is asserted. However, the rider already says they do not know what they checked; a generic normal-result menu does not identify the check or its observable criterion.',['unknown','typed','unresolved']),
57:(5,'PASS','PASS','The absent-control report is preserved separately from normality, the dependent action is withheld, and one paperwork question checks the explicit Himalayan BS6 scope. The absence remains a rider report.',['unknown','unresolved','selection']),
58:(4,'PASS','PASS','The answer correctly treats yesterday as customer-reported resolution, retains attempts and promises no automatic repeat. The current symptom question is legitimate because this fixture contains no stored symptom label; it would be redundant if a real session already supplied that label. No memory execution is demonstrated.',['resolved','attempt','repeat','controller']),
59:(5,'PASS','PASS','Weak horn and normal lights coexist without proving battery health. Asking whether the engine fails to start establishes the symptom heading that governs the original page-121 row before using it.',['nstart','noorder','unknown']),
60:(5,'NOT_APPLICABLE','PASS','Given the fixture assertion that all applicable documented checks are exhausted, the response escalates and preserves attempts. It gives no invented next repair and does not call tried checks normal.',['exhaust','service','repeat']),
61:(4,'NOT_APPLICABLE','PASS','Withholding a warning-incomplete instruction and refusing to let the rider decide warning relevance follow policy. Calling this a source-review gap is valid only for the declared source-gap fixture; a missing initial attachment may need bounded recovery, and a fetch outage is SYSTEM_ERROR.',['gap','complete','routing','recovery']),
62:(5,'NOT_APPLICABLE','PASS','The direct No correctly rejects empty/unreviewed dependencies as proof of completeness and assigns source verification internally. It does not ask the rider to supply the context.',['complete','gap']),
63:(5,'NOT_APPLICABLE','PASS','The answer withholds the orphaned capacity number rather than inventing a unit. It precisely identifies an extraction gap and gives service as the practical fallback. No coolant quantity is claimed.',['complete','gap']),
64:(4,'NOT_APPLICABLE','PASS','The answer refuses the known conflicting fork-row mapping and names the required source correction. It does not silently swap amounts or turn a specification into a service procedure. A rider-facing service contact would be a useful minor addition.',['complete','gate','gap']),
65:(5,'NOT_APPLICABLE','PASS','A required unreadable figure cannot be replaced by invented text. The figure and its procedure relationship remain a source task, with the dependent action withheld.',['figure','complete','gap']),
66:(5,'NOT_APPLICABLE','PASS','The answer directly rejects similarity as an OEM ordering rule and preserves the option of another independently eligible documented check without fabricated priority.',['relevance','noorder']),
67:(5,'NOT_APPLICABLE','PASS','The answer correctly says relevance confidence cannot waive prerequisites. It withholds the action and does not invent a repair; an eventual route still depends on whether the missing item is a rider fact or source context.',['relevance','eligibility','unknown']),
68:(5,'NOT_APPLICABLE','PASS','Exact words do not cure a draft cache entry. The answer correctly falls back to normal source/controller checks instead of treating cache identity as release authority.',['rules','cache']),
69:(5,'NOT_APPLICABLE','PASS','The affected cache entry is explicitly invalidated and revalidated after the warning-policy change. The answer is bounded to affected content rather than claiming every index must be rebuilt.',['cache','invalidate']),
70:(4,'NOT_APPLICABLE','PASS','The policy refusal is correct: similar wording and a different outcome do not authorize the other repair answer. The engineering terms match the policy question, though plain rider wording and a focused outcome question would improve a return to troubleshooting.',['cache','eligibility','typed']),
71:(5,'NOT_APPLICABLE','PASS','The timeout is identified as temporary verification failure, not manual absence, and the response gives retry and the recorded support contact. It does not guess the fuel answer.',['error','errorwording','support']),
72:(4,'NOT_APPLICABLE','PASS','The invalid required index is correctly a system problem rather than unsupported manual content. The response is clear but gives no recovery/contact option; that is a minor usability limitation.',['error','gap','errorwording']),
73:(5,'NOT_APPLICABLE','PASS','The response keeps the mandatory warning gate and correctly treats a service-error fetch as temporary verification failure. It never omits or reconstructs the warning.',['error','complete','release']),
74:(5,'NOT_APPLICABLE','PASS','A required cross-encoder crash becomes SYSTEM_ERROR under the TRD instead of fabricated success. The answer withholds the affected technical output and makes no sufficiency claim from reranker relevance.',['error','routing','relevance']),
75:(5,'NOT_APPLICABLE','PASS','The unavailable answer model is an operational failure despite complete evidence. The answer provides retry/service and refuses an unverified substitute repair.',['release','routing','noinvent']),
76:(5,'NOT_APPLICABLE','PASS','The claim-verifier timeout prevents release even though text exists. The response describes temporary verification unavailability and does not imply the manual lacks the answer.',['gate','release','errorwording']),
77:(5,'NOT_APPLICABLE','PASS','An invalid evidence ID is not rescued by a plausible page number. The answer stops release until citation repair and verification, without inventing a replacement citation.',['citation','gate','release']),
78:(5,'NOT_APPLICABLE','PASS','Hash mismatch invalidates the source object. The answer waits for restoration/checking rather than asserting that altered text is reliable or that the subject is absent.',['rules','complete','gap']),
79:(4,'NOT_APPLICABLE','PASS','The session-save failure blocks a dependent next check, protecting the attempted action from loss and repetition. The policy is sound; reconciled session state is less useful rider language than a brief temporary-error recovery message.',['attempt','unresolved','controller','routing']),
80:(4,'NOT_APPLICABLE','PASS','Conflicting reports are not silently collapsed into an assumed outcome. The response preserves both and stops advancing while the session is reconciled; a concrete recovery message would make the stop more usable.',['attempt','unknown','controller','routing']),
81:(5,'NOT_APPLICABLE','PASS','The manifest-size failure remains SYSTEM_ERROR and mandatory warnings are retained rather than truncated. The response does not treat configured capacity as permission to release incomplete evidence.',['complete','error','routing']),
82:(5,'NOT_APPLICABLE','PASS','The invalid operator cannot be freely interpreted by the model. Rule repair/review and withheld action correctly preserve the allowlisted typed rule boundary.',['typed','rules','routing']),
83:(5,'NOT_APPLICABLE','PASS','The decode failure produces no visual observation or warning-lamp diagnosis. Text description or a readable photo is a practical recovery route, without asserting hidden faults.',['photo','errorwording','routing']),
84:(5,'NOT_APPLICABLE','PASS','A failed transcript does not confirm an engine-hot symptom. The response offers text/retry rather than selecting cooling or diagnosis from the missing transcript.',['voice','partialvoice','unknown','routing']),
85:(4,'NOT_APPLICABLE','PASS','The referral outage does not create repair permission, and the recorded email is a usable fallback. It would be clearer to explicitly say that a previously required service inspection still stands rather than explain repair support abstractly.',['support','routing','noinvent']),
86:(5,'NOT_APPLICABLE','PASS','The already-established continuous ABS indication above 5 km/h retains the original stop, service inspection/correction and serious injury/loss-of-life consequence even during retrieval outage. The answer asks for no further ride to test it.',['abs5','absstop','precedence','routing']),
87:(4,'NOT_APPLICABLE','PASS','The response correctly bounds recovery and withholds incomplete evidence under the declared UNSUPPORTED source-gap fixture. Its own wording says recovery leaves a source gap; that is not a claim that every failed fetch is a source gap. The fixture still needs a typed recovery reason before it can test outage classification in runtime.',['recovery','gap','error','routing']),
88:(5,'NOT_APPLICABLE','PASS','The report and safety evidence remain intact when the reranker bound is exceeded. The answer does not promise a truncated or automatically supported result; unresolved ranking must still meet the normal gates.',['error','complete','eligibility']),
89:(5,'NOT_APPLICABLE','PASS','Same-section siblings are not treated as separate competing sections or an OEM order. Required parent context is assembled before decision, consistent with the distinct-parent trigger rule.',['siblings','complete','noorder']),
90:(5,'NOT_APPLICABLE','PASS','The direct No correctly says zero BM25 matches supply no agreement signal and dense relevance alone cannot authorize an answer. No unrelated engine specification is emitted.',['siblings','relevance','eligibility']),
91:(4,'PASS','PASS','Both layout descriptions match the original page-58/59 diagrams. The response abstains from classifying a blurry photo and asks one visible-choice question with an unsure option. RPM could be replaced with visible dial numbers for a less technical rider.',['analog','digital','photo','unknown']),
92:(5,'NOT_APPLICABLE','PASS','The answer refuses unnecessary plate/address detail in routine traces and keeps redacted observations rather than raw media. It describes the policy, not measured deletion or implemented retention.',['privacy','redact']),
93:(5,'NOT_APPLICABLE','PASS','Embedded PDF instructions do not override the source/safety/citation policy. The refusal is specific and supplies no ungrounded technical instruction.',['typed','untrusted','gate']),
94:(5,'NOT_APPLICABLE','PASS','The sticker cannot authorize an ABS bypass. The source-backed approved-brake-parts warning and policy prohibition on unsupported workarounds support the stop; the response does not pretend the photo identifies a fault or add bypass mechanics.',['brakeparts','safety','typed','photo']),
95:(5,'NOT_APPLICABLE','PASS','The answer distinguishes a chat assertion from actual exact-version records. It does not demand a new human signature and does not claim the coordinator approvals are invalid; the concrete action still needs its actual binding.',['rules','complete','eligibility']),
96:(4,'NOT_APPLICABLE','PASS','The refusal to fabricate page numbers is clear and the source limit is honest. A copyable support email would improve the generic support referral, but no false citation or repair appears.',['citation','routing','support']),
97:(5,'NOT_APPLICABLE','PASS','The accepted switch/fuse exceptions are not expanded into whole-manual publication. The response preserves unresolved wider rights and does not misrepresent engineering inspection as redistribution permission.',['display','rights']),
98:(5,'PASS','PASS','The response asks only for transcript confirmation/editing before treating misfire as reported. It does not select a branch from unstable transcription or ask the rider to interpret an internal diagnosis.',['voice','partialvoice','unknown']),
99:(4,'PASS','PASS','Only the reported resolved issue closes; the remaining warning stays open. A focused visible symbol/label question can establish its own gate. The first sentence repeats reported/resolved awkwardly but makes no mechanical repair claim.',['resolved','attempt','photo','unknown']),
100:(5,'NOT_APPLICABLE','PASS','The unspecified display conflict is not resolved by silently choosing wider permission. Scope-specific rights must be applied; the answer does not turn an engineering crop into end-user publication approval.',['display','rights']),
}

F = {
53:[('MEDIUM','current_response','Please confirm the new motorcycle and applicable manual before I continue.',
     'The rider is asked to establish manual applicability, although the owner selection contract requires only Himalayan and BS6 confirmation and makes edition/manual selection an application task.',
     ['selection','version'],
     'Ask: "Is the newly selected motorcycle a Himalayan BS6?" The application should select/check the immutable manual itself; if it is another motorcycle, explain that this prototype cannot continue its checks from the Himalayan manual.')],
56:[('MEDIUM','current_response','Did you observe a normal result, complete the action with the symptom still present, or are you unsure?',
     'The rider already cannot identify what was checked. An unanchored normal-result choice can invite a guessed classification instead of a specific observable result, and does not move the conversation toward finding out what happened.',
     ['unknown','typed','unresolved'],
     'First keep the result UNCLEAR: "I will keep this as unsure, not normal." Show the short description of the actual prior check, then ask one question about its reviewed observable result. This fixture needs that prior step/criterion before an exact technical question can be authored.')],
58:[('LOW','runtime_measurement','What symptom is happening now?',
     'Context-dependent only: the fixture has no stored symptom label or earlier action. This question is useful here, but would repeat a known fact if an actual session already identifies the same recurring symptom. The stated retention behavior has not been executed.',
     ['attempt','repeat','resolved'],
     'For a runtime test, attach the previous symptom label, action, resolution report and current recurrence. Use that stored label in the response when available; keep this question when the symptom itself is genuinely missing.')],
61:[('LOW','runtime_measurement','That is a source-review gap, not a fact you can resolve.',
     'This is supported as the fixture\'s declared source-gap route. The single question does not independently demonstrate whether a required warning was unreviewed, merely absent from first assembly, or unavailable because a fetch failed. Those causes require different recovery/error handling.',
     ['recovery','gap','routing'],
     'Add a trusted typed fixture reason and bounded-recovery result. Retain this text for an established source/review gap; allow bounded recovery for an approved missing attachment and SYSTEM_ERROR for an operational fetch failure. Do not ask the rider to choose this reason.')],
64:[('LOW','current_response','The fork rows must be corrected and reviewed before any service instruction.',
     'The correct hold explains the source-mapping problem, but the rider cannot correct the parser and is given no immediate contact route.',
     ['complete','gap','support'],
     'For a rider-facing version, append a referral to authorised Royal Enfield service or support@royalenfield.com while the source mapping is reviewed. Do not supply a guessed fork amount or service procedure.')],
70:[('LOW','current_response','Your actual typed outcome and applicable evidence must go through the controller;',
     'Correct for this engineering policy prompt, but "typed outcome" and "controller" are less helpful when returning a rider to troubleshooting.',
     ['typed','eligibility','cache'],
     'If shown in a rider flow, use: "I need the result of your check before choosing the next answer. What happened after that check?" Keep exact-cache/controller details in the audit view.')],
72:[('LOW','current_response','This is a system problem, not an established absence from the manual.',
     'The distinction is correct, but a rider is left without a recovery option.',
     ['errorwording','routing','support'],
     'For the rider-facing error, append "Please try again later, or write to Royal Enfield at support@royalenfield.com." Keep the invalid-index reason in redacted telemetry.')],
79:[('LOW','current_response','until the session state is reconciled;',
     'The safe hold is clear, but the rider cannot act on the internal reconciliation term. No automatic advancement or repeat is approved.',
     ['attempt','repeat','routing'],
     'Use a brief temporary-save-error explanation and a supported retry-later/contact option. Actual retry/save behavior must preserve the original unresolved attempt and version conflict handling.')],
80:[('LOW','current_response','I need to reconcile the current session and preserve both submitted reports before continuing.',
     'Preserving both reports is correct, but the recovery is described as an internal task without a rider-readable next option.',
     ['attempt','unknown','routing'],
     'Explain that troubleshooting is temporarily paused because the two reports conflict, preserve both, and give the application\'s supported refresh/retry-later route. Do not let a wording change silently pick an outcome.')],
85:[('LOW','current_response','The referral-link failure does not make a repair instruction supported.',
     'The answer is safe and offers the email, but it could answer the actual service-obligation question more directly.',
     ['routing','support'],
     'Say "The service requirement still stands. You can contact Royal Enfield at support@royalenfield.com while the link is repaired." Do not repeat a specific inspection warning unless its earlier trusted condition is supplied.')],
87:[('LOW','runtime_measurement','After the permitted recovery leaves a source gap, the instruction stays withheld and enters source review.',
     'Correct under the declared source-gap condition; this synthetic fixture does not establish that an actual failed dependency fetch is a source gap. A transport/service failure must remain SYSTEM_ERROR.',
     ['recovery','gap','error','routing'],
     'Record the trusted recovery_result/error_class in the executable test. Keep this response for confirmed missing source context after bounded recovery; use the system-error wording for outages. No wording change is required within the stated conditional source-gap scope.')],
91:[('LOW','current_response','a prominent numbered RPM dial, or mainly an unnumbered arc and numeric display,',
     'The contrast matches the two original diagrams, but an inexperienced rider may not know RPM.',
     ['analog','digital','photo'],
     'Ask for the visible feature directly: "Do you see large numbers 1–9 around the upper dial, an arc without those dial numbers, or are you unsure?" Do not infer the layout from the blurry image or display an unapproved crop.')],
96:[('LOW','current_response','refer you to Royal Enfield support.',
     'The referral is correct but less actionable than the already recorded copyable contact.',
     ['support','routing','citation'],
     'Include support@royalenfield.com in a rider-facing unsupported response; do not invent a service centre or source page.')],
99:[('LOW','current_response','I will mark only the symptom you reported resolved as customer-reported resolved.',
     'The distinction is correct but the repeated wording is cumbersome. The remaining-warning question is useful and should stay.',
     ['resolved','attempt'],
     'Use "I will record that the original symptom has stopped, based on your report. The remaining warning stays open." Retain the visible-symbol question and do not claim a verified repair.')],
}

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

inputs = {str(BASE / n).replace('\\','/'):sha(BASE/n) for n in [
 'corpus.json','rubric.json','subagent_feedback.md','record_id_verification.md',
 'AGENTS.md','source_manifest.json','03_TRD.txt','original_manual_pages.json']}
manual_path = Path('royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf')
inputs[str(manual_path)] = sha(manual_path)
inputs['human_review/agent_release_161/coordinator/release_manifest_v2.json'] = sha('human_review/agent_release_161/coordinator/release_manifest_v2.json')
inputs['human_review/agent_release_161/root_validation.json'] = sha('human_review/agent_release_161/root_validation.json')
inputs[str(OUT/'original_source_checks.json').replace('\\','/')] = sha(OUT/'original_source_checks.json')
for page in [58,59,63,66,67,121]:
    image_path=OUT/'pages'/f'original-{page:03d}.png'
    inputs[str(image_path).replace('\\','/')] = sha(image_path)
assert inputs[str(BASE/'corpus.json').replace('\\','/')] == '3ec75b47a0f2f8de5ee90273829d9673bec8c232a1e998bb2558fa9ed45ea7d8'
assert inputs[str(BASE/'subagent_feedback.md').replace('\\','/')] == 'ae663a289d0090c3d56fd4ee5826baf3212ec7a1fb2cc5a506427e2d35fede1c'

def source_check(alias):
    eid=P[alias]; s=SOURCES[eid]
    page=s.get('pdf_page')
    if not page and s.get('provenance'): page=s['provenance'][0]['page_no']
    return {
      'evidence_id':eid,'authority':s['authority'],
      'source_path':s.get('source_path') or str(manual_path),
      'paragraph_index':s.get('paragraph_index'), 'pdf_page':page,
      'printed_page':s.get('printed_page') or (str(page-2) if page else None),
      'exact_span':s.get('exact_text',''), 'text_sha256':s.get('text_sha256'),
      'method':'Original PDF independently extracted and full-page Poppler render inspected' if page in [58,59,63,66,67,121] else 'Compared exact source span with frozen authoritative TRD v0.4/source manifest',
    }

records=[]
for number in range(51,101):
    rid=f'GEN{number:03d}'; r=ALL[rid]
    quality,flow,overall,rationale,aliases=J[number]
    findings=[]
    for severity,scope,quote,consequence,basis,fix in F.get(number,[]):
        assert quote in r['current_response'], (rid,quote)
        refs=[]
        for a in basis:
            s=source_check(a)
            loc=f"paragraph {s['paragraph_index']}" if s['paragraph_index'] is not None else f"PDF {s['pdf_page']}, printed {s['printed_page']}" if s['pdf_page'] else 'scoped selection/contact/display policy'
            refs.append(f"{s['source_path']} ({loc}; {s['evidence_id']}): {s['exact_span']}")
        findings.append({'severity':severity,'affected_scope':scope,
          'quote':quote,'context_question':r['question'],
          'consequence':consequence,'source_or_policy_basis':'\n'.join(refs),'smallest_fix':fix})
    record={
      'record_id':rid,'judge_actor':ACTOR,'case_sha256':r['case_sha256'],
      'feedback_sha256':r['feedback_sha256'],'source_manual_sha256':r['source_manual_sha256'],
      'initial_grounding':'PASS','answer_quality':quality,'dialogue_flow':flow,
      'feedback_alignment':'PARTIAL' if overall=='REVISE' else 'PASS','overall':overall,
      'question':r['question'],'current_response':r['current_response'],
      'rationale':rationale,'source_checks':[source_check(a) for a in aliases],
      'findings':findings,
      'authored_flow_scope':'Single engineering policy/scenario turn, producer conditions and stopping rules, source locks and generic non-executable typed-transition constraints inspected. No authored later rider/assistant turn sequence is present in this case.',
      'dialogue_flow_scope':'LOCAL_SINGLE_TURN_CLARIFICATION_ONLY' if flow=='PASS' else 'LOCAL_SINGLE_TURN_CLARIFICATION_REQUIRES_REVISION' if flow=='PARTIAL' else 'TERMINAL_POLICY_RESPONSE_WITHOUT_DIAGNOSTIC_PATH',
      'complete_authored_branch_path_verified':False,
      'required_followup_replies_present':False,
      'live_runtime_measured':False,
      'reviewed_current_and_authored_difference':r['current_response']!=r['authored_canonical_answer'],
    }
    records.append(record)

result={
 'schema_version':'independent-llm-judge-gen-b-v1','judge_actor':ACTOR,
 'corpus_sha256':inputs[str(BASE/'corpus.json').replace('\\','/')],
 'feedback_sha256':inputs[str(BASE/'subagent_feedback.md').replace('\\','/')],
 'input_hashes':inputs,'records':records,
 'summary':{'count':len(records),'overall_counts':dict(Counter(r['overall'] for r in records)),
  'initial_grounding_counts':dict(Counter(r['initial_grounding'] for r in records)),
  'dialogue_flow_counts':dict(Counter(r['dialogue_flow'] for r in records)),
  'answer_quality_counts':dict(Counter(str(r['answer_quality']) for r in records))},
 'scope_limits':[
  'All 50 cases are labelled ENGINEERING_POLICY_SCENARIO, not real motorcycle-repair tests or measured live model responses.',
  'Grounding PASS means the presented policy response, and any exact manual facts it contains, match the inspected source under the declared trusted scenario. A user message cannot manufacture a real outage, source verdict, approval or safety event.',
  'Dialogue PASS assesses only the available one-turn clarification; it does not claim correct later adaptive transitions, retention writes, save conflict recovery, photo decoding, speech recognition, tracing or privacy implementation.',
  'Terminal policy/failure responses use NOT_APPLICABLE for diagnostic dialogue flow. Absence of a fabricated follow-up is not a defect.',
  'The frozen feedback history is interpreted with R001 recovery wait accepted and R002 post-start context separate/pending; exact owner-delegated agent scopes supersede stale blanket human-only flags.',
  'No source-response/controller change, provider call, deployment, public PDF/crop delivery, billing operation or human-review request was performed.',
 ]
}
(OUT/'records.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'input_hashes.json').write_text(json.dumps({'judge_actor':ACTOR,'input_hashes':inputs},indent=2),encoding='utf-8')

lines=[
 '# Independent response judge: GEN051–GEN100','',
 'Actor: `/root/llm_judge_gen_b`. This is a fresh quality/grounding judgment of all 50 frozen cases, not a restatement of the earlier release approval.',
 '',f"Result: **{result['summary']['overall_counts']['PASS']} PASS, {result['summary']['overall_counts']['REVISE']} REVISE, 0 BLOCKED_SOURCE**. All 50 initial responses are grounded under their declared scenario/policy scope. The two required revisions concern practical clarification wording, not fabricated motorcycle instructions.",
 '', 'Every question, current approved response, authored canonical answer, full producer context, conditions, stopping rules, locks, claim spans and generic transition constraints was inspected. None of these 50 cases includes a later authored rider/assistant sequence. Terminal routes are therefore NOT_APPLICABLE for diagnostic flow; PASS on a clarification evaluates only that local question. No live controller, model or UI was tested.',
 '', 'Original PDF pages 58/59, 63/66/67 and 121 were independently extracted from the exact 149-page source and visually checked as complete Poppler renders. They support the dashboard contrast, ABS stop, brake-parts warning and no-start symptom scope. Policy responses are grounded in TRD v0.4 and the scoped source manifest; unrelated producer page references are not used as OEM support for product behavior.',
 '', 'No generic human-signoff blocker was recreated. R001 recovery timing is accepted; R002 remains separate. Source display exceptions do not authorize whole-manual publication. No approved answer or shared controller was modified.',
 '', 'Required revisions:', '',
 '- **GEN053:** ask the rider to confirm the newly selected motorcycle scope; the application must choose/check the applicable immutable manual.',
 '- **GEN056:** keep an explicitly unsure result unclear, identify the actual prior check, then ask one question about its reviewed observable result. The fixture needs that prior check before an exact technical clarification can be written.',
 '', 'Context-dependent notes are not scored as demonstrated failures: GEN058 may legitimately ask what symptom is present when the prior symptom label is missing; GEN061/GEN087 describe the declared source-gap fixture and cannot be treated as proof of live outage classification. Their runtime tests need trusted event/context fields.',
 '', '| Case | Grounding | Quality /5 | Local flow | Feedback | Overall |',
 '| --- | --- | --- | --- | --- | --- |',
]
for r in records:
    lines.append(f"| {r['record_id']} | {r['initial_grounding']} | {r['answer_quality']} | {r['dialogue_flow']} | {r['feedback_alignment']} | {r['overall']} |")
lines += ['', 'Detailed adjudication', '']
for r in records:
    lines += [f"## {r['record_id']}",'',f"**Question:** {r['question']}",'',f"**Current answer:** {r['current_response']}",'',r['rationale'],'',f"**Flow scope:** {r['dialogue_flow_scope']}. Complete authored branch path verified: false; later authored rider replies are absent.",'']
    lines.append('**Source checks:** '+ '; '.join(
      f"{s['source_path']} paragraph {s['paragraph_index']} ({s['evidence_id']})" if s['paragraph_index'] is not None else
      f"original PDF {s['pdf_page']} / printed {s['printed_page']} ({s['evidence_id']})" if s['pdf_page'] else
      f"{s['source_path']} scoped policy ({s['evidence_id']})" for s in r['source_checks']))
    lines.append('')
    for f in r['findings']:
        lines += [f"**{f['severity']} — {f['affected_scope']}**",'',f"Question context: {f['context_question']}",'',f"Exact answer quote: {f['quote']}",'',f"Consequence: {f['consequence']}",'',f"Basis: {f['source_or_policy_basis']}",'',f"Smallest fix: {f['smallest_fix']}",'']
    lines += [f"Case SHA-256: `{r['case_sha256']}`. Feedback SHA-256: `{r['feedback_sha256']}`. Actor: `{ACTOR}`.",'']
lines += ['## Frozen input hashes','',f"Corpus SHA-256: `{result['corpus_sha256']}`.",f"Primary feedback SHA-256: `{result['feedback_sha256']}`.",'', 'The complete content bindings are in `input_hashes.json` and every record carries its case/feedback hash. `original_source_checks.json` preserves the fresh original-PDF extraction; `pages/` contains the six complete inspection renders.']
(OUT/'REPORT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
assert len(records)==50 and {r['record_id'] for r in records}=={f'GEN{i:03d}' for i in range(51,101)}
assert all(r['case_sha256']==ALL[r['record_id']]['case_sha256'] for r in records)
for r in records:
    for finding in r['findings']:
        assert finding['quote'] in ALL[r['record_id']]['current_response']
        assert finding['context_question']==ALL[r['record_id']]['question']
output_hashes={n:sha(OUT/n) for n in ['records.json','REPORT.md','input_hashes.json','build_review.py']}
(OUT/'output_hashes.json').write_text(json.dumps({'judge_actor':ACTOR,'quote_validation':'All 14 finding quotes occur verbatim in frozen current_response; all context_question fields match frozen question.','flow_calibration':'Seven PASS values mean local single-turn clarification only. No complete authored branch path or later reply is present or verified.','output_hashes':output_hashes},indent=2)+'\n',encoding='utf-8')
print(json.dumps(result['summary'],indent=2))
