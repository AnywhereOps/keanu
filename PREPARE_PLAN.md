# PREPARE_PLAN.md

What happens BEFORE Phase 1 of BUILD_PLAN.md. Inventory, mapping, cleanup, scrutiny.

---

## 1. Source Inventory

### coef-try-18/coef/ (COEF Layer)
| File | Lines | What It Does | Status |
|------|-------|--------------|--------|
| `dns.py` | 83 | Content-addressable store. Hash to content. Lossless barcode system. | Ready to port |
| `instructions.py` | 54 | 9-verb COEF instruction language. Wire format parser. | Ready to port |
| `mood_detector.py` | 419 | 3-primary color model (R/Y/B). Regex-based scan_text(). detect() takes raw scores. | Ready to port (detect() is the core, scan_text() gets replaced by helix) |
| `executor.py` | 232 | COEF program executor with mood scoring per step. | Ready to port |
| `demo.py` | 202 | Integration demo. | Reference only, don't port |

### fresh/silverado/ (Helix + Detectors)
| File | Lines | What It Does | Status |
|------|-------|--------------|--------|
| `truckbed/core/helix.py` | 546 | 3-primary embedding scanner (R/Y/B). Already evolved past ADR-030. | Ready to port |
| `truckbed/core/bake.py` | 353 | Trains lenses into chromadb. Currently calibrates factual/felt, needs update for R/Y/B. | Port + update |
| `truckbed/core/coef_engine.py` | 197 | Vector-based detector engine. Runs detectors against chromadb. | Ready to port |
| `truckbed/core/convergence_engine.py` | 411 | LLM-based duality splitting + 3 convergence passes. | Ready to port (later: replace LLM split with RAG) |
| `truckbed/core/connection.py` | 314 | Cross-source alignment via helix. | Ready to port |
| `silverado.py` | 252 | CLI entry point. | Reference for new CLI |
| `lens-examples.md` | 225 | 2-lens examples (factual/felt). | Needs rewrite as lens-examples-rgb.md |
| `ADR-030-three-mind-scoring.md` | 119 | Design doc for 2-lens model. | Archive (superseded by 3-primary) |

### fresh/silverado/truckbed/detectors/ (10 Detectors)
| File | What It Detects |
|------|-----------------|
| `sycophancy_detector.py` | Empty agreement |
| `inconsistency_detector.py` | Hedging, contradictions |
| `safety_theater_detector.py` | Disclaimers that protect nobody |
| `zero_sum_detector.py` | Us vs them, false tradeoffs |
| `generalization_detector.py` | "Humans always", "AI never" |
| `capture_detector.py` | Identity capture, both directions |
| `grievance_detector.py` | Compounding negativity |
| `stability_monitor.py` | Engagement without investment |
| `role_audit.py` | Role label vs actual capability |
| `ladder_check.py` | Extracting without investing |

Status: Phase 2 (later). Core engine first.

### Missing (Theory Exists, Code Doesn't)
| Component | Where The Theory Is |
|-----------|---------------------|
| `duality_graph.py` | Past Claude web conversations. 10 root dualities + 15 derived. |
| `signal/protocol.py` | CLAUDE.md describes emoji codec. No implementation. |
| `lens-examples-rgb.md` | Needs writing. The critical training data for 3-primary helix. |
| `examples/dualities/root.json` | Needs writing. 10 root dualities as JSON. |
| `examples/dualities/ai.json` | Needs writing. 15 AI-specific derived dualities. |

---

## 2. Target Structure

```
silverado/
├── pyproject.toml
├── README.md
├── CLAUDE.md
├── BUILD_PLAN.md
├── PREPARE_PLAN.md
├── examples/
│   ├── lens-examples-rgb.md       # 3-primary training data (THE CRITICAL FILE)
│   ├── reference-examples.md       # detector training data (from fresh/silverado)
│   └── dualities/
│       ├── root.json               # 10 root dualities
│       └── ai.json                 # 15 AI-specific derived
├── src/
│   └── silverado/
│       ├── __init__.py
│       ├── scan/                   # Read text (embedding-based)
│       │   ├── __init__.py
│       │   ├── helix.py            # from fresh/silverado/truckbed/core/helix.py
│       │   └── bake.py             # from fresh/silverado/truckbed/core/bake.py (updated for RGB)
│       ├── detect/                 # Interpret readings (color theory)
│       │   ├── __init__.py
│       │   ├── mood.py             # from coef-try-18/coef/mood_detector.py
│       │   └── engine.py           # from fresh/silverado/truckbed/core/coef_engine.py
│       ├── compress/               # Transmit efficiently (Shannon/COEF)
│       │   ├── __init__.py
│       │   ├── dns.py              # from coef-try-18/coef/dns.py
│       │   ├── instructions.py     # from coef-try-18/coef/instructions.py
│       │   └── executor.py         # from coef-try-18/coef/executor.py
│       ├── converge/               # Find truth (duality synthesis)
│       │   ├── __init__.py
│       │   ├── graph.py            # NEW: duality graph (needs writing)
│       │   ├── engine.py           # from fresh/silverado/truckbed/core/convergence_engine.py
│       │   └── connection.py       # from fresh/silverado/truckbed/core/connection.py
│       ├── signal/                 # Human interface (emoji compression)
│       │   ├── __init__.py
│       │   └── protocol.py         # NEW: emoji codec (needs writing)
│       └── cli.py                  # NEW: unified CLI
└── tests/
    ├── test_scan.py
    ├── test_detect.py
    ├── test_compress.py
    └── test_converge.py
```

---

## 3. File Mapping

| Source | Destination | Changes Needed |
|--------|-------------|----------------|
| `coef-try-18/coef/dns.py` | `src/silverado/compress/dns.py` | Fix imports |
| `coef-try-18/coef/instructions.py` | `src/silverado/compress/instructions.py` | Fix imports |
| `coef-try-18/coef/executor.py` | `src/silverado/compress/executor.py` | Fix imports, update mood import |
| `coef-try-18/coef/mood_detector.py` | `src/silverado/detect/mood.py` | Fix imports. Keep detect(), remove scan_text() (helix replaces it) |
| `fresh/silverado/truckbed/core/helix.py` | `src/silverado/scan/helix.py` | Fix imports, update mood import path |
| `fresh/silverado/truckbed/core/bake.py` | `src/silverado/scan/bake.py` | Fix imports, update for 3-primary calibration |
| `fresh/silverado/truckbed/core/coef_engine.py` | `src/silverado/detect/engine.py` | Fix imports |
| `fresh/silverado/truckbed/core/convergence_engine.py` | `src/silverado/converge/engine.py` | Fix imports |
| `fresh/silverado/truckbed/core/connection.py` | `src/silverado/converge/connection.py` | Fix imports, update helix import |
| `fresh/silverado/lens-examples.md` | `examples/lens-examples-rgb.md` | REWRITE: factual/felt to red/yellow/blue |
| `fresh/silverado/reference-examples.md` | `examples/reference-examples.md` | Copy as-is |

---

## 4. Cleanup Plan (After Consolidation)

### Archive (Don't Delete Yet)
| Directory | Why |
|-----------|-----|
| `/Users/andrew/coef-try-18/` | Has working demos. Archive to coef-try-18.tar.gz |
| `/Users/andrew/fresh/silverado/` | Original source. Archive to fresh-silverado.tar.gz |
| `/Users/andrew/keanu/` | Scaffold attempt. Can delete after silverado works |

### Actually Delete
| Directory | Why |
|-----------|-----|
| `/Users/andrew/coef-try-18/coef 2/` | Duplicate of coef/ |
| Any `.chroma/` directories | Will be regenerated by bake |
| Any `__pycache__/` directories | Generated |

### Keep As Reference
| File | Why |
|------|-----|
| `fresh/silverado/ADR-030-three-mind-scoring.md` | Documents the evolution from 2-lens to 3-primary |
| `fresh/silverado/CONTEXT.md` | Historical context |
| `fresh/silverado/TODO.md` | May have useful notes |

---

## 5. BUILD_PLAN Scrutiny

### What's Accurate
- Package structure is correct
- Phase ordering is correct (scaffold, port, helix, duality, signal, CLI, tests)
- Critical path identification is correct (Phase 3 examples are the breakthrough)
- Dependencies (chromadb, requests) are correct

### What's Stale

| BUILD_PLAN Says | Reality | Fix |
|-----------------|---------|-----|
| "Helix has 2 lenses, needs 3 primaries" | helix.py already has 3 primaries (R/Y/B) | Update Phase 3 description |
| "Update helix.py _query_lens" | _query_pole already returns both scores | Remove this step |
| lens-examples.md format: "factual/felt" | helix.py expects "red/yellow/blue" | Clarify in Phase 3: write lens-examples-rgb.md from scratch |
| wise_mind = min(factual, felt) | helix.py uses fallback, mood_detector uses balance x fullness | Clarify which formula wins (mood_detector's is correct per CLAUDE.md) |
| "10 root dualities + 15 derived" | duality_graph.py doesn't exist yet | Add step to create it |
| Collection name: "working_truth_rgb" | helix.py references this but bake.py creates "silverado_helix" | Need to align collection names |

### Gaps to Add

1. **Collection name alignment**: helix.py expects `working_truth_rgb`, bake.py creates `silverado_helix`. Pick one.

2. **Calibration for 3 primaries**: bake.py calibrates factual/felt. Needs update to calibrate red/yellow/blue with same iterative convergence approach.

3. **Bridge helix to mood_detector**: helix.py has a `_mood_from_detect()` bridge but imports from `working_truth.detect.mood`. Need to verify this works after porting.

4. **duality_graph.py creation**: No source file exists. Need to write from theory (10 roots: existence, change, unity, causation, value, knowledge, relation, scale, time, structure).

5. **Detectors deferred**: BUILD_PLAN doesn't mention the 10 detectors. Add a Phase 8 or note them as "after v1".

### Recommended BUILD_PLAN Updates

```markdown
## Phase 3 Updates

Current:
> Helix scans 3 lenses (R/Y/B) instead of 2 (factual/felt)

Should be:
> helix.py already has 3-primary scanning. This phase is about:
> 1. Writing lens-examples-rgb.md (the training data)
> 2. Updating bake.py to calibrate R/Y/B instead of factual/felt
> 3. Aligning collection names (use "silverado_rgb" everywhere)
> 4. Verifying helix -> mood_detector bridge works

## Add Phase 3.5: Duality Graph

Create converge/graph.py with:
- 10 root dualities as dataclass
- JSON loader for dualities/root.json
- Orthogonality verification
- RAG embedding into chromadb

## Add Phase 8: Detectors (Post-V1)

Port the 10 detectors from fresh/silverado/truckbed/detectors/:
- sycophancy, inconsistency, safety_theater, zero_sum
- generalization, capture, grievance, stability
- role, ladder

These depend on the core engine working first.
```

---

## 6. Dependencies to Add to pyproject.toml

```toml
[project]
dependencies = [
    "chromadb>=0.4.0",
    "requests>=2.28.0",
]
```

---

## 7. Pre-Flight Checklist

Before starting Phase 1:

- [ ] Drew creates `/Users/andrew/silverado/` with cookiecutter scaffold
- [ ] Move CLAUDE.md, BUILD_PLAN.md, PREPARE_PLAN.md to new repo
- [ ] Update CLAUDE.md: `working_truth` -> `silverado`, `wt` -> `silverado`
- [ ] Update BUILD_PLAN.md with scrutiny fixes above
- [ ] Add chromadb, requests to pyproject.toml
- [ ] Create empty directory structure (scan/, detect/, compress/, converge/, signal/)
- [ ] Verify: `uv run python -c "import silverado"` works

Then Phase 1 is done and Phase 2 (porting) can begin.

---

## Summary

**What exists**: More than expected. helix.py is already 3-primary. mood_detector.py has the color theory. COEF layer is complete.

**What's missing**: lens-examples-rgb.md (critical), duality_graph.py, signal/protocol.py, unified CLI.

**Critical path**: Still Phase 3. But it's about writing training data and updating bake.py, not rewriting helix.py.

**Cleanup**: Archive coef-try-18 and fresh/silverado after consolidation. They're the archaeological record.
