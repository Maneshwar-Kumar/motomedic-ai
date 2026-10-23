"""Question-driven adapter over existing retrieval and exact reviewed answers.

Arbitrary text is accepted. Conservative lexical scope checks can abstain on
paraphrases; they never supply source approval, mechanical facts or new wording.
"""
from dataclasses import replace
import hashlib
import json
import re
import unicodedata

from controller_contracts import ResponseType, Truth, Outcome
from reviewed_controller import ReviewedController, start_session, append_attempt
from cloud.arm_a.composer import ArmAComposer
from cloud.arm_a.rider_contract import saved_view

VERSION = 'open-question-exact-components-v2'
# Scope admission is deliberately conservative. Ordered keys preserve subjects,
# operators, negation and comparisons; retrieval relevance cannot establish
# equivalence. These explicit paraphrases require independent source review.
PARAPHRASES = {
    'GEN007': ('Can I use E20 petrol?', 'Is E20 permitted?',
               'Can I use E20 fuel?', 'Is E20 fuel allowed?'),
    'GEN003': ('Why do vehicles look farther in my mirrors?',
               'Do vehicles in mirrors look smaller and farther away?'),
}


def proposition_key(text):
    normalized = unicodedata.normalize('NFKC', text).casefold().strip()
    if normalized.endswith('?'):
        normalized = normalized[:-1].rstrip()
    # Retain every other symbol/script and clause, including comparison signs.
    words = re.findall(r'\w+(?:\.\d+)?|[^\w\s]', normalized)
    # Only spelling/singular and fuel-name substitutions; no grammar deletion.
    spelling = {'petrol':'fuel', 'gasoline':'fuel', 'cars':'vehicles',
                'car':'vehicle', 'mirror':'mirrors', 'tires':'tyres'}
    return tuple(spelling.get(w, w) for w in words)
STOP = frozenset('a an the i me my mine you your we our it its this that these those is are am was were be been being do does did can could would should will shall may might have has had of to for from in on at by with and or as if then than about what which who when where how why please tell explain give describe described manual owner owners motorcycle bike himalayan bs6 royal enfield question listed list specify specified say says according'.split())
ALIASES = {'petrol':'fuel', 'gasoline':'fuel', 'gas':'fuel', 'car':'vehicle',
           'cars':'vehicle', 'vehicles':'vehicle', 'mirror':'mirrors',
           'tires':'tyre', 'tire':'tyre', 'tyres':'tyre', 'liters':'litre',
           'litres':'litre', 'liter':'litre', 'kilograms':'kg',
           'allow':'use', 'allows':'use', 'allowed':'use', 'approved':'use',
           'compatible':'use', 'compatibility':'use', 'permitted':'use',
           'looks':'look', 'appear':'look', 'appears':'look', 'seem':'look',
           'seems':'look', 'further':'farther', 'pressure':'pressure'}
RESTRICTED = frozenset('repair fix replace replacing remove removing dismantle disassemble bypass disable disabling modify modification tune tuning diagnose diagnosis cause causes torque tighten tightening'.split())


def terms(text):
    words = re.findall(r'[a-z]+\d+(?:\.\d+)?|\d+(?:\.\d+)?|[a-z]+',
                       unicodedata.normalize('NFKC', text).casefold())
    return {ALIASES.get(w, w) for w in words if w not in STOP}


class Questions:
    def __init__(self, registry, retriever):
        self.registry, self.retriever = registry, retriever
        self.controller = ReviewedController(registry, retriever, response_generator=ArmAComposer())
        self.controller.audience = 'end_user'
        self.descriptors = {}
        for sid, step in registry.candidate['steps'].items():
            rid = step['canonical_record_id']
            row = registry._consumer.records[rid]
            path = registry._consumer.root / row['planner_file']
            raw = path.read_bytes()
            if hashlib.sha256(raw).hexdigest() != row['planner_file_sha256']:
                raise ValueError('Question scope binding changed')
            case = json.loads(raw)['candidate_case']
            question = case.get('branch_context', {}).get('producer', {}).get('question') or case.get('question')
            if not isinstance(question, str) or not question.strip():
                continue
            claims = ' '.join(c['text'] for c in step['claims'])
            self.descriptors[sid] = {'rid': rid, 'question': question,
                                    'propositions': frozenset(proposition_key(q) for q in
                                        (question,)+PARAPHRASES.get(rid, ())),
                                    'question_terms': terms(question),
                                    'allowed_terms': terms(question+' '+claims),
                                    'operations': terms(question) & RESTRICTED}

    def scope(self):
        r = self.registry
        return {'source_sha256':r.checksum, 'manual_id':r.source['manual_id'],
                'variant':r.source['variant'], 'edition':r.source['edition'],
                'language':r.source['language'], 'motorcycle':r.source['motorcycle']}

    def select(self, query):
        """Rank existing hybrid hits, then exclude out-of-scope question requests.

        Hits and scores are never a release assertion. A selected component must
        still traverse the original eligibility, dependency and citation gates.
        """
        bundle = self.retriever.search(query, limit=10, scope=self.scope(),
                                       applicability_status='CONFIRMED')
        if (bundle.get('manual_checksum', '').lower() != self.registry.checksum or
                bundle.get('index_id') != self.registry.index_id):
            raise ValueError('Candidate source mismatch')
        qterms = terms(query)
        if not qterms:
            return None, 'QUESTION_SCOPE_UNCLEAR'
        ranked = []
        for sid, descriptor in self.descriptors.items():
            if proposition_key(query) not in descriptor['propositions']:
                continue
            if not qterms <= descriptor['allowed_terms']:
                continue
            if not (qterms & RESTRICTED) <= descriptor['operations']:
                continue
            subject = qterms & descriptor['question_terms']
            if not subject:
                continue
            step = self.registry.step(sid)
            # Only direct retrieved objects count here, never all parent-page
            # expansion or an automatically attached mandatory dependency.
            positions = [i for i, hit in enumerate(bundle.get('hits', []))
                         if set(hit.get('evidence_ids', [])) & set(step.action_evidence_ids)]
            if not positions:
                continue
            coverage = len(subject)/len(qterms)
            ranked.append((coverage, -min(positions), sid))
        ranked.sort(reverse=True)
        if not ranked:
            return None, 'NO_SUPPORTED_QUESTION_SCOPE'
        # Competing equally-covered records mean the requested scope is unclear;
        # a retrieval rank cannot resolve a substantive question ambiguity.
        if len(ranked)>1 and ranked[0][0] == ranked[1][0]:
            return None, 'QUESTION_SCOPE_UNCLEAR'
        return ranked[0][2], None

    def new_session(self):
        r = self.registry
        return replace(start_session(r, (), r.source['variant'], r.source['edition']),
                       generation_lock=self.controller.response_generator.config.lock)

    def answer(self, session, query):
        r, c = self.registry, self.controller
        if c.scope_status(session) != 'CONFIRMED':
            raise ValueError('Session scope changed')
        session = replace(session, version=session.version+1, pending_step_id=None,
                          pending_rule_id=None, status='OPEN')
        try:
            sid, reason = self.select(query)
        except Exception:
            response = c.response('SYSTEM_ERROR', 'I am temporarily unable to verify the manual evidence.',
                                  session, reason_codes=('QUESTION_RETRIEVAL_FAILURE',))
        else:
            if sid is None:
                response = c.response('UNSUPPORTED', 'I could not verify a supported answer to this question in the selected manual.',
                                      session, reason_codes=(reason,))
            else:
                session = replace(session, current_symptoms=(self.descriptors[sid]['rid'],))
                decision = c.eligible(session, sid)
                if r.step(sid).kind == 'SAFETY_STOP' and decision.eligibility_status == Truth.TRUE:
                    response = c.render(session, sid, safety=True)
                elif decision.eligibility_status == Truth.TRUE:
                    try:
                        bundle = self.retriever.search(query, dependency_manifest=r.retrieval_manifest(sid),
                            step_id=sid, applicability_status='CONFIRMED', scope=self.scope())
                        response = c.render(session, sid, bundle)
                    except Exception:
                        response = c.response('SYSTEM_ERROR', 'I am temporarily unable to verify the manual evidence.',
                                              session, reason_codes=('QUESTION_RETRIEVAL_FAILURE',))
                    if response.type == ResponseType.SUPPORTED and r.step(sid).kind == 'ACTION':
                        session = append_attempt(session, sid, Outcome.NOT_TRIED, 'issued:'+response.trace_id)
                        session = replace(session, pending_step_id=sid)
                else:
                    response = c.response('UNSUPPORTED', 'I could not verify an applicable supported answer to this question.',
                                          session, reason_codes=decision.reason_codes)
                    # One source-authored condition question is allowed, but no
                    # automatic symptom branch, inferred observation or wizard.
                    if decision.eligibility_status == Truth.UNKNOWN:
                        for result in decision.condition_results:
                            rule = r.rule(result['rule_id'])
                            if (result['result']=='UNKNOWN' and rule.rider_resolvable and
                                    rule.clarification_question and
                                    all(r.evidence_ready(e) for e in rule.clarification_evidence_ids)):
                                session = replace(session, pending_step_id=sid, pending_rule_id=rule.rule_id)
                                response = c.response('AMBIGUOUS', rule.clarification_question, session,
                                    clarification_question=rule.clarification_question,
                                    reason_codes=('UNKNOWN_OBSERVATION',))
                                break
        view, choices = saved_view(r, session, response)
        view['question_policy'] = VERSION
        return session, view, choices
