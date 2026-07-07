# 10. OpenStock Roadmap — Terminal-first Research Workspace & Data Platform

## Strategic direction

OpenStock is a local-first research system for Vietnamese equities.

It is split into two product layers:

```text
vnstock-service  = Docker-managed data platform service
vnalpha          = terminal-first research workspace
```

The roadmap now prioritizes a deployable POC before adding more analytical complexity.

The selected deployment model is:

```text
Data Platform:
  Docker Compose
  - vnstock-service
  - vnalpha-worker
  - shared DuckDB bind mount
  - optional scheduler

Terminal Workspace:
  Debian package
  - vnalpha CLI/TUI
  - direct terminal usage similar to OpenCode
  - reads DuckDB warehouse

Storage:
  DuckDB file
  /var/lib/openstock/warehouse/warehouse.duckdb
```

The OpenCode-inspired long-term direction is:

```text
vnalpha tui
  -> vnalpha local runtime/server
      -> session/message/command/tool/event APIs
      -> permission engine
      -> DuckDB warehouse
      -> vnstock-service
      -> vnalpha-worker jobs
```

The TUI remains terminal-native. The runtime/server becomes the orchestration layer behind the TUI, CLI, and future clients.

## Non-negotiable boundaries

```text
No broker login
No account APIs
No order placement
No portfolio execution
No transfer/margin/trading endpoints
No auto-trading
No LLM-only prediction engine
No investment-advice workflow
No arbitrary shell execution from the research chat
```

AI is allowed only for explanation, critique, summarization, planning, and research assistance over deterministic artifacts.

---

## Roadmap tracks

The system should evolve across five tracks:

```text
Track A — Data Platform
  vnstock-service, data contracts, worker jobs, DuckDB warehouse, scheduler

Track B — Terminal Workspace
  vnalpha CLI/TUI, Debian package, chat/workspace UX, command palette

Track C — Runtime/Server
  local server, session/message APIs, event stream, command/tool execution

Track D — Governance & Safety
  permission policy, agent modes, research-only hard-deny rules, audit traces

Track E — Research Capability
  features, scoring, outcomes, calibration, pattern engine, reports, ML ranking
```

The roadmap below orders these tracks into implementable phases.

---

## Phase R0 — POC Baseline Stabilization

### Goal

Freeze the current end-to-end alpha discovery baseline before packaging and deployment.

### Core question

Can the current local pipeline reliably produce a daily watchlist from `vnstock-service` data?

### Scope

```text
vnstock-service -> vnalpha sync -> DuckDB -> canonical_ohlcv -> feature_snapshot -> candidate_score -> daily_watchlist -> CLI/TUI
```

### Deliverables

```text
- fix remaining data drift and accuracy issues
- finish migration safety for existing DuckDB files
- stabilize feature status taxonomy
- verify lineage propagation into candidate_score and daily_watchlist
- stabilize quality-as-of lookup
- stabilize filter fail-closed behavior
- stabilize outcome metric policy handling
- keep current CLI/TUI usable for demo
```

### Definition of Done

```text
- `vnalpha init` succeeds on a fresh warehouse
- sync symbols/ohlcv/index succeeds for a demo universe
- build canonical/features succeeds for a fixed demo date
- score/watchlist succeeds for a fixed demo date
- known drift/lineage/quality findings are closed or explicitly deferred
- no broker/order/account capability exists
```

---

## Phase R1 — POC Deployment Architecture

### Goal

Document and implement the selected POC deployment architecture.

### Core question

Can OpenStock be installed and operated on a single host without ad-hoc manual steps?

### Deployment decision

```text
Docker manages the data platform and batch jobs.
Debian package manages the terminal user experience.
DuckDB is the persisted analytical warehouse file shared by both sides.
```

### Deliverables

```text
vnalpha/docs/11-deployment-architecture.md
Docker Compose data platform design
vnalpha-worker job model
DuckDB warehouse bind mount model
vnalpha Debian terminal app model
systemd data-platform wrapper design
```

### Definition of Done

```text
- deployment architecture is documented
- roles of vnstock-service, vnalpha-worker, DuckDB, and vnalpha.deb are clear
- TUI is explicitly host-native, not a background Docker daemon
- DuckDB concurrency rules are documented
- data platform remains localhost-only by default
```

---

## Phase R2 — Deploy & Verify POC

### Goal

Make deployment repeatable and verifiable.

### Core question

Can a fresh host deploy the POC, run a smoke pipeline, and prove the system is ready for demo?

### Deliverables

```text
openstock-data-platform Docker Compose
vnalpha-worker Dockerfile
vnalpha.deb packaging scripts
/usr/bin/vnalpha launcher
/usr/bin/vnalpha-poc launcher
/etc/vnalpha/vnalpha.env
/etc/openstock/openstock.env
openstock-data-platform.service
openstock-verify
openstock-backup-warehouse
rollback documentation
fresh-host smoke-test checklist
```

### Required verification checks

```text
- docker and docker compose availability
- openstock-data-platform systemd status
- vnstock-service container status
- GET /healthz returns ok
- forbidden endpoints return 404: /v1/order, /v1/account, /v1/portfolio, /v1/trading
- warehouse path exists
- warehouse schema initializes
- small demo pipeline can sync/build/score
- vnalpha --help works
- vnalpha watchlist --date <demo-date> works
- TUI entrypoint import/help check works without launching interactive UI in CI mode
- optional assistant check warns, not fails, if LLM env is absent
```

### Definition of Done

```text
- fresh host can start data platform
- fresh host can install vnalpha.deb
- `openstock-verify` passes required checks
- warehouse backup is created before risky migrations/upgrades
- rollback package/container/warehouse procedures are documented
- user can run `vnalpha tui` directly from terminal/SSH/tmux
```

---

## Phase R3 — Terminal Workspace POC

### Goal

Make `vnalpha tui` the primary analyst entrypoint, similar to OpenCode's terminal-first UX.

### Core question

Can an analyst open one terminal app and perform the daily research workflow without switching between many commands?

### Deliverables

```text
persistent split-pane TUI shell
watchlist workspace panel
symbol detail panel
quality/rejected data panel
outcome/calibration panel
persistent chat panel
command palette/slash command help
trace/status panel
keyboard shortcuts
read-only demo mode
```

### Required commands

```text
/watchlist today
/watchlist <date>
/scan VN30
/explain <symbol>
/compare <symbol1> <symbol2>
/quality <symbol>
/lineage <symbol>
/outcomes <date>
/help
```

### Definition of Done

```text
- `vnalpha tui --date <demo-date>` starts reliably
- user can inspect watchlist and symbol detail from TUI
- slash commands use the same command execution path as CLI
- TUI does not require Docker interactive execution
- no command exposes trading or broker execution
```

---

## Phase R4 — OpenCode-style Chat Workspace Completion

### Goal

Turn the current chat prototype into a stateful research chat workspace.

### Core question

Can the chat behave like a research control panel instead of a one-shot input box?

### Deliverables

```text
chat_session table usage
chat_message persistence
multi-turn deterministic context
plan preview / approve / cancel
trace timeline rendering
chat-local commands
command routing through unified CommandExecutor
assistant/tool trace linkage
staged output or streaming fallback
```

### Chat-local commands

```text
/new
/clear
/context
/plan
/trace
/help
```

### Definition of Done

```text
- every user/assistant turn is persisted
- chat can recover recent context from transcript and deterministic state
- slash commands and assistant tool calls create traceable records
- plan approval is explicit before pipeline/admin actions
- tool traces are visible in the chat timeline
- research-only hard-deny rules are enforced
```

---

## Phase R5 — Local Runtime/Server Layer

### Goal

Introduce a local runtime/server behind TUI and CLI, following the OpenCode architectural pattern.

### Core question

Can the TUI become a client of a local research runtime instead of directly owning orchestration logic?

### Proposed command

```bash
vnalpha serve --host 127.0.0.1 --port 6901
```

### Minimum APIs

```text
GET  /health
GET  /config
GET  /warehouse/status
GET  /data/health
GET  /sessions
POST /sessions
GET  /sessions/{session_id}
GET  /sessions/{session_id}/messages
POST /sessions/{session_id}/messages
POST /sessions/{session_id}/commands
GET  /events
POST /pipeline/run
GET  /pipeline/status
POST /verify
POST /backup
```

### Deliverables

```text
local runtime process
runtime client used by TUI
session API
message API
command API
event stream
pipeline job adapter
verify/backup adapters
OpenAPI documentation
```

### Definition of Done

```text
- TUI can connect to local runtime
- runtime can also run headless for automation
- session/message state is first-class
- command execution is centralized
- event stream supports realtime TUI progress updates
- runtime binds to 127.0.0.1 by default
```

---

## Phase R6 — Event Stream & Tool Trace Runtime

### Goal

Make all long-running operations observable from TUI and CLI.

### Core question

Can the user see what the system is doing while it syncs, scores, verifies, or calls tools?

### Event types

```text
pipeline.started
pipeline.step.running
pipeline.step.completed
pipeline.step.failed
tool.running
tool.completed
tool.failed
assistant.plan.created
assistant.answer.created
verify.check.ok
verify.check.warn
verify.check.fail
warehouse.backup.created
permission.requested
permission.approved
permission.denied
```

### Deliverables

```text
event schema
event persistence or replay buffer
server-sent event stream
TUI event timeline
CLI event follow mode
trace correlation IDs
```

### Definition of Done

```text
- long-running operations stream status
- TUI can render progress without blocking
- every tool/pipeline run has trace correlation
- failed steps show actionable error messages
```

---

## Phase R7 — Permission Policy & Agent Modes

### Goal

Add a domain-specific permission model inspired by OpenCode's ask/allow/deny model.

### Core question

Can the system safely separate read-only research from pipeline/admin operations?

### Agent modes

```text
Explore
  read-only market/watchlist/features/outcomes

Research
  explain/compare/scan/review research artifacts

Pipeline
  sync/build/score/evaluate with explicit approval

Admin
  verify/backup/deploy diagnostics with strict approval
```

### Permission states

```text
allow
ask
deny
hard_deny
```

### Hard-deny operations

```text
broker_order
account_access
portfolio_mutation
margin
transfer
trading
automated_execution
arbitrary_shell
```

### Deliverables

```text
/etc/vnalpha/policy.yaml
policy loader
permission evaluator
approval prompts in TUI
permission audit records
agent mode switcher
hard-deny tests
```

### Definition of Done

```text
- read-only commands run without approval in Explore mode
- pipeline writes require approval
- backup requires approval
- restore is denied by default
- hard-deny operations cannot be bypassed by prompt text
- permission decisions are traceable
```

---

## Phase R8 — Research Context & Project Memory

### Goal

Give the assistant deterministic context without relying on hidden memory or vague prompts.

### Core question

Can `vnalpha` maintain explicit project/research context similar to a project instruction file?

### Deliverables

```text
VNALPHA.md or research_context.yaml
/vnalpha init-context command
universe defaults
scoring policy version
risk policy version
demo date
feature availability
forbidden actions
explanation style
watchlist thresholds
```

### Definition of Done

```text
- context file is generated and editable
- assistant reads context explicitly
- context changes are visible and auditable
- no hidden assumptions are required for core workflows
```

---

## Phase R9 — Team Deployment Hardening

### Goal

Move from single-user POC to controlled internal team usage.

### Core question

Can multiple users operate the system safely on an internal host without corrupting the warehouse or exposing data service publicly?

### Deliverables

```text
internal host install guide
user/group permissions for /var/lib/openstock
read-only TUI mode while writer job runs
pipeline writer lock
warehouse backup schedule
log rotation
package versioning
signed packages or checksum validation
operator runbook
```

### Definition of Done

```text
- multiple users can run TUI read workflows
- only one writer pipeline can run at a time
- backup/restore is operator-controlled
- data service remains internal/local by default
- deployment has a documented support/runbook path
```

---

## Phase R10 — Research Capability Hardening

### Goal

Improve the quality of research outputs after the platform is deployable.

### Core question

Are watchlist candidates stable, explainable, and useful across different market regimes?

### Deliverables

```text
outcome calibration reports
score bucket analysis
setup-type performance analysis
risk-flag performance analysis
feature drift monitoring
quality status dashboard
regime-aware scoring review
```

### Definition of Done

```text
- every candidate has lineage and feature evidence
- score buckets can be evaluated historically
- risk flags have outcome impact analysis
- poor-performing setup types are visible
- feature/data drift is detectable
```

---

## Phase R11 — Advanced Pattern Engine

### Goal

Add more setup families after v1 is validated.

### Candidate patterns

```text
VCP
HEALTHY_PULLBACK
DISTRIBUTION
RELATIVE_STRENGTH_LEADER
BASE_BREAKDOWN
SHAKEOUT_RECOVERY
```

### Definition of Done

```text
- each detector is deterministic and auditable
- each detector has synthetic tests
- each detector has outcome summary
- detector config is versioned
- added patterns improve research triage, not investment advice
```

---

## Phase R12 — Reports, Journal & Review Workflow

### Goal

Turn daily scanning into a repeatable research process.

### Core question

Can users record reasoning, compare later outcomes, and generate grounded reports?

### Deliverables

```text
research_note and journal workflow
daily report generator
weekly review report
watchlist review notes
outcome comparison against original reasoning
export to markdown
```

### Definition of Done

```text
- notes attach to date/symbol/watchlist/session
- reports cite source data IDs
- AI drafts reports only from grounded artifacts
- later outcomes can be compared with original thesis
```

---

## Phase R13 — Backtest Lab

### Goal

Validate strategy rules beyond simple forward outcome tracking.

### Core question

Can users test entry/exit assumptions and compare performance by market regime?

### Deliverables

```text
backtest_run table
backtest_result table
entry/exit simulation
fee/slippage assumptions
parameter testing
regime-level performance report
benchmark comparison
```

### Definition of Done

```text
- next-session entry assumption supported
- invalidation/stop exits supported
- fees/slippage configurable
- results split by year, sector, regime
- benchmark comparison available
- outputs remain research-only
```

---

## Phase R14 — ML Ranking

### Goal

Rank setups using historical outcomes without replacing deterministic logic.

### Core question

Can ML improve triage after enough labeled pattern outcomes exist?

### Deliverables

```text
training dataset builder
feature leakage checks
ranker model
model registry metadata
ranking explanation
performance by regime
```

### Definition of Done

```text
- ML trains only on historical outcome labels
- no future leakage
- model output is ranking/triage only
- deterministic evidence remains visible
- AI/ML cannot become an investment-advice engine
```

---

## Recommended MVP cuts

### MVP Cut 1 — Deployable POC

Stop here first:

```text
R0 POC baseline stabilization
R1 POC deployment architecture
R2 deploy & verify POC
R3 terminal workspace POC
```

Outcome:

```text
A user can install the system, verify it, run the data pipeline, and open `vnalpha tui` directly from terminal.
```

### MVP Cut 2 — OpenCode-style Research Workspace

Stop here second:

```text
R4 chat workspace completion
R5 local runtime/server
R6 event stream and tool trace runtime
R7 permission policy and agent modes
R8 research context and project memory
```

Outcome:

```text
The TUI becomes a client of a local research runtime with sessions, messages, events, commands, permission modes, and explicit context.
```

### MVP Cut 3 — Team Internal Deployment

Stop here third:

```text
R9 team deployment hardening
R10 research capability hardening
```

Outcome:

```text
A small internal team can use the system safely with operator controls, backup, verification, writer locks, and useful calibration outputs.
```

---

## Dependency summary

```text
R0 baseline stabilization
→ R1 deployment architecture
→ R2 deploy & verify POC
→ R3 terminal workspace POC
→ R4 chat workspace completion
→ R5 local runtime/server
→ R6 event stream and trace runtime
→ R7 permission policy and agent modes
→ R8 research context
→ R9 team hardening
→ R10 research capability hardening
→ R11 advanced patterns
→ R12 reports/journal
→ R13 backtest lab
→ R14 ML ranking
```

## Current priority

The next implementation priority is:

```text
1. Merge deployment architecture documentation.
2. Merge deploy-and-verify OpenSpec.
3. Implement R2 deploy & verify POC.
4. Finish R3/R4 terminal chat workspace gaps.
5. Start R5 runtime/server only after POC deployment is repeatable.
```

This keeps the project disciplined: deployability first, OpenCode-style architecture second, advanced research capability third.
