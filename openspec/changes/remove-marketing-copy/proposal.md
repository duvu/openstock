## Why

`vnstock` still ships public-facing example outputs and notebook content that reads like advertising or subscription upsell copy. The checked-in artifacts include a prominent `THÔNG BÁO QUAN TRỌNG` banner, a `VNSTOCK INSIDERS PROGRAM` pitch, and tier language such as guest/community/sponsor messaging, which makes the project feel promotional instead of focused on data delivery.

## What Changes

- Remove promotional and ad-like copy from checked-in example output files under `examples/output/`.
- Rewrite notebook text in `docs/1_quickstart_stock_vietnam.ipynb` to remove tiered upsell messaging and ad references.
- Replace any remaining public-facing marketing language in repo-owned examples/docs with neutral usage guidance.
- Keep the package API and provider behavior unchanged; this change is about content cleanup, not feature removal.

## Capabilities

### New Capabilities
- `no-promotional-copy`: public example outputs, notebooks, and documentation do not contain advertising, upsell banners, or tier-marketing language.

### Modified Capabilities

## Impact

- Checked-in example outputs in `vnstock/examples/output/`.
- Notebook content in `vnstock/docs/1_quickstart_stock_vietnam.ipynb`.
- Any tests or docs that assert on the visible sample text produced by those artifacts.
