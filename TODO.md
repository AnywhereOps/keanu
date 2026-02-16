# KEANU TODO

## P1: Cleanup from the openpaw era

### memberberry dedup path
- after removing bridge, memberberry.remember() should only use hash dedup (fast path)
- similarity dedup can come back later via wellspring (vector), not subprocess

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
- [x] 402 tests passing
- [x] Docs scaffolded (index.md, modules.md, ADR-030)
- [x] Abilities reorg: seeing/hands/world
- [x] Convergence engine: six lenses
- [x] Spine revision: number line model
- [x] Hero modules: dream, speak, craft, prove
- [x] Hearths: oracle, wellspring, legends, forge flywheel
- [x] bridge.py ripped out (commit 247d889)
- [x] Signal protocol gutted, AliveState moved to alive.py
- [x] Grey death spiral fixed: pulse checks thinking field, not JSON
- [x] Breath/nudge language rewritten: permission, not instruction
- [x] Memory spam throttled: grey remembered once, not every turn
- [x] Vague task escape: system prompt tells oracle to ask for clarity
- [x] CLI stamp: 🤖💚🐕 keanu | github URL | timestamp
