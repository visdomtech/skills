# Skills

This repository publishes the agent skills used by our engineering workflow.
Each top-level directory is one skill. Its `SKILL.md` holds the full rules.

Name a skill in your prompt to run it. Both forms work: the slash command
(`/dev-cycle ...`) and plain language ("run the dev cycle on this change").

`task sync` mirrors every skill directory from `~/.agents/skills` into this
repository. Run it after you edit a skill upstream.

```bash
task sync
```

## Core workflow skills

| Skill | What it does | Use it when |
|---|---|---|
| [`as-goal`](as-goal/SKILL.md) | Runs a role-based agent team until measurable exit gates pass. Budget: 10 iterations. | A large feature with verifiable success criteria. |
| [`dev-cycle`](dev-cycle/SKILL.md) | Runs plan → implement (TDD) → review → simplify → commit. | A non-trivial change across several files. |
| [`pr-review`](pr-review/SKILL.md) | Reviews a PR or local commits with 3 agents, then fixes every finding. | Any "is this good to merge?" request. |
| [`multi-agent-review`](multi-agent-review/SKILL.md) | The same flow with a mandatory build pre-flight and 7 specialist agents. | High-stakes, security, migration, or lifecycle code. |

## How they fit together

```
as-goal                    interview → team roles → exit gates → up to 10 iterations
└── dev-cycle              plan → implement → review → simplify → commit → wrap-up
    ├── multi-agent-planning   (dev-cycle Phase 1)
    └── multi-agent-review     (dev-cycle Phase 5, Option A or Option B)
        └── dev-cycle          (review fixes, then the review skill re-reviews)
```

`pr-review` is the default review entry point. `multi-agent-review` is its
superset and inlines the whole flow. Name the top skill for the job and let it
delegate.

---

## as-goal

Four fixed phases: interview, team assembly, gate definition, iteration. It
runs autonomously once the goal is confirmed. It does not stop between
iterations.

### Example 1 — a feature that needs several iterations

```
/as-goal Operators can upload a CSV of employee records and see import progress
in the UI.
```

What runs:

1. **Phase 1** calls `interview-me` and saves the confirmed goal to
   `docs/as-goals/csv-employee-upload.md`.
2. **Phase 2** writes the four role files to `docs/as-goals/csv-employee-upload/agents/`
   and creates `PROGRESS.md`.
3. **Phase 3** saves each gate to `docs/as-goals/csv-employee-upload/gates/`.
   Gates are immutable after this point.
4. **Phase 4** loops: the Architect plans, the Engineer runs `dev-cycle`, the
   Test Engineer runs `multi-agent-review` and writes an evidence manifest.

Per-iteration output lands in `docs/as-goals/<goal>/1/`, `2/`, and so on. The
run ends in `DONE.md` or `POST-MORTEM.md`.

### Example 2 — a goal that ships to production

```
/as-goal Public webhook endpoint for ingest events, with retry and rate limiting.
```

The Release Engineer bench role activates, because the goal changes deployable
behavior. It adds a launch and rollback gate. If the same gate fails in two
straight iterations with no clear cause, the Debugging Specialist activates in
the middle of the run.

### Example 3 — resume after a restart or context compaction

```
continue
```

The orchestrator reads `docs/as-goals/<goal>/PROGRESS.md` first. It resumes from
the `Next Actions` list. It does not rebuild state from iteration folders.

### Example 4 — when not to use it

```
/as-goal fix the off-by-one in the pagination helper   → use dev-cycle
/as-goal make the dashboard better                     → use interview-me first
```

Use `as-goal` only when the goal can be written as user-facing scenarios with
verifiable gates.

**Check afterwards:** every gate has linked evidence files. Failed gates carry
defect metadata, not a blind retry. `PROGRESS.md` shows the final decision.

---

## dev-cycle

Six phases. Phase 0 checks the branch and classifies the change. Each phase has
an exit gate and its own commit.

### Example 1 — a standard multi-file feature

```
/dev-cycle Add token refresh to the auth middleware, with tests.
```

What runs:

1. **Phase 0** resolves the remote and default branch, then fetches. A dirty tree
   or a branch behind `$REMOTE/$DEFAULT_BRANCH` stops the cycle until you choose
   stash, commit, rebase, merge, or abort.
2. **Phase 1** calls `multi-agent-planning` (3 agents: simplicity, performance,
   minimal change), then shows you the full plan. **It stops and waits** for
   `[Approve / Modify / Reject]`.
3. **Phase 2** implements vertical slices with RED → GREEN → REFACTOR.
4. **Phase 3** reviews every axis and fixes all `Critical` and `Required` findings.
5. **Phase 4** simplifies with behavior and tests unchanged.
6. **Phase 5** commits, prints the recap table, and offers the post-cycle choice.

### Example 2 — execute a plan you already have

```
/dev-cycle Execute docs/plans/retry-backoff.md
```

Phase 1 runs in Adopt mode. It loads the plan instead of re-planning, validates
it against the output contract, and still asks for your approval.

### Example 3 — a bug fix (Diagnose-and-Fix mode)

```
/dev-cycle Fix the panic when a WebSocket client reconnects twice.
```

The root-cause analysis comes before any plan, and you read it in full:

- **Symptom:** the observed error, logs, and when it started.
- **Reproduction:** the exact steps or failing test. Phase 2 turns it into the
  Prove-It test.
- **Root cause:** the mechanism, cited as `file:line`, with evidence.
- **Discarded hypotheses:** at least one alternative, with the proof that ruled
  it out.

If the evidence does not establish a cause, the cycle stops. It does not proceed
to a speculative fix. A bug fix with an unknown cause is never "Trivial", no
matter how few files the fix touches.

### Example 4 — the fast path

```
/dev-cycle Rename the config field userId to user_id in the parser.
```

The change is 3 files or fewer with an unambiguous requirement, so Phase 1 is
skipped. Phases 3 and 4 still run. The shared-state trace also still runs: the
cycle greps every reader of that config key before it commits.

### Example 5 — the post-cycle choice

Phase 5 prints the publish pre-flight before it asks:

```
Option A — local review only (read-only, no push, no gh)
Option B — publish + PR + online review
Commits to push: 3    HEAD: 3f2a1c9    Remote: github    PR base: github/main
```

Option A runs `multi-agent-review` in Local Mode on the cycle's commits. Option
B pushes, opens the PR with `gh pr create`, then runs `multi-agent-review` in PR
Mode. Nothing is pushed until you pick Option B.

**Progress file:** each cycle keeps `<task>-<yyyy-mm-dd-HH-MM>-progress.md` in
the repository root. It is the resume source of truth after compaction. It is
never committed, and Phase 5 deletes it.

**Check afterwards:** `git status` is clean. Each phase has its own commit SHA
(`feat`/`test`, `fix`, `refactor`). The recap lists deferred `Optional`/`Nit`
findings with a reason for each.

---

## pr-review

Three parallel agents: Completeness, Correctness, Impact. Any finding, at any
severity, starts the fix loop.

### Example 1 — review a GitHub PR (default: PR Mode)

```
/pr-review 42
```

What runs:

1. Resolves the remote (`github`, then `origin`) and resets your current branch
   onto the PR head. Your working tree must be clean first.
2. Checks for a prior review from these skills. If it finds one, it reviews only
   the commits pushed since then, and still confirms the old findings are closed.
3. Runs deep investigation: full files, not hunks, plus `grep` on each changed
   symbol, plus removed-capability tracing.
4. Dispatches 3 agents, merges their findings, posts the verdict with
   `gh pr review 42 --approve/--request-changes --body-file`.

### Example 2 — review local commits (Local Mode)

```
/pr-review COMMITS="abc1234..def5678"
```

Or say it in plain language: "review the last 3 commits". Local Mode is
read-only through the verdict. It does not switch branches, run `git reset
--hard`, or call `gh`. The review is shown in chat, and any fix commits stay
local.

### Example 3 — review work in progress

```
review my current changes before I commit
```

With nothing explicit given, the target is inferred in this order: an open PR on
this branch, then uncommitted changes, then unpushed commits, then the last
commit. The skill prints the resolved target on one line so you can catch a
wrong guess early.

### Example 4 — force a full re-review

```
/pr-review 42 FULL=true
```

Also triggered by "review the whole PR". It ignores the prior review and reads
the complete base → head range.

### Example 5 — the fix loop

A Warning about a missing error wrap starts Phase 6 automatically:

1. The findings become a fix brief, one entry per finding with location, problem
   and prescribed fix.
2. `dev-cycle` runs on that brief. Its plan approval gate stays in force, so you
   approve the fix plan before any code changes.
3. PR Mode pushes the fix to the PR head branch, then re-reviews. Local Mode
   commits and stops.
4. The loop guard allows one automatic fix round per invocation. If Critical or
   Warning findings survive it, the skill reports them and stops.

**Verdict rule:** a Warning or Critical anywhere → Request Changes. Nits and
suggestions alone → Approved. `WORKTREE=<path>` points a review at another
checkout.

---

## multi-agent-review

Use it when `pr-review` is not enough: auth, payments, schema migrations, public
APIs, refactors over 10 files, or connection and session lifecycle code.

### Example 1 — high-stakes PR

```
/multi-agent-review 87
```

What runs:

1. **Phase 2 pre-flight (mandatory)** builds and tests before any agent reads
   code:
   ```bash
   go build ./...
   go test -race ./...
   ```
   A build failure is reported, one repair is attempted through `dev-cycle`, and
   the review continues.
2. **Phase 3** traces each changed symbol upstream, downstream, and laterally.
   It also checks migration version uniqueness and `atlas.sum`.
3. **Phase 4** dispatches 7 agents in one message.

| Agent | Lens |
|---|---|
| A1 Architect | Design, module boundaries, API contracts, and impact/regression risk |
| A2 Logician | Logic bugs, nil dereference, races, error handling, panic paths |
| A3 Sentinel | Injection, auth bypass, data exposure, secrets, unsafe deserialization |
| A4 Performer | N+1 queries, unbounded scans, missing indexes, hot-path allocation |
| A5 Cartographer | Completeness against stated intent, orphaned TODOs, docs |
| A6 Observer | Test coverage, logging, metrics, production debuggability |
| A7 Tracer | Connect/disconnect and mount/unmount journeys, stale references, buffer replay |

4. **Phase 5** deduplicates, assigns severities, and prints a readiness score.

### Example 2 — a hard local gate before you open the PR

```
/multi-agent-review COMMITS="github/main..HEAD"
```

Local Mode keeps the whole review read-only. Fixes commit locally, with no push
and no `gh` call. This is also the default outcome of `dev-cycle` Option A.

### Example 3 — a small but risky diff

```
ultra review of the uncommitted changes in the acme provider
```

A diff of 3 files or fewer and 50 lines or less skips subagents. It does not
skip lenses: one pass applies all 7. Pre-flight and the deep investigation still
run.

### Example 4 — escalation from pr-review

```
this touches the JWT signing path — run the deeper review on PR 87
```

Every `pr-review` lens maps to an agent here, so no perspective is lost when you
escalate: Completeness → Cartographer, Correctness → Logician + Sentinel +
Performer + Tracer, Impact → Architect.

### Example 5 — re-review after your own fixes

```
/multi-agent-review 87
```

The target inference finds the open PR again. The incremental rule reviews only
what you pushed since the last verdict. Re-dispatch follows scope: a mechanical
fix → no subagents, a complex logic change → only the agents that had findings,
a large refactor → all 7 again. Pre-flight always re-runs.

**Readiness score:** Critical −20, Warning −8, Suggestion −2, Nit 0. The score
is advisory. It never overrides the severity-driven verdict, so both review
skills agree on identical findings.

---

## Which skill to call

| Situation | Skill |
|---|---|
| One file, clear fix | Direct edit, or `dev-cycle` on the fast path |
| Multi-file change that needs a plan | `dev-cycle` |
| Large feature judged by verifiable gates | `as-goal` |
| "Is this safe to merge?" | `pr-review` |
| Auth, payments, migrations, lifecycle, 10+ files | `multi-agent-review` |
| Only a design question, no code yet | `multi-agent-planning` |

Cost rises with depth. `pr-review` runs 3 agents. `multi-agent-review` runs 7
agents plus a build and test pass. `as-goal` runs the full team up to 10 times.

## Guardrails that apply to all four

- **No local branches.** These skills never create a branch or worktree. A
  different revision is reached with `git reset --hard <revision>` in place.
- **PR Mode moves your checkout.** It runs `git reset --hard` onto the PR head,
  so the working tree must be clean. It aborts and reports if it is not.
- **Local Mode is push-free.** No `git checkout`, no `gh`, no push. The only
  write is the fix commit.
- **The plan gate stays.** A review skill hands findings to `dev-cycle`, which
  still asks you to approve its fix plan. `as-goal` auto-approves it, because you
  approved the goal instead.
- **Scratch state is never committed.** `docs/as-goals/`, `*-progress.md`, and
  `review*.md` stay out of every commit. Stage files by name, never `git add -A`.
- **One auto-fix round per invocation.** Unresolved Critical or Warning findings
  are reported for you to decide, not looped on silently.

## See also

- [`multi-agent-planning`](multi-agent-planning/SKILL.md) — the 3-perspective planner behind `dev-cycle` Phase 1.
- [`interview-me`](interview-me/SKILL.md) — the goal extraction used by `as-goal` Phase 1.
- [`test-driven-development`](test-driven-development/SKILL.md) — the TDD rules used by `dev-cycle` Phase 2.
- [`code-review-and-quality`](code-review-and-quality/SKILL.md) — review axes and severity definitions.
