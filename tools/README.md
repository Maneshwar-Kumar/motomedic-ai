# Maintenance tools

- [check_repository_structure.py](check_repository_structure.py): read-only navigation and root-layout audit; run from the repository root.
- [render_docx.py](render_docx.py): vendored document renderer used in hosted visual verification.
- [update_architecture_decision_v05.py](update_architecture_decision_v05.py): TRD v0.5 update utility; historical references in generated prose retain their original context.

Put future maintenance utilities here. Keep provider/model calls and ingestion in their existing hosted workflows. A layout check must never print file contents or secrets.

## Private UI integration

- [prepare_arm_a_ui_wiring.py](prepare_arm_a_ui_wiring.py): freeze reviewed backend/UI build contexts; preserve earlier versions.
- [connect_arm_a_ui.py](connect_arm_a_ui.py): private managed credential connection and exact-image deployment with budget/context checks.
- [accept_arm_a_ui.py](accept_arm_a_ui.py): live question API and IAM-authenticated browser acceptance; credentials stay in memory.
- [cleanup_arm_a_expired.py](cleanup_arm_a_expired.py): read-only default inventory and narrowly scoped expired-session cleanup.

- [accept_arm_a_feedback.py](accept_arm_a_feedback.py): bounded live ownership denial and exact reviewed typed-feedback verification.
