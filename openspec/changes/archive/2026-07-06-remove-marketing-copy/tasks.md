## 1. Audit Public Copy

- [x] 1.1 Search public-facing docs and example artifacts for promotional or upsell language.
- [x] 1.2 Confirm the affected surfaces are limited to checked-in examples, notebooks, and docs.

## 2. Clean the Notebook Source

- [x] 2.1 Rewrite the quickstart notebook prose in `docs/1_quickstart_stock_vietnam.ipynb` to remove guest/community/sponsor tier language.
- [x] 2.2 Remove ad-removal and sponsor-program messaging from the notebook narrative while preserving the usage guidance.

## 3. Clean Example Outputs

- [x] 3.1 Remove the `THÔNG BÁO QUAN TRỌNG` / `VNSTOCK INSIDERS PROGRAM` banner block from checked-in files under `examples/output/`.
- [x] 3.2 Keep the sample output structure and data examples intact while replacing promotional lines with neutral text or trimming them entirely.

## 4. Regenerate or Sync Derived Artifacts

- [x] 4.1 If any output files are derived from the notebook or a script, regenerate them from the cleaned source.
- [x] 4.2 Ensure the checked-in outputs and notebook remain consistent after regeneration.

## 5. Verify Cleanup

- [x] 5.1 Grep the repo for the removed marketing phrases and confirm they no longer appear in active public examples/docs.
- [x] 5.2 Review the final diff to ensure no runtime API or provider changes were introduced.
