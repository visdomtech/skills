---
name: multi-agent-planning
description: "Read-only multi-agent design planning for non-trivial changes. Launches 3 parallel high-reasoning agents (Simplicity, Performance, Minimal-Change) then critically reviews and synthesizes into a single compact plan with rejected alternatives. Use for architectural decisions, refactors, feature design, or anywhere a durable decision record is wanted. Read-only: never mutates the working tree."
---

# Multi-Agent Planning

## Overview

Produce a single synthesized plan for a non-trivial change by running three parallel high-reasoning design agents from distinct perspectives, then critically reviewing and merging their outputs. Operates in **strict read-only mode** - it never mutates the working tree. The deliverable is a compact, self-contained plan (plus rejected alternatives) that downstream execution can apply without re-exploring the repo.

```
1. PARALLEL DESIGN    (3 agents, distinct perspectives)
2. READ-ONLY AUDIT    (restore clean tree if any agent wrote)
3. CRITICAL REVIEW    (completeness, feasibility, risk, trade-offs)
4. SYNTHESIS          (unified plan + rejected alternatives + optional persistence)
```

## When to Use

- Non-trivial multi-file changes before implementation
- Architectural or data-model decisions
- Choosing between competing approaches
- Producing a durable decision artifact for a refactor or feature
- "Should we even do this, and how?" questions

## When NOT to Use

- Trivial changes (≤3 files, unambiguous requirements) - just use a TodoWrite list.
- Execution itself - this skill plans, it does not implement. Hand the synthesized plan to an execution skill (e.g. `dev-cycle` Phase 2) or implement directly.

## Inputs

- A change description (what needs to happen and why).
- The repository root (defaults to current directory).
- Optional: constraints, hard requirements, or a target path to persist the plan.
- Optional: an existing plan to refine (re-synthesis mode) - a draft the caller wants critically reviewed and improved rather than designed from scratch.

## 1. Parallel Design

Launch 3 research agents **concurrently** with distinct, named perspectives:

- **Agent A - Simplicity & Maintainability:** Optimizes for code clarity and long-term maintainability.
- **Agent B - Performance & Scalability:** Optimizes for runtime efficiency and scalability.
- **Agent C - Minimal Change & Risk:** Optimizes for smallest diff footprint and lowest regression risk.

Each agent operates read-only and outputs the same shape so synthesis is mechanical:

- **Exploration summary:** files and line ranges examined.
- **Approach overview:** the proposed direction in 3–6 sentences.
- **Numbered step-by-step tasks:** ordered, each with acceptance criteria.
- **Dependencies:** between tasks and on external state.
- **Risks & mitigations:** concrete, each paired with a mitigation.
- **Critical files:** 3–5 files the change hinges on.

**Re-synthesis mode:** If an existing plan is supplied as input, the three agents review and refine that plan (hunting gaps, stress-testing tasks, proposing tighter alternatives) rather than designing from a blank slate. The Output Contract still applies to the result.

## 2. Read-Only Audit

Run `git status --porcelain`. If any planning agent modified a file, run `git checkout -- .` to restore a clean tree. Planning must leave the working tree untouched.

## 3. Critical Review

Evaluate the three plans against:

- **Completeness:** do the tasks cover the stated goal end-to-end?
- **Feasibility:** can each task be implemented as described?
- **Risk:** which plan has the lowest regression surface for the value delivered?
- **Trade-offs:** what does each plan give up?

## 4. Synthesis

Produce a single unified plan:

1. Select the strongest base plan.
2. Integrate the best elements from the other two where they reduce risk or improve clarity without inflating scope.
3. Carry forward the merged risk list, each with its mitigation.
4. **Tiebreaker:** prefer the smallest diff. If two synthesized options remain fundamentally incompatible, present both to the caller rather than silently picking.

### Rejected Alternatives (required)

Document at least 2 alternatives that were considered and rejected, each with a one-line rationale. This is the decision record - future readers (human or agent) must see not just what was chosen but what was discarded and why.

### Output Contract (compact, self-contained)

The synthesized plan MUST be self-contained enough that a downstream executor can implement it **without re-exploring the repo**:

- Ordered tasks, each ≤5 files, each with acceptance criteria and a verification step.
- Critical files listed once at the top (3–5 files).
- Risks + mitigations inline.
- Rejected alternatives inline.

This compactness is the contract that lets execution start fresh in a new context window.

### Optional Persistence

If a target path was supplied (or the caller requests it), write the synthesized plan to that path so it survives as a durable artifact. Otherwise return it inline.

## Exit Gate

- Working tree clean (`git status --porcelain` empty) - planning never mutates.
- Single synthesized plan with ordered, ≤5-file tasks, each with acceptance + verification.
- At least 2 alternatives explicitly rejected with rationale.
- Output is compact and self-contained per the Output Contract.
