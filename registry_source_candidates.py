"""Agent-authored draft span proposals from inspected original PDF pages.

These role/claim/dependency proposals are not independent review and stay blocked.
No semantic graph edges or OEM diagnostic ordering are inferred.
"""

def refine(c, evidence):
    def eid(prefix):
        matches=[key for key in evidence if key.startswith('evidence_'+prefix)]
        if len(matches)!=1: raise ValueError('Source evidence prefix is not unique: '+prefix)
        return matches[0]
    table121=eid('15e1ce'); table122=eid('3ab349'); intro=eid('724d49')
    for rid, rule in c['rules'].items():
        table=table122 if rid in ('rule_q_side_stand_indicator','rule_q_engine_hot') else table121
        rule['source_evidence_ids']=[table]
        rule['clarification_evidence_ids']=[table]
        rule['authorship_note']='Predicate/question proposed against original troubleshooting observation cell; independent review required.'
    def ids(prefixes): return [eid(p) for p in prefixes]
    fuse_warnings=ids(['4e1a61','00497a','0c58e6','8b5ef0'])
    fuel_warnings=ids(['c4b345','2a4402','fd5a91','b57860','ff04ce','59184c','4e632b','5034a9','a66e86','b02f38','3b85a6','430d1f'])
    definitions={
      'a_switches_on': {'actions':[table121,eid('001335')], 'conditions':[table121],
                       'prerequisites':ids(['f4dbcf','017a78','a7a5ea']), 'warnings':ids(['533bb7']),
                       'starting_limits':ids(['b4e9c2','1b6ac2']), 'cross_references':[intro]},
      'a_refuel': {'actions':[table121,eid('272bd8')], 'conditions':[table121], 'warnings':fuel_warnings,
                   'cap_operation':ids(['acf750','90eff9','99063a','a50914']),
                   'figures':ids(['45666c','2609f2']), 'figure_labels':ids(['652701','95ed4d','323bca']), 'cross_references':[intro]},
      'a_fuse': {'actions':[table121,eid('8b5ef0')], 'conditions':[table121], 'warnings':fuse_warnings,
                 'prerequisites':ids(['590e77']), 'tables':ids(['90b50d']), 'cross_references':[intro]},
      'a_reconnect': {'actions':[table121], 'conditions':[table121], 'cross_references':[intro]},
      'a_raise_stand': {'actions':[table122,eid('a7a5ea')], 'conditions':[table122], 'cross_references':[intro]},
      'a_cool_engine': {'actions':[table122], 'conditions':[table122], 'cross_references':[intro]},
      'lookup_oil_grade': {'actions':ids(['a6950e']), 'tables':ids(['a6950e']), 'warnings':ids(['37c6c3']),
                           'table_context':ids(['36ee91','8b9b87','424971'])},
      'lookup_tyre_pressure': {'actions':ids(['f1b023']), 'tables':ids(['f1b023']),
                               'warnings':ids(['c762ef','f3dd00','cb7062']), 'context':ids(['114a6d'])},
      'lookup_fan_fuse': {'actions':ids(['90b50d']), 'tables':ids(['90b50d']), 'warnings':fuse_warnings,
                          'prerequisites':ids(['590e77'])},
      'lookup_starter_duration': {'actions':ids(['b4e9c2','1b6ac2']), 'warnings':ids(['533bb7']),
                                  'prerequisites':ids(['f4dbcf','017a78','a7a5ea'])},
      'lookup_usb_charging': {'actions':ids(['13dac6']), 'warnings':ids(['b345d2','ea69e5','a35159']),
                              'context':ids(['82764f','3f0254','662d4a'])}}
    for sid,categories in definitions.items():
        step,dep=c['steps'][sid],c['dependencies'][sid]
        required=sorted({x for values in categories.values() for x in values})
        step['action_evidence_ids']=categories['actions']
        step['required_evidence_ids']=required
        step['draft_pdf_pages']=sorted({p['page_no'] for x in required for p in evidence[x]['provenance']})
        step['authoring_required']=['Independent original-page claim and scope review','Confirm mandatory prerequisites and safety rules','Review table/figure spans and stopping conditions']
        step['source_span_proposal']=[{'evidence_id':x,'role':role,'provenance':evidence[x]['provenance']}
                                      for role,values in categories.items() for x in values]
        step['claims'][0]['evidence_ids']=categories['actions']
        for n,x in enumerate(dict.fromkeys(categories.get('warnings',[])+categories.get('prerequisites',[]))):
            step['claims'].append({'claim_id':sid+':context:'+str(n),
                                   'text':evidence[x]['raw_object']['text'], 'evidence_ids':[x],
                                   'verbatim_warning':True,'presentation_mode':'ENGINEERING_SOURCE_EXCERPT',
                                   'authoring_note':'Replace with a source-reviewed paraphrase for end-user output.'})
        step['claims'][0]['presentation_mode']='DRAFT_PARAPHRASE'
        dep.update(action_evidence_ids=categories['actions'],required_evidence_ids=required,categories=categories,
                   scope_review_complete=False,
                   authorship_note='Concrete proposed dependencies from agent visual source inspection; scope still requires independent review.')
        if step['parent_procedure_id']:
            c['procedures'][step['parent_procedure_id']].update(evidence_ids=required,boundaries_checked=False,
                source_span_proposal=step['source_span_proposal'],
                authorship_note='Candidate owner-manual check boundaries, not an OEM-ranked decision tree.')
    def prerequisite(sid, name, prefix, question):
        rid='rule_'+name
        x=eid(prefix)
        c['rules'][rid]=dict(rule_id=rid,predicate_type='BOOLEAN',fact_key=name,operator='EQ',expected_value=True,
                             unit=None,origin='MANUAL',source_evidence_ids=[x],policy_version=None,
                             clarification_evidence_ids=[x],review_status='DRAFT',rule_version='rules-v1',
                             clarification_question=question,rider_resolvable=True)
        c['steps'][sid]['applicability_rule_ids'].append(rid)
    for name,prefix,q in [('gear_neutral','f4dbcf','Is the gear in neutral with the neutral lamp glowing?'),
                           ('clutch_held','017a78','Is the clutch lever held in its depressed position?'),
                           ('stand_retracted','a7a5ea','Is the side stand retracted?')]:
        prerequisite('a_switches_on',name,prefix,q)
    for name,prefix,q in [('engine_off','b57860','Is the engine turned off?'),
                          ('fuel_area_ventilated','b57860','Is the refuelling area well ventilated?'),
                          ('no_smoke_flame_sparks','fd5a91','Is the area free of smoking, open flames and sparks?'),
                          ('handheld_devices_off','2a4402','Are mobile phones and handheld electronic devices switched off?')]:
        prerequisite('a_refuel',name,prefix,q)
    prerequisite('a_fuse','ignition_off','590e77','Is the ignition switch off?')
    c['steps']['a_fuse']['unresolved_route']='ESCALATE'
    c['steps']['a_fuse']['unresolved_evidence_ids']=[table121]
    c['review_findings']=[{'finding_id':'FUSE_UNRESOLVED_ROUTE','original_pdf_page':121,
                           'evidence_id':table121,'status':'AGENT_CHECKED_REQUIRES_INDEPENDENT_REVIEW',
                           'finding':'Fuse row explicitly sends persistent problems to authorised service. Legacy D024/D035 continue to connection checks; this draft conflict must be adjudicated. Reviewed controller honors an approved ESCALATE stopping condition.',
                           'affected_legacy_cases':['D024','D035'],'release_approved':False}]
    c['version']='candidate-steps-v2'
    return c
