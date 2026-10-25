"""Build the scoped v2 source-structure proposal from immutable index objects (revision 2).

Decisions (components, exclusions, links, mandatory displays, review notes) are
the reviewer's judgement after original-page visual review, revised for the
independent review findings F1-F15 (review_round1_findings.json). This script
only binds them to exact immutable objects and hashes. It grants no action,
diagnosis, OEM-sequence or parent-text authority and changes no existing approval.

Usage (from the project root): python reports/grounded_generation/structural_review_v2/build_proposal.py
"""
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from evidence_registry import content_hash  # noqa: E402

INDEX = ROOT / 'build/index-bge-final'
OUT = Path(__file__).resolve().parent / 'proposal.json'
MANUAL = 'cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89'
INDEX_ID = 'index_a3282c4d98cf54595e4ba168'
AUTHORITY = 'OEM_MANUAL_AGENT_READ_ONLY_V2'
OPS, MMT = 'OPERATION OF CONTROLS', 'MINOR MAINTENANCE TIPS'
BATTERY = [MMT, 'BATTERY AND MAINTENANCE']

# Each display: (evidence suffixes, role, reviewed paraphrase). Evidence may be a member or a linked external.
COMPONENTS = {
    'LUGGAGE_AND_ACCESSORY_LOADING': {
        'parents': {'section_e94f77a5': ['ACCESSORIES AND LUGGAGE'],                      # F2: p14 body
                    'section_564cd294': ['ACCESSORIES AND LUGGAGE', 'WARNING'],
                    'section_3c2e48e8': ['ACCESSORIES AND LUGGAGE', 'LUGGAGE CATEGORIES']},
        'display': [
            (['41ddc000'], 'WARNING', 'Do not exceed 110 km/h when riding solo, carrying a pillion or payload on an accessory-equipped motorcycle.'),
            (['b45cd327'], 'WARNING', "Do not load weight or install accessories incorrectly; doing so may affect the motorcycle's stability, handling characteristics and safe operation and could result in an accident causing serious injury or loss of life."),
            (['a4bb14d7', '32a2dfb5'], 'WARNING', 'Royal Enfield cautions you against use of non-standard parts such as aftermarket and custom-made extended front forks, which may adversely affect performance and handling. Removing or altering original parts may adversely affect the performance of the motorcycle, causing an accident, which could result in serious injury or loss of life.'),  # F3
            (['bbf3e2f0'], 'WARNING', 'Do not ignore model/design specifications; doing so constitutes motorcycle and accessories misuse, which may adversely affect handling and performance, causing an accident which could result in serious injury or loss of life.'),  # F4
        ],
        'notes': {'ca7dffc6': 'Unlinked external reference: the maximum pannier/top-box payload is defined in the GMA fitting instructions, which are not part of this manual and give no value here.'},  # F14
    },
    'RE_APP_PHONE_COMPATIBILITY': {
        'parents': {'section_038b8464': [OPS, 'Smartphones compatible version to use RE Mobile app'],
                    'section_4c05e0fe': [OPS, 'Smartphones compatible version to use RE Mobile app', 'NOTE']},
        'display': [],
    },
    'DISPLAY_LANGUAGE_MENU': {
        'parents': {'section_00e75771': [OPS, '4. SYSTEM', 'v. Language'],               # F10
                    'section_eb9d4abf': [OPS, '4. SYSTEM', 'v. Language']},
        'exclude': {'01e2246c': 'FIGURE_LABEL_TEXT_ARTIFACT: lone "0" from a cropped speedometer in the page-51 dashboard illustration; not manual prose',
                    '97dc90ba': 'FIGURE_LABEL_TEXT_ARTIFACT: lone "0" from a cropped speedometer in the page-51 dashboard illustration; not manual prose'},
        'display': [],
    },
    'COMPASS_NAVIGATION_NOTE': {
        'parents': {'section_65601974': [OPS, '6. FAVORITES', 'v. Compass', 'NOTE']},     # F10
        'external': ['0e636256'],                                                          # F11
        'display': [],
    },
    'TELL_TALE_INDICATORS': {
        'parents': {'section_bd4e814dc': [OPS, 'TELL TALES'],                             # F10
                    'section_dc5e0e70': [OPS, 'TELL TALES', 'NOTE'],
                    'section_6a192547': [OPS, 'TELL TALES', 'CAUTION']},
        'display': [
            (['aef43455'], 'WARNING', 'Do not run the motorcycle if the malfunction indication remains ON continuously, as it can cause severe damage to the ECU and sensors; visit the nearest authorised Royal Enfield dealer to diagnose and rectify the EMS defect.'),
            (['bc21f201', 'd867f6c7'], 'WARNING', 'The ABS indicator is ON during the initial check-up (until or after the vehicle has run a particular distance/speed) and turns OFF if the system is OK; it lights up again in case of any ABS system malfunction. Do not run the motorcycle if the ABS indicator lamp remains continuously ON.'),  # R2-N1/N8: page-62 evidence only
        ],
        'notes': {'d1dbf489': 'Page 62 says tell-tale lights switch OFF after the engine is started, while item (3) says the ABS lamp is ON during the initial check-up. The separate ABS INDICATOR LAMP section (page 63, not linked here) states the ABS lamp stays ON until 5 km/h and the caution applies when it stays ON continuously above 5 km/h.'},
    },
    'BATTERY_HANDLING_NOTES': {
        'parents': {'section_706883ce': BATTERY + ['DISMANTLING', 'NOTE'],               # F10
                    'section_42dd9f913': BATTERY + ['DISMANTLING', 'WARNING'],            # F7
                    'section_24cb80bc': BATTERY + ['NOTE'],                               # F7
                    'section_8a2de6af': BATTERY + ['ASSEMBLY', 'CAUTION'],               # F7
                    'section_1702f591': BATTERY + ['ASSEMBLY', 'NOTE']},
        'display': [
            (['7c9ae62e'], 'WARNING', 'Always disconnect the black negative (-ve) battery cable first and then the red positive (+ve) cable when removing the battery connections.'),
            (['fd9b2d78'], 'WARNING', 'Caution: when connecting the battery, connect the red positive (+ve) terminal first and then the black negative (-ve) terminal.'),
            (['1ef48d8f'], 'WARNING', 'Caution: keep both battery terminal cables firmly connected to their terminals; failure to do so may damage the motorcycle electrical system.'),
            (['e56e7474'], 'WARNING', 'Note: poor contact or loose fitment of the battery terminals may cause ECU failure.'),
        ],
    },
    'HEADLIGHT_BEAM_ADJUSTMENT': {
        'parents': {'section_449dd82a': [MMT, 'HEAD LIGHT BEAM ADJUSTMENT']},
        'display': [],
        'notes': {'d8072550': 'The text does not say which turning direction raises or lowers the beam; the adjusting-screw location is shown only in the page figure.',  # F12
                  '4c953cab': 'Printed wording is kept verbatim, including the unclear phrase "help prevent the other riders/vehicles passing nearby".'},
    },
    'TAIL_AND_LICENSE_PLATE_LAMP': {
        'parents': {'section_a36b268b': [MMT, 'TAIL LAMP/TRAFFICATOR & LICENSE PLATE ILLUMINATOR']},
        'display': [],
    },
    'BRAKE_PAD_WEAR_CHECK': {
        'parents': {'section_51e7cccd': [MMT, 'BRAKE PADS'],
                    'section_3468a439': [MMT, 'BRAKE PADS'],                              # F6: p91 criterion
                    'section_b019c7b8': [MMT, 'BRAKE PADS', 'NOTE']},                     # F6: p91 NOTE
        'display': [],
        'notes': {'9d8a9d4e': 'Check intervals are in the periodic maintenance chart, which is outside this scope and not linked. The page-91 replacement criterion is printed as "warm to the indicator"; that wording is unclear and is kept verbatim. The page-91 NOTE that mild disc-brake noise is normal does not establish that the pads are not worn.'},
    },
    'REAR_SUSPENSION_PRELOAD': {
        'parents': {'section_fae5accf2': ['REAR SUSPENSION SETTING'],
                    'section_390d8440': ['REAR SUSPENSION SETTING', 'NOTE'],
                    'section_22b83cdc': ['REAR SUSPENSION SETTING']},                     # F10: no invented label
        'display': [
            (['fb5ddc13'], 'FACT', 'In the rear-suspension setting table, tyre pressure is printed as one merged cell reading 32 psi that spans Front and Rear for both the rider-only and the laden rows.'),  # F1
        ],
        'notes': {'fb5ddc13': 'Parser loss: the printed merged 32 psi cell was stored only in the first Front cell; the reviewed FACT display records the printed cell. Suspension notches (3rd rider-only, 6th laden) are intact.',
                  '2be6f399': 'Page 116 says the six-step adjuster "is kept at first notch position"; the page 117 table lists 3rd notch for rider-only and 6th for laden use. Both statements are retained, unreconciled.'},  # F13
    },
    'STORAGE_PRECAUTIONS': {
        'parents': {'section_19373e580b': ['STORAGE PRECAUTIONS']},
        'external': ['7c9ae62e', 'fd9b2d78', '1ef48d8f'],                                  # F7 battery (closure 7, clean)
        'display': [],
        'notes': {'66858581': "The manual's fuel-handling warnings (page 8: no smoking, open flames or sparks when refuelling or servicing the fuel system; page 27: gasoline vapour is highly explosive, fill only in a well-ventilated area) apply to draining fuel but are not linked here, because their existing dependency closure would add unrelated warnings."},
    },
    'LUBRICANT_TABLE_FOOTNOTE': {
        'parents': {},
        'unparented': {'36ee9102': ['RECOMMENDED LUBRICANTS', 'FOOTNOTE']},  # F9, R2-N4
        'display': [],
        'display_omitted_reason': 'The footnote qualifies only the DOT 4 brake-fluid cell; a mandatory display would append it to every lubricant answer (engine oil, coolant, fork oil). It stays in reviewed context.',
    },
}
EVIDENCE_DEPENDENCIES = {
    'a6950ea7': {'targets': ['424971c8f0be958200b09990', '8b9b87ad8adcc025075370ea', '3a4f927af191ec4ce7915444', '36ee9102'],
                 'relationship': 'LUBRICANT_TABLE_HAS_NUMBERED_NOTES_AND_FOOTNOTE',
                 'reason': 'Page 21: NOTE items 1-3 sit directly under the RECOMMENDED LUBRICANTS table (item 3: "The above values are approximate and the actual capacity will vary."); the "* Do not mix DOT 4 or other brake fluid together" footnote is referenced by the table\'s "DOT 4*" cell.'},
}
PRINTED = {14: '12', 15: '13', 21: '19', 50: '48', 51: '49', 54: '52', 57: '55', 62: '60', 63: '61', 90: '88',
           91: '89', 104: '102', 105: '103', 107: '105', 109: '107', 110: '108', 116: '114', 117: '115', 120: '118',
           8: '6', 20: '18', 27: '25'}
CHECKS = {'original_page_visual_review': True, 'all_children_individually_source_reviewed': True,
          'table_headers_units_and_notes_preserved': True, 'warning_and_note_boundaries_checked': True,
          'no_positive_procedure_authority': True}


def lines(name):
    return {json.loads(l)['id']: json.loads(l) for l in (INDEX / name).open(encoding='utf-8')}


def raw(obj):
    r = obj['raw_object']
    return json.loads(r) if isinstance(r, str) else r


def exact_text(obj):
    r = raw(obj)
    if obj['type'] == 'table':
        cells = r.get('data', {}).get('table_cells', [])
        return '\n'.join(f"r{c['start_row_offset_idx']}c{c['start_col_offset_idx']}: {c['text']}" for c in cells)
    return r.get('text') or r.get('orig') or ''


def one(suffix, ids):
    suffix = suffix.split('_', 1)[-1]
    match = [i for i in ids if suffix in i.split('_', 1)[-1]]  # unique hex fragment of the ID
    if len(match) != 1:
        raise SystemExit(f'cannot resolve {suffix}: {match}')
    return match[0]


def pages_of(evidence, ids):
    return sorted({p['page_no'] for e in ids for p in evidence[e]['provenance']})


def source_row(evidence, eid, path, parent_ids, note):
    obj = evidence[eid]
    context = {'section_path': path, 'parent_section_ids': parent_ids, 'parent_text_authorized': False,
               'review_status': 'APPROVED_AGENT_READ_ONLY_CONTEXT_V2', **({'review_note': note} if note else {})}
    so = {'authority': AUTHORITY, 'evidence_id': eid, 'manual_sha256': MANUAL, 'index_id': INDEX_ID,
          'object_type': obj['type'], 'exact_text': exact_text(obj), 'provenance': obj['provenance'],
          'raw_object_sha256': content_hash(obj['raw_object']), 'review_status': 'APPROVED_AGENT_READ_ONLY_FACTS_ONLY',
          'context_sha256': content_hash(context), 'requires_visual_verification': False, 'index_membership': True}
    return {'raw_object_sha256': content_hash(obj['raw_object']), 'provenance_sha256': content_hash(obj['provenance']),
            'source_object': so, 'source_object_sha256': content_hash(so), 'context': context,
            'context_sha256': content_hash(context)}


def main():
    manifest = json.loads((INDEX / 'manifest.json').read_text(encoding='utf-8'))
    parents, evidence = lines('parents.jsonl'), lines('evidence.jsonl')
    parented = {e for p in parents.values() for e in p['evidence_ids']}
    source_objects, parent_rows, components, unparented_rows = {}, {}, {}, {}
    for name, comp in COMPONENTS.items():
        pmap = {one(s, parents): path for s, path in comp['parents'].items()}
        children = [e for pid in pmap for e in parents[pid]['evidence_ids']]
        excluded = {one(s, children): reason for s, reason in comp.get('exclude', {}).items()}
        loose = {one(s, evidence): path for s, path in comp.get('unparented', {}).items()}
        if set(loose) & parented:
            raise SystemExit(f'{name}: unparented object has a parent')
        members = sorted({e for e in children if e not in excluded} | set(loose))
        external = sorted(one(s, evidence) for s in comp.get('external', ()))
        if any(evidence[e]['type'] in ('picture', 'figure', 'image') for e in members):
            raise SystemExit(f'{name}: figure object cannot be approved here')
        notes = {one(s, members): text for s, text in comp.get('notes', {}).items()}
        display = []
        for i, (suffixes, role, text) in enumerate(comp['display']):
            ids = [one(s, members + external) for s in suffixes]
            display.append({'claim_id': f'structural-v2-{name.lower()}-{i + 1}', 'text': text, 'response_role': role,
                            'evidence_ids': ids, 'presentation_mode': 'REVIEWED_PARAPHRASE'})
        components[name] = {'parent_section_ids': sorted(pmap), 'unparented_evidence_ids': sorted(loose),
                            'required_evidence_ids': members, 'external_dependency_evidence_ids': external,
                            'excluded_evidence_ids': excluded, 'mandatory_display': display,
                            'source_pages': pages_of(evidence, members), 'external_pages': pages_of(evidence, external),
                            **({'display_omitted_reason': comp['display_omitted_reason']} if 'display_omitted_reason' in comp else {})}
        for pid, path in pmap.items():
            approved = sorted(e for e in parents[pid]['evidence_ids'] if e not in excluded)
            parent_rows[pid] = {'component': name, 'parent_object_sha256': content_hash(parents[pid]),
                'approved_evidence_ids': approved,
                'excluded_evidence_ids': {e: r for e, r in excluded.items() if e in parents[pid]['evidence_ids']},
                'section_path': path, 'review_status': 'APPROVED_EXACT_CHILD_STRUCTURE_V2',
                'parent_text_authorized': False, 'source_pages': pages_of(evidence, approved), 'checks': CHECKS}
            for eid in approved:
                source_objects[eid] = source_row(evidence, eid, path, [pid], notes.get(eid))
        for eid, path in loose.items():
            unparented_rows[eid] = {'component': name, 'section_path': path,
                                    'review_status': 'APPROVED_EXACT_UNPARENTED_NOTE_CONTEXT_V2',
                                    'source_pages': pages_of(evidence, [eid]), 'checks': CHECKS}
            source_objects[eid] = source_row(evidence, eid, path, [], notes.get(eid))
    deps = {}
    for suffix, row in EVIDENCE_DEPENDENCIES.items():
        eid = one(suffix, evidence)
        targets = [one(t, evidence) for t in row['targets']]
        deps[eid] = {'external_dependency_evidence_ids': targets, 'relationship': row['relationship'],
                     'source_pages': pages_of(evidence, [eid] + targets), 'reason': row['reason'],
                     'review_status': 'APPROVED_SAME_COMPONENT_LIMITATIONS', 'action_authority': False,
                     'oem_sequence_authority': False}
    all_pages = sorted({p for c in components.values() for p in c['source_pages'] + c['external_pages']}
                       | {p for d in deps.values() for p in d['source_pages']})
    proposal = {'version': 'scoped-source-structure-proposal-v2', 'revision': 4,
        'manual_checksum': MANUAL, 'index_id': INDEX_ID,
        'immutable_parents_sha256': manifest['file_checksums']['parents.jsonl'],
        'immutable_evidence_sha256': manifest['file_checksums']['evidence.jsonl'],
        'authority_requested': 'OWNER_DELEGATED_INDEPENDENT_AGENT_SOURCE_STRUCTURE',
        'proposer': 'claude-code-session-20261023', 'human_signoff': False,
        'parent_text_authorized': False, 'action_authority': False, 'diagnosis_authority': False,
        'oem_sequence_authority': False, 'questions_or_expected_answers_included': False,
        'existing_approvals_changed': False,
        'scope_reason': 'Sections containing manual evidence cited by approved 161-package cases that the v10.14 serving gate could not admit (local stage replay reports/answer_quality/20261023_stage_replay_v1), plus the warning/note/caution context the independent review required.',
        'round1_findings_addressed': ['F%d' % i for i in range(1, 16)],
        'round2_findings_addressed': ['R2-N%d' % i for i in range(1, 9)],
        'round3_findings_addressed': ['R3-N1', 'R3-N2'],
        'residual_limitations': [
            'R2-N2: fuel no-flame/no-spark warnings for draining fuel are carried as a review_note, not a mandatory display, because linking those objects pulls their broad v4 closure (fuse, starter, troubleshooting warnings) into storage answers.',
            'R2-N7: evidence_1fd98dd6 and evidence_408acecc keep their earlier exact bindings and contexts (v2 never rebinds an existing approval); the BRAKE PADS path and wording notes reach the model through evidence_9d8a9d4e.',
            'R2-N3: the merged-cell FACT display has not been exercised by the hosted verifier; a verifier rejection would fail closed.'],
        'original_pdf_pages': all_pages, 'printed_page_labels': {str(p): PRINTED[p] for p in all_pages},
        'components': components, 'parents': parent_rows, 'unparented': unparented_rows,
        'source_objects': source_objects, 'evidence_dependencies': deps}
    OUT.write_text(json.dumps(proposal, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    print('components', len(components), 'parents', len(parent_rows), 'unparented', len(unparented_rows),
          'source objects', len(source_objects), 'pages', all_pages,
          'sha256', hashlib.sha256(OUT.read_bytes()).hexdigest())


if __name__ == '__main__':
    main()
