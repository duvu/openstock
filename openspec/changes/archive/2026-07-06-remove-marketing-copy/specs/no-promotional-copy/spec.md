## ADDED Requirements

### Requirement: Public example outputs shall not include promotional copy
The repository SHALL keep checked-in public example output files free of advertising banners, upsell text, subscription pitches, and sponsor-program promotion.

#### Scenario: Example output is reviewed
- **WHEN** a user opens a checked-in file under `examples/output/`
- **THEN** the visible content contains only neutral example text and data output, with no marketing banner or upsell messaging

### Requirement: Public notebooks and docs shall use neutral wording
Public-facing notebooks and documentation SHALL describe usage, limits, and examples in factual, product-focused terms and SHALL NOT present paid tiers, ad-removal messaging, or sponsor-program promotion as part of the current product experience.

#### Scenario: Quickstart notebook is read
- **WHEN** a reader opens `docs/1_quickstart_stock_vietnam.ipynb`
- **THEN** the notebook explains the package without guest/community/sponsor tier language or ad-related selling points

### Requirement: Regenerated sample artifacts shall remain promotion-free
Any maintained example output or notebook regenerated from repository content SHALL continue to satisfy the promotion-free wording rules after regeneration.

#### Scenario: Maintainer regenerates artifacts
- **WHEN** the public example outputs or notebook are regenerated from source materials
- **THEN** the resulting checked-in artifacts still omit promotional, upsell, and ad-related language
