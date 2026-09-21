---
name: multi-agent-review
description: "Ultra-thorough 7-agent parallel code review with build verification, deep dependency tracing, and structured readiness scoring. Use for high-stakes changes, large refactors, security-sensitive code, or when the user invokes multi-agent-review or asks for an 'ultra review'. Goes beyond pr-review's 3-agent approach with specialized agents for architecture & impact, correctness, security, performance, completeness, test/observability, and lifecycle & state transitions."
---

# Multi-Agent Review

## Overview

Deep, ultra-thorough code review dispatching **7 specialized review agents** in parallel, preceded by mandatory build/test verification and deep dependency tracing. Produces a structured readiness score and auto-fixes findings via `dev-cycle`. **Self-contained superset of `pr-review`:** every mode, phase, and rule is inlined below — executing this skill never requires opening another skill file.

**Core principle:** Every review dimension deserves a dedicated expert. A single reviewer misses cross-cutting concerns; 3 reviewers cover the basics; 7 reviewers catch what the others miss.

**Two modes:**
- **PR Mode** (default): Reviews a GitHub PR via `gh` and posts the structured verdict to GitHub. When findings exist, fixes via `dev-cycle`, pushes to the PR branch, and re-reviews.
- **Local Mode** (`COMMITS` given, or inferred from WIP): Reviews commits or uncommitted changes **read-only through the verdict** (no branch switching, no `git reset --hard`, no `gh`). When findings exist, fixes via `dev-cycle` and commits locally only (no push, no `gh`).

**Invocation semantics:** Invoking this skill means the user wants *something* reviewed. Your first job is to determine the **review target** (Phase 0 priority rules), not to ask "do you want a review?". Only ask when the target is genuinely ambiguous.

> **Maintenance note:** The full review flow is inlined in this file; `pr-review` keeps its own copy as the lightweight default entry point. Apply review-flow behavior changes to both files.

## When to Use

- High-stakes changes touching auth, payments, data migrations, or public APIs
- Large refactors spanning 10+ files or multiple subsystems
- Security-sensitive code (JWT handling, RBAC, SQL, encryption)
- Performance-critical paths (database queries, hot loops, background workers)
- Lifecycle-heavy components: sessions, connections, buffers, DOM-bound instances (xterm, charts, maps), attach/detach flows
- When `pr-review` is insufficient — need deeper, more specialized analysis
- User explicitly invokes `multi-agent-review` or asks for "ultra review"

## Workflow

```
0. Setup            (Resolve target: PR number -> commits/range -> infer WIP; PR mode resets HEAD to the PR head in place, Local mode is read-only)
1. Gather Context   (PR metadata or git log + diff; extract intent)
2. Pre-Flight       (Build verification + test suite — MANDATORY)
3. Deep Investigation (Full-file reads, dependency graph, usage sites)
4. Parallel Review  (7 specialized subagents dispatched concurrently)
5. Synthesize       (Deduplicate, severity-tag, readiness score)
6. Deliver          (Post to GH or present in chat)
7. Fix Findings     (dev-cycle resolves ALL findings)
8. Re-Review        (Verify fixes; updated readiness score)
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

> 🛑 **Read-Only Guardrail (Phases 0–6):** NEVER run `git reset --hard`, `git checkout`, `git switch`, `git branch -D`, `git fetch --force`, or any `gh` command during the review. Do not alter HEAD or the working tree. The only writes happen in Phase 7, and only a local commit - never a push, never `gh`.

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

## Phase 2: Pre-Flight Verification (MANDATORY)

Before dispatching review agents, verify the code compiles and tests pass:

```bash
# Go projects
go build ./...
go test -race ./...

# Node/frontend projects
bun run typecheck 2>/dev/null || npm run typecheck 2>/dev/null
bun run lint 2>/dev/null || npm run lint 2>/dev/null
bun run test 2>/dev/null || npm run test 2>/dev/null
```

**If build fails:** Report the build error, attempt one fix via `dev-cycle`, then proceed with review. (This gate repair is separate from the Phase 7 fix loop and does not consume its one-iteration guard.)
**If tests fail:** Report failures — agents must assess whether failures are pre-existing or introduced by the change.

Record results:
```
Pre-Flight: build=✅  tests=✅ (142 passed, 0 failed)  lint=✅  typecheck=✅
```

## Phase 3: Deep Investigation

Surface diffs are insufficient. Perform deep verification:

1. **Read Full Files:** Diff shows changes; full files show context. Local Mode (committed range): read via `git show $HEAD_REV:<path>` (or `$BASE:<path>` for before-state). Uncommitted WIP: read the working tree directly; before-state via `git show HEAD:<path>`.
2. **Trace Removed Component Hierarchies:** What did removed code render/do? Check child components, navbars, sidebars, providers. Check side effects (context providers, event listeners, cleanup hooks, DB transactions). Ensure replacements provide equivalent capabilities.
3. **Check Usage Sites:** `grep -r "ChangedSymbol" src/ pkg/ internal/` to verify callers adapt to changes.
4. **Verify Imports/Exports:** Removed exports aren't required elsewhere; new imports are valid.
5. **Migrations & Schemas:** Verify schema/SQL changes, column renames, and migration checksums (e.g., `atlas.sum`).
6. **Incomplete Implementation Patterns:** Watch for `TODO`s, disabled lints without explanation (`// eslint-disable`), hardcoded values, and empty callbacks.

Then go deeper than a standard review:

7. **Trace the dependency graph** — for each changed symbol:
   - **Upstream:** Who calls this? What depends on this interface?
   - **Downstream:** What does this call? What side effects does it trigger?
   - **Lateral:** What else implements this interface? What shares this pattern?
8. **Wider usage-site grep:** extend step 3 to `grep -r "ChangedSymbol" src/ pkg/ internal/ handler/ service/`.
9. **Migration version uniqueness:** unique 14-digit versions, `atlas.sum` consistent.
10. **Swallowed errors** in the incomplete-patterns watch (alongside `TODO`s, disabled lints, hardcoded values, empty callbacks).

## Phase 4: Parallel 7-Agent Review

Dispatch 7 subagents **concurrently** in a single message:

| Agent | Codename | Focus |
|-------|----------|-------|
| **A1** | **Architect** | Design patterns, SOLID principles, separation of concerns, API contract consistency, module boundaries, interface stability — and the **impact lens** (pr-review's Agent C): regressions to existing behavior, broken callers, backward compatibility, schema drift |
| **A2** | **Logician** | Logic bugs, off-by-one, nil dereference, race conditions, deadlocks, error handling gaps, panic paths, type safety |
| **A3** | **Sentinel** | Security vulnerabilities: injection, auth bypass, data exposure, CSRF, secrets in code, unsafe deserialization, privilege escalation |
| **A4** | **Performer** | N+1 queries, unbounded scans, missing indexes, hot-path allocations, algorithmic complexity (O(n²) in loops), goroutine leaks, connection pool exhaustion |
| **A5** | **Cartographer** | Completeness: diff delivers stated intent, no missing pieces, no orphaned TODOs, consistent naming, documentation updated, error messages user-friendly |
| **A6** | **Observer** | Test coverage of new/changed code, logging adequacy, metrics/tracing instrumentation, alerting hooks, debuggability (can you diagnose this in production?) |
| **A7** | **Tracer** | Lifecycle & state transitions: enumerate user journeys across connect→disconnect→reconnect and mount→unmount→remount; stale references (closures, refs, goroutines) to destroyed DOM elements/connections; gap-window data flow — is output buffered and replayed in full, or lost?; UI/backend consistency after each transition; buffer-and-replay correctness (what goes in during normal operation vs. only while detached; drained vs. accumulated) |

Every pr-review lens maps to exactly one agent above: A Completeness → Cartographer, B Correctness → Logician + Sentinel + Performer + Tracer, C Impact → Architect. No perspective is dropped when escalating from pr-review.

### Agent Instructions Template

Each agent receives:
```
You are [CODENAME], reviewing [PR #N | commits BASE..HEAD | uncommitted changes].

**Your lens:** [FOCUS from table above]

**Diff:**
<paste relevant diff sections>

**Full files (read them):**
- file1.go
- file2.go

**Intent:** <extracted intent from Phase 1>

**Pre-flight:** build=<status> tests=<status>

**Rules:**
- Only report issues within YOUR lens. Do not duplicate other agents' perspectives.
- Severity per the Phase 5 taxonomy.
- Cite file and line numbers.
- Pre-existing bugs are out of scope UNLESS the change makes them worse.
- For each finding, prescribe a concrete fix.
```

### Subagent File Access

- **PR Mode:** Read working-tree files directly (HEAD was reset to the PR head in Phase 0); before-state via `git show $BASE:<path>`.
- **Local Mode (committed range):** Read strictly via `git show $HEAD_REV:<path>` / `$BASE:<path>`; forbid state-changing git commands.
- **Local Mode (uncommitted WIP):** Read working-tree files directly; before-state via `git show HEAD:<path>`. Forbid state-changing git commands.

Build/test verification is covered by the mandatory Pre-Flight (Phase 2) — agents consume its recorded status rather than re-running suites.

### Size-Based Dispatch

| Size | Threshold | Review Path |
|------|-----------|-------------|
| **Small** | ≤3 files AND ≤50 lines changed | **Single-pass review.** Full investigation (Phase 3), but review directly without subagents, applying all 7 lenses. |
| **Large** | >15 files OR >500 lines changed | **7-agent review + flag size.** Recommend splitting PR. |
| **Standard** | Everything else | **7-agent parallel review.** |

## Phase 5: Synthesize

1. **Deduplicate:** Collapse findings reported by multiple agents into single entries with cross-references (e.g., *"Also flagged by Sentinel"*).
2. **Severity assignment:**
   - **Critical (MUST FIX):** Security flaw, data loss/corruption, broken core functionality, race condition, panic path.
   - **Warning (SHOULD FIX):** Logic gap, missing error handling, incomplete implementation, N+1 query, missing test.
   - **Suggestion (CONSIDER):** Optional performance, structural, or observability improvement.
   - **Nit / FYI:** Style, naming, documentation clarity.
3. **Readiness Score:** Compute a numeric score (0–100):

| Finding | Deduction |
|---------|-----------|
| Critical | -20 each |
| Warning | -8 each |
| Suggestion | -2 each |
| Nit | 0 |

Score = max(0, 100 - sum of deductions). The score is an **advisory signal only** — it never overrides the severity-driven verdict (step 5). Bands:
- **90–100:** Excellent — at most minor polish outstanding
- **70–89:** Solid — warnings to address before merge
- **50–69:** Significant rework likely
- **0–49:** Fundamental issues — reconsider approach

4. **Structure output:**

```markdown
# [PR #N | Local Review BASE..HEAD] — [Verdict]

**Readiness Score: NN/100** (advisory — see bands above)
**Pre-Flight:** build=✅ tests=✅ lint=✅
**Agents dispatched:** Architect, Logician, Sentinel, Performer, Cartographer, Observer, Tracer

## Critical Issues (MUST FIX)
### [Title]
[file#Lstart-Lend](path) — *Flagged by: [Agent]*
**Problem:** [Description]
**Fix:** [Concrete solution]

## Warnings (SHOULD FIX)
...

## Suggestions (CONSIDER)
...

## Nits / FYI
...

## Summary of Changes
- [3–5 bullet points: what changed, approach, key patterns]

## Dependency Impact
- [Upstream/downstream effects of the change]
```

5. **Verdict:** Zero issues → **Approved**. Nits/FYIs/Suggestions only → **Approved** (verdict reflects mergeability only). Any Warning or Critical → **Request Changes**. Report the readiness score alongside as advisory context only — it never changes the verdict, so both skills agree on identical findings.

## Phase 6: Deliver

- **PR Mode:** `gh pr review <N> --approve/--request-changes --body-file review.md` (always use `--body-file`). Then output a clickable PR link so the user can jump straight to it: `gh pr view <N> --json url --jq .url`.
- **Local Mode:** Present the formatted review in chat. Do NOT call `gh`. Offer to save to `review-<sha>.md` (or `review-wip.md` for uncommitted changes).
- **Report files are scratch artifacts:** any `review*.md` written during the review (body files, saved local reports, re-review updates) is intermediate. Never `git add`/commit it — the Phase 7 fix commit must not include it — and delete it once delivered; prefer a temp path (e.g., `mktemp`) for the `--body-file` so the working tree stays clean. A Local Mode save the user explicitly accepted may persist, but stays uncommitted.

**Next:** No findings at all → done. One or more findings of **ANY** severity → **Phase 7** (mandatory). Even an *Approved* verdict carrying nits/suggestions enters Phase 7 — the verdict is about mergeability, the fix loop is about cleanliness.

## Phase 7: Fix Findings (Auto-Fix via dev-cycle)

**Trigger:** Phase 5 produced ≥1 finding of any severity. A clean approval with zero findings skips this phase.

**Principle:** Don't stop at the verdict. Hand every finding to `dev-cycle` for resolution, then close the loop: PR Mode pushes and re-reviews; Local Mode commits and stops.

**Write-authorization gate:** `dev-cycle` runs its own pipeline with a HARD user-approval gate on its synthesized fix plan (Phase 1.3) and its own multi-axis review. Honor that gate - do not bypass it. (Trivial fix sets may take dev-cycle's fast path and skip planning; its model-confirmation gate still applies in multi-model environments.) **Autonomous callers** (`as-goal`) auto-approve this gate per the autonomy contract in dev-cycle Phase 1.3.

### 7.1 Hand off findings to dev-cycle

1. Compile the full findings list (every severity) into a structured fix brief - per finding: title, location (`file#Lstart-Lend`), problem, prescribed fix.
   Map severities into dev-cycle's taxonomy (its Phase 3 uses `Critical`/`Required`/`Optional`/`Nit`):

   | Severity here | dev-cycle severity | Disposition |
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

### 7.2 Mode-specific completion

**PR Mode - fix, push, re-review:**
1. After dev-cycle commits fixes locally (on the current branch, which was reset to the PR head in Phase 0), push to the PR's head branch:
   - `HEAD_REF=$(gh pr view <N> --json headRefName --jq '.headRefName')`; check `headRepositoryOwner` / `headRepository` to detect forks.
   - **Same-repo PR:** `git push $REMOTE "HEAD:$HEAD_REF"` (no local branch is created).
   - **Fork PR:** add the fork as a remote (`git remote add fork <fork-url>`) and push to the fork's `HEAD_REF`; if credentials don't allow it, ask the user how to publish. Never silently push to the wrong repo.
2. Proceed to **Phase 8** against the updated online PR.

**Local Mode - fix, commit, stop:**
1. After dev-cycle commits fixes locally, **stop**. Do NOT push and do NOT call `gh`.
2. Present an updated findings-status table: each prior finding marked **Fixed** (with fix commit SHA) or **Still-open**, plus any new issues dev-cycle's review surfaced.
3. Remind the user Local Mode is push-free; to re-review the fix commit(s), re-invoke this skill with the fix range as `COMMITS`.

### 7.3 Loop guard

Run **at most one automatic fix iteration** per review invocation. If the Phase 8 re-review still surfaces Critical or Warning findings, present them and stop - do **not** auto-loop. The user may re-invoke for another round. Suggestions/Nits remaining after one iteration are reported but don't trigger another auto-fix round.

## Phase 8: Re-Review

Verifies prior findings are resolved without new regressions. Entered as the tail of Phase 7 (PR Mode, after fix push) or on demand when the user pushes fixes independently.

- **PR Mode:** Re-run Phase 0 PR Mode Setup to refresh `$HEAD_REV` and `git reset --hard` to it, then verify previous findings are resolved without new regressions. Post updated review via `gh pr review`, then output a clickable PR link: `gh pr view <N> --json url --jq .url`.
- **Local Mode (on demand):** Ask for fix commit SHA(s)/range. Verify prior findings against `git show <fix-sha>` or `git diff <old-head>..<new-head>`. Present updated status in chat. (Phase 7 Local Mode does not auto-enter here - it stops after commit.)
- **Re-review scope:** Mechanical/small fixes → 0 subagents (verify directly). Complex logic updates → re-dispatch only the agents that had findings (not all 7). Large refactors → full 7-agent review.
- **Always:** Re-run Pre-Flight (Phase 2) and compute the updated readiness score.
- When entered from Phase 7, apply the **Loop guard** (7.3): if Critical/Warning findings remain after one fix iteration, report and stop rather than re-entering Phase 7.

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

### Go Backend
- [ ] Race condition safety (`-race` flag, mutex/atomic usage)
- [ ] Context propagation (no `r.Context()` after response write)
- [ ] Error wrapping (`fmt.Errorf("...: %w", err)`)
- [ ] Named SQL params (`@name`) with `pgx.NamedArgs`
- [ ] Transaction boundaries (`pgx.Tx`, `defer tx.Rollback`)
- [ ] Migration safety (unique 14-digit versions, `atlas.sum` hashed)

### Frontend (React/TypeScript)
- [ ] State management (initial values, derived state, invalidation)
- [ ] Responsive layout (flex/grid, breakpoints)
- [ ] Error boundaries and loading states

### API / Handler
- [ ] Request validation (OpenAPI spec matches handler expectations)
- [ ] Error responses consistent with existing patterns

### Database / Migration
- [ ] No duplicate 14-digit version prefixes
- [ ] Index coverage for new query patterns
- [ ] `workspace_id` scoping on all new tables/queries
