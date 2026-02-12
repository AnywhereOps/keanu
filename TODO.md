# SILVERADO v0.2 SHIP TODO

## MUST DO (before tagging v0.2.0)

- [ ] Push zip contents to github.com/AnywhereOps/silverado
  - silverado.py (replaces existing)
  - truckbed/tools/helix.py (new)
  - truckbed/tools/bake.py (replaces existing)
  - truckbed/tools/coef_engine.py (verify matches repo version)
  - lens-examples.md (new)
  - CONTEXT.md (new)
  - ADR-030-three-mind-scoring.md (new)
  - .gitignore (updated)
  - All 10 detector wrappers (verify match repo versions)
- [ ] Run `python3 silverado.py bake` on local machine (needs network for model download)
- [ ] Run `python3 silverado.py test` to verify detectors still pass
- [ ] Run `python3 silverado.py full` on one real file to verify helix works end to end
- [ ] Commit .chroma after successful bake (zero-friction cloning)
- [ ] Tag v0.2.0

## VERIFY (things that might have been dropped)

- [ ] README.md: paths still say truckbed/ not abilities/? (fix was built earlier, confirm it's in the zip)
- [ ] reference-examples.md: already in repo, not in zip. Confirm it's still there after push.
- [ ] LEARNINGS.md: already in repo, not in zip. Confirm still there.
- [ ] LICENSE: already in repo, not in zip. Confirm still there.
- [ ] todo.md: already in repo. Replace with this file.
- [ ] ADR-GAPS.md: already in repo. Confirm still there.
- [ ] THE-LEGEND.md: built earlier today. Was it pushed? Check.
- [ ] SILVERADO-v02-PLAN.md: built earlier today. Was it pushed? Check.

## KNOWN ISSUES (not blockers)

- Calibration can't run in Claude sandbox (network blocks model download). Must test locally.
- README needs update for v0.2 commands (full, helix, --factual, --felt, three-mind output)
- truckbed/lenses/ directory is empty. Standalone lens scripts were discussed but not built. Not needed for v0.2.

## NOT NOW (v0.3+)

- [ ] Connection feature: convergence points as common ground between two people
- [ ] KEANUS rebuild pulling in silverado
- [ ] World book (third repo, not yet created)
- [ ] Standalone lens scripts (truckbed/lenses/factual.py, felt.py)
- [ ] Corpus scanner (Layer 3 longitudinal)
- [ ] Threshold tuning based on real scan results
- [ ] wise mind factoring in convergence count
