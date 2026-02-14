# KEANU TODO

## DONE
- [x] Phase 1-6: Core scaffold, port, helix, duality, signal, CLI
- [x] Phase B1: Git-backed memberberry (JSONL, namespaces, dedup, deprioritize)
- [x] Phase B2: Vector empathy detection (9 states, regex removed from vibe.py)
- [x] Phase B3: Disagreement tracker (bilateral vectors, sycophancy/capture alerts)
- [x] Alignment scorecard: 3.7 -> 4.0
- [x] Tests: 87 passing (memory, JSONL, disagreement, compress, converge, mood, signal, CLI)

## COOL (5-15 min)
- [ ] Add CLI tests for new commands (disagree, sync, deprioritize)
- [x] Add `keanu detect empathy_frustrated file.md` support (wire empathy detectors into DETECTORS list)

## WARM (20-45 min)
- [ ] Phase A: Watch mode (`keanu watch file.md` for continuous detection)
- [ ] Phase A: Confidence tiers for detector output
- [ ] Bake and verify empathy vectors end-to-end (`keanu bake` then `keanu detect empathy_frustrated`)

## HOT (1-2 hours)
- [ ] Phase A: Sycophancy/deception detection upgrades (score 3.8, 3.9)
- [ ] Phase C: Preference signals, escalation protocols, ALIVE contract
- [ ] Phase 7: Wiki / documentation pass
