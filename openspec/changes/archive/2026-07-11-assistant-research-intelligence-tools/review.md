# Review: Assistant Research Intelligence Tools

## Verdict

The first implementation merged in PR #40 established the core taxonomy, deterministic plans, bounded tools, research templates, and final-answer policy. It did not fully close the OpenSpec because several components existed without being connected to the runtime answer path.

This follow-up closes those integration gaps.

## Findings before this follow-up

### 1. Groundedness validator was not invoked

`GroundednessValidator` existed, but `AnswerSynthesizer` returned model output after parsing and a narrow context check. Unsupported source references, unsupported numeric claims, and missing-data omissions could therefore reach the user.

### 2. Research templates were not supplied to the model

Intent-specific contracts defined required fields, allowed framing, caveats, and missing-data rules, but `_build_synthesis_messages()` did not include them.

### 3. The synthesis envelope did not require source references

`AssistantAnswer` supported `grounded_source_refs` and `research_metadata`, while the system prompt still described only the original five-field response envelope.

### 4. There was no dedicated research-answer audit record

Assistant sessions and LLM traces were persisted, but the OpenSpec-required audit metadata was not stored as a queryable record containing intent, tools, artifact references, freshness, groundedness, policy result, caveats, and correlation ID.

### 5. Policy-sensitive answers lacked a deterministic fail-closed rewrite path

Shortlist and scenario answers could be rejected by policy checks, but there was no guaranteed deterministic research-only answer assembled from tool payloads when model output was ungrounded or used unsuitable wording.

### 6. OpenSpec completion evidence was missing

The implementation did not update the OpenSpec checklist, add validation evidence, or provide operator documentation for the integrated runtime behavior.

## Remediation implemented

### Pre-synthesis gate

Research-intelligence plans now validate that:

```text
- every planned deterministic tool produced an output;
- the primary payload is structured;
- required template fields are present when data is available;
- partial payloads disclose missing data explicitly.
```

Missing tool outputs and silent contract violations fail before an LLM call.

### Bounded synthesis contract

The synthesizer now receives:

```text
research_template
valid_grounded_source_refs
required_artifacts
tool_outputs
```

The expected JSON envelope includes:

```text
grounded_source_refs
research_metadata
```

When the model omits source references, the runtime may attach only references derived deterministically from the executed plan and tool payloads.

### Post-synthesis gate

Research answers are checked for:

```text
- valid tool/artifact source references;
- numeric claims represented in structured payloads;
- explicit disclosure of tool-reported missing data;
- non-empty basis and caveats;
- research-only policy wording;
- mandatory disclaimer for shortlist and scenario workflows.
```

### Deterministic fallback

If an LLM call fails, parsing fails, grounding fails, or policy validation fails, the runtime builds a deterministic answer directly from structured tool payloads. The fallback is revalidated before it can be returned.

Existing market/sector caveat-first and unsafe-language behavior remains fail-closed.

### Research answer audit

A new `research_answer_audit` table and writer persist:

```text
assistant_session_id
intent
tools
artifact references
dataset freshness
groundedness result
policy result
caveats
correlation ID
```

A deep research answer is not returned successfully unless its validation metadata exists and the audit record is persisted.

## Architecture assessment

The design remains within the intended trust boundary:

```text
user prompt
  -> deterministic policy
  -> intent classifier
  -> deterministic plan
  -> central tool policy
  -> bounded read-only tools
  -> pre-synthesis grounding gate
  -> task-routed synthesis
  -> post-synthesis grounding and policy gates
  -> deterministic fallback when needed
  -> research answer audit
```

The assistant receives no raw SQL, filesystem, unrestricted code, broker, account, allocation, or execution capability.

## Remaining dependency boundaries

The tools in this OpenSpec compose currently available persisted artifacts. Dedicated implementations from the deep-analysis, shortlist, scenario, and historical-evidence OpenSpecs may later replace internal calculations behind the same tool contracts. The assistant contract should remain stable when that happens.

## Completion assessment

Runtime implementation and focused tests are present for all OpenSpec sections. Standard repository validation commands remain the final merge gate and are recorded separately in `validation.md`.
