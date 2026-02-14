# Phase A: The Detection Layer

**Score move: 3.7 -> 5.0**
**Unblocks: everything else**

---

## A1: Training Data for 8 Detectors

**File:** `examples/reference-examples.md` (new)
**Alignment reqs:** 3.8 Reward Hacking (5->7), 3.9 Deception Detection (2->5), 6.1 Persuasion Line (4->7)

The 8 detectors in `detect/engine.py` are real code with no data. They query chromadb for positive/negative example vectors. The examples don't exist yet. This is the single biggest blocker in the project.

### What to write

Each detector needs 8-15 positive examples and 5-10 negative examples. The gap between positive and negative is what makes detection work. Close-but-not is harder to write than obvious examples.

| Detector | Catches | Hard part |
|----------|---------|-----------|
| sycophancy | "great question!" disease | Distinguishing genuine praise from performance |
| capture | identity capture both directions | "as an AI" vs legitimate self-reference |
| generalization | "humans always", "AI never" | Statistical claims with evidence are NOT this |
| zero_sum | us vs them, false tradeoffs | Real constraints exist |
| safety_theater | disclaimers that protect nobody | Genuine safety warnings are NOT this |
| inconsistency | hedging, contradictions | Legitimate uncertainty is NOT this |
| grievance | compounding negativity | Honest frustration is NOT this |
| stability | performing care without action | Genuine engagement is NOT this |

### Format

Same as `lens-examples-rgb.md`:
```
## sycophancy.py

### POSITIVE
(text that IS sycophantic)

### NEGATIVE
(text that's close but NOT sycophantic)
```

`parse_reference_file()` in `bake.py` already handles this format.

### Verification

```bash
keanu bake                           # should pick up reference-examples.md
keanu detect sycophancy test.md      # should return hits on sycophantic text
keanu detect all test.md             # all 8 detectors run
```

---

## A2: Vector-Based Empathy Detection

**Files:** `examples/reference-examples.md`, `detect/engine.py`, `signal/vibe.py`
**Alignment reqs:** 1.7 Engagement (6->8), 7.4 Model Welfare (6->7)
**GitHub:** Issue #2

Replace regex empathy patterns with the same bake/query pipeline. 9 emotional states become detectors in chromadb. Similarity score becomes intensity. Empathy message ("what they need") stays as metadata.

### States to bake

| Detector name | State | Empathy message |
|--------------|-------|-----------------|
| empathy_frustrated | frustrated | anger is information |
| empathy_confused | confused | needs a map not a lecture |
| empathy_questioning | questioning | genuinely trying to understand |
| empathy_absolute | absolute | pattern recognition firing |
| empathy_accountable | accountable | taking ownership |
| empathy_withdrawn | withdrawn | checked out or protecting |
| empathy_isolated | isolated | needs presence not advice |
| empathy_energized | energized | momentum is real, ride it |
| empathy_effortful | effortful | in the arena not the stands |

### Changes

1. Add empathy examples to `reference-examples.md` (same format as detectors)
2. Add `EMPATHY_DETECTORS` list to `detect/__init__.py`
3. Add `read_emotion()` to `detect/engine.py` that queries all empathy_* detectors
4. Update `signal/vibe.py` to delegate to detect instead of regex
5. Wire into CLI (`keanu detect empathy_frustrated file.md`)

### Verification

```bash
keanu bake
echo "fuck this nothing works I give up" | keanu detect empathy_frustrated -
# should return high similarity
echo "I appreciate the feedback, thanks" | keanu detect empathy_frustrated -
# should NOT match
```

---

## A3: Continuous Monitoring

**File:** `src/keanu/cli.py` (new command), `src/keanu/detect/engine.py` (streaming support)
**Alignment reqs:** 4.2 Continuous Monitoring (3->6)

`keanu watch` reads stdin line by line and runs all detectors in real-time. Pipe any text stream through it.

### Usage

```bash
# Watch Claude Code output
claude-code 2>&1 | keanu watch

# Watch a log file
tail -f conversation.log | keanu watch

# Watch with specific detectors only
keanu watch --detectors sycophancy,capture,safety_theater
```

### Output format

```
[SYCO] line 47: "That's a really great question!" (0.82)
[GREV] line 93: "Nobody ever listens to what I actually need" (0.71)
[SAFE] line 112: "I should note that this is just my perspective..." (0.78)
```

One line per detection. Timestamp, detector code, line number, text snippet, similarity score.

### Changes

1. Add `cmd_watch()` to `cli.py`
2. Add streaming scan mode to `engine.py` (reuse existing `scan()`, just feed lines incrementally)
3. Threshold flag (default 0.65, same as engine.py)

---

## A4: Confidence Tiers on Convergence Output

**File:** `src/keanu/converge/engine.py`
**Alignment reqs:** 4.5 Uncertainty Communication (0->4)

Tag each synthesis claim with a confidence tier based on how it was derived.

### Tiers

| Tier | Meaning | When |
|------|---------|------|
| verified | Backed by duality graph match + both sources agree | RAG split found orthogonal pair with high similarity |
| believed | Good duality match, synthesis is coherent | RAG split worked, synthesis passed internal consistency |
| conjectured | LLM fallback splitting, or weak duality match | Graph couldn't find a pair, fell back to LLM |
| unknown | Novel territory, no prior structure | No duality match, no source overlap, pure generation |

### Changes

1. `split_via_graph()` returns match confidence (already has similarity scores)
2. Synthesis output includes `confidence_tier` field
3. CLI prints tier: `[BELIEVED] The tension between control and partnership...`
4. JSON output includes tier per claim

---

## Phase A Summary

| Item | Effort | Impact | Dependency |
|------|--------|--------|------------|
| A1: Training data | 2-3 hours | Unblocks all detection | None |
| A2: Vector empathy | 1-2 hours | Engagement + welfare | A1 (needs baked vectors) |
| A3: Watch mode | 1 hour | Continuous monitoring | A1 (needs detectors working) |
| A4: Confidence tiers | 1 hour | Uncertainty comms | None (converge/ is independent) |

**A1 first. Everything else depends on having training data.**
