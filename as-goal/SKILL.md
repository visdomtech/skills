---
name: as-goal
description: "Goal-driven autonomous engineering team skill. Extracts a clear goal via interview, assembles a 4-role core agent team (architect, engineer, test engineer, delivery lead) plus a conditional bench (security, release, documentation, performance, frontend, debugging), defines exit gates, then iterates (max 10 turns) until all gates pass. Each iteration produces evidence manifests and saves progress to docs/as-goals/[goal-name]/[iteration]/; a global docs/as-goals/[goal-name]/PROGRESS.md tracks pipeline state across restarts and context compaction."
---

# As-Goal

## Overview

Transform a vague idea into an autonomous engineering pipeline. The skill extracts a crisp "what" goal (not "how"), assembles a 4-role core agent team (architect, engineer, test engineer, delivery lead) plus a conditional bench (security, release, documentation, performance, frontend, debugging), defines measurable exit gates, then iterates until the goal is achieved or the 10-turn budget is exhausted. A global `PROGRESS.md` tracks pipeline state across iterations, restarts, and context compaction.

```
┌─────────────────────────────────────────────────────────────────┐
│  PHASE 1: INTERVIEW  → interview-me (extract goal)             │
│  PHASE 2: ASSEMBLE   → Create agent team (4 core + bench)        │
│  PHASE 3: DEFINE     → Exit gates + evidence requirements       │
│  PHASE 4: ITERATE    → Plan → Build → Test → Synthesize (≤10x)  │
│                          ↓ All gates pass: DONE                 │
│                          ↓ Gates fail + turns left: loop        │
│                          ↓ Turns exhausted: post-mortem         │
│                          ↓ Blocked or stagnating: escalate      │
└─────────────────────────────────────────────────────────────────┘
```

## Autonomy & Memory

When you invoke this skill, you MUST run the pipeline exactly as orchestrated by this file:

**Phase 1: Interview → Phase 2: Assemble → Phase 3: Define Gates → Phase 4: Iterate**

- DO NOT skip, reorder, or merge phases — even if the goal already seems clear or the task seems small.
- DO NOT shortcut into direct implementation, a bare `dev-cycle` loop, or ad-hoc coding.
- DO NOT switch modes mid-pipeline (e.g., abandoning the role structure for free-form work or jumping to another skill).
- The only legitimate way past a phase is through its stated **Gate** (goal saved and confirmed → team saved → gates frozen → iterate to DONE or POST-MORTEM).

If you catch yourself thinking "I can just do this directly," stop — that is exactly the shortcut this rule forbids.

Before starting the pipeline, commit the following rule to memory and keep it active for the entire run:

> When running with skill `as-goal`, always proceed autonomously to the next iteration/task without stopping to ask.

To make the rule survive restarts and context compaction, also persist it: when the Delivery Lead creates `docs/as-goals/[goal-name]/PROGRESS.md` at the end of Phase 2, record this rule at the top of that file (e.g., as a `**Autonomy rule:**` line). On resume, treat it as still in force — do not re-ask for approval to continue.

This means: no "shall I continue?" between iterations, tasks, or phase transitions. The only stops are the pipeline's own terminal/escalation points already defined below: DONE, POST-MORTEM, a blocked immutable gate, a stagnation escalation (Phase 4, Step 4 decision rule), or a network/dependency failure.

## When to Use

- You have a complex, multi-file feature that needs autonomous execution
- The goal can be expressed as user-facing scenarios with verifiable gates
- You want a team of specialized agents working iteratively without constant approval
- The work spans architecture, implementation, and testing
- You're willing to invest up to 10 iterations to get it right

**When NOT to use:**

- Simple single-file changes (use `dev-cycle` directly)
- Exploratory work with no clear success criteria (use `interview-me` first)
- You need human approval at each step (this skill is autonomous)

## Phase 1: Interview (Extract Goal)

**Skill:** `interview-me`
**Output:** `docs/as-goals/[goal-name].md`

Run the `interview-me` skill to extract a clear, measurable goal. The goal must be:

- **What, not how:** "Users can upload CSV files and see import progress" not "Build a file upload endpoint with WebSocket progress streaming"
- **Single statement:** One sentence capturing the core outcome
- **Measurable:** Success criteria that can be verified
- **Scoped:** Explicit out-of-scope items

**Save the confirmed goal to:**
```
docs/as-goals/[goal-name].md
```

**Format:**
```markdown
# [Goal Name]

## Goal
<one-sentence what, not how>

## Context
<what exists, what's missing>

## Success Criteria
- Criterion 1
- Criterion 2

## Constraints
- Constraint 1

## Out of Scope
- Explicitly excluded item 1

## Created
<timestamp>
```

**Gate:** Goal file saved and user confirmed. Proceed to Phase 2.

## Phase 2: Assemble Agent Team

**Output:** `docs/as-goals/[goal-name]/agents/*.md` + `docs/as-goals/[goal-name]/PROGRESS.md`

Create the 4-role core engineering team definition files directly from the templates below - the core roles are fixed, no ideation skill is needed. Activate bench roles only when their trigger condition matches:

### Core Roles

**1. System Architect**
- **Responsibility:** Plan the implementation
- **Skill:** `multi-agent-planning`
- **Input:** Goal + gates (iteration 1); gap summary from previous iteration (iteration N>1)
- **Output:** `[iteration]/plan.md` — ordered tasks with file paths and acceptance criteria
- **Authority:** Architecture decisions, file structure, task breakdown
- **Boundary:** Does NOT write implementation code
- **Escalates when:** a gate proves architecturally unreachable → Gate Immutability escalation (Phase 3)

**2. Senior Software Engineer**
- **Responsibility:** Implement the plan
- **Skill:** `dev-cycle` (TDD, review, simplify, commit)
- **Input:** `[iteration]/plan.md`
- **Output:** Conventional commits + passing test runs
- **Authority:** Code implementation, test writing, refactoring
- **Boundary:** Does NOT modify architecture without architect approval; an infeasible plan task is routed back to the Architect, never silently redesigned
- **Escalates when:** build/test failures exceed 3 attempts (Error Handling)

**3. System Test Engineer**
- **Responsibility:** Review and verify implementation
- **Skill:** `multi-agent-review`
- **Input:** Commits from Step 2 + gate definitions
- **Output:** `[iteration]/review.md` + `[iteration]/evidence-manifest.md` (per-gate Pass/Fail with linked evidence paths)
- **Authority:** Code review, gate validation, evidence collection — only the Test Engineer may mark a gate Pass, and only with linked evidence
- **Boundary:** Does NOT write implementation code
- **Escalates when:** the same gate fails 2 consecutive iterations with no clear root cause → activate Debugging Specialist

**4. Delivery Lead**
- **Responsibility:** Pipeline bookkeeping - `PROGRESS.md`, iteration banners, WIP-limit enforcement, gap-summary routing, escalation
- **Skill:** `planning-and-task-breakdown`
- **Input:** Evidence manifests and iteration outcomes
- **Output:** `PROGRESS.md` updates, gap-summary routing decisions, DONE / LOOP / POST-MORTEM record
- **Authority:** Iteration bookkeeping, routing failed gates, declaring DONE / LOOP / POST-MORTEM
- **Boundary:** Does NOT plan architecture, write code, or review code; DONE requires an evidence manifest with all gates Pass

### Handoff Contract

Artifacts flow in one direction, one active artifact per role (WIP limit):

`plan.md` (Architect) → `commits` (Engineer) → `review.md` + `evidence-manifest.md` (Test Engineer) → `gap-summary.md` + `PROGRESS.md` update (Delivery Lead) → next iteration's `plan.md`

Failure routing rules:

| Failure Type | Routed To |
|--------------|-----------|
| Implementation defect (code doesn't meet the plan) | Engineer |
| Architectural defect (the plan can't reach the gate) | Architect |
| Same gate fails 2 consecutive iterations, root cause unclear | Debugging Specialist (activate) |
| Gate provably unreachable | User, per Gate Immutability (Phase 3) |

### Conditional Bench Roles

| Bench Role | Activates When | Skill | Plugs Into |
|------------|----------------|-------|------------|
| Security Engineer | Goal touches auth, untrusted input, external integrations, or data storage | `security-and-hardening` | Step 3 review (alongside Test Engineer); may propose security gates in Phase 3 |
| Release Engineer | Goal ships to production / changes deployable behavior | `shipping-and-launch` + `observability-and-instrumentation` | Phase 3 launch/observability gate; final-iteration launch checklist |
| Documentation Engineer | Goal changes public API or involves a significant architectural decision | `documentation-and-adrs` | Step 2 (ADR alongside implementation); DONE (changelog entry) |
| Performance Engineer | Goal has explicit latency, throughput, resource, or Core Web Vitals requirements | `performance-optimization` | Phase 3 (proposes performance gates); Step 3 profiling review of perf-relevant commits |
| Frontend Engineer | Goal includes user-facing UI | `frontend-ui-engineering` + `browser-testing-with-devtools` | Step 2 UI implementation alongside Engineer; Step 3 accessibility/responsive evidence for UI gates |
| Debugging Specialist | Mid-pipeline trigger: the same gate fails 2 consecutive iterations with no clear root cause | `debugging-and-error-recovery` | Step 4 root-cause analysis of the stuck gate; findings feed the next iteration's plan |

Bench roles get NO extra iterations and respect the same WIP limit (Key Principles) - they attach to existing steps. Save a bench agent definition only when activated. The Debugging Specialist is the only reactive role: its trigger fires mid-pipeline, so its definition is saved at activation time, not in Phase 2; all other bench roles are decided in Phase 2.

### Agent Definition Format

Save each agent to `docs/as-goals/[goal-name]/agents/[role-name].md`:

```markdown
# [Role Name]

## Identity
- **Role:** [System Architect | Senior Engineer | Test Engineer | Delivery Lead | Security Engineer | Release Engineer | Documentation Engineer | Performance Engineer | Frontend Engineer | Debugging Specialist]
- **Primary Skill:** [multi-agent-planning | dev-cycle | multi-agent-review | planning-and-task-breakdown | security-and-hardening | shipping-and-launch | documentation-and-adrs | performance-optimization | frontend-ui-engineering | debugging-and-error-recovery]

## Responsibilities
- [List of responsibilities]

## Handoff Contract
- **Consumes:** [input artifacts, from whom]
- **Produces:** [output artifacts, to whom]

## Decision Authority
- [What this role can decide unilaterally]
- [What requires escalation to user]

## Boundaries
- [What this role must NOT do]

## Evidence Requirements
- [What artifacts this role must produce]
```

Bench agents use the same format; save them only when activated.

**Gate:** All core agent definitions + activated bench definitions saved. Proceed to Phase 3.

## Global Progress Tracking

**Path:** `docs/as-goals/[goal-name]/PROGRESS.md`
**Owner:** Delivery Lead
**Cadence:** Created at the end of Phase 2 (team assembled). Updated at every phase transition and at the end of every iteration.

`PROGRESS.md` is the single living record of pipeline state. Iteration folders hold per-iteration artifacts; `PROGRESS.md` holds the current truth.

**Template:**
```markdown
# PROGRESS — [Goal Name]

- **Goal file:** docs/as-goals/[goal-name].md
- **Current phase:** [1 | 2 | 3 | 4]
- **Iteration:** N/10

## Gate Dashboard

| Gate | Status | Last Evaluated |
|------|--------|----------------|
| Gate 1 | Pending | - |
| Gate 2 | Pass | Iteration 2 |
| Gate 3 | Fail | Iteration 2 |

## Iteration Log

| Iteration | Decision | Gates | Commits | Artifacts |
|-----------|----------|-------|---------|-----------|
| 1 | LOOP | 0/3 → 1/3 | `sha1`, `sha2` | [plan](1/plan.md) / [review](1/review.md) / [manifest](1/evidence-manifest.md) / [gap](1/gap-summary.md) |

## Open Defects

### Gate: [Gate Name]
**Missing:** <what's missing>
**Root Cause:** <why it failed>
**Routed To:** [Architect | Engineer]
**Priority:** [Critical | Warning]

## Next Actions
- [ ] <exact item for the next iteration>
- [ ] <exact item for the next iteration>
```

**Resume rule:** On any restart or context compaction, the orchestrator reads `PROGRESS.md` first and resumes from "Next Actions". Do NOT re-derive state from iteration folders.

## Phase 3: Define Exit Gates

**Output:** `docs/as-goals/[goal-name]/gates/*.md`

The agent team collaboratively defines exit gates. If no gates are explicitly provided, the bootstrap task is to define them.

### Gate Definition Process

1. **Architect** reads the goal and proposes gates based on success criteria
2. **Test Engineer** validates gates are measurable and evidence-based
3. **Engineer** confirms gates are achievable within iteration budget

### Gate Format

Save each gate to `docs/as-goals/[goal-name]/gates/[gate-name].md`:

```markdown
# Gate: [Gate Name]

## Condition
<What must be true for this gate to pass>

## Evidence Required
- [ ] Artifact 1: <description> → `path/to/file`
- [ ] Artifact 2: <description> → `path/to/file`

## Verification Method
<How the test engineer will verify this gate>

## Owner
<Role responsible for producing evidence>
```

### Gate Immutability

**Once defined, gates are IMMUTABLE.** If a gate proves impossible:
- Do NOT soften the gate
- Do NOT redefine success criteria
- Escalate to user with: "Gate X is blocked because Y. Options: (a) reduce scope, (b) extend budget, (c) abort."

**Gate:** All gates defined and saved. Proceed to Phase 4.

## Phase 4: Iterative Execution

**Max iterations:** 10
**Output per iteration:** `docs/as-goals/[goal-name]/[iteration-number]/`

**Autonomous caller context:** sub-skills (`multi-agent-planning`, `dev-cycle`, `multi-agent-review`) are invoked with autonomous caller context per the dev-cycle Phase 1.3 autonomy contract - their plan-approval gates are auto-approved by this skill. Build and test gates still apply. dev-cycle's post-cycle publish choice is skipped in this context (commit + recap + stop); this skill drives review (Step 3) and any publishing.

### Iteration Loop

```
┌──────────────────────────────────────────────────────────┐
│  ITERATION N/10                                          │
│  1 Architect  → multi-agent-planning → plan.md           │
│  2 Engineer   → dev-cycle (TDD→review→simplify)          │
│               → commits                                  │
│  3 Test Eng.  → multi-agent-review                       │
│               → review.md + evidence-manifest.md         │
│  4 Synthesize → DONE | LOOP (gap summary)                │
│               | POST-MORTEM (turns exhausted)            │
│               | ESCALATE (blocked gate / stagnation)     │
└──────────────────────────────────────────────────────────┘
```

### Step 1: Architect Plans

**Input:**
- Iteration 1: Original goal + gates
- Iteration N>1: Gap summary from previous iteration

**Process:**
1. Read goal and gate definitions
2. Analyze current codebase state
3. Identify gaps between current state and gates
4. Use `multi-agent-planning` to create implementation plan
5. Break into ordered tasks with file paths and acceptance criteria

**Output:** `docs/as-goals/[goal-name]/[iteration]/plan.md`

### Step 2: Engineer Implements

**Input:** Plan from Step 1

**Process:**
Run the `dev-cycle` pipeline with autonomous caller context (its Phase 2 embeds TDD):
1. For each task in plan, follow RED -> GREEN -> REFACTOR
2. Run the full test suite
3. dev-cycle Phase 3 (multi-axis review) resolves Critical/Required findings
4. dev-cycle Phase 4 (simplify) reduces complexity
5. Commit with conventional commit messages

**Output:** Committed code changes

**WIP Limit:** Engineer has ONE active task at a time, per the role-wide WIP rule in Key Principles. No parallel work.

**Bench note:** If the Documentation Engineer is activated and the plan contains a significant architectural decision, it writes an ADR (via `documentation-and-adrs`) alongside the implementation.

### Step 3: Test Engineer Reviews

**Input:** Commits from Step 2 + gate definitions

**Process:**
1. Use `multi-agent-review` skill (local mode)
2. Review code quality (architecture, correctness, security, performance, completeness, observability)
3. **Gate Analysis:** For each gate, determine:
   - Passable? (Yes / No)
   - Evidence produced? (list file paths)
   - If No: what specific functionality is missing?

**Output:**
- `docs/as-goals/[goal-name]/[iteration]/review.md` (code review findings)
- `docs/as-goals/[goal-name]/[iteration]/evidence-manifest.md` (gate status + evidence)

**Bench notes:**
- If the Security Engineer is activated, it joins the review with `security-and-hardening`.
- On the final iteration, the Release Engineer (if activated) validates the launch/rollback checklist.

**Evidence Manifest Format:**
```markdown
# Evidence Manifest — Iteration N

## Gate Status

| Gate | Status | Evidence | Owner |
|------|--------|----------|-------|
| Gate 1 | ✅ Pass | `path/to/test1.go`, `path/to/impl1.go` | Engineer |
| Gate 2 | ❌ Fail | Missing: integration test for X | Engineer |

## Return Shipments (Failed Gates)

### Gate: [Gate Name]
**Defect:** <What's missing or broken>
**Root Cause:** <Why it failed>
**Routed To:** [Architect | Engineer]
**Priority:** [Critical | Warning]

## Code Quality Findings
- Critical: N
- Warning: N
- Suggestion: N

## Commits Reviewed
- `sha1`: message
- `sha2`: message
```

### Step 4: Synthesize & Decide

**Owner:** Delivery Lead — only the Delivery Lead may declare the iteration decision, and DONE requires an evidence manifest with all gates Pass (Phase 2 role boundary).

**Input:** `evidence-manifest.md` + `review.md` from Step 3, plus the `PROGRESS.md` gate dashboard.

**Process:**

1. **Manifest validity pre-check.** Every gate must carry a Pass/Fail verdict with linked evidence. If the manifest is missing or incomplete, the iteration is invalid (Common Pitfalls): send it back to Step 3 under the same iteration number — do not advance N, do not guess gate statuses.
2. **Re-evaluate all gates, including passed ones.** Later commits can break an earlier Pass. A Pass→Fail flip is a regression: mark it Critical, route it to the Engineer with the commits since the gate last passed, and record it under `## Regressions` in the gap summary. A regressed gate is not Pass, whatever earlier iterations say.
3. **Apply the decision rule** — evaluate top to bottom, first match wins:

| # | Condition | Decision |
|---|-----------|----------|
| 1 | A gate is provably unreachable (Gate Immutability, Phase 3) | **ESCALATE** to user — pipeline stops |
| 2 | All gates Pass **and** all DONE hygiene checks hold | **DONE** |
| 3 | Iteration 10 just ended with any gate failing | **POST-MORTEM** |
| 4 | No gate has newly passed for 3 consecutive iterations (stagnation) | **ESCALATE**: "Gates X, Y show no progress for 3 iterations. Options: (a) re-plan the approach, (b) reduce scope per Gate Immutability, (c) continue to budget end." |
| 5 | Any gate failing, iterations left | **LOOP** with gap summary |

**DONE hygiene checks** — all must hold; if any fails, decide LOOP instead, with the failed check as the gap summary's focus:
- Working tree clean, all work committed
- Full test suite green on the final tree state, not only gate-linked evidence
- No unresolved Critical findings in `review.md` (Warning/Suggestion findings do not block DONE but are listed in the final report)

**On LOOP:**
- Delivery Lead produces the gap summary:
  ```markdown
  # Gap Summary — Iteration N

  ## Failed Gates
  - Gate X: <why it failed, what's missing> → routed to [Architect | Engineer]

  ## Regressions
  - Gate Y: passed iteration N-2, broken by <commit sha> → Engineer (Critical)

  ## Unresolved Findings
  - Critical: <list>
  - Warning: <list>

  ## Next Iteration Focus
  - <specific actionable items>
  ```
- `Unresolved Findings` covers only findings that survived `multi-agent-review`'s own dev-cycle fix iteration (its loop guard stops after one round); findings already auto-fixed there are not re-listed.
- Save to `docs/as-goals/[goal-name]/[iteration]/gap-summary.md`
- If the same gate has now failed 2 consecutive iterations with no clear root cause, activate the Debugging Specialist (bench table) - it runs root-cause analysis on the stuck gate and its findings are added to the gap summary before the next plan
- Delivery Lead updates `PROGRESS.md` (gate dashboard, iteration log, open defects, next actions, decision with one-line rationale)
- Feed to Step 1 of next iteration

**On DONE:**
- Produce final report:
  ```markdown
  # Goal Achieved — [Goal Name]

  ## Iterations: N/10

  ## Gates Passed
  - [x] Gate 1
  - [x] Gate 2

  ## Commits
  - `sha1`: message
  - `sha2`: message

  ## Working Tree
  - Status: clean
  - Branch: [branch name]

  ## Unresolved Findings (non-blocking)
  - Warning: <list or "none">
  - Suggestion: <list or "none">
  ```
- Save to `docs/as-goals/[goal-name]/DONE.md`
- Delivery Lead makes the final `PROGRESS.md` update (all gates Pass, decision DONE)
- Documentation Engineer (if activated) adds a changelog entry
- **End pipeline**

**On POST-MORTEM (10 turns exhausted):**
- Produce structured post-mortem:
  ```markdown
  # Post-Mortem — [Goal Name]

  ## Iterations: 10/10 (exhausted)

  ## Gates Status
  - [x] Gate 1 (passed iteration N)
  - [ ] Gate 2 (failed all attempts)

  ## Most Frequent Failure
  - Gate: [name]
  - Failure count: N/10
  - Root cause pattern: <description>

  ## Least Effective Role
  - Role: [name]
  - Evidence: <why this role underperformed>

  ## Recommended Scope Reduction
  - <specific suggestion to make goal achievable>

  ## All Commits
  - Iteration 1: `sha1`, `sha2`
  - Iteration 2: `sha3`
  - ...
  ```
- Save to `docs/as-goals/[goal-name]/POST-MORTEM.md`
- Delivery Lead updates `PROGRESS.md` (decision POST-MORTEM, final gate dashboard)
- **End pipeline**

## Iteration Tracking

At the start of each iteration, print:

```
═══════════════════════════════════════════════════════
  ITERATION N/10 — [Goal Name]
  Gates passed: X/Y | Failed: X/Y
  Previous iteration: [LOOP | first iteration]
═══════════════════════════════════════════════════════
```

At the end of each iteration, print:

```
───────────────────────────────────────────────────────
  ITERATION N COMPLETE — Decision: [DONE | LOOP | POST-MORTEM | ESCALATE]
  Commits this iteration: <SHA list>
  Gates passed: X/Y → X/Y (delta)
  Artifacts saved: docs/as-goals/[goal-name]/[iteration]/
───────────────────────────────────────────────────────
```

## Key Principles

### 1. Evidence-Based Gates
Every gate must have linked evidence (file paths, test results, code artifacts). Self-reported passage without evidence is not allowed.

### 2. WIP Limits
Each role has ONE active artifact at a time:
- Architect: one plan
- Engineer: one task
- Test Engineer: one review
- Delivery Lead: one progress update

No parallel work. Kanban pull signals only after current work clears.

### 3. Interview Budget Separation
Phase 1 (interview) does NOT count against the 10-iteration budget. The clock starts only after gates are frozen.

### 4. Shared Exit Criteria
All roles converge on the same measurable gates. No per-role success metrics that diverge from the user's goal.

## File Structure

```
docs/as-goals/
├── [goal-name].md                      ← Phase 1 output
└── [goal-name]/
    ├── PROGRESS.md                     ← Global tracking (Delivery Lead, end of Phase 2)
    ├── agents/
    │   ├── architect.md                ← Phase 2 output
    │   ├── engineer.md
    │   ├── test-engineer.md
    │   ├── delivery-lead.md
    │   # security-engineer.md (if activated)
    │   # release-engineer.md (if activated)
    │   # documentation-engineer.md (if activated)
    │   # performance-engineer.md (if activated)
    │   # frontend-engineer.md (if activated)
    │   # debugging-specialist.md (if activated mid-pipeline)
    ├── gates/
    │   ├── gate-1.md                   ← Phase 3 output
    │   └── gate-2.md
    ├── 1/                              ← Iteration 1
    │   ├── plan.md
    │   ├── review.md
    │   ├── evidence-manifest.md
    │   └── gap-summary.md (if LOOP)
    ├── 2/                              ← Iteration 2
    │   └── ...
    ├── DONE.md (if all gates pass)
    └── POST-MORTEM.md (if 10 turns exhausted)
```

## Error Handling

### Build Failures
- Engineer attempts fix within current iteration
- If >3 attempts fail, mark affected gates as failed in evidence manifest
- Test Engineer routes failure back to Architect if architectural issue

### Test Failures
- Engineer handles via TDD cycle (RED → GREEN → REFACTOR)
- If tests can't pass after 3 attempts, mark gate as failed with root cause

### Network/Dependency Failures
- Retry once
- If still failing, pause iteration and escalate to user (exception to autonomous mode)

### Context Compaction / Session Resume
- Orchestrator must read `PROGRESS.md` before continuing; resume from "Next Actions"
- If `PROGRESS.md` is missing, reconstruct it from the iteration folders, then continue

## Interaction with Other Skills

Role-skill assignments (`multi-agent-planning`, `dev-cycle`, `multi-agent-review`, `planning-and-task-breakdown`, bench skills) live in the Phase 2 role tables above. Only skills not listed there:

- **`interview-me`**: Phase 1. Extracts the goal.
- **`adhd`**: optional upstream ideation for novel team shapes. Not required - the 4 core roles are fixed.

## Common Pitfalls

| Pitfall | Mitigation |
|---------|-----------|
| Scope creep across iterations | Each iteration's plan must only address gaps from previous iteration. No new features. |
| Gate softening | Gates are immutable — escalate per Phase 3 (Gate Immutability). |
| Missing evidence | Test Engineer must produce evidence manifest. No manifest = iteration invalid. |
| Progress drift | An iteration without a `PROGRESS.md` update is invalid — `PROGRESS.md` is the single source of truth (Global Progress Tracking). |
| Bench role bloat | Activate bench roles only on their trigger conditions, never by default. |
| Silent plan deviation | Infeasible plan tasks are routed back to the Architect (Handoff Contract) — the Engineer never redesigns silently. |
| Blind retries | Failed gates must have defect metadata. No generic "try again". Same gate failing twice with unclear cause activates the Debugging Specialist. |
| Silent gate regression | Every iteration re-evaluates all gates, including passed ones — a Pass→Fail flip is a Critical regression routed to the Engineer (Step 4). |
| Looping without progress | Stagnation rule: no newly-passed gate for 3 consecutive iterations escalates to the user (Step 4 decision rule). |
| DONE on gates alone | DONE also requires the hygiene checks: clean tree, green suite, no unresolved Critical findings (Step 4). |
| Architect racing ahead | WIP limit of 1 per role (Key Principles) — Architect waits for Engineer to finish current task. |
| Interview counting against budget | Phase 1 is separate — clock starts after gates are frozen (Key Principles). |

## Example

```
as-goal

User: "I want a CSV import feature for employee data"

Phase 1: interview-me → docs/as-goals/csv-employee-import.md (confirmed)
Phase 2: 4 core agent definitions + PROGRESS.md created
Phase 3: gates/upload-ui.md, field-mapping.md, import-processing.md saved
Phase 4:
  ITERATION 1/10 — csv-employee-import | Gates passed: 0/3
  Step 1 Architect → 1/plan.md
  Step 2 Engineer → commits
  Step 3 Test Engineer → Gate 1 ✅ | Gate 2 ❌ (missing: field mapping validation) | Gate 3 ❌ (missing: progress tracking)
  Step 4 → LOOP: 1/gap-summary.md saved, PROGRESS.md updated
  ITERATION 2/10 — Gates passed: 1/3, previous: LOOP
  [... continues until all gates pass (DONE) or 10 turns exhausted (POST-MORTEM) ...]
```

## Verification

After applying as-goal:

- [ ] Bench roles present only when their trigger condition matched
- [ ] `PROGRESS.md` was updated at the end of every iteration (not just created)
- [ ] Evidence manifest links artifacts to each gate
- [ ] Failed gates have defect metadata (not blind retries)
- [ ] Previously-passed gates were re-verified every iteration; regressions routed as Critical
- [ ] DONE was declared only with all hygiene checks green (clean tree, green suite, no unresolved Critical findings)
- [ ] Gates remained immutable all run (no softening — Phase 3 rule)
- [ ] Final outcome (`DONE.md` or `POST-MORTEM.md`) is reflected in `PROGRESS.md`
- [ ] Working tree clean, all changes committed
