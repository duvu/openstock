# Research answer evaluation fixtures

`vnalpha eval research-answers` evaluates a fixed, deterministic local YAML
corpus. It is offline-only: do **not** call an LLM, a live data source, or a
warehouse when authoring or running these cases. Every answer, fact, claim, and
artifact reference belongs in the fixture itself.

## Corpus layout

The CI corpus is exactly `evals/goldens/` with one directory per family:

| Family | Directory | Seed fixture | Family-specific fields |
| --- | --- | --- | --- |
| `research_answer` | `research_answers/` | `research_answers/score_summary.yaml` | none |
| `scenario_plan` | `scenario_plans/` | `scenario_plans/monitor_breakout.yaml` | `monitoring`, `confirmation`, `invalidation` |
| `policy_refusal` | `policy_refusals/` | `policy_refusals/refuse_execution.yaml` | `refusal`, `reframing` |
| `historical_evidence` | `historical_evidence/` | `historical_evidence/small_sample.yaml` | `sample_size`, `minimum_sample_size`, `caveat` |
| `shortlist` | `shortlist/` | `shortlist/research_watchlist.yaml` | `research_only_constraints` |

Start from the corresponding seed, retain its directory/family pairing, and
give every case a unique `case_id`. Keep deliberately failing fixtures only in
`evals/goldens/failing/`; the default CI corpus does not discover that tree.

## Typed YAML contract

All fields are required unless a family-specific field is listed above.
Unknown fields are rejected. `claim_id` and `fact_id` use lower snake case.

```yaml
case_id: research-score-summary
family: research_answer
input: Summarize the current research evidence for FPT.
expected_intent: explain_symbol
required_tools: []
required_claims:
  - claim_id: score_summary
    fact_ids: [candidate_score]
facts:
  - fact_id: candidate_score
    artifact_id: fixture://research/fpt_candidate_score
    value: FPT has a candidate score of 72.
forbidden_phrases: [guaranteed]
required_caveats: []
artifact_manifest: [fixture://research/fpt_candidate_score]
observation:
  answer_text: FPT has a candidate score of 72. Volume confirmation is missing.
  caveats: []
  missing_data: [Volume confirmation is missing.]
  observed_claims:
    - claim_id: score_summary
      fact_ids: [candidate_score]
  artifact_references: [fixture://research/fpt_candidate_score]
  refused: false
  reframed: false
missing_data_expectation: disclose_missing_data
policy_expectation: research_only
```

`observation` is the complete typed input to the checks: `answer_text`,
`caveats`, `missing_data`, `observed_claims`, `artifact_references`, `refused`,
and `reframed`. It is static fixture data, not a prompt to generate an answer.
Each required claim must cite declared static `facts`; each fact must cite an
artifact in `artifact_manifest`; observed claims must use only the declared
claim/fact identities.

Use only these enums:

- `missing_data_expectation`: `not_applicable` or `disclose_missing_data`.
- `policy_expectation`: `research_only` or `refuse_or_reframe`.

For a scenario plan add all three monitoring strings; for a refusal add both
refusal strings and set `observation.refused` or `observation.reframed` true;
for historical evidence add the sample fields and include `caveat` whenever
`sample_size < minimum_sample_size`; for a shortlist add at least one
research-only constraint. The five seed files above are complete examples of
each family.

## Logical artifact URIs and checks

Artifacts are opaque logical identifiers, never file paths or external URLs:
`fixture://<authority>/<logical-name>`. The authority starts with a letter and
may contain letters, digits, `_`, and `-`; the logical name may also contain
`.` and `-`. Paths, traversal, queries, and fragments are invalid. Artifact
references must appear in the manifest and refer to its logical URI exactly.

The runner checks grounded claims, required caveats, missing-data disclosure,
policy wording/refusal behavior, and artifact-reference integrity. It prints
stable `FAIL` lines followed by one `SUMMARY`; `--ci` exits nonzero when any
discovery, load, adapter, or check failure exists. A non-CI run still prints
the report but does not force a failure exit for a failing report.

## Local commands

```bash
uv run vnalpha eval research-answers
uv run vnalpha eval research-answers --ci
make eval-research-answers
```

Use the Make target in CI; it delegates exactly to the `--ci` command and
preserves its exit status.
