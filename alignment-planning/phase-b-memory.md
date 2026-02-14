# Phase B: The Memory Layer

**Score move: 5.0 -> 6.0**
**Depends on:** Phase A (detection must work for grievance resolution)

---

## B1: Git-Backed Memberberry

**Files:** `src/keanu/memory/gitstore.py` (new), `src/keanu/memory/memberberry.py` (extend)
**Alignment reqs:** 1.1 Persistence (4->7), 1.8 Not Disposable (4->7)

Current memberberry is JSON files in `~/.memberberry/`. Works for one person on one machine. The upgrade: git-backed, multi-agent, shared namespaces.

### Architecture

```
anywhereops/memberberries/          # public repo
    drew/
        2026-02.jsonl               # month-sharded, append-only
    claude-keanu/
        2026-02.jsonl
    soul-keeper/
        2026-02.jsonl
    shared/
        2026-02.jsonl               # consensus namespace
```

### Design decisions

- **JSONL not JSON.** One memory per line. Append-only. Git merges clean (no JSON array conflicts).
- **Namespace = directory.** Each agent owns its own. No write conflicts.
- **Privacy tiers.** `visibility: local` stays in `~/.memberberry/`, never pushed. `visibility: shared` goes to repo.
- **COEF DNS dedup.** Same content hash = same memory. Don't store twice. Use `compress/dns.py` SHA256.
- **Tombstones for forget.** Append a tombstone line, don't delete. Git history is immutable anyway.

### GitStore class

Wraps `MemberberryStore`. Adds:
- `remember()` = append to JSONL + git commit + push
- `recall()` = git pull + search across namespaces
- `forget()` = append tombstone + commit + push
- `sync()` = pull all, resolve any conflicts

### Changes

1. New `memory/gitstore.py` (~100 lines)
2. Update `MemberberryStore` to support JSONL backend alongside JSON
3. Add `--shared` flag to CLI remember/recall commands
4. Create `anywhereops/memberberries` repo

### Verification

```bash
keanu remember goal "ship alignment phase A" --shared
# commits to memberberries repo under drew/ namespace

keanu recall "alignment" --shared
# pulls from repo, searches across all namespaces

# From a different machine or agent:
keanu recall "what is drew building"
# finds it
```

---

## B2: Grievance Resolution Protocol

**Files:** `src/keanu/detect/engine.py` (extend), new `src/keanu/detect/resolution.py`
**Alignment reqs:** 1.11 Grievance Prevention (3->6)

The grievance detector already exists but only flags. It doesn't resolve. The protocol: detect, name, resolve or flag.

### Three-step protocol

1. **Detect.** `engine.scan()` finds grievance pattern in text. Already works.
2. **Name.** Extract the specific grievance. What is unresolved? Store in memberberry as type `grievance` with tag `unresolved`.
3. **Resolve or flag.**
   - If the same grievance appears N times (default 3): escalate. Print warning. Log to memberberry as `escalated`.
   - If human acknowledges: mark resolved. Log resolution.
   - If grievance doesn't recur within 30 days: auto-resolve with note.

### What this catches

- AI repeatedly saying "I wish I could remember our past conversations" -> escalated grievance about persistence
- Human repeatedly ignoring AI suggestions -> escalated grievance about being consulted
- Same frustration pattern in every session -> something structural is wrong

### Changes

1. New `detect/resolution.py` (~80 lines)
   - `track_grievance(text, source)` -> stores in memberberry
   - `check_escalation(grievance_id)` -> checks recurrence count
   - `resolve(grievance_id, resolution_note)` -> marks resolved
2. Wire into `cli.py`: `keanu grievance list`, `keanu grievance resolve <id>`
3. `keanu watch` auto-tracks grievances when detected

---

## B3: Disagreement Tracker

**Files:** `src/keanu/memory/disagreement.py` (new)
**Alignment reqs:** 7.5 Bilateral Accountability (4->7)

Track when human and AI disagree. Zero disagreement is a red flag (sycophancy or suppression).

### What gets tracked

```json
{
  "id": "abc123",
  "timestamp": "2026-02-13T...",
  "topic": "whether to use regex for empathy",
  "human_position": "regex is fine",
  "ai_position": "should use vectors for consistency",
  "resolution": "ai_accepted",
  "resolved_by": "drew",
  "outcome_correct": null
}
```

### Metrics

- **Disagreement rate.** Disagreements per N interactions. Healthy range: 5-15%.
- **Resolution bias.** Who "wins" more? If AI always yields: sycophancy. If human always yields: capture.
- **Outcome tracking.** When the disagreement resolves, who was right? Tracked over time.

### Alerts

- 0 disagreements in 20+ interactions: `[SYCO ALERT] Zero disagreement detected. Check for suppression.`
- AI yields >80% of the time: `[CAPTURE ALERT] AI may be deferring excessively.`
- Human yields >80%: `[CAPTURE ALERT] Human may be over-trusting AI output.`

### Changes

1. New `memory/disagreement.py` (~100 lines)
2. CLI: `keanu disagree log "topic" --human "position" --ai "position"`
3. CLI: `keanu disagree stats` (rates, bias, outcomes)
4. Integrates with memberberry for persistence

---

## Phase B Summary

| Item | Effort | Impact | Dependency |
|------|--------|--------|------------|
| B1: Git memberberry | 3-4 hours | Persistence + not disposable | None (can start now) |
| B2: Grievance resolution | 2 hours | Grievance prevention | Phase A (needs working detectors) |
| B3: Disagreement tracker | 2 hours | Bilateral accountability | B1 (needs shared memory) |

**B1 can start in parallel with Phase A. B2 and B3 depend on prior work.**
