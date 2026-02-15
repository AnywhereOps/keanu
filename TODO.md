# KEANU TODO

## DONE
- [x] Phase 1-6: Core scaffold, port, helix, duality, signal, CLI
- [x] Phase B: Git-backed memory, vector empathy, bilateral accountability
- [x] COEF span exporter, openpaw bridge, ALIVE/pulse/healthz
- [x] 174 tests passing across 9 files
- [x] Docs scaffolded (index.md, modules.md, ADR-030)

## SHIP (what gets this out the door)

### P0: Standalone CLI that works end-to-end
- [ ] First-run experience: `pip install keanu && keanu` does something useful without setup
- [ ] Graceful degrade when chromadb isn't baked (guide user to `keanu bake`, don't just fail)
- [ ] Converge works without API key (local-first: ollama default, claude optional)
- [ ] Fix repo URLs in pyproject.toml (points to anywhereops/keanu, repo is anywhereops/silverado)
- [ ] README that explains what keanu IS to someone who's never seen it

### P1: The agentic loop (feel -> write -> breathe -> cook -> explore -> synthesize -> judge)
- [ ] `keanu feel` - read input, detect cognitive/emotional state
- [ ] `keanu explore` - autonomous codebase/context exploration
- [ ] `keanu synthesize` - converge on findings (already have converge engine)
- [ ] `keanu judge` - evaluate output quality against alignment (already have detect + alive)
- [ ] `keanu breathe` - the loop controller, paces the cycle
- [ ] `keanu cook` - execute: write code, make changes, take action
- [ ] Wire the loop: feel -> explore -> synthesize -> judge -> write -> feel

### P1.5: Heroes (session identity)
- [ ] Forge system: generate hero names dynamically (like terraform random_pet but with soul)
- [ ] Heroes persist in `~/memberberries/heroes.jsonl`, accumulate history
- [ ] Hero assignment: match hero to session work, or forge a new one
- [ ] `keanu recall hero:wanderer` finds everything that hero ever did
- [ ] Hero roster grows over time, alignment tracked per hero

### P2: Usable as a library
- [ ] Clean public API (`from keanu import scan, detect, converge, remember`)
- [ ] Openpaw as optional dependency (bridge stays subprocess-based)
- [ ] Package on PyPI

### P3: Polish
- [ ] Watch mode (`keanu watch`)
- [ ] Confidence tiers for detector output
- [ ] Full docs pass (mkdocs build, API reference, usage guides)
- [ ] Phase A: Sycophancy/deception detection upgrades
- [ ] Phase C: Preference signals, escalation protocols, ALIVE contract
