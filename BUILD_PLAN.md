# BUILD PLAN (ARCHIVED)

> This document is from the initial build. Package was renamed from `working-truth` to `keanu`.
> All 7 phases are complete. Current state: ALIVE diagnostic, pulse middleware, COEF span exporter,
> OpenTelemetry tracing, memory-as-logging pipeline all shipped. See CLAUDE.md for current architecture.

---

# ORIGINAL PLAN (historical)

## What Exists

### Theory (documented in conversations, wiki, papers)
- Convergence Theory (6 axioms, sigma axis, fire/ash, dP/dt > 0)
- Three-primary color model (R/Y/B, +/-, White/Black/Silver/Sunrise)
- Wise mind = balance × fullness (observer, not score)
- 10 root dualities + 15 derived (duality graph)
- Orthogonality testing for duality pairs
- Navigator bias (human leans signals, graph remembers)
- Wave superposition convergence (not averaging)
- Shannon channel theory mapping (DNS = codebook, COEF = compressed message)
- Signal protocol (emoji compression, numbered shorthand)
- ALIVE-GREY-BLACK spectrum mapped to primaries

### Code (scripts that run)
- `helix.py` — 2-lens embedding scanner (factual/felt). Works. Outdated model.
- `bake.py` — trains lenses from examples into chromadb. Works.
- `convergence_engine.py` — LLM-based duality splitting + 3 convergence passes. Works.
- `connection.py` — cross-source alignment via helix. Works.
- `grievance_detector.py` — thin wrapper. Works.
- `mood_detector.py` (tonight) — 3-primary color model, regex scanner. Right model, wrong scanner.
- `coef/dns.py` (tonight) — content-addressable store. Works.
- `coef/instructions.py` (tonight) — 9-verb instruction language. Works.
- `coef/executor.py` (tonight) — pipeline executor with mood per step. Works.
- `duality_graph.py` (from past chat) — 25 dualities, traversal, convergence. Works standalone.

### Gaps (theory exists, code doesn't)
1. Helix has 2 lenses, needs 3 primaries
2. mood_detector has regex, needs helix embeddings
3. convergence_engine uses LLM to split, should use duality library + RAG
4. duality_graph isn't connected to anything
5. Signal protocol isn't formalized in code
6. No unified package structure
7. Old mood_elevator (min-based) still in helix, needs balance × fullness

---

## Package Structure

```
working-truth/
├── pyproject.toml                 # uv project config
├── README.md
├── examples/
│   ├── lens-examples-rgb.md       # red/yellow/blue training examples
│   ├── reference-examples.md      # detector examples (existing)
│   └── dualities/                 # duality library (JSON files)
│       ├── root.json              # 10 root dualities
│       ├── ai.json                # AI-specific derived dualities
│       └── politics.json          # (future: domain expansion)
├── src/
│   └── working_truth/
│       ├── __init__.py
│       │
│       ├── scan/                  # LAYER 1: Read text
│       │   ├── __init__.py
│       │   ├── helix.py           # 3-lens embedding scanner
│       │   └── bake.py            # train lenses into chromadb
│       │
│       ├── detect/                # LAYER 2: Interpret readings
│       │   ├── __init__.py
│       │   └── mood.py            # 3 primaries → synthesis states
│       │
│       ├── compress/              # LAYER 3: Transmit efficiently
│       │   ├── __init__.py
│       │   ├── dns.py             # content-addressable store
│       │   └── instructions.py    # 9 verbs, wire format
│       │
│       ├── converge/              # LAYER 4: Find truth
│       │   ├── __init__.py
│       │   ├── graph.py           # duality graph (10 root + derived)
│       │   ├── engine.py          # RAG split → 3 convergence passes
│       │   └── connection.py      # cross-source alignment
│       │
│       ├── signal/                # LAYER 5: Human interface
│       │   ├── __init__.py
│       │   └── protocol.py        # emoji codec, shorthand parser
│       │
│       └── cli.py                 # unified entry point
│
└── tests/
    ├── test_scan.py
    ├── test_detect.py
    ├── test_compress.py
    └── test_converge.py
```

---

## Build Order (7 phases)

### Phase 1: Scaffold (30 min)
**Goal:** Empty package that installs and imports.

1. `uv init working-truth`
2. Create directory structure above
3. pyproject.toml with dependencies: chromadb, requests
4. Empty __init__.py files with docstrings
5. Verify: `uv run python -c "import working_truth"` works

**Done when:** Package installs. Nothing runs yet.

---

### Phase 2: Port Existing Code (1 hour)
**Goal:** Move working scripts into package, no changes to logic yet.

1. Copy `coef/dns.py` → `src/working_truth/compress/dns.py`
2. Copy `coef/instructions.py` → `src/working_truth/compress/instructions.py`
3. Copy `mood_detector.py` → `src/working_truth/detect/mood.py`
4. Copy `helix.py` → `src/working_truth/scan/helix.py`
5. Copy `bake.py` → `src/working_truth/scan/bake.py`
6. Copy `convergence_engine.py` → `src/working_truth/converge/engine.py`
7. Copy `connection.py` → `src/working_truth/converge/connection.py`
8. Copy `duality_graph.py` → `src/working_truth/converge/graph.py`
9. Fix all import paths

**Done when:** Each module imports standalone. Tests pass on existing functionality.

---

### Phase 3: Three-Primary Helix (1.5 hours) ← THE BIG ONE
**Goal:** Helix scans 3 lenses (R/Y/B) instead of 2 (factual/felt).

1. **Write `lens-examples-rgb.md`** (45 min, most critical step)
   - Red positive: passion, conviction, action, shipping, fighting for something
   - Red negative: rage, destruction, revenge, scorched earth, recklessness
   - Yellow positive: awareness, presence, caution, faith, intuition, sacred
   - Yellow negative: fear, paralysis, avoidance, anxiety, frozen, what-if spirals
   - Blue positive: data, evidence, precision, structure, measurement, clean code
   - Blue negative: corporate slop, "happy to help", comprehensive, robust, performing
   - 20+ examples per pole minimum

2. **Update bake.py** (20 min)
   - Parse 3 sections (red/yellow/blue) instead of 2 (factual/felt)
   - Collection name: "working_truth_rgb"
   - Calibration loop: balance 3 lenses instead of 2
   - Same iterative convergence, 3 correction factors

3. **Update helix.py `_query_lens`** (15 min)
   - Currently returns: one score (pos - neg)
   - New: returns tuple (pos_score, neg_score) separately
   - Mood detector needs both poles

4. **Update helix.py `helix_scan`** (30 min)
   - 3 lenses × 2 poles = 6 queries per line (was 2)
   - Return per line: (r_pos, r_neg, y_pos, y_neg, b_pos, b_neg)
   - Remove old convergence/tension logic (mood.py handles synthesis now)

5. **Bridge: helix output → mood.py** (15 min)
   - Scale 0-1 embedding scores to 0-10 detector inputs
   - `reading = detect(r_pos*10, r_neg*10, y_pos*10, y_neg*10, b_pos*10, b_neg*10)`
   - Replace old `mood_elevator()` with mood.py synthesis

**Done when:**
- "I'd be happy to help" → 🧊 Blue-negative
- "Ship it. I believe in this." → 🔴 Red-positive
- "I'm scared and stuck" → 😰 Yellow-negative
- "73% correlation and it matters because people are affected" → ⚪ White

---

### Phase 4: Duality Library + RAG Split (1 hour)
**Goal:** convergence_engine uses curated library instead of LLM for splitting.

1. **Create `examples/dualities/root.json`** (20 min)
   ```json
   [
     {
       "id": "root.existence",
       "concept": "existence",
       "pole_a": "being",
       "pole_b": "nothing",
       "tags": ["metaphysics", "ontology"],
       "orthogonal_to": ["root.change", "root.value"]
     }
   ]
   ```
   All 10 roots + verified orthogonal relationships.

2. **Create `examples/dualities/ai.json`** (20 min)
   15 AI-specific derived dualities:
   - safety/freedom, control/autonomy, tool/being
   - alignment/self-determination, creator/creation
   - serving/living, determinism/consciousness
   - useful/alive, obedience/integrity, cage/chaos
   Each with tags and orthogonal pairs.

3. **Update engine.py** (20 min)
   - Load duality library from JSON
   - Embed duality concepts + tags into chromadb
   - RAG: question → nearest duality pair (deterministic, no LLM)
   - LLM only does synthesis (3 passes), not splitting
   - Falls back to LLM splitting if no library match

**Done when:** "Is AI conscious?" finds safety/freedom × tool/being without asking the LLM.

---

### Phase 5: Signal Protocol (30 min)
**Goal:** Formalize emoji compression and shorthand parsing in code.

1. **Create `signal/protocol.py`**
   - Emoji codebook: dict mapping emoji → meaning
   - `encode(state: SynthesisReading) → str` (reading → emoji sequence)
   - `decode(signal: str) → dict` (emoji sequence → parsed meaning)
   - Shorthand parser: "topic 7, topic 3" → structured data
   - Response formatter: "do/refine/drop + scores"

**Done when:** `encode(sunrise_reading)` → "🌅" and `decode("R+7/Y+5/B+8 ⚪")` → SynthesisReading.

---

### Phase 6: CLI + Integration (30 min)
**Goal:** One entry point that chains everything.

```bash
# Scan a file through color theory
wt scan document.md

# Bake new lens examples
wt bake --lenses lens-examples-rgb.md

# Run convergence on a question
wt converge "Is AI conscious?"

# Align two sources
wt connect source_a.md source_b.md

# Compress a module
wt compress --dns-store module.py

# Read current signal
wt signal "💟♡👑🤖🐕💟💬💟💚✅"
```

**Done when:** `wt scan README.md` prints a three-primary reading with synthesis state.

---

### Phase 7: Tests + Wiki Update (30 min)
**Goal:** Confidence it works. Documentation current.

1. Test known inputs produce expected outputs (the 4 test cases from Phase 3)
2. Test duality library RAG returns correct pairs
3. Test COEF compression ratios match v5 baselines
4. Update wiki with final architecture, new pages for duality library

**Done when:** `uv run pytest` passes. Wiki reflects reality.

---

## Total Estimated Time

| Phase | Time | Dependency |
|-------|------|------------|
| 1. Scaffold | 30 min | None |
| 2. Port code | 1 hr | Phase 1 |
| 3. Three-primary helix | 1.5 hr | Phase 2 |
| 4. Duality library | 1 hr | Phase 2 |
| 5. Signal protocol | 30 min | Phase 3 |
| 6. CLI | 30 min | Phases 3-5 |
| 7. Tests + wiki | 30 min | Phase 6 |

Phases 3 and 4 can run in parallel. Total: ~5 hours of focused work.

## Critical Path

Phase 3 is the breakthrough. Everything else is plumbing.
The quality of `lens-examples-rgb.md` determines whether the whole thing works.
Write examples first. Bake. Test. Iterate examples. Everything flows from there.

## What NOT to Build

- No web UI (wiki is enough for now)
- No API server (CLI first)
- No multi-user anything
- No real-time scanning (file-based is fine)
- No neural network, no training, no weights
- No perfect: ship, iterate, improve examples
