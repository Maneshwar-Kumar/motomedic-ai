"""Unresolved feedback is not observation or adaptive source authority."""
from dataclasses import replace
from pathlib import Path
import os
import unittest
from approved_registry import ApprovedEvidenceRegistry
from constrained_generator import ValidationFailure
from controller_contracts import Fact, Outcome, StepDefinition
from reviewed_controller import append_attempt, start_session, update_symptoms
from cloud.grounded_generation.transitions import exhausted_after_unresolved


def step(sid='action', **changes):
    base=StepDefinition(sid,'sha',('e',),'procedure',('symptom',),(),('e','edge'),
                        'dep','APPROVED','rule',unresolved_route='CONTINUE_DOCUMENTED')
    return replace(base, **changes)


class Registry:
    terminal_initial_scope_only=True
    checksum='sha';lock='lock';source={'manual_id':'manual'}
    def __init__(self):
        self.steps={'action':step(),'other_initial':step('other_initial')}
        self.source_ok=True;self.not_ready=set();self.bad_evidence=set()
    def source_ready(self):return self.source_ok
    def step(self,sid):return self.steps[sid]
    def step_ready(self,sid):return sid not in self.not_ready
    def evidence_ready(self,eid):return eid not in self.bad_evidence


class Tests(unittest.TestCase):
    def setUp(self):
        self.r=Registry();self.s=start_session(self.r,['symptom'],'variant','edition')
    def unresolved(self):
        return append_attempt(self.s,'action',Outcome.ACTION_COMPLETED_UNRESOLVED,'action-feedback')
    def test_no_unresolved_feedback_has_no_guard_effect(self):
        self.assertFalse(exhausted_after_unresolved(self.r,self.s))
    def test_unresolved_is_not_normal_and_other_initial_scope_cannot_escape(self):
        s=self.unresolved()
        self.assertEqual(s.known_observations(),{})
        self.assertTrue(exhausted_after_unresolved(self.r,s))
        self.assertEqual(s.active_attempts()[0].outcome_enum,Outcome.ACTION_COMPLETED_UNRESOLVED)
    def test_observation_correction_and_symptom_revision_do_not_grant_transition(self):
        s=self.unresolved()
        s=append_attempt(s,'action',Outcome.OBSERVED_ABNORMAL,'obs',condition_id='r',facts=(('x',Fact(False,'BOOLEAN')),))
        s=append_attempt(s,'action',Outcome.OBSERVED_NORMAL,'correct',condition_id='r',facts=(('x',Fact(True,'BOOLEAN')),),supersedes=s.active_attempts()[-1].attempt_id)
        self.assertTrue(exhausted_after_unresolved(self.r,update_symptoms(s,['new-symptom'])))
    def test_superseding_unresolved_with_unclear_does_not_grant_scope(self):
        s=self.unresolved()
        s=append_attempt(s,'action',Outcome.UNCLEAR,'correction',supersedes=s.active_attempts()[0].attempt_id)
        self.assertTrue(exhausted_after_unresolved(self.r,s))
    def test_unresolved_cannot_smuggle_observation_or_condition(self):
        s=self.unresolved();a=s.attempted_steps[0]
        for change in ({'condition_id':'r'},{'observed_details':(('x',Fact(True,'BOOLEAN')),)}):
            with self.subTest(change=change),self.assertRaisesRegex(ValidationFailure,'STEP_BINDING'):
                exhausted_after_unresolved(self.r,replace(s,attempted_steps=(replace(a,**change),)))
    def test_source_and_session_binding_fail_as_integrity(self):
        for field,value in [('version_lock','stale'),('manual_checksum','stale'),('manual_id','stale')]:
            with self.subTest(field=field),self.assertRaisesRegex(ValidationFailure,'SOURCE_BINDING'):
                exhausted_after_unresolved(self.r,replace(self.unresolved(),**{field:value}))
        self.r.source_ok=False
        with self.assertRaisesRegex(ValidationFailure,'SOURCE_BINDING'):exhausted_after_unresolved(self.r,self.unresolved())
    def test_missing_unready_wrong_kind_prior_or_unresolved_facts_are_integrity(self):
        s=self.unresolved();self.r.not_ready.add('action')
        with self.assertRaisesRegex(ValidationFailure,'STEP_BINDING'):exhausted_after_unresolved(self.r,s)
        self.r.not_ready.clear();self.r.steps['action']=step(kind='LOOKUP')
        with self.assertRaisesRegex(ValidationFailure,'STEP_BINDING'):exhausted_after_unresolved(self.r,s)
        self.r.steps.clear()
        with self.assertRaisesRegex(ValidationFailure,'STEP_BINDING'):exhausted_after_unresolved(self.r,s)
    def test_all_active_actions_binding_checked_before_exhaustion(self):
        s=append_attempt(self.unresolved(),'missing',Outcome.ACTION_COMPLETED_UNRESOLVED,'other')
        with self.assertRaisesRegex(ValidationFailure,'STEP_BINDING'):exhausted_after_unresolved(self.r,s)
    def test_authored_next_ids_alone_cannot_expand_initial_scope(self):
        self.r.steps['action']=step(next_step_ids=('other_initial',),next_step_evidence_ids=('edge',))
        self.assertTrue(exhausted_after_unresolved(self.r,self.unresolved()))
    def allow_edge(self):
        self.r.steps['action']=step(next_step_ids=('other_initial',),next_step_evidence_ids=('edge',))
        self.r.unresolved_transition_ready=lambda prior,target: prior=='action' and target=='other_initial'
    def test_fresh_reviewed_edge_allows_controller_to_check_target(self):
        self.allow_edge();self.assertFalse(exhausted_after_unresolved(self.r,self.unresolved()))
        self.r.unresolved_transition_ready=lambda *args:False
        self.assertTrue(exhausted_after_unresolved(self.r,self.unresolved()))
    def test_repeat_or_stale_next_edge_never_proceeds(self):
        self.allow_edge();self.r.steps['action']=step(next_step_ids=('action',),next_step_evidence_ids=('edge',))
        with self.assertRaisesRegex(ValidationFailure,'EDGE_BINDING'):exhausted_after_unresolved(self.r,self.unresolved())
        self.allow_edge();self.r.not_ready.add('other_initial')
        with self.assertRaisesRegex(ValidationFailure,'EDGE_BINDING'):exhausted_after_unresolved(self.r,self.unresolved())
        self.r.not_ready.clear();self.r.bad_evidence.add('edge')
        with self.assertRaisesRegex(ValidationFailure,'EDGE_BINDING'):exhausted_after_unresolved(self.r,self.unresolved())
    def test_explicit_escalation_wins_even_with_fresh_edge(self):
        self.allow_edge();self.r.steps['action']=replace(self.r.steps['action'],unresolved_route='ESCALATE_NO_APPROVED_NEXT_STEP')
        self.assertTrue(exhausted_after_unresolved(self.r,self.unresolved()))
    def test_general_adaptive_registry_retains_ordinary_controller(self):
        self.r.terminal_initial_scope_only=False
        self.assertFalse(exhausted_after_unresolved(self.r,self.unresolved()))
    def test_real_approved_initial_action_stops_and_tamper_fails(self):
        root=Path(__file__).resolve().parents[2]
        r=ApprovedEvidenceRegistry.load(root,Path(os.environ.get('MOTOMEDIC_TEST_INDEX',str(root/'build/index-bge-final'))))
        sid=next(s for s in r.candidate['steps'] if r.step_ready(s) and r.step(s).kind=='ACTION')
        s=append_attempt(start_session(r,['symptom'],r.source['variant'],r.source['edition']),sid,Outcome.ACTION_COMPLETED_UNRESOLVED,'real-feedback')
        self.assertTrue(exhausted_after_unresolved(r,s));self.assertEqual(s.known_observations(),{})
        r.candidate['steps'][sid]['unresolved_route']='CONTINUE_DOCUMENTED'
        with self.assertRaisesRegex(ValidationFailure,'STEP_BINDING'):exhausted_after_unresolved(r,s)

if __name__=='__main__':unittest.main()