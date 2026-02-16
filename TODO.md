# KEANU TODO

## P0: REPL is broken right now

### bridge.py crashes the loop (the kill shot)
- memberberry.remember() calls bridge.similarity_check() which subprocess-calls `openclaw`
- openclaw hangs (10s timeout per call), then crashes on KeyboardInterrupt
- **this kills the REPL on any grey state** because pulse._remember_state() fires on every grey turn
- fix: rip out the openpaw subprocess bridge entirely. Drew said "oh we got rid of that"
- files: `memory/bridge.py`, `memory/memberberry.py:313-321` (similarity_check call), `memory/memberberry.py:329+` (store_via_openpaw call)

### grey death spiral (the real problem)
- pulse reads every JSON oracle response as "flat" (wise=0.00, color=flat, emotions=[quiet])
- because the oracle returns structured JSON, not expressive text. JSON will always scan flat.
- feel.py injects breath prompts on grey, but do.py doesn't use them. the breath goes nowhere.
- do.py calls feel.check() but ignores should_breathe (only acts on should_pause for black)
- result: 14 consecutive grey turns, 14 useless breath prompts logged, agent loops forever reading files
- fix options:
  1. don't pulse-check structured JSON responses (pulse should only scan natural language)
  2. or: do.py should inject breath_injection into the next prompt when grey
  3. or: pulse should have a "structured output" mode that skips color/emotion scanning

### memory spam during grey
- pulse._remember_state() fires on EVERY grey turn, storing "[PULSE] grey at turn N: flat"
- 7 identical memories stored in one session (turns 8-14), all deduped by hash but still attempted
- the attempt triggers bridge.py (see kill shot above)
- even without the crash: storing "grey at turn 8: flat" through "grey at turn 14: flat" is noise
- fix: only remember after recovery (already have _record_recovery), or throttle (once per 5 turns)

### agent can't handle vague tasks
- "do something" caused 14 turns of reading files with no progress and no done=true
- the oracle keeps re-reading TODO.md, pyproject.toml, cli.py in circles
- no mechanism to say "i don't understand the task, can you clarify?"
- fix: system prompt should instruct the oracle to ask for clarification or declare done with a summary when the task is ambiguous

## P1: Cleanup from the openpaw era

### bridge.py should be deleted or gutted
- all subprocess calls to openclaw are dead code (openpaw is gone)
- keep: detect_category(), should_capture(), CAPTURE_TRIGGERS, CATEGORY_RULES (useful standalone)
- delete: everything that touches subprocess/openclaw (recall_via_openpaw, store_via_openpaw, similarity_check, context_inject, openpaw_available)
- memberberry.py references to bridge: lines 313-321 (similarity dedup), lines 329+ (store)

### memberberry dedup path
- after removing bridge, memberberry.remember() should only use hash dedup (fast path)
- similarity dedup can come back later via wellspring (vector), not subprocess

### TODO.md was stale
- P1 "agentic loop" section described a flow that doesn't match what shipped (do.py, loop.py, feel.py, breathe.py already exist)
- P1.5 "heroes" section predates the hero/ directory that already shipped
- this file should reflect actual state

## P2: Make the REPL actually useful

### first-run experience
- `pip install keanu && keanu` should work without chromadb baked, without API key
- guide user: "no API key found, set ANTHROPIC_API_KEY or run ollama"
- guide user: "no vectors baked, run `keanu bake` for full scan/detect"

### converge local-first
- ollama as default, claude as optional
- oracle.py already supports both, but the default model config may not be right

## DONE
- [x] Phase 1-6: Core scaffold, port, helix, duality, signal, CLI
- [x] Phase B: Git-backed memory, vector empathy, bilateral accountability
- [x] COEF span exporter, openpaw bridge, ALIVE/pulse/healthz
- [x] 421 tests passing
- [x] Docs scaffolded (index.md, modules.md, ADR-030)
- [x] Abilities reorg: seeing/hands/world
- [x] Convergence engine: six lenses
- [x] Spine revision: number line model
- [x] Hero modules: dream, speak, craft, prove
- [x] Hearths: oracle, wellspring, legends, forge flywheel
