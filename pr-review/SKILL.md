---
name: pr-review
description: "Parallel 3-agent code review (completeness, correctness, impact) with dependency tracing. Invoke whenever the user asks to review anything - a GitHub PR, local commits, or the current work in progress. Reviews a GitHub PR and posts the verdict to GitHub, or reviews local commits/working tree. When any findings exist (critical, warning, suggestion, or nit), drives them to resolution via the dev-cycle skill: PR mode commits, pushes to the PR branch, and re-reviews; Local mode commits locally only."
---

# PR Review

## Overview

Deep PR/commit review with systematic dependency tracing and parallel multi-perspective analysis. Traces component hierarchies, verifies side effects of removals, and dispatches independent review agents. **A review that only reports problems is half the job** - when findings exist, this skill closes the loop by delegating fixes to `dev-cycle`, then re-reviewing.

**Core insight:** Diffs show what changed. Files show what exists. The gap between them is where bugs hide.

**Two modes:**
- **PR Mode** (default): Reviews a GitHub PR via `gh` and posts the structured verdict to GitHub. When findings exist, fixes via `dev-cycle`, pushes to the PR branch, and re-reviews.
- **Local Mode** (`COMMITS` given, or inferred from WIP): Reviews commits or uncommitted changes **read-only through the verdict** (no branch switching, no `git reset --hard`, no `gh`). When findings exist, fixes via `dev-cycle` and commits locally only (no push, no `gh`).

**Invocation semantics:** Invoking this skill means the user wants *something* reviewed. Your first job is to determine the **review target** (Phase 0 priority rules), not to ask "do you want a review?". Only ask when the target is genuinely ambiguous.

> **Maintenance note:** `multi-agent-review` inlines this skill's full flow as a self-contained superset (6-agent deep dive). Apply review-flow behavior changes to both files.

## When to Use

- Reviewing a GitHub PR or local commit range (e.g., output of `dev-cycle`)
- Reviewing the current branch's work-in-progress before committing/opening a PR
- Reviewing refactors that modify component structure or API contracts
- Pre-approval safety checks for PRs removing or restructuring code
- Re-reviewing PRs after fixes have been pushed

This is the default entry point for review requests. For high-stakes or security-sensitive changes, escalate to `multi-agent-review` (mandatory pre-flight, 6 specialized agents, readiness score) — it uses the same severity-driven verdict rule as this skill.

**Trigger phrases:** "review this", "check my changes", "look over what I did", "is this PR good to merge" - all imply this skill, even without a PR number or commit SHA.

## Workflow Overview

```
0. Setup           (Resolve target: PR number -> commits/range -> infer WIP; PR mode resets HEAD to the PR head in place, Local mode is read-only)
1. Gather Context  (PR metadata or git log + diff; extract intent)
2. Assess Size     (small ≤3 files & ≤50 lines -> single-pass; else -> 3-agent parallel)
3. Investigate     (read full files, trace removals, grep usage sites)
4. Analyze         (parallel subagents or single-pass)
5. Merge & Deliver (deduplicate, severity tags; post to GH or present in chat; if ANY findings -> Phase 6)
6. Fix Findings    (dev-cycle fixes ALL findings; PR mode: commit + push to PR branch + re-review; Local mode: commit only)
7. Re-Review       (verify fixes against prior findings; post updated review to GH or present in chat)
```

## Phase 0: Setup

### Parameters & Mode Selection

| Parameter | Default | Description |
|-----------|---------|-------------|
| `COMMITS` | *(empty)* | Space-separated SHAs/refs or range `A..B`. When set, triggers **Local Mode** (read-only through verdict). |
| `FULL` | `false` | **Full review flag.** When set (e.g., "full review", `FULL=true`), PR Mode ignores any prior review and reviews the complete `$BASE..$HEAD_REV` range — every change in the PR, not just the delta since the last review. |
| `WORKTREE`| repo root | Directory path of the target git workspace (`cd "$WORKTREE"` if provided). |

**No branch creation:** This skill never creates local branches. PR Mode switches revisions in place with `git reset --hard <revision>` (Phase 0 PR Mode Setup).

### Review Target Inference

Resolve the target in this priority order:

1. **Explicit PR number/URL** (e.g., "review PR #42", "review https://github.com/org/repo/pull/42") -> **PR Mode** on that PR.
2. **Explicit commits/range** (e.g., "review abc123..def456", "review the last 3 commits") -> **Local Mode** on that range.
3. **Nothing explicit** -> infer current WIP:
   a. Current branch has an open PR (`gh pr view --json number` succeeds) -> **PR Mode** on that PR.
   b. Working tree has uncommitted changes (`git status --porcelain` non-empty) -> **Local Mode** on uncommitted changes (`git diff HEAD` + untracked files).
   c. Branch has unpushed commits vs. upstream/default -> **Local Mode** on `<merge-base>..HEAD` (e.g., `git merge-base HEAD origin/main`..`HEAD`).
   d. Else -> **Local Mode** on the most recent commit (`HEAD~1..HEAD`).
4. **Ask only when truly ambiguous** (e.g., both a PR number and an unrelated range given, or nothing reviewable found). Announce the resolved target (one line: mode + range/PR) before gathering context, so a wrong inference is caught early.

### Local Mode Setup

> 🛑 **Read-Only Guardrail (Phases 0–5):** NEVER run `git reset --hard`, `git checkout`, `git switch`, `git branch -D`, `git fetch --force`, or any `gh` command during the review. Do not alter HEAD or the working tree. The only writes happen in Phase 6, and only a local commit - never a push, never `gh`.

1. `cd "$WORKTREE"` if specified.
2. Resolve the review range:
   - **Explicit `COMMITS="A..B"`:** `BASE=A`, `HEAD_REV=B`.
   - **Explicit commit list:** `BASE` = parent of earliest commit (or `4b825dc642cb6eb9a060e54bf8d69288fbee4904` if root), `HEAD_REV` = latest commit.
   - **Inferred unpushed commits:** `BASE=$(git merge-base HEAD @{upstream} 2>/dev/null || git merge-base HEAD origin/main)`, `HEAD_REV=HEAD`.
   - **Inferred last commit:** `BASE=HEAD~1`, `HEAD_REV=HEAD`.
   - **Inferred uncommitted WIP:** No range - the diff is `git diff HEAD` (staged + unstaged) + untracked files. Read files from the working tree; before-state via `git show HEAD:<path>`.
3. Validate refs (skip for WIP): `git rev-parse --verify "$BASE^{commit}" "$HEAD_REV^{commit}"`.
4. Summary: Mode=local (read-only), Target=<range | WIP>, Base=$BASE, Head=$HEAD_REV.

### PR Mode Setup

1. `cd "$WORKTREE"` if specified, then fetch PR base and head. This step must succeed before continuing:
   `PR_JSON=$(gh pr view <N> --json headRefOid,baseRefName)` — abort with the `gh` error if it fails.
2. Resolve the review range:
   `HEAD_REV=$(echo "$PR_JSON" | jq -r .headRefOid)`
   `BASE=$(echo "$PR_JSON" | jq -r .baseRefName)`
3. Detect remote (prefer `github`, fall back to `origin`, else abort) and switch to the PR head **in place** - never create a local branch; use `git reset --hard` to move the current branch onto the expected revision. The working tree must be clean first (`git status --porcelain` empty) - `git reset --hard` discards uncommitted work; if dirty, abort and surface to the user:
   ```
   if git remote | grep -qx github; then REMOTE=github
   elif git remote | grep -qx origin; then REMOTE=origin
   else echo "abort: no github/origin remote" >&2; exit 1; fi
   git fetch --force "$REMOTE" "pull/<N>/head"
   git reset --hard "$HEAD_REV"
   ```
4. **Incremental review — review only changes since the last review.** Check whether this PR already has a review from the current actor (this skill's own prior verdict, posted via `gh pr review`):
   ```
   gh api repos/{owner}/{repo}/pulls/<N>/reviews --jq '[.[] | select(.user.login == "'"$(gh api user --jq .login)"'")] | last | {id, commit_id, submitted_at}'
   ```
   - **Prior review exists:** set `REVIEW_BASE` to that review's `commit_id` (the PR head at the time of the last review). Review only the delta `$REVIEW_BASE..$HEAD_REV` — commits pushed since the last review. Verify the delta is non-empty (`git rev-parse "$REVIEW_BASE^{commit}"`; if `$REVIEW_BASE == $HEAD_REV`, report "no new commits since last review" and stop). Still read prior findings (from the last review body) to confirm they were addressed in the delta. Announce: `Incremental review: <REVIEW_BASE>..<HEAD_REV> (N new commits since review <id>)`.
   - **No prior review:** full review of `$BASE..$HEAD_REV` as before.
   - **Escape hatch (`FULL` flag):** if `FULL` is set or the user explicitly asks for a full re-review ("review the whole PR", "full review"), skip the prior-review lookup entirely and use `$BASE..$HEAD_REV`.
5. Summary: Mode=PR, Remote=$REMOTE, Target=$BASE..$HEAD_REV (or incremental $REVIEW_BASE..$HEAD_REV), Base=$BASE, Head=$HEAD_REV.

## Phase 1: Gather Context

- **PR Mode:**
  `gh pr view <N> --json number,title,headRefName,baseRefName,commits,files,body,additions,deletions`
  `gh pr diff <N>`
  - **Incremental review (REVIEW_BASE set in Phase 0):** scope the diff to the delta instead of the whole PR: `git log --format='--- %h ---%n%s%n%b' $REVIEW_BASE..$HEAD_REV` and `git diff $REVIEW_BASE..$HEAD_REV`. Use the full `gh pr diff` only as background context for how the delta fits into the overall PR.
- **Local Mode:**
  - Committed range: `git log --format='--- %h ---%n%s%n%b' $BASE..$HEAD_REV` and `git diff $BASE..$HEAD_REV`
  - Uncommitted WIP: `git status --porcelain`, `git diff HEAD`; read untracked files directly
- **Extract intent:** Summarize stated goals, problem solved, and chosen approach from PR body or commit log. For WIP reviews with no commit messages, infer intent from the conversation that produced the changes. Note if intent is missing or vague.

## Phase 2: Assess PR Size

| Size | Threshold | Review Path |
|------|-----------|-------------|
| **Small** | ≤3 files AND ≤50 lines changed | **Single-pass review.** Full investigation (Phase 3), but review directly without subagents. |
| **Large** | >15 files OR >500 lines changed | **3-agent review + flag size.** Recommend splitting PR. |
| **Standard** | Everything else | **3-agent parallel review** (Phase 4). |

## Phase 3: Deep Investigation

Surface diffs are insufficient. Perform deep verification:

1. **Read Full Files:** Diff shows changes; full files show context. Local Mode (committed range): read via `git show $HEAD_REV:<path>` (or `$BASE:<path>` for before-state). Uncommitted WIP: read the working tree directly; before-state via `git show HEAD:<path>`.
2. **Trace Removed Component Hierarchies:** What did removed code render/do? Check child components, navbars, sidebars, providers. Check side effects (context providers, event listeners, cleanup hooks, DB transactions). Ensure replacements provide equivalent capabilities.
3. **Check Usage Sites:** `grep -r "ChangedSymbol" src/ pkg/ internal/` to verify callers adapt to changes.
4. **Verify Imports/Exports:** Removed exports aren't required elsewhere; new imports are valid.
5. **Migrations & Schemas:** Verify schema/SQL changes, column renames, and migration checksums (e.g., `atlas.sum`).
6. **Incomplete Implementation Patterns:** Watch for `TODO`s, disabled lints without explanation (`// eslint-disable`), hardcoded values, and empty callbacks.

## Phase 4: Parallel Analysis (3 Subagents)

*Skip for Small PRs (use single-pass).*

Dispatch 3 subagents concurrently in a single message with multiple tool calls:

| Agent | Perspective | Primary Focus |
|-------|------------|---------------|
| **A** | **Completeness** | Validates the diff fully delivers stated intent. Maps goals to changes; flags missing or partial implementations. |
| **B** | **Correctness** | Syntax, logic bugs, security vulnerabilities, error handling, performance, invalid imports, missing cleanup, lifecycle/state-transition bugs (stale references across mount/unmount or connect/disconnect, gap-window data loss in buffers). |
| **C** | **Impact** | Regressions to existing behavior, API contract breaks, broken callers, schema drift. Pre-existing bugs are out of scope. |

**Lifecycle & state-transition tracing (Agent B mandate):** Code review finds bugs in functions, but lifecycle bugs live *between* functions, across time. For every component with persistent state (connections, sessions, buffers, DOM-bound instances such as xterm/charts/maps), enumerate the user journeys through state transitions — not just "does this function work" but "what sequence of states does the user pass through?":

- connect → attached → detached → reattached
- connect → attached → tab away (unmount) → tab back (remount)
- connect → attached → browser close → reopen → reattach

For each transition, trace three things:
(a) **Who holds a reference to what?** Closures, refs, pointers, goroutines — do they still point at valid targets after the transition, or at destroyed DOM elements / closed connections?
(b) **Where does data flow during the gap?** Between detach and reattach, unmount and remount — is anything buffering? Is anything lost?
(c) **What does the user see?** After the transition completes, is the UI consistent with backend state?

**Subagent file access:**
- PR Mode: Read working-tree files directly (HEAD was reset to the PR head in Phase 0); before-state via `git show $BASE:<path>`.
- Local Mode (committed range): Read strictly via `git show $HEAD_REV:<path>` / `$BASE:<path>`; forbid state-changing git commands.
- Local Mode (uncommitted WIP): Read working-tree files directly; before-state via `git show HEAD:<path>`. Forbid state-changing git commands.

**Verification Runs:** Execute project build/test scripts (e.g., `go test -race ./...`, `npm test`, `bun run typecheck`).

## Phase 5: Merge & Deliver Review

1. **Deduplicate & Group:** Collapse duplicate findings across perspectives into single entries with cross-references.
2. **Assign Severities:**
   - **Critical (MUST FIX):** Security flaw, data loss, broken core functionality.
   - **Warning (SHOULD FIX):** Logic gap, missing error handling, incomplete feature.
   - **Suggestion (CONSIDER):** Optional performance or structural improvement.
   - **Nit / FYI:** Minor style, formatting, or purely informational note.
3. **Structure Output:**

```markdown
# PR #<N> Review - [Verdict]   <!-- Local Mode: # Local Review <BASE>..<HEAD_REV> - [Verdict] | # Local Review - Uncommitted Changes - [Verdict] -->

## Critical Issues (MUST FIX)
### [Title]
[file#Lstart-Lend](path)
**Problem:** [Description]
**Fix:** [Solution/Guidance]

## Warnings (SHOULD FIX)
...

## Suggestions (CONSIDER)
...

## Nits / FYI
...

## Summary of Changes
- [3–5 bullet points summarizing changes, approach, and key patterns]
```

4. **Verdict:** Zero issues -> **Approved**. Nits/FYIs/Suggestions only -> **Approved** (verdict reflects mergeability only). Any Warning or Critical -> **Request Changes**. `multi-agent-review` uses this same severity-driven rule — its readiness score is advisory and never overrides it.
5. **Deliver:**
   - **PR Mode:** `gh pr review <N> --approve/--request-changes --body-file review.md` (always use `--body-file`). Then output a clickable PR link so the user can jump straight to it: `gh pr view <N> --json url --jq .url`.
   - **Local Mode:** Present formatted review in chat. Do NOT call `gh`. Offer to save to `review-<sha>.md` (or `review-wip.md` for uncommitted changes).
   - **Report files are scratch artifacts:** any `review*.md` written during the review (body files, saved local reports, re-review updates) is intermediate. Never `git add`/commit it — the Phase 6 fix commit must not include it — and delete it once delivered; prefer a temp path (e.g., `mktemp`) for the `--body-file` so the working tree stays clean. A Local Mode save the user explicitly accepted may persist, but stays uncommitted.
6. **Next phase:** No findings at all -> done. One or more findings of **ANY** severity -> **Phase 6** (mandatory). Even an *Approved* verdict carrying nits/suggestions enters Phase 6 - the verdict is about mergeability, the fix loop is about cleanliness.

## Phase 6: Fix Findings (Auto-Fix via dev-cycle)

**Trigger:** Phase 5 produced ≥1 finding of any severity. A clean approval with zero findings skips this phase.

**Principle:** Don't stop at the verdict. Hand every finding to `dev-cycle` for resolution, then close the loop: PR mode pushes and re-reviews; Local mode commits and stops.

**Write-authorization gate:** `dev-cycle` runs its own pipeline with a HARD user-approval gate on its synthesized fix plan (Phase 1.3) and its own multi-axis review. Honor that gate - do not bypass it. (Trivial fix sets may take dev-cycle's fast path and skip planning; its model-confirmation gate still applies in multi-model environments.) **Autonomous callers** (`as-goal`) auto-approve this gate per the autonomy contract in dev-cycle Phase 1.3.

### 6.1 Hand off findings to dev-cycle

1. Compile the full findings list (every severity) into a structured fix brief - per finding: title, location (`file#Lstart-Lend`), problem, prescribed fix.
   Map severities into dev-cycle's taxonomy (its Phase 3 uses `Critical`/`Required`/`Optional`/`Nit`):

   | pr-review severity | dev-cycle severity | Disposition |
   |---|---|---|
   | Critical | `Critical` | Fixed and committed under Phase 3 |
   | Warning | `Required` | Fixed and committed under Phase 3 |
   | Suggestion | `Optional` | Batched into the same fix commit (explicitly allowed for review hand-offs) |
   | Nit / FYI | `Nit` | Batched into the same fix commit, or reported as declined with rationale |

2. Invoke `dev-cycle` in the same workspace (`$WORKTREE`), seeded with the fix brief as the work to implement. State the goal: **resolve every listed finding without introducing regressions**.
3. Let `dev-cycle` own its full pipeline (branch verification, planning, TDD, multi-axis review, simplification, commit). Don't reimplement its phases here. Respect its gates:
   - **Phase 0** may ask about an unclean working tree (notably Local Mode WIP reviews) - resolve per dev-cycle's rules with the user.
   - **Phase 1.3** is a HARD approval gate - STOP and wait for the user to approve / modify / reject the fix plan.
   - **Phase 5** commits fixes with a Conventional Commit message (e.g., `fix: address pr-review findings`).
4. Capture the fix commit SHA(s) for the re-review and status table.

### 6.2 Mode-specific completion

**PR Mode - fix, push, re-review:**
1. After dev-cycle commits fixes locally (on the current branch, which was reset to the PR head in Phase 0), push to the PR's head branch:
   - `HEAD_REF=$(gh pr view <N> --json headRefName --jq '.headRefName')`; check `headRepositoryOwner` / `headRepository` to detect forks.
   - **Same-repo PR:** `git push $REMOTE "HEAD:$HEAD_REF"` (no local branch is created).
   - **Fork PR:** add the fork as a remote (`git remote add fork <fork-url>`) and push to the fork's `HEAD_REF`; if credentials don't allow it, ask the user how to publish. Never silently push to the wrong repo.
2. Proceed to **Phase 7** against the updated online PR.

**Local Mode - fix, commit, stop:**
1. After dev-cycle commits fixes locally, **stop**. Do NOT push and do NOT call `gh`.
2. Present an updated findings-status table: each prior finding marked **Fixed** (with fix commit SHA) or **Still-open**, plus any new issues dev-cycle's review surfaced.
3. Remind the user Local Mode is push-free; to re-review the fix commit(s), re-invoke this skill with the fix range as `COMMITS`.

### 6.3 Loop guard

Run **at most one automatic fix iteration** per review invocation. If the Phase 7 re-review still surfaces Critical or Warning findings, present them and stop - do **not** auto-loop. The user may re-invoke for another round. Suggestions/Nits remaining after one iteration are reported but don't trigger another auto-fix round.

## Phase 7: Re-Review

Verifies prior findings are resolved without new regressions. Entered as the tail of Phase 6 (PR mode, after fix push) or on demand when the user pushes fixes independently.

- **Local Mode (on demand):** Ask for fix commit SHA(s)/range. Verify prior findings against `git show <fix-sha>` or `git diff <old-head>..<new-head>`. Present updated status in chat. (Phase 6 Local mode does not auto-enter here - it stops after commit.)
- **PR Mode:** Re-run Phase 0 PR Mode Setup to refresh `$HEAD_REV` and `git reset --hard` to it, then verify previous findings are resolved without new regressions. Post updated review via `gh`, then output a clickable PR link: `gh pr view <N> --json url --jq .url`.
- **Re-review scope:** Mechanical/small fixes -> 0 subagents (verify directly). Complex logic updates -> 1-2 focused subagents on new diff. Large refactors -> full 3-agent review.
- When entered from Phase 6, apply the **Loop guard** (6.3): if Critical/Warning findings remain, report and stop rather than re-entering Phase 6.

## Specific Checklists

### UI Component Refactor
- [ ] Traced all removed components and their rendered children (navbars, footers, sidebars).
- [ ] Verified context providers, state wrappers, and responsive layout classes (flex/grid).
- [ ] Checked accessibility attributes (ARIA, focus management, keyboard navigation).

### API / Handler Refactor
- [ ] Auth & middleware enforced across all updated endpoints.
- [ ] Error handling paths preserved; response payloads match client contracts.
- [ ] Rate limits and CORS headers verified.

### State Management
- [ ] Verified state consumers, initial values, and useEffect dependency arrays (no stale closures).
- [ ] Storage persistence (localStorage / cookies) synced.

### Lifecycle & State Transitions
- [ ] Buffer & replay patterns: what goes INTO the buffer during normal operation (not just during disconnection)? What comes OUT on replay — the full history the user expects, or only the gap window? Is the buffer drained on replay or accumulated?
- [ ] DOM-bound instances (xterm, charts, maps): is the DOM element always mounted or conditionally rendered? If conditional, what happens to the bound instance on unmount? Are there closures/goroutines/read loops holding stale references to the old element?
- [ ] Reconnect/reattach paths: state re-initialized or reused? Subscriptions and event listeners re-established exactly once (no leaks, no doubles)?

### Migration & Schema Changes
- [ ] Migration checksums updated (e.g., `atlas.sum`).
- [ ] Column/table renames handled with data migration strategies and updated queries.
