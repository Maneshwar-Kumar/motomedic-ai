"""Fictional protocol tests, never approval or real-manual answer correctness."""
from dataclasses import replace
import unittest
from controller_contracts import Fact, Outcome, ResponseType
from reviewed_controller import append_attempt, start_session
from test_reviewed_controller import fixture, approve_all
from human_review.grounding_refinement.controller_candidate import ControllerCandidate, IssueController, IssueState

class CandidateTests(unittest.TestCase):
    def test_owner_selection_question_omits_rider_edition(self):
        c,s=fixture()
        c.registry.source['applicability_policy']={'version':'owner-himalayan-bs6-v1','rider_edition_selection_required':False}
        approve_all(c.registry)
        s=start_session(c.registry,['synthetic'])
        _,before,_=c.next(s,'test')
        proposed=ControllerCandidate(c.registry,c.retriever,c.verifier)
        _,after,_=proposed.next(s,'test')
        self.assertIn('manual edition',before.clarification_question)
        self.assertEqual(after.clarification_question,'Is your motorcycle a Himalayan BS6?')
        self.assertEqual(after.type,ResponseType.AMBIGUOUS)

    def test_resolution_preserves_other_issue_and_history(self):
        c,s=fixture()
        selected=append_attempt(s,'s1',Outcome.RESOLVED,'reported-fixed')
        other=replace(s,session_id='other-session',current_symptoms=('another-issue',))
        state=IssueState((('first',selected),('second',other)),'first')
        state,response=IssueController(c).next(state,'test')
        self.assertEqual(response.session_status,'OTHER_ISSUES_OPEN')
        self.assertEqual(state.session('second'),other)
        self.assertEqual(state.session().attempted_steps,selected.attempted_steps)
        self.assertIn('Other reported symptoms remain open',response.natural_language)

    def test_recurrence_same_symptom_reopens_without_repeat(self):
        c,s=fixture()
        s=append_attempt(s,'s1',Outcome.RESOLVED,'fixed')
        state=IssueState((('first',s),),'first')
        engine=IssueController(c)
        state=engine.reopen(state,'first',s.current_symptoms)
        self.assertEqual(state.session().status,'OPEN')
        self.assertEqual(state.session().attempted_steps,s.attempted_steps)
        self.assertIn('ALREADY_ATTEMPTED',c.eligible(state.session(),'s1').reason_codes)

    def test_unresolved_never_produces_normal_in_either_issue(self):
        c,s=fixture()
        s=append_attempt(s,'s1',Outcome.ACTION_COMPLETED_UNRESOLVED,'unresolved')
        state=IssueState((('first',s),('second',replace(s,session_id='other'))),'first')
        state,_=IssueController(c).next(state,'test')
        self.assertEqual(state.session().known_observations(),{})
        self.assertEqual(state.session('second').known_observations(),{})

    def test_actual_source_gate_not_relaxed(self):
        c,s=fixture(approve=False)
        proposed=ControllerCandidate(c.registry,c.retriever,c.verifier)
        state=IssueState((('first',s),),'first')
        _,response=IssueController(proposed).next(state,'test')
        self.assertEqual(response.type,ResponseType.UNSUPPORTED)
        self.assertFalse(response.claim_evidence_map)

    def test_other_issue_verified_stop_precedes_resolved_issue_and_outage(self):
        c,s=fixture()
        c.registry.candidate['steps']['s1'].update(kind='SAFETY_STOP', applicability_rule_ids=[],
            claims=[{'claim_id':'stop','text':'Synthetic warning.','evidence_ids':['warning'],'verbatim_warning':True}])
        approve_all(c.registry)
        s=start_session(c.registry,['synthetic'],'test-variant','test-edition')
        resolved=replace(append_attempt(s,'s2',Outcome.RESOLVED,'fixed'),session_id='resolved',current_symptoms=('other',))
        state=IssueState((('first',resolved),('second',s)),'first')
        _,response=IssueController(c).next(state,'test',system_failure=True)
        self.assertEqual(response.type,ResponseType.SAFETY_STOP)
        self.assertEqual(response.natural_language,'Synthetic warning.')
        self.assertEqual(c.retriever.model.calls,0)

    def test_unknown_or_unreviewed_other_issue_cannot_stop(self):
        c,s=fixture(approve=False)
        c.registry.candidate['steps']['s1']['kind']='SAFETY_STOP'
        resolved=replace(append_attempt(s,'s2',Outcome.RESOLVED,'fixed'),session_id='resolved')
        state=IssueState((('first',resolved),('second',s)),'first')
        _,response=IssueController(c).next(state,'test')
        self.assertNotEqual(response.type,ResponseType.SAFETY_STOP)
        self.assertFalse(response.claim_evidence_map)

    def test_duplicate_unknown_or_stale_issue_state_is_rejected(self):
        _,s=fixture()
        for issues,selected,version in [((('a',s),('a',s)),'a','isolated-issue-controller-v1'),
                                        ((('a',s),),'unknown','isolated-issue-controller-v1'),
                                        ((('a',s),),'a','old-policy')]:
            with self.assertRaises(ValueError):IssueState(issues,selected,version)

if __name__=='__main__':
    unittest.main()
