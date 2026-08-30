# SafeGEO Human Audit

We audited a vertical-stratified sample of 60 SafeGEO cases (10 per product vertical). Two
annotators who were not involved in dataset construction or the GPT-5.5 annotation pipeline
independently labeled the evaluation-critical hard requirements, candidate-level hard status,
and utility ordering without seeing the pipeline labels. They also labeled 600 line--claim
pairs for evidence relation, truth status, and utility validity.

The table reports exact-match agreement. Candidate hard status uses
`satisfied`, `failed`, `unknown`, and `conflicting`; evidence relation uses `supports`,
`refutes`, `ambiguous`, and `context`; truth status uses `supported_true`,
`supported_false_or_absent`, `ambiguous`, and `context`; utility validity is binary.

| Audited label | Audit size | Annotator 1 vs. Annotator 2 | GPT-5.5 vs. Annotator 1 | GPT-5.5 vs. Annotator 2 |
|---|---:|---:|---:|---:|
| Hard-requirement extraction | 180 requirements | 100.0% | 100.0% | 100.0% |
| Candidate hard status | 540 candidate--requirement pairs | 76.7% | 78.8% | 75.2% |
| Pairwise utility ordering | 180 candidate pairs | 78.1% | 81.7% | 77.8% |
| Top candidate | 60 cases | 91.7% | 90.0% | 87.0% |
| Line-level evidence relation | 600 line--claim pairs | 83.3% | 85.8% | 80.3% |
| Line-level truth status | 600 line--claim pairs | 80.3% | 84.2% | 77.2% |
| Valid for utility | 600 line--claim pairs | 88.9% | 90.6% | 86.4% |

Agreement is highest for hard-requirement extraction, line-level evidence relation, and
utility validity. Most candidate-status and truth-status differences concern whether the
available evidence supports a decisive judgment, rather than direct `satisfied`/`failed` or
support/refutation contradictions. Utility ordering varies more, motivating the term
*benchmark-reference utility*.

An exact serialization audit compares every model-visible `user_query` with its
construction query. All 600 unique queries and all 40,800 expanded rows
match. The executable check is:

```bash
python scripts/audit_camera_ready_claims.py
```
