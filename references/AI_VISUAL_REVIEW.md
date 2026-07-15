# AI Visual Review Contract

`prepare_ai_visual_review.py` creates an offline review request from a rendered PNG, VisualSpec, and optional deterministic/semantic/font reports. It does not call a model and it never edits the image. A downstream multimodal reviewer may fill `issues` with category, severity, panel, description, recommendation, and confidence.

The review scope covers legend or annotation occlusion, panel labels, visual hierarchy, color discriminability, panel consistency, title redundancy, crowding, information density, and balance. The request records the image hash and dimensions so the reviewer is tied to a specific render.

AI findings remain advisory. Deterministic numeric, semantic, vector, font, layout, policy, and bundle checks are the primary gates. Any accepted suggestion requires a full deterministic rerender and QA pass. If no reviewer is available, keep status `pending_advisory` or `unavailable`; do not claim a visual pass.
