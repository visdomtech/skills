---
name: dev-cycle
description: "Runs a plan→implement (TDD)→review→simplify pipeline with parallel multi-agent planning. Use for non-trivial multi-file changes."
---

# Dev Cycle

## Overview

Execute a strict sequential pipeline with mandatory setup and wrap-up. Each phase consumes the previous phase's output through an explicit exit gate.

```
Phase 0  SETUP       (branch verification + complexity assessment + model selection)
Phase 1  PLAN        (bug fixes: root-cause analysis FIRST (§1.0); then synthesize via 3 parallel agents OR adopt supplied plan → validate → user approval)
Phase 2  IMPLEMENT   (faster model: incremental vertical slices / TDD)
Phase 3  REVIEW      (high-reasoning model: multi-axis code review with deep investigation)
Phase 4  SIMPLIFY    (high-reasoning model: complexity reduction)
Phase 5  WRAP-UP     (conventional commit + user recap + post-cycle choice: local multi-agent-review OR push -> PR -> online multi-agent-review)
```

Default execution is in the current directory on the current branch.

---

## Phase 0: Setup (Branch Verification + Complexity Assessment + Model Selection)

### 0.1 Branch & Remote Verification
1. **Detect primary remote:** `git remote` (prefer `github`, else `origin`). Store as `$REMOTE`.
2. **Detect default branch:** `git symbolic-ref refs/remotes/$REMOTE/HEAD --short 2>/dev/null | sed "s|^$REMOTE/||"` (fallback `main`). Store as `$DEFAULT_BRANCH` and use `$REMOTE/$DEFAULT_BRANCH` as the base ref everywhere below.
3. **Check working tree:** `git status --porcelain`. If uncommitted changes exist, ask user (stash / commit / abort).
4. **Fetch & compare:** Run `git fetch $REMOTE` then `git rev-list --left-right --count $REMOTE/$DEFAULT_BRANCH...HEAD`.
   - Output: `<behind>\t<ahead>`. Behind **must be 0**. If behind > 0, ask user (rebase / merge / abort).
5. **Revision switch (only if the user explicitly requested a different base):** Never create branches or worktrees (Pipeline Rule 5) - switch in place with `git reset --hard <revision>` (e.g. `git reset --hard $REMOTE/$DEFAULT_BRANCH` to move the current branch onto the expected base revision).

### 0.2 Complexity Assessment
| Complexity | Criteria | Path |
|---|---|---|
| **Trivial** | ≤3 files, unambiguous requirements | Fast path: Skip Phase 1. Proceed to Phase 2 with TodoWrite list. Run Phase 3 & 4. |
| **Standard** | 4–10 files, design choices needed | Full path: Run Phase 1 (3-agent planning). |
| **Large** | >10 files, architectural decisions | Full path: Run Phase 1 (3-agent planning). Consider splitting into multiple cycles. |

> **State-machine signal (always run, <1 s):** Regardless of file count, scan the pending
> or described changes for shared-state writes: SQL `SET status =`, `SET state =`, or
> equivalent state-field mutations. If found, carry a **state-machine-touching** note into
> Phases 2 and 3, which activates one additional check in each. This does NOT change the
> complexity classification — it adds a trace, not a process escalation.

> **Supplied-plan override:** If the invocation includes a plan file, ignore the trivial-skip above - a supplied plan signals intent to execute it, so run Phase 1 in Adopt mode regardless of file count.

> **Bug-fix exception:** If the task is diagnosing and fixing an existing issue (bug, regression, broken behavior) and the root cause is **not yet established**, the change is never Trivial — an unknown root cause is an ambiguous requirement, regardless of how few files the eventual fix touches. Run the full Phase 1 in Diagnose-and-Fix mode (§1.0). The fast path applies only when the root cause is already known and the fix is unambiguous.

### 0.3 Model Selection & Confirmation
1. Inspect available models (High-Reasoning vs Faster Execution).
2. **Single-model environment:** If distinct models are unavailable, assign current model to all phases, state *"Single-model environment: all phases will use the current model"*, and proceed. No confirmation prompt required.
3. **Multi-model environment:** Present allocation table to user and wait for explicit confirmation before Phase 1:
   - **High-Reasoning Model:** `PLAN`, `REVIEW`, `SIMPLIFY`
   - **Faster Model:** `IMPLEMENT`

### Exit Gate
- `$REMOTE` and `$DEFAULT_BRANCH` set; HEAD is at or ahead of `$REMOTE/$DEFAULT_BRANCH`; working tree clean.
- Complexity classified; model choices confirmed (or single-model fallback noted).

---

## Phase 1: Plan (Parallel Multi-Perspective)
Delegates to the `multi-agent-planning` skill (read-only, High-Reasoning Model). Has two entry modes.

### 1.0 Diagnose-and-Fix Mode (bug fixes & issue diagnosis)

Applies whenever the task is to diagnose and fix an existing issue (bug, regression, broken behavior). The most common failure mode of this pipeline on bug fixes is jumping to implementation with an abbreviated plan and no visible reasoning - this mode exists to prevent that.

**Before choosing an entry mode, produce an explicit Root Cause Analysis (RCA) and write it out in full for the user** - it is a required, visible output, never a one-liner buried inside the plan:

- **Symptom:** what is actually observed - error messages, logs, wrong behavior, when it started.
- **Reproduction:** the exact steps or failing test that demonstrates the issue. This becomes Phase 2's Prove-It reproduction test.
- **Root cause:** the precise mechanism, cited as `file:line` plus *why* it produces the symptom, backed by evidence from code, logs, or test runs - never a guess.
- **Discarded hypotheses:** at least one alternative explanation that was investigated and ruled out, with the evidence that ruled it out.

If the root cause cannot be established with evidence, **STOP** and report what was investigated and what remains unknown - do not proceed to implementation with a speculative fix.

The RCA then feeds planning:
- **Synthesize mode:** include the full RCA in the change description passed to `multi-agent-planning`; task 1 of the plan is typically the reproduction test.
- **Adopt mode:** validate that the supplied plan's fix matches the RCA; if it addresses a different cause, surface the mismatch.

### 1.1 Entry Mode

**Adopt (plan file supplied):** If the invocation includes an existing plan path (e.g. a draft saved from a prior `multi-agent-planning` run, or a user-authored plan), load it; do not re-plan from scratch.

**Synthesize (no plan supplied):** Run `multi-agent-planning` with the change description and repo root. It returns a compact, self-contained synthesized plan and leaves the working tree clean.

### 1.2 Validate Against Output Contract
Confirm the plan (synthesized or adopted) meets the `multi-agent-planning` Output Contract (ordered tasks <=5 files with acceptance criteria and verification steps; critical files; risks; at least 2 rejected alternatives).

If an adopted plan fails validation, surface the specific gaps and offer: (a) re-synthesize via `multi-agent-planning` using the adopted plan as input, or (b) let the user amend the plan file. Do not silently proceed with an under-specified plan.

### 1.3 User Approval (HARD GATE)
Present the plan to the user **in full**: the complete RCA (in Diagnose-and-Fix mode), every task with its acceptance criteria and verification steps, risks, and rejected alternatives. Never present an abbreviated summary or paraphrase - the user approves the actual plan text, and must be able to read the root cause and the fix plan before approving. **STOP and wait for explicit confirmation** (`[Approve / Modify / Reject]`). Do not proceed until approved. On modify:
- **Adopt:** user amends the plan file; re-load and re-validate.
- **Synthesize:** re-invoke `multi-agent-planning` with the adjusted constraints.

**Autonomous callers:** when invoked by `as-goal` (a pipeline running under a caller-approved goal), this approval gate is auto-approved by the caller - do not STOP for plan confirmation. All other gates (build, tests, per-phase commit scope) still apply; the Phase 5 post-cycle publish choice is skipped under autonomous context (commit + recap + stop - the caller drives review and publishing). The invoking skill must state it is passing autonomous context.

### Exit Gate
- Plan (synthesized or adopted) validated against the Output Contract; tasks ordered with acceptance criteria & verification steps; no task >5 files.
- In Diagnose-and-Fix mode: RCA produced and shown to the user in full - evidence-backed root cause, reproduction, and discarded hypotheses.
- At least 2 alternatives explicitly rejected with rationale.
- User explicitly approved the plan.

---

## Phase 2: Implement (Incremental Vertical Slices)
Executed using Faster Model. See `test-driven-development` for full TDD guidelines.

### Increment Cycle (TDD: RED → GREEN → REFACTOR)
1. **RED:** Write failing test establishing target behavior before writing implementation code.
2. **GREEN:** Write minimal code required to pass test.
3. **REFACTOR:** Clean up implementation while keeping tests green.
4. **Verify & Advance:** For bug fixes, write a reproduction test first (Prove-It Pattern).

### Core Rules
- Test outcomes and state, not internal method call sequences.
- Keep setup self-contained (DAMP > DRY); prefer real implementations over mocks.
- Commit at the phase exit gate, not at Phase 5, per Pipeline Rule 4 (Per-Phase Commit Gate); commit WIP only if interrupted mid-phase.

### Implementation Quality Bar
While implementing, self-check against the lenses an external review (`pr-review` / `multi-agent-review`) will later apply:
- **Errors:** handle or wrap every error (`fmt.Errorf("...: %w", err)`); no swallowed errors, no empty callbacks.
- **Input:** validate untrusted input at boundaries; no secrets in code; parameterize queries.
- **Lifecycle:** every subscription, listener, goroutine, or connection opened has a defined cleanup path; no stale references after unmount/disconnect.
- **Completeness:** no TODOs, disabled lints, or hardcoded placeholders in committed code; update docs/comments that describe the old behavior; **when modifying values written to shared state (DB status columns, config keys, message types), grep for and verify all consumer code handles the new values.**

### Exit Gate
- All plan tasks implemented; full verification passes: **build, lint, typecheck, and tests** (with race detector where available, e.g. `go test -race ./...`).
- Commit in-scope changes per Pipeline Rule 4; `git status` clean.

---

## Phase 3: Review (Multi-Axis Code Review)
Executed using High-Reasoning Model. Review diff (`git diff $REMOTE/$DEFAULT_BRANCH...HEAD`). The goal is to catch in-cycle what an external review would catch later — same lenses, same depth. A diff-only skim is not a review.

### 3.1 Deep Investigation (before judging anything)
Surface diffs are insufficient. For every changed file and symbol:
1. **Read full files**, not just diff hunks — context explains the change.
2. **Trace usage sites:** `grep -r "ChangedSymbol" src/ pkg/ internal/` — all callers adapt to signature changes; removed exports aren't referenced elsewhere; new imports are valid. **If the change writes new values to shared state (DB status columns, config keys, message types, enum fields), grep for every other file that reads or guards on that same field and verify the new value is accepted by their WHERE clauses, switch statements, and filter expressions.**
3. **Trace side effects of removals:** context providers, event listeners, cleanup hooks, DB transactions — replacements provide equivalent capabilities.
4. **Check incomplete-implementation patterns:** TODOs, disabled lints without explanation, hardcoded values, empty callbacks, swallowed errors.

### 3.2 Axes & Severities
- **Axes:** Correctness, Readability, Architecture, Security, Performance, Test Coverage, plus:
  - **Impact:** regressions to existing behavior, broken callers, backward compatibility, schema drift, **state-machine contract violations (producer writes a value that consumers' guard clauses do not accept).**
  - **Completeness:** stated intent delivered end-to-end, no missing pieces, docs/comments updated.
  - **Observability:** logging adequacy, production debuggability (can you diagnose this in production?).
  - **Lifecycle & State:** mount/unmount, connect/disconnect/reconnect transitions, stale references, buffer/replay correctness, subscription leaks.
- **Severities:** `Critical:` (blocks merge), `Required` (must fix before proceeding), `Optional:` / `Consider:`, `Nit:`, `FYI`.

### 3.3 Dispatch
- **Small diff** (≤3 files AND ≤50 lines changed): review directly, applying all axes. **Mandatory:** Step 2's shared-state trace applies regardless of diff size — a 1-file, 5-line status update can silently break N consumers.
- **Larger diff:** dispatch 3 fresh-context review subagents concurrently, splitting the axes — (1) Correctness + Security + Lifecycle, (2) Architecture + Impact + Performance, (3) Readability + Test Coverage + Completeness + Observability. Fresh context beats self-review: the implementer's own context rationalizes its choices. Subagents read files directly and consume the Phase 2 verification status instead of re-running suites.

### 3.4 Process
Categorize findings by severity. Fix all `Critical` and `Required` issues, running tests after each fix. Record every unresolved `Optional`/`Nit`/`FYI` finding in a **deferred-findings list** (finding + one-line rationale) — never silently drop them; the list feeds the Phase 5 recap.

### Exit Gate
- Deep investigation done; all Critical and Required findings resolved; build, lint, typecheck, and tests pass (race detector where available).
- Deferred-findings list captured for the Phase 5 recap.
- Commit in-scope changes per Pipeline Rule 4; `git status` clean.

---

## Phase 4: Simplify (Complexity Reduction)
Executed using High-Reasoning Model.

### Core Principles & Signals
- **Principles:** Preserve exact behavior, match project conventions, prioritize clarity, scope to changed files (Chesterton's Fence).
- **Signals:** Reduce deep nesting (3+ levels), long functions (50+ lines), nested ternaries, duplicated logic (5+ lines), dead code, and generic variable names.

### Exit Gate
- All existing tests pass without modification; full verification re-run (build, lint, typecheck, tests) — simplification lands *after* review, so it must re-prove the gates, not just tests.
- Behavior and public APIs unchanged; if a simplification would alter logic in untested paths, split it into a new cycle instead of forcing it into Phase 4.
- Commit in-scope changes per Pipeline Rule 4; `git status` clean.

---

## Phase 5: Wrap-Up (Commit & Recap)

### Steps
1. **Commit residual changes:** Run `git status --porcelain`. If anything remains after the per-phase commits (e.g., docs, generated files, minor polish), `git add -A` and commit with a Conventional Commit (`docs`/`chore`/`test`/`fix`). If the tree is already clean, skip this commit.
2. **Commit type guidance:** Use [Conventional Commits](https://www.conventionalcommits.org/) (`feat`, `fix`, `refactor`, `chore`, `docs`, `test`). Use `fix` for small tweaks/polish; reserve `feat` for major features. Per-phase types are defined in the Per-Phase Commit Gate (Pipeline Rules #4).
3. **Recap Table:** Present summary including branch, pipeline path, models used, tasks completed, review findings fixed, **deferred findings** (the Phase 3 deferred-findings list: every unresolved `Optional`/`Nit`/`FYI` with a one-line rationale — never let them vanish silently), simplifications, and per-phase commit SHAs (`git log --oneline $REMOTE/$DEFAULT_BRANCH..HEAD`).
4. **Post-Cycle Choice - Local Review vs. Publish + Online Review:** Present a two-way choice; the user may also decline both and stop. Do NOT execute either path until the user explicitly picks one. State exactly what each option authorizes.

   **Autonomous callers** (`as-goal`): skip this choice entirely - commit, deliver the recap, and stop. The caller pipeline drives any review and decides on publishing; never push or open a PR autonomously.

   - **Option A - Local review only (read-only):** Run `multi-agent-review` in **Local Mode** on the cycle's commits (`COMMITS="$REMOTE/$DEFAULT_BRANCH..HEAD"`). Authorizes *only* the local, read-only review - no `git push`, no `gh`, no PR. Use this when the user wants feedback before publishing.
   - **Option B - Publish & online review:** Push the cycle's commits to a remote branch on `$REMOTE`, open a PR against the default branch (`$REMOTE/$DEFAULT_BRANCH`), then run `multi-agent-review` in **PR Mode** on the new PR. Authorizes `git push` to `$REMOTE`, `gh pr create`, and the subsequent online `multi-agent-review` (which may push fix commits to the PR branch and post reviews to GitHub).

   When presenting the choice, compute and display the **publish pre-flight** alongside Option B so the user knows precisely what would be pushed:
   - **Commits to push:** `git log --oneline $REMOTE/$DEFAULT_BRANCH..HEAD` (list every commit).
   - **HEAD commit SHA:** `$(git rev-parse HEAD)`.
   - **Remote:** `$REMOTE`.
   - **Remote branch:** the branch the commits land on (resolved in Option B below).
   - **PR base:** `$REMOTE/$DEFAULT_BRANCH`.

   **Option B steps (run only after the user picks it):**
   1. `CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)`.
   2. Never create a local branch (Pipeline Rule 5). Resolve the push ref:
      - If `CURRENT_BRANCH` is the default branch (`$DEFAULT_BRANCH`), never push cycle work directly there: derive a feature-branch name from the Conventional Commit (e.g., `<type>/<scope>` or `<type>/<short-subject>`), state it, and set `PUSH_REF="HEAD:<feature-branch>"` and `PR_HEAD=<feature-branch>` (lands on a remote-only branch; no local branch is created).
      - Otherwise set `PUSH_REF="$CURRENT_BRANCH"` and `PR_HEAD="$CURRENT_BRANCH"`.
   3. Push (non-force): `git push -u "$REMOTE" "$PUSH_REF"`. If rejected as non-fast-forward, surface it to the user - do **not** force-push.
   4. Open the PR: `gh pr create --base "$DEFAULT_BRANCH" --head "$PR_HEAD" --title "<commit subject>" --body "<recap body>"`. Capture the PR number/URL.
   5. Invoke `multi-agent-review` in **PR Mode** on the new PR. `multi-agent-review` owns its own Phase 0 sync (fetch PR head, `git reset --hard` to it - no review branch), 7-agent review, and - if findings exist - its fix/push/re-review loop.

### Exit Gate
- All changes committed with conventional messages (per-phase commits from Phases 2-4 plus any residual from Step 1); recap delivered.
- Post-cycle choice presented with an accurate publish pre-flight; the user's chosen path (local review, or publish + PR + online review) executed or explicitly declined. (Under autonomous callers the choice is skipped; recap only.)
- `git status` clean.

---

## Pipeline Rules & Context Management

1. Never skip Phases 0, 3, 4, or 5. Phase 1 may be skipped only for trivial changes.
2. Never execute phases in parallel; re-run tests after every fix and simplification.
3. Watch context budget: the `multi-agent-planning` skill's Output Contract guarantees a compact, self-contained plan, so proceed directly through Phase 2 without re-exploring files; split large tasks into multiple shippable cycles.
4. **Per-Phase Commit Gate (Phases 2, 3, 4):** At the exit of each implementation/review/simplify phase, if the phase produced changes, verify the changes belong to the *current* phase before committing:
   - **Phase 2 (Implement):** changes match plan tasks only - tests plus implementation code.
   - **Phase 3 (Review):** changes are fixes for `Critical`/`Required` findings only - no new features, no `Optional`/`Nit` tweaks folded in. Exception: when fixes arrive via a `pr-review`/`multi-agent-review` hand-off, batched `Optional`/`Suggestion`/`Nit` fixes from the same findings list may ride in the same `fix` commit (they were pre-approved by the invoking review).
   - **Phase 4 (Simplify):** changes preserve behavior (refactor only) - no behavior or API changes.

   If a change is out of scope (belongs to a different phase or is unrelated), do **not** commit it under the current phase: stash it (`git stash push -m "out-of-phase: <desc>"`) and surface it to the user. Commit in-scope changes with the matching Conventional Commit type (`feat`/`fix`/`test` for implement, `fix` for review, `refactor` for simplify). Leave the working tree clean (`git status` empty) before advancing to the next phase.
5. **No branch or worktree creation:** In all cases, never create additional local branches or worktrees. When a step needs a different revision, switch in place with `git reset --hard <revision>` (see Phase 0.1 step 5). The only branch-shaped artifact allowed is the remote-only publish ref in Phase 5 Option B (`git push $REMOTE HEAD:<remote-branch>`), which creates no local branch. Review skills invoked post-cycle (e.g. `multi-agent-review` PR Mode) manage their own review state and are outside this rule.
