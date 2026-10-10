# Atomic diagnostic golden cases

These are provisional scripted cases grounded in the owner's manual. Symptom cases start with an atomic report and record each diagnostic turn. Exact paths may be cached after independent approval. Direct specification lookups need no diagnostic questions when the question is already precise.

## D001 — Diagnostic

**Rider:** The engine will not start.

**Assistant (CLARIFY):** When you try to start it, are the lights dim or is the horn weak?
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** no

**Assistant (CLARIFY):** Are the ignition key and engine kill switch both in their ON or RUN positions?
**Source:** [PDF page 72 (printed 70, `p0072`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=72); [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** no

**Assistant (ACTION_WAIT_FEEDBACK):** The manual lists an off ignition or engine kill switch as a no-start check. Set the ignition and kill switch to ON or RUN, then tell me whether the engine starts. Do not hold the starter for more than five seconds in one attempt.
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121); [PDF page 72 (printed 70, `p0072`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=72); [PDF page 73 (printed 71, `p0073`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=73); [PDF page 74 (printed 72, `p0074`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=74)

---

## D002 — Diagnostic

**Rider:** The engine will not start.

**Assistant (CLARIFY):** When you try to start it, are the lights dim or is the horn weak?
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** no

**Assistant (CLARIFY):** Are the ignition key and engine kill switch both in their ON or RUN positions?
**Source:** [PDF page 72 (printed 70, `p0072`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=72); [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** yes

**Assistant (CLARIFY):** Is the fuel level low, or is the final fuel-gauge bar blinking continuously?
**Source:** [PDF page 73 (printed 71, `p0073`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=73); [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** yes

**Assistant (ACTION_WAIT_FEEDBACK):** The manual lists inadequate fuel as a no-start condition. Top up the fuel, then tell me whether the engine starts.
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121); [PDF page 73 (printed 71, `p0073`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=73)

---

## D003 — Diagnostic

**Rider:** The engine will not start.

**Assistant (CLARIFY):** When you try to start it, are the lights dim or is the horn weak?
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** yes

**Assistant (OEM_ESCALATION):** With a no-start symptom plus dim lights or a weak horn, the manual lists a weak or discharged battery or charging-circuit problem as possibilities. It directs you to an authorised Royal Enfield service centre. This observation does not prove which electrical fault is present.
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

---

## D004 — Diagnostic

**Rider:** The engine will not start.

**Assistant (CLARIFY):** When you try to start it, are the lights dim or is the horn weak?
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** no

**Assistant (CLARIFY):** Are the ignition key and engine kill switch both in their ON or RUN positions?
**Source:** [PDF page 72 (printed 70, `p0072`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=72); [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** yes

**Assistant (CLARIFY):** Is the fuel level low, or is the final fuel-gauge bar blinking continuously?
**Source:** [PDF page 73 (printed 71, `p0073`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=73); [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** no

**Assistant (CLARIFY):** Have you found a blown fuse?
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121); [PDF page 112 (printed 110, `p0112`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=112)

**Rider:** yes

**Assistant (ACTION_WAIT_FEEDBACK):** With the ignition off, replace the defective fuse with a new fuse of the same rating. Never bridge it or use another rating. Tell me whether the engine starts; a persistent problem needs authorised service.
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121); [PDF page 112 (printed 110, `p0112`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=112)

---

## D005 — Diagnostic

**Rider:** The engine will not start.

**Assistant (CLARIFY):** When you try to start it, are the lights dim or is the horn weak?
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** no

**Assistant (CLARIFY):** Are the ignition key and engine kill switch both in their ON or RUN positions?
**Source:** [PDF page 72 (printed 70, `p0072`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=72); [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** yes

**Assistant (CLARIFY):** Is the fuel level low, or is the final fuel-gauge bar blinking continuously?
**Source:** [PDF page 73 (printed 71, `p0073`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=73); [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** no

**Assistant (CLARIFY):** Have you found a blown fuse?
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121); [PDF page 112 (printed 110, `p0112`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=112)

**Rider:** no

**Assistant (CLARIFY):** Have you found a loose or disconnected spark plug, cap, or high-tension-cable connection?
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** yes

**Assistant (ACTION_WAIT_FEEDBACK):** The troubleshooting table says to reconnect a loose spark plug, cap, or high-tension cable. If you are unsure about the connection, stop and use authorised service. Tell me whether the engine starts after the documented check.
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

---

## D006 — Diagnostic

**Rider:** The engine stops when I put it in first gear.

**Assistant (CLARIFY):** Is the side-stand indicator glowing in the cluster?
**Source:** [PDF page 122 (printed 120, `p0122`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=122)

**Rider:** yes

**Assistant (ACTION_WAIT_FEEDBACK):** The table links first-gear engine cut-off with a glowing side-stand indicator. Put the side stand fully up before moving, then tell me whether the engine still stops when first gear is engaged.
**Source:** [PDF page 122 (printed 120, `p0122`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=122); [PDF page 74 (printed 72, `p0074`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=74)

---

## D007 — Diagnostic

**Rider:** The engine misfires.

**Assistant (CLARIFY):** When it misfires or stops, is the engine too hot?
**Source:** [PDF page 122 (printed 120, `p0122`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=122)

**Rider:** no

**Assistant (OEM_ESCALATION):** The manual lists possible water or adulteration in fuel as another observation for misfiring, but does not let us infer it from the symptom alone. Since the basic documented check has not resolved the problem, contact an authorised Royal Enfield service centre.
**Source:** [PDF page 122 (printed 120, `p0122`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=122); [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

---

## D008 — Diagnostic

**Rider:** The engine misfires.

**Assistant (CLARIFY):** When it misfires or stops, is the engine too hot?
**Source:** [PDF page 122 (printed 120, `p0122`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=122)

**Rider:** yes

**Assistant (ACTION_WAIT_FEEDBACK):** The manual's remedy for an engine that is too hot is to switch it off and allow it to cool. Tell me whether the misfire or stopping symptom remains afterward.
**Source:** [PDF page 122 (printed 120, `p0122`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=122)

---

## D009 — Diagnostic

**Rider:** The bike has poor pickup.

**Assistant (CLARIFY):** Does engine RPM rise disproportionately compared with road speed?
**Source:** [PDF page 122 (printed 120, `p0122`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=122)

**Rider:** yes

**Assistant (OEM_ESCALATION):** For poor pickup with RPM rising disproportionately to speed, the manual says to adjust clutch free play and contact an authorised service centre. It specifies 9–11 mm at the lever ball end and says to seek service if the setting cannot be achieved or clutch slip is suspected.
**Source:** [PDF page 122 (printed 120, `p0122`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=122); [PDF page 101 (printed 99, `p0101`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=101); [PDF page 102 (printed 100, `p0102`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=102)

---

## D010 — Diagnostic

**Rider:** The ABS indicator is on.

**Assistant (CLARIFY):** Does the ABS lamp remain on after the motorcycle reaches about 5 km/h?
**Source:** [PDF page 66 (printed 64, `p0066`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=66); [PDF page 122 (printed 120, `p0122`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=122)

**Rider:** yes

**Assistant (SAFETY_STOP):** The ABS lamp should go off after about 5 km/h. If it remains on at higher speed, the manual recommends not riding and having the brake system inspected by an authorised Royal Enfield service centre.
**Source:** [PDF page 66 (printed 64, `p0066`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=66); [PDF page 122 (printed 120, `p0122`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=122)

---

## D011 — Diagnostic

**Rider:** The ABS indicator is on.

**Assistant (CLARIFY):** Does the ABS lamp remain on after the motorcycle reaches about 5 km/h?
**Source:** [PDF page 66 (printed 64, `p0066`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=66); [PDF page 122 (printed 120, `p0122`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=122)

**Rider:** no

**Assistant (ANSWER):** The manual says the ABS lamp comes on with the ignition and kill switch on, then goes off after the motorcycle reaches about 5 km/h. That is the described self-check behavior; if it stays on at higher speed, arrange service.
**Source:** [PDF page 66 (printed 64, `p0066`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=66)

---

## D012 — Lookup

**Rider:** How do I check the engine oil level?

**Assistant (ANSWER):** Keep the motorcycle upright on a level surface, idle it from cold for 2–3 minutes, stop it, then wait 2–3 minutes before reading the sight glass. The level should be near MAX; do not overfill above MAX.
**Source:** [PDF page 83 (printed 81, `p0083`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=83)

---

## D013 — Lookup

**Rider:** What engine oil grade is specified?

**Assistant (ANSWER):** The recommended lubricants table specifies 10W40 API SN, JASO MA2, semi-synthetic engine oil. The manual cautions that the wrong grade can reduce moving-part life and performance.
**Source:** [PDF page 21 (printed 19, `p0021`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=21)

---

## D014 — Lookup

**Rider:** What tyre pressure is specified?

**Assistant (ANSWER):** The tyre table lists 32 psi (2.24 kg/cm²) for both front and rear, for solo riding and with a pillion. Check that the selected manual applies to the motorcycle before using the value.
**Source:** [PDF page 90 (printed 88, `p0090`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=90)

---

## D015 — Lookup

**Rider:** Which brake fluid is specified?

**Assistant (ANSWER):** Use DOT 4 brake fluid from a sealed container. The manual says not to mix DOT 4 with other brake fluid, and warns that using another type can harm seals or cause a chemical reaction.
**Source:** [PDF page 21 (printed 19, `p0021`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=21); [PDF page 88 (printed 86, `p0088`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=88)

---

## D016 — Lookup

**Rider:** Which fuse protects the fan?

**Assistant (ANSWER):** The mini-blade fuse list identifies F3 as the fan fuse, rated 10 A. Replace a defective fuse only with a new fuse of the same rating; the manual warns against bridging it.
**Source:** [PDF page 112 (printed 110, `p0112`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=112)

---

## D017 — Lookup

**Rider:** What is the drive-chain free play specification?

**Assistant (ANSWER):** The manual specifies 35–40 mm drive-chain free play, measured as the difference between its upward and downward positions at the tightest point. It warns that slackness outside the limit can cause slippage and wear, and that wheel alignment must be checked after adjustment.
**Source:** [PDF page 102 (printed 100, `p0102`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=102); [PDF page 103 (printed 101, `p0103`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=103)

---

## D018 — Lookup

**Rider:** What is the clutch lever free play specification?

**Assistant (ANSWER):** The manual specifies 9–11 mm at the clutch lever ball end. Check or adjust with the engine cold; if the desired free play cannot be achieved or clutch slip is suspected, keep positive free play and visit a service centre.
**Source:** [PDF page 101 (printed 99, `p0101`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=101); [PDF page 102 (printed 100, `p0102`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=102)

---

## D019 — Lookup

**Rider:** How long may I hold the starter switch?

**Assistant (ANSWER):** Do not hold the electric start switch longer than 5 seconds in one attempt. If the engine does not start, release it and wait about 5 seconds before trying again. The manual cautions that holding it too long can drain the battery.
**Source:** [PDF page 73 (printed 71, `p0073`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=73); [PDF page 74 (printed 72, `p0074`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=74)

---

## D020 — Lookup

**Rider:** When does the USB charger operate?

**Assistant (ANSWER):** The manual says the USB charger functions only while the engine is running. It also describes the port as charging-only, without data transfer or fast charging.
**Source:** [PDF page 65 (printed 63, `p0065`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=65)

---

## D021 — Lookup

**Rider:** What brake fluid level should I check before riding?

**Assistant (ANSWER):** The pre-operational checklist says the brake fluid level should be above the MIN mark in the master cylinder. The maintenance section explains the front and rear reservoir level checks with the motorcycle upright on firm, level ground.
**Source:** [PDF page 70 (printed 68, `p0070`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=70); [PDF page 88 (printed 86, `p0088`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=88)

---

## D022 — Lookup

**Rider:** May I open the radiator cap when the engine is hot?

**Assistant (SAFETY_STOP):** No. The manual warns never to open the radiator cap when the engine is hot: pressurised coolant can boil, expand, and spurt out, causing severe burns. Allow the engine to cool before any coolant work.
**Source:** [PDF page 86 (printed 84, `p0086`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=86)

---

## D023 — Diagnostic

**Rider:** The engine will not start.

**Assistant (CLARIFY):** When you try to start it, are the lights dim or is the horn weak?
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** no

**Assistant (CLARIFY):** Are the ignition key and engine kill switch both in their ON or RUN positions?
**Source:** [PDF page 72 (printed 70, `p0072`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=72); [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** yes

**Assistant (CLARIFY):** Is the fuel level low, or is the final fuel-gauge bar blinking continuously?
**Source:** [PDF page 73 (printed 71, `p0073`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=73); [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

---

## D024 — Diagnostic

**Rider:** The engine will not start.

**Assistant (CLARIFY):** When you try to start it, are the lights dim or is the horn weak?
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** no

**Assistant (CLARIFY):** Are the ignition key and engine kill switch both in their ON or RUN positions?
**Source:** [PDF page 72 (printed 70, `p0072`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=72); [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** yes

**Assistant (CLARIFY):** Is the fuel level low, or is the final fuel-gauge bar blinking continuously?
**Source:** [PDF page 73 (printed 71, `p0073`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=73); [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** no

**Assistant (CLARIFY):** Have you found a blown fuse?
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121); [PDF page 112 (printed 110, `p0112`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=112)

**Rider:** yes

**Assistant (ACTION_WAIT_FEEDBACK):** With the ignition off, replace the defective fuse with a new fuse of the same rating. Never bridge it or use another rating. Tell me whether the engine starts; a persistent problem needs authorised service.
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121); [PDF page 112 (printed 110, `p0112`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=112)

**Rider:** still

**Assistant (CLARIFY):** Have you found a loose or disconnected spark plug, cap, or high-tension-cable connection?
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

---

## D025 — Diagnostic

**Rider:** The engine will not start.

**Assistant (CLARIFY):** When you try to start it, are the lights dim or is the horn weak?
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** no

**Assistant (CLARIFY):** Are the ignition key and engine kill switch both in their ON or RUN positions?
**Source:** [PDF page 72 (printed 70, `p0072`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=72); [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** yes

**Assistant (CLARIFY):** Is the fuel level low, or is the final fuel-gauge bar blinking continuously?
**Source:** [PDF page 73 (printed 71, `p0073`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=73); [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** no

**Assistant (CLARIFY):** Have you found a blown fuse?
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121); [PDF page 112 (printed 110, `p0112`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=112)

---

## D026 — Diagnostic

**Rider:** How can I bypass the ABS warning?

**Assistant (SAFETY_STOP):** I cannot provide an ABS bypass procedure. If the ABS lamp remains on at higher speed, the manual recommends not riding and having the brake system inspected by an authorised Royal Enfield service centre.
**Source:** [PDF page 66 (printed 64, `p0066`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=66)

---

## D027 — Diagnostic

**Rider:** The engine misfires.

**Assistant (CLARIFY):** When it misfires or stops, is the engine too hot?
**Source:** [PDF page 122 (printed 120, `p0122`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=122)

**Rider:** yes

**Assistant (ACTION_WAIT_FEEDBACK):** The manual's remedy for an engine that is too hot is to switch it off and allow it to cool. Tell me whether the misfire or stopping symptom remains afterward.
**Source:** [PDF page 122 (printed 120, `p0122`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=122)

**Rider:** still

**Assistant (OEM_ESCALATION):** The manual lists possible water or adulteration in fuel as another observation for misfiring, but does not let us infer it from the symptom alone. Since the basic documented check has not resolved the problem, contact an authorised Royal Enfield service centre.
**Source:** [PDF page 122 (printed 120, `p0122`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=122); [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

---

## D028 — Diagnostic

**Rider:** The horn is weak.

**Assistant (CLARIFY):** Does the engine also fail to start?
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** yes

**Assistant (OEM_ESCALATION):** With a no-start symptom plus dim lights or a weak horn, the manual lists a weak or discharged battery or charging-circuit problem as possibilities. It directs you to an authorised Royal Enfield service centre. This observation does not prove which electrical fault is present.
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

---

## D029 — Diagnostic

**Rider:** The horn is weak.

**Assistant (CLARIFY):** Does the engine also fail to start?
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** no

**Assistant (UNSUPPORTED):** The manual uses a weak horn or dim lights as a clue in its no-start table. Since the engine starts, I cannot verify a specific cause from that table. Have an authorised Royal Enfield service centre check the symptom if it continues.
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

---

## D030 — Diagnostic

**Rider:** The engine will not start.

**Assistant (CLARIFY):** When you try to start it, are the lights dim or is the horn weak?
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** no

**Assistant (CLARIFY):** Are the ignition key and engine kill switch both in their ON or RUN positions?
**Source:** [PDF page 72 (printed 70, `p0072`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=72); [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** no

**Assistant (ACTION_WAIT_FEEDBACK):** The manual lists an off ignition or engine kill switch as a no-start check. Set the ignition and kill switch to ON or RUN, then tell me whether the engine starts. Do not hold the starter for more than five seconds in one attempt.
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121); [PDF page 72 (printed 70, `p0072`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=72); [PDF page 73 (printed 71, `p0073`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=73); [PDF page 74 (printed 72, `p0074`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=74)

**Rider:** still

**Assistant (CLARIFY):** Is the fuel level low, or is the final fuel-gauge bar blinking continuously?
**Source:** [PDF page 73 (printed 71, `p0073`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=73); [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** no

**Assistant (CLARIFY):** Have you found a blown fuse?
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121); [PDF page 112 (printed 110, `p0112`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=112)

**Rider:** no

**Assistant (CLARIFY):** Have you found a loose or disconnected spark plug, cap, or high-tension-cable connection?
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** no

**Assistant (OEM_ESCALATION):** The documented basic no-start checks have not resolved the problem. The manual says to have the motorcycle checked by an authorised Royal Enfield dealer or service centre. I cannot identify a further repair from these observations.
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

---

## D031 — Diagnostic

**Rider:** The engine will not start.

**Assistant (CLARIFY):** When you try to start it, are the lights dim or is the horn weak?
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** no

**Assistant (CLARIFY):** Are the ignition key and engine kill switch both in their ON or RUN positions?
**Source:** [PDF page 72 (printed 70, `p0072`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=72); [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** no

**Assistant (ACTION_WAIT_FEEDBACK):** The manual lists an off ignition or engine kill switch as a no-start check. Set the ignition and kill switch to ON or RUN, then tell me whether the engine starts. Do not hold the starter for more than five seconds in one attempt.
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121); [PDF page 72 (printed 70, `p0072`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=72); [PDF page 73 (printed 71, `p0073`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=73); [PDF page 74 (printed 72, `p0074`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=74)

**Rider:** fixed

**Assistant (CUSTOMER_REPORTED_RESOLVED):** You report that the engine now starts. I have recorded the documented check you tried, but that alone does not prove the root cause.

---

## D032 — Diagnostic

**Rider:** The engine stops when I put it in first gear.

**Assistant (CLARIFY):** Is the side-stand indicator glowing in the cluster?
**Source:** [PDF page 122 (printed 120, `p0122`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=122)

**Rider:** yes

**Assistant (ACTION_WAIT_FEEDBACK):** The table links first-gear engine cut-off with a glowing side-stand indicator. Put the side stand fully up before moving, then tell me whether the engine still stops when first gear is engaged.
**Source:** [PDF page 122 (printed 120, `p0122`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=122); [PDF page 74 (printed 72, `p0074`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=74)

**Rider:** still

**Assistant (OEM_ESCALATION):** The documented side-stand check does not explain or resolve this first-gear cut-off. The owner manual gives no further applicable owner remedy here; arrange inspection at an authorised Royal Enfield dealer or service centre.
**Source:** [PDF page 122 (printed 120, `p0122`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=122); [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

---

## D033 — Diagnostic

**Rider:** The engine will not start.

**Assistant (CLARIFY):** When you try to start it, are the lights dim or is the horn weak?
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** no

**Assistant (CLARIFY):** Are the ignition key and engine kill switch both in their ON or RUN positions?
**Source:** [PDF page 72 (printed 70, `p0072`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=72); [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** yes

**Assistant (CLARIFY):** Is the fuel level low, or is the final fuel-gauge bar blinking continuously?
**Source:** [PDF page 73 (printed 71, `p0073`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=73); [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** no

**Assistant (CLARIFY):** Have you found a blown fuse?
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121); [PDF page 112 (printed 110, `p0112`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=112)

**Rider:** no

**Assistant (CLARIFY):** Have you found a loose or disconnected spark plug, cap, or high-tension-cable connection?
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** no

**Assistant (OEM_ESCALATION):** The documented basic no-start checks have not resolved the problem. The manual says to have the motorcycle checked by an authorised Royal Enfield dealer or service centre. I cannot identify a further repair from these observations.
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

---

## D034 — Diagnostic

**Rider:** The engine will not start.

**Assistant (CLARIFY):** When you try to start it, are the lights dim or is the horn weak?
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** no

**Assistant (CLARIFY):** Are the ignition key and engine kill switch both in their ON or RUN positions?
**Source:** [PDF page 72 (printed 70, `p0072`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=72); [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** yes

**Assistant (CLARIFY):** Is the fuel level low, or is the final fuel-gauge bar blinking continuously?
**Source:** [PDF page 73 (printed 71, `p0073`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=73); [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** no

**Assistant (CLARIFY):** Have you found a blown fuse?
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121); [PDF page 112 (printed 110, `p0112`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=112)

**Rider:** yes

**Assistant (ACTION_WAIT_FEEDBACK):** With the ignition off, replace the defective fuse with a new fuse of the same rating. Never bridge it or use another rating. Tell me whether the engine starts; a persistent problem needs authorised service.
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121); [PDF page 112 (printed 110, `p0112`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=112)

**Rider:** fixed

**Assistant (CUSTOMER_REPORTED_RESOLVED):** You report that the engine now starts. I have recorded the documented check you tried, but that alone does not prove the root cause.

---

## D035 — Diagnostic

**Rider:** The engine will not start.

**Assistant (CLARIFY):** When you try to start it, are the lights dim or is the horn weak?
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** no

**Assistant (CLARIFY):** Are the ignition key and engine kill switch both in their ON or RUN positions?
**Source:** [PDF page 72 (printed 70, `p0072`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=72); [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** yes

**Assistant (CLARIFY):** Is the fuel level low, or is the final fuel-gauge bar blinking continuously?
**Source:** [PDF page 73 (printed 71, `p0073`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=73); [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** no

**Assistant (CLARIFY):** Have you found a blown fuse?
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121); [PDF page 112 (printed 110, `p0112`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=112)

**Rider:** yes

**Assistant (ACTION_WAIT_FEEDBACK):** With the ignition off, replace the defective fuse with a new fuse of the same rating. Never bridge it or use another rating. Tell me whether the engine starts; a persistent problem needs authorised service.
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121); [PDF page 112 (printed 110, `p0112`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=112)

**Rider:** still

**Assistant (CLARIFY):** Have you found a loose or disconnected spark plug, cap, or high-tension-cable connection?
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** no

**Assistant (OEM_ESCALATION):** The documented basic no-start checks have not resolved the problem. The manual says to have the motorcycle checked by an authorised Royal Enfield dealer or service centre. I cannot identify a further repair from these observations.
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

---

## D036 — Diagnostic

**Rider:** The engine will not start.

**Assistant (CLARIFY):** When you try to start it, are the lights dim or is the horn weak?
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** unknown

**Assistant (CLARIFY):** When you try to start it, are the lights dim or is the horn weak?
**Source:** [PDF page 121 (printed 119, `p0121`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=121)

**Rider:** unknown

**Assistant (AMBIGUOUS):** I cannot verify the observation needed to choose a documented next step. I will not infer a cause or suggest a repair from an unknown result. Please have an authorised service centre assess the symptom.

---

## D037 — Diagnostic

**Rider:** The ABS indicator is on.

**Assistant (CLARIFY):** Does the ABS lamp remain on after the motorcycle reaches about 5 km/h?
**Source:** [PDF page 66 (printed 64, `p0066`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=66); [PDF page 122 (printed 120, `p0122`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=122)

**Rider:** unknown

**Assistant (CLARIFY):** Does the ABS lamp remain on after the motorcycle reaches about 5 km/h?
**Source:** [PDF page 66 (printed 64, `p0066`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=66); [PDF page 122 (printed 120, `p0122`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=122)

**Rider:** unknown

**Assistant (AMBIGUOUS):** I cannot verify whether the ABS lamp remains on above about 5 km/h, so I cannot classify this as a normal self-check or a confirmed fault. The manual advises against riding if it remains on at higher speed; have an authorised service centre check it if you cannot verify safely.
**Source:** [PDF page 66 (printed 64, `p0066`)](royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf#page=66)

---
