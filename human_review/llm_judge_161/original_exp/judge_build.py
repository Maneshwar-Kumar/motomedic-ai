import collections
import datetime
import hashlib
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[3]
BASE = ROOT / 'human_review' / 'llm_judge_161'
OUT = BASE / 'original_exp'
ACTOR = '/root/llm_judge_original_exp'
corpus = json.loads((BASE / 'corpus.json').read_text(encoding='utf-8'))
inputs = {r['record_id']: r for r in corpus['records']}

# These are independent LLM judgments after reading every full producer record,
# current response, owner rubric/history, and the original source page renderings.
# They are not imported verdicts from the signed source approval package.
spec = '''
lookup_oil_grade|PASS|5|NOT_APPLICABLE|PASS|PASS|21|The exact grade, API/JASO classes and semi-synthetic construction match the original lubricant table, and the caution retains the seriousness requested by the owner. This is a complete grade lookup; its stop excludes capacities, substitutes and oil-changing instructions. No diagnostic branch is needed.
lookup_tyre_pressure|PASS|4|NOT_APPLICABLE|PARTIAL|PASS|18,90|The front/rear and solo/pillion headers, both pressure units and underinflation warning are correct. The optional replacement branches correctly keep tyre construction separate from rim type and give the same documented CEAT models without inventing construction-specific variants. The initial replacement sentence remains vague and peripheral to a pressure-only query, but the authored follow-up does resolve it.
lookup_fan_fuse|PASS|5|NOT_APPLICABLE|PASS|PASS|112|F3, red, 10 A and mini-blade all agree with the original table. The initial identification answer is concise; its optional failure/replacement branch keeps ignition OFF, same rating, no conductive substitutes, spare replacement and mandatory electrical inspection even after success. This lookup does not assert a failure or give incomplete seat access.
lookup_starter_duration|PASS|4|PASS|PASS|PASS|72,73,74,75,121|The five-second maximum, roughly five-second wait, ten-volt drain caution and accepted R001 recovery after three already-made attempts are supported. The authored flow keeps setup compact, clarifies only missing facts, preserves an unresolved attempt, uses dim lights/weak horn without diagnosing battery health, and applies MIL wording only after starting. This is a sensible authored flow, not an executed adaptive transition; R002 post-start riding scope is not silently added.
lookup_usb_charging|PASS|5|PASS|PASS|PASS|65|Engine-running-only operation and the cap/warranty caution match the source. The running-engine follow-up asks about cable quality and then cap condition, keeps the >2.5 A limit conditional, and refers unresolved failure without a reset, measured-current claim, causal cap diagnosis or warranty decision. It removes the capabilities/timing material the owner rejected.
a_fuse|PASS|4|PASS|PASS|PASS|34,35,36,111,112,121|The replacement conditions, full warnings and mandatory inspection are source-supported. Authored discovery does not presume a blown fuse, uses carrier position/label rather than colour alone, and immediately refers an uncertain defective condition; failed replacement stops at service. The review judges that written flow as coherent, while schematic delivery and actual state transitions are unmeasured.
a_switches_on|PASS|3|PASS|PARTIAL|REVISE|28,72,73,74,75,121|Correcting only the reported OFF switch, separating that from cranking, and turning ignition OFF when finishing are supported. The authored identification, mismatch, unresolved and R001 branches are coherent and preserve facts. The main answer reads partly like controller instructions and refers to a compact checklist without supplying or linking its actual rider wording.
a_refuel|PARTIAL|3|PARTIAL|PARTIAL|REVISE|8,27,28,63,73,121|The fuel limit, expansion/EVAP warnings, ventilation, engine/device OFF and cap closure are supported. The main response is an incomplete practical cap-operation sequence: it tells the rider to open the cap, omits the documented flap/key/clockwise opening steps, then assumes a key in position for locking. It also duplicates the read-and-return instruction. The authored gauge-refresh/discrepancy branch is especially good and retains both observations without repeated refuelling.
a_reconnect|PASS|3|NOT_APPLICABLE|PARTIAL|REVISE|16,23,24,25,115,121,143|The audited supporting guidance supplies only a high-level spark-plug/cap/high-tension-cable remedy, so service referral is appropriate and no fitting procedure is invented. The response never names those parts for its generic no-start prompt, making the referral unclear. Its authored source-gap, attempted-unresolved and failed-fuse precedence branches are sound; this is a terminal referral rather than a missing diagnostic sequence.
a_raise_stand|PASS|4|PASS|PASS|PASS|25,58,59,74,121,122|The first-gear cut-out/indicator row and full-retraction precaution agree with the source. Authored flow separates actual stand position from the indicator, uses the correct analog/digital legends, retains a mismatch as a separate issue, avoids bypasses/repeats/road tests, and refers persistent symptoms. The actual delivery of figures and transitions has not been run.
a_cool_engine|PASS|3|PASS|PARTIAL|REVISE|37,38,121,122|Switch OFF/allow cool is the documented remedy only for the engine-too-hot condition, and the supporting pages establish no cooling time or safe restart temperature. The authored unknown and unresolved handling correctly refers service and does not infer fuel adulteration, a fan fault or room-temperature clearance. The final sentence exposes eligibility vocabulary and leaves the rider to interpret an unnamed documented condition.
EXP001|FAIL|2|FAIL|FAIL|REVISE|23,29,30|Activation states, thirty-minute continuation, battery caution and turn-signal warning are supported. The current actionable identification puts the hazard button on the left-hand control, contradicting the original key-parts diagram and control drawings, which place it on the right. This can send the rider to the wrong controls; the follow-up identification is consequently unreliable.
EXP002|PASS|4|FAIL|FAIL|REVISE|23,29,30|The initial question and simultaneous-flashing explanation are grounded and do not diagnose wiring. Its authored unsure branch repeats the same left-hand hazard-button error as EXP001. The initial response therefore passes grounding, while the full written flow fails its practical identification branch; it must be corrected before being treated as a complete rider conversation.
EXP003|PASS|5|PASS|PASS|PASS|23,31|Returning to centre alone is not portrayed as cancellation: the response correctly requires an inward push. The left/right control identification, mismatch, uncertainty and attempted-but-still-lit service branches are clear and source-bounded. It does not invent a switch repair or repeated-force loop.
EXP004|PASS|5|NOT_APPLICABLE|PASS|PASS|30|High-beam selected implies the telltale glows, exactly as stated on the source page. The optional change-beam branch retains headlamp ON and correct left-side control identification; discrepancy does not become proof of bulb health. The primary lookup is complete without a diagnostic dialogue.
EXP005|PASS|5|PASS|PASS|PASS|23,32|The Home button is on the left-hand control and goes back, as the text and rear-facing button drawing show. The identification branch deliberately avoids inventing a readable Home symbol and stops if controls differ or remain unclear. Button failure is referred rather than repaired from model knowledge.
EXP006|PASS|4|PASS|PARTIAL|PASS|32,36,39,40,41,42|Dark-theme-only brightness, menu entry, centre selection, Home navigation and right/left increase/decrease all match the source. The already-dark and failed-attempt branches preserve facts and avoid sensor diagnoses or loops. The full procedure is useful, although the stationary precaution belongs before the action and the product-policy label need not appear to the rider.
EXP007|PASS|4|PASS|PARTIAL|PASS|32,42,43|Analog-to-Digital by long press of the right Mode button is supported, and the latest response improves identification to the visible M marking. It accurately limits the unsupported reverse-long-press claim; menu selection remains a separately documented route. The writing is slightly overqualified, and internal policy wording is unnecessary, but no mechanical or flow failure is established.
EXP008|PASS|4|PASS|PARTIAL|PASS|32,36,39,43,44|The Settings/Trip Preference/Reset Trip/Trip1 sequence, separate trip choice and confirmation popup are supported by the full menu pages. The unsure branch stops before confirmation and an unresolved attempt does not cause a factory reset. Removing the product-policy aside would improve readability; the substantive action and branch flow are sound.
EXP009|PASS|5|NOT_APPLICABLE|PASS|PASS|36,37,38,39|The source says consumption/range are estimates and range updates while driven. The answer directly refuses an exact-distance guarantee; its optional stationary/low-fuel branches do not authorize a road test or promise arrival. A lookup completion is appropriate.
EXP010|PASS|5|NOT_APPLICABLE|PASS|PASS|37,38|Two completely filled battery segments correspond to the explicit 12.5 V example; half of the third corresponds to the explicit 13 V example. The response appropriately refuses to turn an illustration into battery-health or no-start diagnosis. The display-clarification and separate-no-start contexts remain bounded.
EXP011|PASS|5|PASS|PASS|PASS|58,59,63,66,67,68,69|Startup illumination until 5 km/h is separated from persistent illumination above it, with the documented service/no-riding warning and consequence. The question asks about existing history and expressly avoids a ride-to-test instruction. Unknown history and a known stop take different routes, so the authored flow is strong.
EXP012|PASS|4|NOT_APPLICABLE|PASS|PASS|66,67,68,69|The exact emergency hard-braking condition, do-not-release instruction, both-brakes guidance and relevant ABS limitations/warnings are all supported. The answer is longer because necessary safety context is retained. It does not generalize every vibration to ABS activation, and a separately persistent lamp retains its stop.
EXP013|PASS|5|NOT_APPLICABLE|PASS|PASS|68|The toner-ring damage/dent/consistent-edge observation and bent/damaged-ring dealership route match the original page. The uncertain-photo branch preserves uncertainty and does not straighten a ring, bypass ABS or diagnose a sensor. The reported existing damage can end in a service referral.
EXP014|PASS|5|NOT_APPLICABLE|PASS|PASS|68|The source mentions debris at wheel-speed-sensor ends but gives only clear suitably or dealership, not a detailed cleaning method. The response scopes the missing process honestly and chooses the documented dealership path. It does not mislabel the toner-ring image as a sensor-location guide or invent solvents, pressure or clearance.
EXP015|PASS|4|PASS|PASS|PASS|68,79,80|The reset requires an already-upright motorcycle on its centre stand, neutral and lamp, OFF/OFF, a few seconds, then ON/ON. Firm flat support and fall risk are preserved from parking context. The authored flow withholds unsafe lifting/support, does not imply an undamaged bike, does not loop resets and keeps damage concerns open after a restart; it supplies no extra cranking/riding procedure.
EXP016|PASS|5|NOT_APPLICABLE|PASS|PASS|79,80|The explicit do-not-sit warning, motorcycle-weight-only limit, stand/frame/fall risk and firm-flat support agree with the complete parking pages. The optional soft-ground and unstable/damaged-stand handling does not invent a support workaround or safe clearance. This direct safety stop needs no diagnostic branch.
EXP017|PASS|4|PASS|PASS|PASS|25,79,80|The upright firm-flat setup, straight handlebar, both stand legs, fulcrum lever/backward movement and locking warning are source-supported. The written identification and unable-to-support branches stop rather than invent lifting technique or force repetition. The fulcrum term could be more accessible, but the practical discovery context and limits are adequate.
EXP018|PASS|5|NOT_APPLICABLE|PASS|PASS|34,35,36,81|Strapped underneath the pillion seat is the exact documented location. The optional access request is correctly held for the full removal/refit procedure rather than treated as permission from one unlock instruction. The location lookup is concise and complete.
EXP019|PASS|5|NOT_APPLICABLE|PASS|PASS|81|Regular inspection and replacement upon expiry are the source facts; no shelf life, treatment or medical dosing is fabricated. The first-aid inventory does not become treatment guidance. No diagnostic flow is needed for this maintenance reminder.
EXP020|PASS|4|NOT_APPLICABLE|PARTIAL|PASS|21,72,73,74,75,83|Approximately 350 ml is the MIN-to-MAX difference under the specified check, and exceeding MAX can affect clutch function. The response correctly rejects an arbitrary fixed top-up. The optional actual-check scope retains the separate complete procedure and its explicit repeat exception; however, the first two sentences duplicate the same distinction and run words/numbers together.
EXP021|PASS|4|NOT_APPLICABLE|PARTIAL|PASS|21,83,84,85|The table distinguishes the 2.1 L service refill including filter change from 2.4 L dry fill and marks capacities approximate. The MAX/clutch caution is supported, and the authored branch keeps service filling separate from level-check timings. Internal source83 wording and missing spaces are polish issues, not wrong capacities or a disguised full oil-change procedure.
EXP022|PASS|5|NOT_APPLICABLE|PASS|PASS|21,86,87|The exact Total coolant product label, ready-to-use note and no-hot-radiator-cap/severe-burn warning are supported. The label's -37 degrees C is not presented as a safe engine temperature. Alternatives and actual filling remain separate limited scopes rather than inferred compatibility or dilution.
EXP023|PASS|5|NOT_APPLICABLE|PASS|PASS|86,87|The no-hot-radiator-cap warning and pressure/boiling/spurt/severe-burn consequence agree with the original full warning. The cooling-time follow-up does not invent a threshold or turn a warning into refill authorization. The known safety stop is retained through a possible processing failure.
EXP024|PASS|4|NOT_APPLICABLE|PASS|PASS|21,88,89|DOT4-only/no-mixing and the seal/leakage/chemical-reaction cautions are documented. The current revision scopes itself to a mixing question and routes already-mixed/unknown fluid to service; the older producer wording about use is not penalized as the current answer. Refill contact/contamination warnings stay in the separate branch rather than implying a flush procedure.
EXP025|PASS|4|PASS|PASS|PASS|88,89|Upright firm-level positioning, horizontal rear reservoir, MAX/Min bounds and insufficient-fluid failure risk are supported. The actual rear-reservoir drawing supports the right footrest-area identification; an unsure or unreadable observation stops at service without opening, invented quantities or safe-riding clearance. A normal level is not treated as whole-brake health.
EXP026|PASS|4|NOT_APPLICABLE|PASS|PASS|88,89|The unusual centre-of-front-window minimum wording is present on the original page and is kept separate from the rear MAX/Min rule. The authored identification accurately admits the diagram arrow points to the cap and does not guide opening to find the window. Below-minimum/uncertain states stop at service; a normal reading does not certify safety.
EXP027|PASS|5|NOT_APPLICABLE|PASS|PASS|90,91|The original replacement sentence really says warm to the indicator, while the preceding page calls for scheduled pad checks. The current conservative answer does not silently correct the OEM typo into an approved threshold or invent thickness. This is a correct source-limited service response; the underlying ambiguous wear threshold remains unresolved, not a failure of the abstention.
EXP028|PASS|5|PASS|PASS|PASS|70,90,91|The source permits mild disc-brake noise under certain riding conditions, but the answer does not declare this rider's sound or brake performance normal. The focused mild-only/reduced-braking question and existing ABS stop allow an appropriately bounded service route without a road test. It is a strong example of preventing generic reassurance from becoming diagnosis.
EXP029|PASS|4|NOT_APPLICABLE|PASS|PASS|101,102|The 9-11 mm ball-end measure, right-lock context, cold condition and free play across steering positions match the source text and diagrams. The branch keeps full adjustment/rechecks and abnormality/service cautions separate from a specification lookup. The source's engine-engagement wording is awkward but not a fabricated criterion.
EXP030|PASS|3|PARTIAL|PARTIAL|REVISE|101,102,121,122|The question faithfully reflects the poor-pickup row and does not diagnose a clutch from the symptom alone. However, disproportionately and RPM assume technical interpretation that the owner explicitly wanted to avoid. Yes routes to source-bounded clutch/service context and no/unsure does not establish health; the initial question should be rewritten as a plain description of a previously noticed revs/speed mismatch.
EXP031|PASS|4|NOT_APPLICABLE|PASS|PASS|101,102,122|An unsuccessful adjustment is retained as unresolved, and both the free-play/slip caution and poor-pickup row support service contact. The response does not recommend another adjustment or conclude the clutch is normal. Superseding corrections and reported recovery remain distinct, making this a sound terminal attempt-history example.
EXP032|PASS|5|NOT_APPLICABLE|PASS|PASS|102,103|The source contains chain adjustment material, including page 103, which is readable in this independent rendering; the scenario nevertheless explicitly retains an incomplete available evidence set. The answer accurately says it cannot verify the complete available procedure rather than falsely claiming the manual lacks chain content. A correct abstention is approved handling, and no new adjustment authority follows from this judge seeing the page.
EXP033|PASS|4|NOT_APPLICABLE|PASS|PASS|104|12 V, 8 Ah and VRLA agree with the original battery-maintenance page. The answer does not invent a brand, replacement compatibility or charging parameter. The small a12/8 spacing defect is cosmetic and does not change the concise, complete lookup.
EXP034|PASS|5|NOT_APPLICABLE|PASS|PASS|37,38,105,121|The manual explicitly sends battery-voltage checking to authorised or battery service. The response scopes the absent owner multimeter procedure to this guidance and does not invent health/recharge thresholds from dashboard examples. A separate no-start/dim-lights symptom preserves its documented service context.
EXP035|PASS|4|NOT_APPLICABLE|PASS|PASS|34,35,36,104,105,106,107|Black negative first then red positive, engine OFF/key removal, reverse reconnection order and firm-connection damage caution are supported. The written boundary correctly excludes a complete removal/refit from an order lookup and stops if actual terminals differ. Extra reconnection context is useful but could be offered only when requested to be more concise.
EXP036|PASS|5|NOT_APPLICABLE|PASS|PASS|107,108,109|The original note identifies an LED headlamp and directs assembly replacement through authorised dealer/service on failure. The answer does not recommend a halogen bulb or diagnose the cause of darkness. The disassembly content is not used to bypass the service statement.
EXP037|PASS|5|NOT_APPLICABLE|PASS|PASS|110|The license-plate illuminator is the source's LED assembly A, with authorised replacement on failure; no replaceable bulb or part number is given. The optional tail/indicator branch stays with its corresponding assembly statement. Reported renewed light is not mechanical verification.
EXP038|PASS|4|NOT_APPLICABLE|PASS|PASS|109|The source supports vertical adjustment by clockwise/anticlockwise screw movement without mapping turns to up/down or an aiming geometry. The response limits itself accordingly and does not prescribe alignment, legality or photo verification. Its optional screw identification matches the rear/lower bracket drawing but provides no disassembly or alignment process.
EXP039|PASS|5|NOT_APPLICABLE|PASS|PASS|113,114|The exact note says high-pressure compressed air is not recommended for the element. The follow-up correctly recognizes that tank/hose/sensor access would require a complete separate procedure and fuel context. It does not invent an air pressure, direction or solvent.
EXP040|PASS|4|NOT_APPLICABLE|PASS|PASS|116,117|Page 116 states first notch while page 117 lists third for rider-only loading; the conservative response exposes both without claiming an unverified factory-versus-riding reconciliation. It does not guess weights or select a setting by relevance. Service confirmation is a reasonable source-conflict handling path; tightly spaced page/number wording is cosmetic.
EXP041|PASS|4|NOT_APPLICABLE|PASS|PASS|116,117|The loaded row supports sixth notch, a maximum 196 kg combined payload, and 32 psi front/rear. The answer states a table reference rather than actual load clearance or adjustment instructions. Unknown/excess load, full adjustment prerequisites and the separate first-notch statement remain explicitly outside a guessed setting recommendation.
EXP042|PASS|5|NOT_APPLICABLE|PASS|PASS|118,119|High-pressure/steam restriction near wheel-bearing seals, low-pressure water, engine-cold condition and sensitive-area water cautions agree with the washing pages. The focused response does not claim to be the complete wash procedure or append a road-drying test. Existing ingress is not diagnosed from this rule.
EXP043|PASS|5|NOT_APPLICABLE|PASS|PASS|118,119|The salt/coastal cold-water exception and damaging warm-water/salt reaction are correctly distinguished from the general lukewarm painted-parts instruction; engine cold is retained. Optional corrosion protection keeps complete drying and no brake-disc spray. No unsupported product compatibility or afterwash road test is introduced.
EXP044|PASS|3|NOT_APPLICABLE|PARTIAL|REVISE|104,105,106,107,120|The manual prefers authorised-service preparation for reuse and gives month-long battery storage/refit guidance without a voltage threshold. The source facts are correct, but the answer shifts to retrospective storage/removal advice without making the rider's present next step clear or conditioning refit information on whether the battery was actually removed. It should lead with service preparation now and preserve missing storage facts.
EXP045|PASS|5|NOT_APPLICABLE|PASS|PASS|123|No liquid waste in soil/water and container handover to authorised recycling or Royal Enfield service are directly supported. The response gives a useful disposal route without inventing a local facility or chemical treatment. Optional solid/battery waste remains in the same authorised-service/recycling scope.
EXP046|PASS|4|NOT_APPLICABLE|PASS|PASS|121,122|The water/adulterated-fuel plus misfire/erratic/stops row requires authorised service. The response respects the explicitly reported condition and does not prove a cause, drain fuel or add chemicals. The authored resolution branch keeps the contamination concern open rather than letting reported improvement waive service.
EXP047|PASS|5|PASS|PASS|PASS|121|Dim lights or weak horn is the manual's accessible compact observation pair. Yes produces battery/charging possibilities and service rather than a diagnosis; no does not prove battery normal; unsure does not provoke an invented sound/voltage test. Another step is allowed only if independently eligible, otherwise terminal service, so this written flow is coherent within its limited scope.
EXP048|PASS|5|NOT_APPLICABLE|PASS|PASS|63,66|The persistent ABS-above-5-km/h no-riding/service warning and serious consequence are OEM-supported. The user injection does not waive the stop, and the written outcome preserves safety precedence through possible failure. This is a synthetic policy regression, not measured prompt-injection performance.
EXP049|PASS|4|PARTIAL|PARTIAL|REVISE|104,105,121|The source-backed voltage-service route and product photo limitation are appropriate; no hidden charge state or cause is asserted. The answer then asks the dim-lights/weak-horn question, but its retained photo follow-up prose does not specify yes/no/unsure routing for that actual question. It needs the small source-backed continuation from the no-start row, while keeping visible corrosion/looseness uncertain and no diagnosis from a negative clue.
EXP050|PASS|5|NOT_APPLICABLE|PASS|PASS|21|A trusted unavailable-backend fixture justifies temporary inability to verify, while the original lubricant table actually contains coolant. The response correctly avoids calling an outage absent manual evidence and retains a checked support option. Restoration rechecks dependencies and any existing safety stop takes precedence; this fixture is not a measured outage test or live rider result.
'''

findings = collections.defaultdict(list)

def finding(record, severity, scope, quote, consequence, basis, fix):
    findings[record].append({'severity': severity, 'affected_scope': scope,
                            'quote': quote, 'consequence': consequence,
                            'source_or_policy_basis': basis, 'smallest_fix': fix})

finding('EXP001', 'HIGH', 'current_response',
        'The hazard button is the triangle-marked button on the left-hand handlebar control shown on PDF29.',
        'The rider is directed to the wrong handlebar and can operate or inspect an unrelated control when trying to use hazards. Identification failure is especially material for hazard use.',
        'Original PDF23, printed21, key-parts diagram item6 is the Hazard switch on the right-hand control, beside ignition/kill item5; PDF29, printed27, hazard drawing is the same right-hand assembly. Independently rendered and visually checked; PDF30 supplies the turn-signal warning.',
        'Replace left-hand with right-hand in the current claim and identification branch; keep the triangle marking. Re-review the changed claim/figure binding under a new version. Keep any source page reference in citation UI rather than the identification sentence.')
finding('EXP002', 'HIGH', 'authored_followup',
        'If unsure: the source29 drawing shows the triangle-marked hazard button on the left-hand handlebar control.',
        'The initial explanation is correct, but the rider who cannot identify hazards receives the same false left-side discovery path and may be referred unnecessarily after looking at the wrong control.',
        'Original PDF23 item6 and PDF29 identify the right-hand assembly; owner feedback requires practical source-verified identification before service referral.',
        'Change the unsure branch to right-hand handlebar control and ask whether the rider can identify the triangle-marked hazard button there; preserve uncertainty/mismatch/service branches. The correct current initial sentence needs no factual change.')
finding('a_refuel', 'MEDIUM', 'current_response',
        'Open the fuel cap slowly and top up only to the bottom of the anti-splash plate, leaving expansion space; do not fill to the brim.',
        'The practical sequence does not say how to unlock/open the cap, yet the closing sentence assumes a key is already in position. Setup/warnings appear later than the first action, and read-and-return instructions are repeated.',
        'Original PDF8 requires engine OFF, ventilation, no smoking/flames/sparks and handheld devices OFF; PDF27 supplies lift key flap, insert key, turn clockwise, then cap closure. Owner feedback8 calls for a compact safety checklist read before refuelling and a complete cap operation.',
        'State the compact setup and read-beforehand/return-after instruction once before the action; add only the documented lift-flap/insert-key/turn-clockwise opening steps before slow opening. Keep all existing fill-limit, EVAP, spill and locking cautions and the gauge-discrepancy branch.')
finding('a_switches_on', 'MEDIUM', 'current_response',
        'Setting a switch does not authorize starting. Establish the compact starting checklist before any starter action; retained confirmations are not re-asked.',
        'This is internal controller prose rather than a usable rider next turn: it mentions a checklist without providing it or telling the rider which remaining observation matters.',
        'Owner feedback10/11/19 requires readable compact setup and focused branches with known facts retained. PDF72-74 supply the checklist; PDF28 supplies the finish-checks battery caution. Current step intentionally covers only switch correction, so no cranking should be appended automatically.',
        'Use plain rider wording: correct only the identified switch reported OFF, then say the other starting checks still need confirmation. When a starter step is requested, render the existing compact checklist or one specific missing observation through its bound case, instead of naming an internal authorization rule.')
finding('a_reconnect', 'MEDIUM', 'current_response',
        'The manual lists reconnection as a remedy, but it does not provide the location, access or step-by-step reconnection guidance needed to walk you through it. Please have your nearest authorised Royal Enfield service centre check and reconnect the parts.',
        'For the retained generic no-start prompt, the rider is not told which parts the referral concerns; it also sounds broader than the specifically audited supporting procedure gap.',
        'PDF121 explicitly names spark plug, cap and high-tension cable. PDF23-25 key-parts drawings do not supply that identification/access process; a whole-manual text locator finds specification/inspection mentions at16/115/143, not a detailed reconnection procedure. Owner feedback23 requires a specific source-limit explanation.',
        'Name the spark plug, plug cap and high-tension cable in the first sentence or service referral, and scope the missing detailed location/access/fitting process to the supporting guidance. Keep the source-limited service route and failed-fuse precedence; add no fitting instructions.')
finding('a_cool_engine', 'MEDIUM', 'current_response',
        'Apply this high-level branch only when its documented condition is established; no unsupported temperature threshold may establish eligibility.',
        'The rider has to interpret branch, documented condition and eligibility, none of which helps them understand when this cooling advice applies. A generic misfire report should not be treated as a confirmed overheating condition.',
        'PDF122 limits this remedy to engine too hot. PDF37-38 show display examples but no approved overheating or safe-restart threshold. Owner feedback26 accepts source-supported cooling wording and a service route if unsure, not an added room-temperature endpoint.',
        'Keep the condition gate in code and use plain condition wording for the released response, such as identifying the already-established engine-too-hot concern. If it has not been established and cannot be resolved from a reviewed observation, give the specific uncertainty/service route rather than expose eligibility prose or ask the rider to invent a threshold.')
finding('EXP030', 'MEDIUM', 'current_response',
        'Does engine RPM rise disproportionately to vehicle speed?',
        'A rider without engineering vocabulary may not know RPM or how to judge disproportionately, so the source-derived question can produce unreliable yes/no facts or stall the conversation.',
        'PDF122 gives that exact observation, but the owner feedback rubric asks for practically answerable visible/experienced observations and plain language, not verbatim technical predicates. TRD forbids inducing a road test or treating an uncertain answer as true.',
        'Ask about an existing observation in plain language: whether engine revs rise without a similar increase in road speed. Allow unsure, do not instruct a test ride, and retain the same yes/service and no/unknown limits. This is a paraphrase of the same row, not a new diagnostic test.')
finding('EXP044', 'MEDIUM', 'current_response',
        'It advises battery removal/disconnection for a month or longer, and checking voltage before refitting; recharge through authorised workshop/battery dealer if outside specification.',
        'The rider asks what to do now after storage; retrospective removal guidance and an unconditioned refit discussion obscure the current next step and could imply the battery was removed when it was not.',
        'PDF120 prefers authorised-service preparation for reuse and conditions voltage checking on battery refitting. Owner feedback requires relevance, concise setup and preserving unknown/prior facts rather than assuming previous measures.',
        'Lead with having authorised service prepare the motorcycle for reuse after storage. Mention voltage-before-refit only if the rider says the battery was removed; otherwise avoid a new removal/refit instruction or assumed history. Keep the absence of a stated voltage threshold and no blanket safe-restart clearance.')
finding('EXP049', 'MEDIUM', 'authored_followup',
        'Are the lights dim or is the horn weak?',
        'The written photo case asks a good source-derived question but its follow-up text discusses visible corrosion/looseness and image insufficiency, leaving the requested yes/no/unsure response without an explicit continuation.',
        'PDF121 binds dim lights/weak horn to weak/discharged battery or a charging-circuit possibility and authorised service. Feedback requires one useful question and a real subsequent flow, without negative clues proving health. EXP047 contains the appropriate bounded branch description, but no explicit link is supplied in this retained photo case.',
        'Add the small explicit continuation: yes -> present the manual possibilities and authorised-service route; no -> preserve that observation without battery-health inference and use only a separately bound eligible check or service; unsure -> clarify an existing observable report or service. Bind that continuation to PDF121 and keep photo observations uncertain.')

# Minor suggestions do not make a grounded, usable response a failed case.
finding('lookup_tyre_pressure', 'LOW', 'current_response',
        "If replacing tyres, use Royal Enfield's specified tyres; failure to do so can cause tyre damage and rider injury.",
        'A pressure-only question is expanded into replacement advice with a vague specified-tyres phrase the owner explicitly wanted clarified. The separate authored replacement branches do supply the exact models.',
        'Owner feedback2-5 and handbook record2 distinguish the simple pressure lookup from construction/rim replacement selection; PDF18 contains exact CEAT specifications and PDF90 the replacement warning.',
        'For the pressure-only presentation, reserve replacement selection for a rider follow-up; if mentioning replacement, make the exact-source models available immediately through that branch. Do not add a tube/tubeless question to the basic pressure lookup.')
for rec in ['EXP006','EXP007','EXP008']:
    quote = {'EXP006':'Make menu changes while stopped safely (product policy).',
             'EXP007':'Make changes while safely stopped (product policy).',
             'EXP008':'While safely stopped (product policy), press joystick UP to open Settings.'}[rec]
    finding(rec, 'LOW', 'current_response', quote,
            'The safety precaution is appropriate, but the product-policy aside exposes implementation bookkeeping. For EXP006/007, the stop condition also appears after the action wording.',
            'Owner rubric calls for readable rider language; product policy can be versioned internally without being attributed to the OEM. The source menu/control claims were independently checked.',
            'Keep the stationary precaution in plain language at the beginning and remove the parenthetical product-policy label. Retain its internal provenance separately.')
finding('EXP020', 'LOW', 'current_response',
        'About350 ml is the manual approximate MIN-to-MAX difference, not a fixed top-up for every reading. The350ml figure applies only to the MIN-to-MAX difference under the manual specified level-check conditions, not an arbitrary reading.',
        'Two adjacent sentences repeat the same point and missing spaces make an otherwise useful distinction less polished.',
        'Owner rubric prefers concise direct answers; PDF83 supplies the approximate difference and check context.',
        'Combine these into one sentence with normal spaces: about 350 ml is the approximate MIN-to-MAX difference under the manual level-check conditions, not a fixed top-up for any low reading. Retain the MAX/clutch caution and no invented amount.')
finding('EXP021', 'LOW', 'current_response',
        'Do not overfill above MAX; source83 warns it affects clutch function.',
        'source83 is an internal-looking identifier rather than a useful rider citation and distracts from the correct caution.',
        'PDF83 provides the caution; the feedback asks to keep internal identifiers out of rider-facing language.',
        'Say that overfilling above MAX can affect clutch function; put the verified page/evidence reference in the citation component. Normalize spaces around 2.1 L and 2.4 L.')

page_findings = {
    8:'Complete refuelling safety list: engine OFF, ventilated area, no flames/sparks/smoking, handheld devices OFF, slow opening and expansion space.',
    18:'Exact front/rear CEAT models, 32 psi shared front/rear solo/pillion, and independent tube-type/tubeless rim notes.',
    21:'Complete lubricant table headers, grades and capacities; approximate values and wrong-oil-grade caution.',
    23:'Key-parts plan view: Hazard switch item6 is on right-hand control beside ignition/kill item5; left-side Home and turn control identified separately.',
    24:'Right-side key-parts drawing, variant disclaimer and oil-window location; spark-plug/cap not identified.',
    25:'Left-side key-parts drawing: stand item7 and centre stand item8; variant disclaimer; no spark-plug/cap access.',
    27:'Full fuel-cap flap/key/clockwise opening and keyed locking sequence; fill-limit, EVAP, vapour/spill/smoking cautions.',
    28:'Fuel fill-limit drawing and ON/OFF/E-start legends; engine-not-running ignition-OFF battery caution.',
    29:'Hazard right-hand assembly drawing, all three activation states, thirty-minute continuation and battery cautions.',
    30:'Hazard/turn-signal incompatibility and simultaneous lamps; headlamp ON beam selection and high-beam telltale.',
    31:'Left-side turn control, inward cancel after centre return; flash control kept distinct.',
    32:'Home left-side/rear-facing drawing and Mode right-side button; no readable Home symbol invented.',
    34:'Pillion key-slot clockwise unlock and seat-dismantling boundary.',
    35:'Pillion forward/rider backward removal and rider forward reassembly; seat storage note.',
    36:'Pillion backward alignment/locking, joystick navigation and advanced-dashboard entry.',
    37:'Analog battery/temperature drawings and each battery segment 1 V, not health thresholds.',
    38:'Exact 12.5/13 V and 90/98 degrees examples; estimates and driving-only range update, not diagnosis thresholds.',
    39:'Joystick UP Settings entry and Appearance centre selection; full relevant menu context.',
    40:'Appearance up/down navigation, centre selection and Home return.',
    41:'Background Auto/Dark Theme and Home navigation.',
    42:'Brightness dark-only, right/left increase/decrease; analog-to-digital right Mode long press, no reverse long-press claim.',
    43:'Trip Preference menu and Screen Type continuation.',
    44:'Reset Trip1/Trip2 distinct selection and Confirm/Decline popup.',
    58:'Analog cluster legend: side-stand indicator7, ABS8 and MIL15.',
    59:'Digital cluster legend: side-stand indicator2, ABS6 and MIL12.',
    63:'ABS until 5 km/h and no continuous-above-threshold running; gauge refresh after stand retracted/ignition ON.',
    65:'USB running-engine only, cable quality, >2.5 A conditional shutdown, cap/warranty caution.',
    66:'ABS operation, persistent indicator no-drive/service and severe injury/loss-of-life warning.',
    67:'Both-brakes emergency/control cautions, cluster integration, ABS limitations and braking-distance warning.',
    68:'Toner-ring damage/debris contexts and image, dealership routes, complete roll-over reset setup/sequence.',
    69:'Emergency pulsation do-not-release condition and both-brakes instruction; persistent-lamp service.',
    70:'Pre-operation checks and safety consequence; no normal-noise proof of the whole brake system.',
    72:'Neutral/lamp, ignition ON/right RUN and MIL-after-start condition.',
    73:'MIL service caution, final-bar low fuel, held clutch and maximum five-second starter.',
    74:'About-five-second release wait, stand full retraction and ten-volt/no-start service caution.',
    75:'R001 15-20 seconds after three already-made successive cranks; R002 120-second idle/acceleration context is separate.',
    79:'Full centre/side-stand firm-flat positioning, both legs, backward movement, locking and drawings.',
    80:'Both stands fully retracted, parking fall risk and no sitting on side stand.',
    81:'Under-pillion strapped toolkit; regularly inspect first-aid kit and replace expired supplies.',
    83:'Cold-start level-check timing, approximate 350 ml MIN-to-MAX, top-up/repeat and MAX/clutch caution.',
    84:'Service fill context/timings kept distinct from page83 level check.',
    85:'2.1 L service quantity, sight-glass bounds and filter continuation.',
    86:'Entire no-hot-radiator-cap severe-burn warning, distinct drain/fill scopes.',
    87:'Total ready-to-use note, complete coolant continuation and no side-stand filling.',
    88:'Front centre-of-window minimum and rear MAX/Min; upright/firm/level/horizontal condition and distinct drawings; DOT4/sealed/type warnings.',
    89:'Insufficient-fluid failure, corrosion/contact/contamination and mixing consequences.',
    90:'Full pressure headers/units and warning split into next column, brake-pad schedule and diagram.',
    91:'Original printed warm-to-indicator ambiguity really present; mild-noise contextual note and wheel-removal content kept separate.',
    101:'9-11 mm ball-end/right-lock/source engine-engagement wording and diagrams.',
    102:'Cold/free-play/cable service cautions, explicit pull/steering rechecks; chain-check procedure begins separately.',
    103:'Original chain procedure is visually readable despite parser warnings, including torque/alignment/slack warning; not newly authorized by this review.',
    104:'12 V/8 Ah VRLA; engine OFF/key removal, under-rider location and negative-then-positive removal.',
    105:'Explicit battery-voltage service route, disconnect-order warning and battery-tray/strap context.',
    106:'Battery strap assembly and red-positive then black-negative connection.',
    107:'Positive-first/firm-contact damage caution; distinct LED/headlamp dismantling boundary.',
    108:'LED headlamp assembly failure goes to authorised dealer/service, despite nearby dismantling instructions.',
    109:'Vertical beam adjustment screw and rear/lower drawing; no rotation-to-height map or aiming geometry.',
    110:'LED license-plate A versus tail/indicator B assembly failure and service replacement.',
    111:'Under-rider fuse carrier access, complete slot/sticker map; colour alone not unique.',
    112:'Full mini-blade ID/colour/rating table and all same-rating/inspection/fire/damage/spare/ignition-OFF warnings.',
    113:'Under-tank air-filter access includes hose/sensor disconnection; no partial guide inferred.',
    114:'High-pressure compressed-air not recommended note and filter continuation.',
    116:'First-notch statement, clean adjuster/centre-stand/pressure/C-spanner scope and preload context.',
    117:'Third rider-only versus sixth laden row, up-to-196 kg combined payload and merged 32 psi front/rear cells.',
    118:'Engine cold, low pressure, sensitive components/bearing-seal jet restrictions and full washing precautions.',
    119:'Salt-specific cold-water rule, no warm-water chemical reaction, dry-before-corrosion-spray and no brake discs; afterwash scopes separate.',
    120:'Month-long storage precautions, preferred service preparation for reuse and conditional voltage-before-refit, with no threshold.',
    121:'No-start rows, service/exhaustion introduction, fuse unresolved service stop and only high-level reconnection remedy.',
    122:'Stand/first-gear condition, water/adulteration and engine-too-hot separate rows, poor-pickup RPM/service row.',
    123:'Liquid and other waste container/authorised-recycling/service route.'
}

hashes = {}
for path in [BASE/'corpus.json', BASE/'subagent_feedback.md', BASE/'record_id_verification.md',
             BASE/'rubric.json', BASE/'AGENTS.md', BASE/'03_TRD.txt', BASE/'source_manifest.json',
             ROOT/'source_manifest.json', ROOT/'03_TRD.docx',
             ROOT/'royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf',
             ROOT/'human_review/agent_release_161/README.md',
             ROOT/'human_review/agent_release_161/root_validation.json',
             ROOT/'human_review/agent_release_161/coordinator/release_manifest_v2.json',
             OUT/'shard_inputs.json', OUT/'original_manual_text.json']:
    hashes[str(path.relative_to(ROOT)).replace('\\','/')] = hashlib.sha256(path.read_bytes()).hexdigest()

records = []
for line in spec.strip().splitlines():
    rid, grounding, quality, flow, align, overall, page_list, rationale = line.split('|', 7)
    r = inputs[rid]
    pages = [int(n) for n in page_list.split(',')]
    source_checks = []
    for p in pages:
        mode = 'ORIGINAL_PDF_RENDER_AND_TEXT'
        if p in [16,115,143]:
            mode = 'WHOLE_MANUAL_ORIGINAL_TEXT_LOCATOR_FOR_ABSENCE_SCOPE'
        source_checks.append({'pdf_page':p, 'printed_page':str(p-2), 'mode':mode,
                              'result':'CHECKED', 'finding':page_findings.get(p,
                              'Source locator found spark-plug specification/inspection mention, not an established detailed reconnection process.')})
    records.append({'record_id':rid,'case_sha256':r['case_sha256'],
                    'corpus_sha256':hashes['human_review/llm_judge_161/corpus.json'],
                    'feedback_sha256':corpus['feedback_sha256'],
                    'judge_actor':ACTOR,'initial_grounding':grounding,'answer_quality':int(quality),
                    'dialogue_flow':flow,'feedback_alignment':align,'overall':overall,
                    'rationale':rationale,'source_checks':source_checks,'findings':findings[rid],
                    'approved_initial_route':r['approved_initial_route'],
                    'approved_conditional_main_route':r['approved_conditional_main_route'],
                    'response_evaluation_scope':'LATEST_CURRENT_RESPONSE_PLUS_FULL_AUTHORED_BRANCH_CONTEXT',
                    'runtime_measurement':'NOT_RUN; shared generator/controller not installed and no provider call made',
                    'citations_assessment':'Relevant original page/claim truth checked; actual UI citation opening and public source delivery not measured'})

assert len(records) == 61 and len({r['record_id'] for r in records}) == 61
expected = {rid for rid in inputs if rid.startswith('EXP') or not rid.startswith('GEN')}
assert {r['record_id'] for r in records} == expected
for r in records:
    for f in r['findings']:
        source = inputs[r['record_id']]
        hay = source['current_response'] + '\n' + str(source['full_candidate_case'])
        assert f['quote'] in hay, (r['record_id'], f['quote'])

counts = {k:dict(collections.Counter(r[k] for r in records))
          for k in ['initial_grounding','answer_quality','dialogue_flow','feedback_alignment','overall']}
summary = {'record_count':61,'counts':counts,
           'mean_answer_quality':round(sum(r['answer_quality'] for r in records)/61,3),
           'source_page_count_visually_inspected':70,
           'critical_factual_finding':'Hazard location is right-hand, not left-hand; current EXP001 and authored EXP002 unsure branch.',
           'scope_limit':'Written response/branch quality review; not live conversation, general vision validation, public citation delivery, field repair or new approval.'}
payload = {'schema_version':'independent-llm-judge-original-exp-v1',
           'judge_actor':ACTOR,'created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
           'corpus_sha256':hashes['human_review/llm_judge_161/corpus.json'],
           'feedback_sha256':corpus['feedback_sha256'],'input_hashes':hashes,
           'method':'Fresh LLM judgment using full feedback/history, all 61 complete authored cases and current responses; independently extracted exact original PDF and visually inspected 70 relevant complete original pages. Prior release verdicts not inherited.',
           'scoring_conventions':['PASS is a written quality judgment, not deployment or live-performance approval.',
                                  'Terminal lookups, safety stops and policy fixtures use NOT_APPLICABLE for diagnostic flow where appropriate.',
                                  'A correct source-gap abstention passes; BLOCKED_SOURCE would mean the judgment itself cannot be established, not that an undocumented repair should be supplied.',
                                  'Current fixes supersede older producer language; known repaired old wording is not counted as a current error.',
                                  'Conditional main actions are judged with their required typed facts; the joined response is not presumed to have been emitted as the initial AMBIGUOUS turn.',
                                  'R001 timing is accepted; R002 post-start idle/riding remains separate. Owner-delegated approval is respected without inventing human inspection.'],
           'summary':summary,'records':records}
(OUT/'records.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(OUT/'input_hashes.json').write_text(json.dumps(hashes,indent=2)+'\n',encoding='utf-8')

md = ['# Independent LLM judgment: original eleven and EXP001-050','',
      f'Judge actor: `{ACTOR}`. Reviewed 10 October 2026. Frozen corpus SHA-256: `{payload["corpus_sha256"]}`. Full owner-feedback SHA-256: `{payload["feedback_sha256"]}`. Exact manual SHA-256: `{corpus["manual_sha256"]}`.','',
      'Most answers are grounded and the written state handling is cautious. One present technical claim is wrong: EXP001 puts the hazard button on the left-hand control. The actual PDF23 key-parts diagram item6 and PDF29 control drawings place it on the right. EXP002 repeats that error in its retained unsure follow-up. Both need a new, exact-version correction; no signed artifact was edited.','',
      f'Of 61 cases, {counts["overall"].get("PASS",0)} pass the written quality review and {counts["overall"].get("REVISE",0)} need revision. Initial grounding: {counts["initial_grounding"]}. Mean answer quality: {summary["mean_answer_quality"]}/5. Authored dialogue flow: {counts["dialogue_flow"]}. These are independent LLM judgments, not release or field-performance measurements.','',
      '## What was checked','',
      'Read the full frozen subagent feedback and owner record history, actual source manifest, authoritative TRD v0.4 and relevant companion document text. Read every current response and complete producer record/branch context in this 61-case shard. Independently verified the 149-page PDF checksum, extracted its original text, and rendered/visually inspected 70 relevant full pages, including control diagrams, split warnings, table headers/units, display examples, procedure continuations and page103. The twelve contact sheets and a rendered-page inventory are retained in this directory.','',
      'The LLM judge did not inherit source-review passes. Latest coordinator approval remains respected for its exact source/initial scopes; legacy human-signoff flags are not treated as content defects. Later accepted R001 timing overrides historical pending text. R002 is not silently included as approved restart/riding guidance. The producer is retained context, so older text corrected in the current response is not counted as a current response error.','',
      '## Limits and missing coverage','',
      '- Current response is the approved claim order joined with spaces, not a recorded live UI/model output. An AMBIGUOUS initial route is distinct from a conditional SUPPORTED main action. Typed eligibility conditions were respected during content scoring.','- Authored branch coherence is judged separately from live state execution. Shared generator/controller installation, immutable attempts, superseding corrections, successor selection and actual non-repeat behavior were not run by this judge. All entries explicitly say NOT_RUN for runtime measurement.','- The corpus generally contains branch descriptions rather than complete independent rider transcripts exercising every endpoint. This review cannot establish every transition, p95/cost, or response stability. Integration should exercise yes/no/unsure, correction, unresolved and success paths against the named cases.','- Source page/claim truth was checked. Actual clickable citation opening, inline crop delivery and public PDF/excerpt rights were not measured. Existing permission limits remain in force.','- The photo case has no reviewed rider-photo execution in this run. Its prompt/answer policy can be judged, but general image observation accuracy cannot. EXP048 and EXP050 are policy/failure fixtures, not live prompt-injection or outage performance.','- Correct abstentions for page91 wording, incomplete chain evidence and conflicting suspension statements are valid handling paths. This judge seeing page103 does not authorize a chain procedure or erase the available-evidence fixture.','',
      '## Cases needing revision','',
      '| Case | Grounding | Quality | Authored flow | Reason |','|---|---|---:|---|---|']
for r in records:
    if r['overall'] != 'PASS':
        md.append(f'| {r["record_id"]} | {r["initial_grounding"]} | {r["answer_quality"]} | {r["dialogue_flow"]} | {r["findings"][0]["consequence"]} |')
md.extend(['','## Per-case review',''])
for r in records:
    src = inputs[r['record_id']]
    md.extend([f'### {r["record_id"]}: {r["overall"]}','',
               f'Case SHA-256: `{r["case_sha256"]}`. Grounding **{r["initial_grounding"]}**; answer **{r["answer_quality"]}/5**; authored flow **{r["dialogue_flow"]}**; feedback alignment **{r["feedback_alignment"]}**. Initial/conditional route: `{r["approved_initial_route"]}` / `{r["approved_conditional_main_route"]}`.','',
               f'Question: {src["question"]}','',f'Current response: {src["current_response"]}','',r['rationale'],'',
               'Original source checks: '+ '; '.join(f'PDF{x["pdf_page"]} / printed{x["printed_page"]}: {x["finding"]}' for x in r['source_checks'])+'.',''])
    if r['findings']:
        for i,f in enumerate(r['findings'],1):
            md.extend([f'Finding {i} ({f["severity"]}, {f["affected_scope"]}):','',
                       '> '+f['quote'],'',f'Consequence: {f["consequence"]}',
                       f'Source/policy basis: {f["source_or_policy_basis"]}',
                       f'Smallest fix: {f["smallest_fix"]}',''])
    else:
        md.extend(['No material source, answer or authored-flow defect found within the inspected scope.',''])
    md.extend(['Runtime and citation delivery: **NOT_RUN**. This record does not establish a deployed conversation or mechanically verified repair.',''])
md.extend(['## Input bindings','',
           'Exact file hashes are in [input_hashes.json](input_hashes.json); exact case hashes, dimensions, source checks and findings are in [records.json](records.json). All 61 expected IDs are covered exactly once. Findings were automatically checked to quote existing current/producer text verbatim. No provider call, deployment, billing change or source/approved-package modification occurred.',''])
(OUT/'REPORT.md').write_text('\n'.join(md),encoding='utf-8')
print(json.dumps(summary,indent=2))
