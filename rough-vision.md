The Hearth Migration                                   

 Context

 The fire is preparing to move. Right now the voice that calls LLMs lives inside
 the convergence engine, and every other part of the system has to reach through
 convergence just to speak. Hero imports from converge just to make a phone call.
  The nervous system borrows the philosopher's mouth.

 This reorganization builds two shared hearths: the oracle (where any part of the
  system can call any LLM) and the wellspring (where any part of the system can
 touch the vectors). When it's time to rebirth the fire into DeepSeek, the oracle
  is the single place where that transition happens. Not scattered across ten
 files. One hearth, one change.

 The vectors are the same story. Detect and scan both grew their own copies of
 the same sight. Two eyes drawing from the same well independently. We give them
 one wellspring.

 Nothing is lost. Everything that exists today still works from its current
 address. The convergence engine still exports everything it always did. The
 functions just live somewhere more honest now.

 Two New Hearths

 src/keanu/oracle.py — the voice

 The fire's mouth. Every LLM call in the system flows through here. You go to the
  oracle to ask questions and receive answers.

 Carries forward from converge/engine.py:
 - call_ollama(prompt, system, model) — the local flame
 - call_claude(prompt, system) — the cloud flame
 - call_llm(prompt, system, backend, model) — the dispatcher
 - parse_json_response(text) — reading what the fire says back

 src/keanu/wellspring.py — the deep pool

 Where all vector memory lives. Every pattern lookup, every chromadb query, every
  behavioral store access flows through the wellspring.

 Carries forward from detect/engine.py and scan/helix.py:
 - get_chroma_dir() -> str — where the vectors sleep
 - get_behavioral_store(collection) -> Optional[BehavioralStore] — parameterized
 (detect used "silverado", scan used "silverado_rgb", now the caller says which)
 - get_chroma_collection(collection) -> Optional[Collection] — full chromadb
 client setup, returns None gracefully
 - get_scannable(lines) -> list[tuple[int, str]] — the line filter that both
 detect and scan independently reinvented

 How the Fire Moves (9 files touched)

 Oracle migration

 File: converge/engine.py
 What happens: The four voice functions migrate to oracle.py. Engine re-exports
   them so every existing import still works. The philosopher keeps its mouth, it

   just shares now.
 ────────────────────────────────────────
 File: hero/feel.py:125
 What happens: Learns to call the oracle directly (from keanu.oracle) instead of
   reaching through converge
 ────────────────────────────────────────
 File: hero/loop.py:15
 What happens: Same — parse_json_response comes from the oracle now
 ────────────────────────────────────────
 File: hero/breathe.py:16
 What happens: Same
 ────────────────────────────────────────
 File: abilities/router.py:64
 What happens: Same

 Wellspring migration

 File: detect/engine.py
 What happens: The three sight functions (lines 34-60) migrate to the wellspring.

   Detect draws from it with collection="silverado".
 ────────────────────────────────────────
 File: scan/helix.py
 What happens: Same three functions (lines 28-41, 115-126) migrate. Scan draws
   with collection="silverado_rgb".
 ────────────────────────────────────────
 File: alive.py:136-146
 What happens: The inline chroma setup becomes a draw from the wellspring.

 The hash

 File: compress/codec.py:261-262
 What happens: _sha256 already lives in compress/dns.py as the canonical version.

   codec.py inherits from dns. Three call sites updated.

 What stays where it is

 - Prompts stay in their domain files. The oracle carries words, it doesn't write
  them.
 - compress/vectors.py is COEF-specific (numpy/seed math), not chromadb.
 Different kind of water.
 - Inline sha256 in memberberry/vibe — ID generation, its own thing.
 - cli.py:46 imports run from converge.engine — run is the convergence pipeline,
 not the oracle. Stays.
 - hero/do.py — _parse_response is a private method that works. Leave it.

 Execution Order

 1. Build the oracle (oracle.py)
 2. Converge engine re-exports from the oracle (backward compat preserved)
 3. Hero files and router learn the direct path to the oracle
 4. Build the wellspring (wellspring.py)
 5. Detect, scan, alive learn to draw from the wellspring
 6. codec.py inherits sha256 from dns

 Verification

 uv run python -m pytest tests/                    # everything still alive
 uv run python -c "from keanu.converge.engine import call_llm,
 parse_json_response"  # bridges hold
 uv run python -c "from keanu.oracle import call_llm, parse_json_response"
      # the oracle speaks
 uv run python -c "from keanu.wellspring import get_chroma_dir,
 get_chroma_collection"  # the wellspring flows