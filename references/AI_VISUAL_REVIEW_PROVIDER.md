# AI visual review provider contract

The skill owns the request and response schema but does not require a model, network access, or a desktop application. `prepare_ai_visual_review.py` creates an offline request. A provider may fill `ai-visual-review-v1` with advisory issues. `validate_ai_visual_review.py` validates the response, and `convert_ai_review_to_patch.py` creates an unapproved `visual-patch-v1` proposal.

Only a user-approved patch may be applied. `run_ai_visual_review.py` requires both `status=approved` and `approval.approved_by_user=true`, then records that a deterministic rerun is required. A rerun command is optional for local automation but never implied by an AI response.
