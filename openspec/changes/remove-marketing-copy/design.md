## Context

`vnstock` contains public-facing example artifacts that still advertise a paid or promotional experience. The clearest instances are static example outputs under `examples/output/` and the quickstart notebook in `docs/1_quickstart_stock_vietnam.ipynb`, which includes a banner, an insiders-program pitch, and tier language.

The runtime Python package does not appear to generate these strings directly in the currently inspected source tree, so this change is a content cleanup rather than an API or provider behavior change.

## Goals / Non-Goals

**Goals:**

- Remove advertising, upsell, and sponsor-program copy from public example artifacts.
- Keep public examples and docs focused on neutral usage, data output, and setup guidance.
- Ensure regenerated example artifacts stay promotion-free.

**Non-Goals:**

- Do not change provider APIs, data behavior, or package exports.
- Do not redesign the examples themselves beyond replacing promotional text.
- Do not remove historical references from archived specs or old commits.

## Decisions

1. Update the public artifacts in place instead of adding a runtime sanitizer.

   Rationale: the problem is already present in checked-in content, not in active Python code. A runtime filter would add complexity without solving the source-of-truth issue for notebooks and sample outputs.

   Alternative considered: add a shared text normalizer for generated examples. Rejected because the current evidence points to a small set of static artifacts that can be corrected directly.

2. Preserve technical content and sample structure, only removing promotional language.

   Rationale: users still need example outputs and quickstart guidance, but they do not need advertising copy to understand the package.

   Alternative considered: delete the example artifacts entirely. Rejected because that would remove useful documentation value and make the package harder to evaluate.

3. Treat the notebook as a public artifact that must match the new tone.

   Rationale: the notebook is checked in and visible to users, so its prose should follow the same neutral standard as the output samples.

   Alternative considered: leave notebook prose untouched and only edit generated text files. Rejected because the notebook is a source artifact for future regeneration.

## Risks / Trade-offs

- [Sample drift] Example outputs may no longer match prior captured output exactly → regenerate or edit them consistently from the cleaned notebook/text source.
- [Missed copy] Similar promotional text may exist in other public docs → search the repository for related phrases before finishing.
- [Historical references] Some archived docs may still mention old tier concepts → keep the change scoped to active public-facing artifacts unless a follow-up change is needed.

## Migration Plan

1. Replace promotional prose in the quickstart notebook with neutral wording.
2. Update checked-in `examples/output/*.txt` artifacts so the visible sample output no longer includes banners or upsell text.
3. Grep the repository for the removed marketing phrases to confirm they no longer appear in active public examples/docs.
4. If any sample outputs are generated from the notebook or a script, regenerate them from the cleaned source so they stay aligned.
5. Roll back by restoring the previous content if a downstream documentation consumer depends on the old text.

## Open Questions

- Are there any additional public notebooks or docs outside the currently inspected paths that should be brought under the same neutral-copy standard?
