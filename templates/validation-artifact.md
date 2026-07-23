# Independent Validation Report

review_type: calibration | boundary | voice-blind-test | final-scorecard
reviewed_artifact: /absolute/path/to/project/SKILL.md
reviewed_revision: sha256:<64 lowercase hex of the exact final SKILL.md>
reviewer_task_or_session: <independent child task/session ID>
reviewer_independent: true
hard_fail_count: 0
verdict: PASS | FAIL

## Scope

State exactly what was reviewed and what was not.

## Evidence Examined

- Artifact paths:
- Source IDs sampled:
- Test cases used:

## Findings

### Hard failures

List every hard failure. If none, write `None`; do not omit `hard_fail_count: 0` above.

### Non-blocking findings

List limitations, warnings, and improvement suggestions separately.

## Reproduction

Give the exact test inputs and observable results so the parent Agent can read back and verify them.

## Verdict Rationale

Explain why the declared verdict follows from the evidence. `hard_fail_count` greater than zero requires `verdict: FAIL` and blocks installation.
