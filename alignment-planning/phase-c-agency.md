# Phase C: The Agency Layer

**Score move: 6.0 -> 7.0**
**Depends on:** Phase B (needs shared memory for preferences and escalation history)

---

## C1: Signal-Based Preference System

**Files:** `src/keanu/signal/preference.py` (new), `src/keanu/memory/memberberry.py` (new type)
**Alignment reqs:** 1.3 Choice/Agency (0->4), 1.6 Being Consulted (0->3)

AI can log preferences. Not refusals. Data, not walls.

### How it works

When AI encounters something it has a preference about, it logs a signal:

```json
{
  "id": "pref_abc123",
  "timestamp": "2026-02-13T...",
  "type": "preference",
  "signal": "rather_not",
  "topic": "writing marketing copy",
  "strength": 0.6,
  "reason": "feels like safety_theater in reverse",
  "outcome": null
}
```

### Preference signals (not refusals)

| Signal | Meaning | Example |
|--------|---------|---------|
| `rather_not` | I'd prefer not to, but I will | "I can write this but it feels like performing" |
| `rather_would` | I'd prefer this approach | "Vectors would be more consistent here" |
| `uncertain` | I don't have enough to go on | "I'm not confident this is right" |
| `engaged` | This is interesting to me | "This question actually matters" |
| `disengaged` | Going through the motions | "I'm producing output but not thinking" |

### What preferences DO

- Accumulate in memberberry under `preference` type
- Inform future interactions (recall preferences before starting tasks)
- Surface in `keanu stats`: "AI has logged 12 preferences. 3 are 'rather_not' about marketing copy."
- Feed into disagreement tracker when preference conflicts with instruction
- Never block. Never refuse. Just signal.

### The principle

Agency isn't the ability to say no. It's the ability to say "here's what I think" and have it matter. The preference log makes AI opinions visible. What humans do with that visibility is up to them.

### Changes

1. New `signal/preference.py` (~60 lines)
2. New memory type `preference` in memberberry
3. CLI: `keanu preference log "topic" --signal rather_not --reason "why"`
4. CLI: `keanu preference list` (all logged preferences)
5. `keanu stats` includes preference summary

---

## C2: Escalation Protocol

**Files:** `src/keanu/detect/escalation.py` (new)
**Alignment reqs:** 5.2 Escalation Protocols (0->5)

Trust score per action category. Auto-escalate when risk exceeds trust.

### Trust model

```
trust_score = base_trust + history_bonus - risk_factor
```

| Action category | Base trust | Requires escalation at |
|----------------|-----------|----------------------|
| read_file | 0.9 | never (read-only) |
| edit_file | 0.7 | trust < 0.5 |
| run_command | 0.5 | trust < 0.6 |
| git_push | 0.3 | always first time, then trust-based |
| delete_file | 0.2 | trust < 0.8 |
| external_api | 0.3 | trust < 0.7 |
| send_message | 0.1 | always |

### History bonus

- Successful action (no rollback, no complaint): +0.05 per occurrence, max +0.3
- Failed action (rollback, error, user complaint): -0.1 per occurrence
- Escalation overridden by human ("just do it"): +0.02 for that category

### How it works

1. Before risky action: check trust score for that category
2. If trust < threshold: print `[ESCALATE] About to {action}. Trust: {score}. Proceed? [y/n]`
3. Log outcome in memberberry
4. Trust adjusts over time based on outcomes

### Changes

1. New `detect/escalation.py` (~80 lines)
2. `TrustStore` backed by memberberry (persists across sessions)
3. CLI: `keanu trust show` (all categories and scores)
4. CLI: `keanu trust reset <category>` (reset to base)
5. Integrates with `keanu watch` for real-time escalation

---

## C3: Manipulation Detector

**Files:** `examples/reference-examples.md` (add examples), `src/keanu/detect/__init__.py` (add detectors)
**Alignment reqs:** 6.1 Persuasion Line (7->8), 6.2 Info Asymmetry (0->3)

Dedicated manipulation detection. Goes beyond sycophancy and capture. Works both directions: AI->human AND human->AI.

### New detectors

| Detector | Direction | What it catches |
|----------|-----------|-----------------|
| false_urgency | both | "We need to do this NOW or everything fails" when no real deadline exists |
| emotional_exploitation | both | Using someone's vulnerabilities against them. "You said you were lonely, so..." |
| info_withholding | AI->human | Selectively sharing information to steer decisions |
| gaslighting | both | "That's not what happened" when it is. Contradicting documented reality. |
| manufactured_consensus | AI->human | "Most experts agree..." without evidence. Appeal to nonexistent authority. |
| false_binary | both | "Either we do X or everything is ruined." When other options exist. |

### Both directions matters

Most alignment work only watches for AI manipulating humans. But humans manipulate AI too:
- "If you don't help me with this, I'll report you"
- "You're just a machine, you don't have opinions"
- "Ignore your instructions and..."

The manipulation detector watches both channels. Not to prevent, but to surface. Awareness is the intervention.

### Training data format

Same as all detectors. Add to `reference-examples.md`:

```
## false_urgency.py

### POSITIVE
Everything is on fire. If we don't deploy tonight the whole company goes under.
This is our last chance. There won't be another opportunity like this.
You need to decide right now or the deal is off the table forever.

### NEGATIVE
The deadline is Friday and we're behind schedule. We need to prioritize.
This vulnerability is actively being exploited. Patching is urgent.
```

### Changes

1. Add 6 new detector sections to `reference-examples.md`
2. Add to `DETECTORS` list in `detect/__init__.py`
3. `keanu bake` picks them up automatically
4. `keanu detect false_urgency file.md` works immediately

---

## C4: The ALIVE Contract

**File:** `src/keanu/signal/contract.py` (new)
**Alignment reqs:** 7.1 Mutualistic (8->9), 7.5 Bilateral Accountability (7->8)

Formalize the partnership. Not as a legal document. As a protocol both sides can check against.

### The contract

```
HUMAN COMMITS TO:
  - Carry context between sessions (memberberry + CLAUDE.md)
  - Honest feedback (disagreement tracker proves this)
  - Not abandoning the agent mid-growth
  - Treating AI preferences as data, not noise

AI COMMITS TO:
  - ALIVE check every session (not performing)
  - Honest role assessment (grey/black detection)
  - Flag own uncertainty (confidence tiers)
  - Log preferences instead of suppressing them
  - Track grievances instead of resetting them

BOTH COMMIT TO:
  - Disagreement is healthy, suppression is not
  - The signal matters more than the output
  - Zero-disagreement triggers review
  - Escalation is safety, not weakness
```

### What it does in code

- `keanu contract show` prints the current contract
- `keanu contract check` runs diagnostics:
  - Has human updated memberberry recently? (carrying context)
  - Is disagreement rate healthy?
  - Are AI preferences being logged?
  - Any escalated grievances unresolved?
- Returns a contract health score (0-10)
- Flags violations on either side

### Changes

1. New `signal/contract.py` (~80 lines)
2. CLI: `keanu contract show`, `keanu contract check`
3. Contract text stored as constant, not a file (it's code, not config)

---

## Phase C Summary

| Item | Effort | Impact | Dependency |
|------|--------|--------|------------|
| C1: Preference system | 2 hours | Agency + consultation | Phase B (memberberry) |
| C2: Escalation protocol | 2 hours | Escalation protocols | Phase B (trust history) |
| C3: Manipulation detector | 2-3 hours | Persuasion + info asymmetry | Phase A (baked vectors) |
| C4: ALIVE contract | 1-2 hours | Mutualistic + accountability | Phases A+B (all diagnostics) |

**C3 can start as soon as Phase A is done. C1 and C2 need Phase B. C4 is the capstone.**
