# FiinQuantX Boolean-Only Activation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. This repository session forbids subagent delegation, and the user requires exactly one final commit.

**Goal:** Remove both FiinQuantX approval-reference variables and fingerprints while retaining boolean runtime/persistence opt-ins and every other Gate A requirement.

**Architecture:** Runtime activation remains fail-closed on `VNSTOCK_FIINQUANTX_LICENSED`; warehouse persistence remains fail-closed on `VNALPHA_FIINQUANTX_PERSISTENCE_APPROVED`. Provider and persistence lineage keep provider, SDK/contract, source method, price basis, correlation, and ingestion-run metadata but no approval identifier or fingerprint. Compose, installed-host verification, docs, tests, and OpenSpec use the same boolean-only contract.

**Tech Stack:** Python 3.12/3.13, pytest, pandas, DuckDB, Bash, Docker Compose, Ruff, OpenSpec.

---

### Task 1: Make provider runtime activation boolean-only

**Files:**
- Modify: `vnstock/tests/unit/providers/test_fiinquantx_foundation.py`
- Modify: `vnstock/tests/unit/providers/test_fiinquantx_runtime_hardening.py`
- Modify: `vnstock/tests/live/providers/test_fiinquantx_live.py`
- Modify: `vnstock/tests/unit/core/runtime/test_plugin_runtime.py`
- Modify: `vnstock/vnstock/providers/fiinquantx/approval.py`
- Modify: `vnstock/vnstock/providers/fiinquantx/plugin.py`
- Modify: `vnstock/vnstock/core/runtime/plugin_runtime.py`

- [x] **Step 1: Write failing provider tests**

Replace the reference-dependent tests with observable boolean-only behavior:

```python
def test_boolean_acknowledgement_enables_runtime(monkeypatch) -> None:
    monkeypatch.setenv("VNSTOCK_FIINQUANTX_LICENSED", "true")

    approval = fiinquantx_license_approval()

    assert approval.acknowledged is True
    assert approval.approved is True
    assert approval.diagnostics() == {"acknowledged": True, "approved": True}
```

Add assertions that successful frames and provider/runtime diagnostics contain no key with `approval_reference` or `approval_fingerprint`.

- [x] **Step 2: Verify RED**

Run:

```bash
cd vnstock
uv run pytest -q \
  tests/unit/providers/test_fiinquantx_foundation.py \
  tests/unit/providers/test_fiinquantx_runtime_hardening.py \
  tests/unit/core/runtime/test_plugin_runtime.py
```

Expected: failures showing boolean acknowledgement is not approved without a reference and legacy fingerprint fields remain present.

- [x] **Step 3: Implement the minimal provider contract**

Reduce `FiinQuantXLicenseApproval` to the boolean state:

```python
@dataclass(frozen=True, slots=True)
class FiinQuantXLicenseApproval:
    acknowledged: bool

    @property
    def approved(self) -> bool:
        return self.acknowledged

    def diagnostics(self) -> dict[str, bool]:
        return {"acknowledged": self.acknowledged, "approved": self.approved}
```

Construct it only from `VNSTOCK_FIINQUANTX_LICENSED`; remove reference normalization, hashing, frame attrs, diagnostic fields, runtime safe-key propagation, and the live-test reference precondition.

- [x] **Step 4: Verify GREEN**

Run the Task 1 pytest command and:

```bash
cd vnstock
uv run ruff check vnstock/providers/fiinquantx vnstock/core/runtime/plugin_runtime.py \
  tests/unit/providers tests/unit/core/runtime/test_plugin_runtime.py
uv run ruff format --check vnstock/providers/fiinquantx vnstock/core/runtime/plugin_runtime.py \
  tests/unit/providers tests/unit/core/runtime/test_plugin_runtime.py
```

Expected: all commands exit 0.

### Task 2: Make vnalpha persistence activation boolean-only

**Files:**
- Modify: `vnalpha/tests/test_vnstock_source_policy.py`
- Modify: `vnalpha/tests/test_ingestion_persistence.py`
- Modify: `vnalpha/tests/test_fiinquantx_membership_ingestion.py`
- Modify: `vnalpha/src/vnalpha/clients/vnstock/source_policy.py`
- Modify: `vnalpha/src/vnalpha/ingestion/persistence.py`
- Modify: `vnalpha/src/vnalpha/ingestion/sync_membership.py`

- [x] **Step 1: Write failing persistence tests**

Define boolean-only approval and absence of fingerprint lineage:

```python
def test_boolean_acknowledgement_enables_persistence(monkeypatch) -> None:
    monkeypatch.setenv("VNALPHA_FIINQUANTX_PERSISTENCE_APPROVED", "true")

    approval = fiinquantx_persistence_approval()

    assert approval.approved is True
    assert approval.diagnostics() == {"acknowledged": True, "approved": True}
    assert validate_persistence_source("fiinquantx") == "FIINQUANTX"
```

Change OHLCV and membership persistence expectations so serialized lineage preserves basis, method, SDK/contract, and correlation but contains neither `approval_reference` nor `approval_fingerprint`.

- [x] **Step 2: Verify RED**

Run:

```bash
cd vnalpha
uv run pytest -q \
  tests/test_vnstock_source_policy.py \
  tests/test_ingestion_persistence.py \
  tests/test_fiinquantx_membership_ingestion.py
```

Expected: failures from the missing reference and legacy fingerprint persistence.

- [x] **Step 3: Implement the minimal persistence contract**

Reduce `FiinQuantXPersistenceApproval` to `acknowledged: bool`, make `approved` equal that boolean, and return only `acknowledged`/`approved` diagnostics. Remove hashing/regex imports, reference parsing, legacy reference remediation text, safe-lineage fingerprint keys, and fingerprint injection from OHLCV and membership ingestion.

- [x] **Step 4: Verify GREEN**

Run the Task 2 pytest command and focused Ruff check/format for the listed Python files. Expected: exit 0.

### Task 3: Align deployment and installed-host verification

**Files:**
- Modify: `packaging/tests/test_verify_mvp1_warehouse.sh`
- Modify: `packaging/scripts/openstock-verify`
- Modify: `docker-compose.yml`
- Modify: `.env.example`
- Modify: `packaging/config/vnalpha.env`
- Modify: `packaging/deb/etc/vnalpha/vnalpha.env`

- [x] **Step 1: Write failing shell acceptance cases**

Update the verifier fixture so this environment passes without either reference:

```bash
VNSTOCK_FIINQUANTX_LICENSED=true \
VNALPHA_FIINQUANTX_PERSISTENCE_APPROVED=true \
OPENSTOCK_REFERENCE_SOURCE=VCI \
bash packaging/scripts/openstock-verify --mvp1
```

Keep negative cases for each missing/false boolean, wrong VCI reference source, and missing Gate A capability. Add a repository assertion that deployment templates do not contain either retired variable name.

- [x] **Step 2: Verify RED**

Run:

```bash
bash packaging/tests/test_verify_mvp1_warehouse.sh
```

Expected: the boolean-only positive case fails because the verifier still requires references.

- [x] **Step 3: Implement boolean-only verifier and Compose contract**

Delete the legacy reference validator, both local reference variables, and both reference checks. Keep explicit `truthy` checks for the runtime and persistence booleans. Remove the two reference environment entries from every Compose service and installed/config template.

- [x] **Step 4: Verify GREEN**

Run:

```bash
bash -n packaging/scripts/openstock-verify
bash packaging/tests/test_verify_mvp1_warehouse.sh
bash packaging/test/test_mvp1_start.sh
docker compose config >/dev/null
```

Expected: all commands exit 0.

### Task 4: Synchronize documentation and OpenSpec

**Files:**
- Modify: `vnstock/docs/providers/FIINQUANTX.md`
- Modify: `vnstock/docs/providers/FIINQUANTX_LICENSE_DECISION.md`
- Modify: `packaging/docs/OPERATOR.md`
- Modify: `openspec/changes/fiinquantx-provider-integration/proposal.md`
- Modify: `openspec/changes/fiinquantx-provider-integration/design.md`
- Modify: `openspec/changes/fiinquantx-provider-integration/specs/fiinquantx-provider-integration/spec.md`
- Modify: `openspec/changes/fiinquantx-provider-integration/tasks.md`
- Modify: `openspec/changes/fiinquantx-provider-integration/validation.md`
- Modify: `openspec/active-changes.yaml`

- [x] **Step 1: Replace the policy text**

Document that the two explicit booleans are the only activation switches, both default false, credentials remain local, and every other license/data/read-only restriction remains unchanged. Remove approval-reference and fingerprint requirements from Gate A, task evidence, lineage, operator examples, and decision templates.

- [x] **Step 2: Verify no runtime/config dependency remains**

Run:

```bash
rg -n --hidden --glob '!ya-router/**' --glob '!.git/**' \
  '<retired-runtime-reference>|<retired-persistence-reference>|<retired-fingerprint-fields>' .
```

Expected: no output after replacing the temporary retired-name note in the approved design with generic migration wording.

- [x] **Step 3: Validate OpenSpec**

Run:

```bash
openspec validate fiinquantx-provider-integration --strict
openspec validate tui-terminal-rendering-integrity --strict
openspec validate chat-data-provisioning-contract --strict
```

Expected: all commands exit 0.

### Task 5: Run complete local verification before candidate commit

**Files:**
- Review all intended tracked/untracked files; exclude `ya-router/`, `.env`, `.debug-journal.md`, and other local artifacts.

- [x] **Step 1: Run full component and repository gates**

Run vnalpha full pytest/Ruff/format, vnstock full offline pytest/Ruff/format, package verification, secret scan, root Make validation targets, strict OpenSpec validation, `git diff --check`, and the mandatory implementation-failures checklist.

- [x] **Step 2: Review the full diff and staged scope**

Confirm all 14 issues are covered, no secret/licensed rows are present, no research-only boundary is weakened, and `ya-router/` remains unstaged.

### Task 6: Create one candidate commit and verify exact SHA on localhost

**Files:**
- No new source files beyond Tasks 1-5.

- [ ] **Step 1: Create the single candidate commit**

Stage only intended repository files and commit once using the repository's dominant message style. Do not create intermediate commits.

- [ ] **Step 2: Build and deploy exact SHA on localhost**

Preserve existing FiinQuantX credentials without printing them, build the current `vnstock-service` image with `VNSTOCK_INSTALL_FIINQUANTX=true`, bind only `127.0.0.1:6900`, and use clean dedicated warehouse/knowledge/log paths. Configure the two retained booleans true, VCI reference source, ya-router `127.0.0.1:7071`, model `thiendu`, and raw LLM storage false.

- [ ] **Step 3: Drive the real Gate A surfaces**

Verify service health/capabilities, bounded FiinQuantX equity/index OHLCV and membership via `PluginRuntime`, VCI reference bootstrap, vnalpha persistence with raw-unadjusted lineage, LLM preflight, natural-language `Phân tích FPT`, slash parity, TUI result/copy/F12 behavior, restart/reuse, explicit provider failure, LLM degradation, and SDK-disabled base behavior. Record only sanitized metadata.

- [ ] **Step 4: Amend only if exact-SHA QA exposes a defect**

If a defect is found, add a failing test, fix it, amend the same single commit, and rerun all exact-SHA gates.

### Task 7: Publish one PR and close the 14 issues

**Files:**
- GitHub metadata only.

- [ ] **Step 1: Push the candidate branch and run exact-SHA CI**

Push `agent/complete-open-issues`, inspect every required workflow job, and require green status for the exact SHA used in localhost acceptance.

- [ ] **Step 2: Create exactly one PR**

Create one PR with summary, root causes, behavioral impact, sanitized command evidence, exact SHA, localhost/FiinQuantX/LLM/TUI acceptance, and issue linkage.

- [ ] **Step 3: Post sanitized evidence and close issues**

Close child issues `#173`, `#174`, `#175`, `#176`, `#178`, `#179`, `#180`, `#190`, `#191`, `#192`; then close `#189`, `#193`, `#181`, and finally `#162`, only after each issue's acceptance evidence exists.
