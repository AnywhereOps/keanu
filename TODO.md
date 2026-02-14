# KEANU TODO

## COOL (5-15 min)
- [ ] Create test files in `tests/` (directory exists but is empty)
- [ ] Review and commit uncommitted changes: REPARE_PLAN.md, Script/run_devcontainer_claude_code.ps1, TODO.md, uv.lock, plugins/effort-todo/ (+3 more)

## WARM (20-45 min)
- [ ] Create `grievance_detector.py` (referenced in BUILD_PLAN.md)
- [ ] Create `mood_detector.py` (referenced in BUILD_PLAN.md)
- [ ] Create `duality_graph.py` (referenced in BUILD_PLAN.md)
- [ ] Create `lens-examples-rgb.md` (referenced in BUILD_PLAN.md)
- [ ] Create `examples/dualities/root.json` (referenced in BUILD_PLAN.md)
- [ ] Create `examples/dualities/ai.json` (referenced in BUILD_PLAN.md)
- [x] Create `signal/protocol.py` (referenced in BUILD_PLAN.md)

## HOT (1-2 hours)
- [ ] Create `convergence_engine.py` (referenced in BUILD_PLAN.md)
- [ ] Complete Phase 7: Tests + Wiki Update (30 min)
- [ ] Scalable memberberry: `anywhereops/memberberries` git-backed multi-user/agent store

### Memberberry Scale Plan
1. **Create `anywhereops/memberberries` repo** (public, free, fuck microsoft)
2. **JSONL not JSON** - append-only, one memory per line, git merges clean
3. **Namespace = directory** - `drew/`, `claude-keanu/`, `soul-keeper/`, `shared/`
4. **Build `GitStore`** - wraps `MemberberryStore`, adds git pull/commit/push (~50 lines)
   - `remember` = append to JSONL + commit + push
   - `recall` = git pull + search across namespaces
   - `forget` = append tombstone + commit + push
5. **Privacy tiers** - `visibility: local | shared` tag on memories
   - Local stays in `~/.memberberry/`, never pushed
   - Shared goes to repo
6. **COEF DNS dedup** - same content hash = same memory, don't store twice
7. **Month sharding (later)** - `memories/2026-02.jsonl` when files get big
8. **Multi-agent writes** - each agent owns its namespace, no conflicts
   - `shared/` uses simple lock or PRs for consensus

## DONE
- [x] Add `__all__` exports to `compress/__init__.py`
- [x] Wire memberberry into keanu CLI (remember, recall, plan, fill, stats, forget, plans)
