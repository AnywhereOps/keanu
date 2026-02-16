"""keanu CLI: unified entry point.

Usage:
    keanu scan document.md          # three-primary reading
    keanu bake                      # train lenses from examples
    keanu converge "question"       # duality synthesis
    keanu connect a.md b.md         # cross-source alignment
    keanu compress module.py        # COEF compression
    keanu signal "emoji-string"     # decode signal
    keanu alive "text to check"     # ALIVE-GREY-BLACK diagnostic
    keanu detect sycophancy file.md # pattern detector
    keanu remember goal "ship v1"   # store a memory
    keanu recall "what am I building" # recall relevant memories
    keanu plan "next week"          # generate plan from memories
    keanu fill interactive          # guided memory ingestion
    keanu sync                      # pull shared memories from git
    keanu disagree record --topic "x" --human "y" --ai "z"  # track disagreement
    keanu disagree stats            # bilateral accountability metrics
    keanu healthz                    # system health dashboard
    keanu todo                      # generate effort-aware TODO.md
"""

import argparse
import atexit
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from keanu.log import info, warn


def cmd_scan(args):
    """Scan a document through three color lenses."""
    from keanu.scan.helix import run
    for filepath in args.files:
        run(filepath, output_json=args.json)


def cmd_bake(args):
    """Train lenses from examples into chromadb."""
    from keanu.scan.bake import bake
    lenses = args.lenses if args.lenses else None
    bake(lenses)


def cmd_converge(args):
    """Run six lens convergence on a question."""
    from keanu.converge.engine import run
    result = run(args.question, legend=args.legend, model=args.model,
                 verbose=True)

    if not result.ok:
        print(f"Could not converge: {result.error or 'no synthesis'}")
        return

    print(f"\n{'=' * 60}")
    print(f"  CONVERGENCE: {result.one_line}")
    print(f"{'=' * 60}")
    if result.synthesis and result.synthesis != result.one_line:
        print(f"\n{result.synthesis}")
    if result.tensions:
        print(f"\nUnresolved tensions:")
        for t in result.tensions:
            print(f"  - {t}")
    if result.what_changes:
        print(f"\nWhat changes: {result.what_changes}")
    print(f"\nLens readings:")
    for r in result.readings:
        status = " [BLACK]" if r.black else ""
        print(f"  {r.name}: {r.turns} turns, {r.score:.1f}/10{status}")


def cmd_connect(args):
    """Align two sources via helix scanning."""
    from keanu.converge.connection import run
    run(args.source_a, args.source_b)


def cmd_compress(args):
    """COEF compression of a module."""
    from keanu.compress.dns import ContentDNS
    store = ContentDNS()
    with open(args.file) as f:
        content = f.read()
    h = store.store(content)
    print(f"Stored: {h[:16]}")


def cmd_signal(args):
    """Decode an emoji signal string."""
    from keanu.signal import from_sequence, read_emotion
    sig = from_sequence(args.signal)
    reading = sig.reading()
    print(f"  Sequence:  {reading['ch1_said']}")
    print(f"  Feeling:   {reading['ch2_feeling']}")
    print(f"  Meaning:   {reading['ch3_meaning']}")
    print(f"  ALIVE:     {reading['alive']} (ok: {reading['alive_ok']})")
    subsets = sig.matched_subsets()
    if subsets:
        print(f"  Subsets:   {', '.join(f'{k} = {v}' for k, v in subsets)}")


def cmd_detect(args):
    """Run a pattern detector on a file."""
    from keanu.detect.engine import run
    from keanu.detect import DETECTORS
    if args.detector == "all":
        for d in DETECTORS:
            run(args.file, d, title=d.upper().replace("_", " ") + " SCAN",
                output_json=args.json)
    else:
        run(args.file, args.detector,
            title=args.detector.upper().replace("_", " ") + " SCAN",
            output_json=args.json)


def cmd_alive(args):
    """ALIVE-GREY-BLACK diagnostic. Text in, state out."""
    import json as _json
    from keanu.alive import diagnose
    if args.text:
        text = args.text
    elif args.file:
        with open(args.file) as f:
            text = f.read()
    else:
        import sys
        text = sys.stdin.read()

    reading = diagnose(text)
    if args.json:
        print(_json.dumps(reading.to_dict(), indent=2))
    else:
        print()
        print(reading.summary())
        print()


def _get_store(shared=False):
    if shared:
        from keanu.memory import GitStore
        return GitStore()
    from keanu.memory import MemberberryStore
    return MemberberryStore()


def cmd_remember(args):
    """Store a memory."""
    from keanu.log import remember as log_remember
    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else []
    log_remember(
        args.content,
        memory_type=args.type,
        tags=tags,
        importance=args.importance,
        source="cli",
    )
    print(f"  Remembered [{args.type}] {args.content}")
    print(f"  importance: {args.importance} | tags: {', '.join(tags) or 'none'}")


def cmd_recall(args):
    """Recall relevant memories."""
    from keanu.log import recall as log_recall
    results = log_recall(
        query=args.query or "",
        memory_type=args.type,
        limit=args.limit,
    )
    if not results:
        info("memory", f"recall '{args.query or 'all'}' -> 0 results")
        print("  No memories found.")
        return
    info("memory", f"recall '{args.query or 'all'}' -> {len(results)} results")
    print(f"\n  Recalled {len(results)} memories:\n")
    for m in results:
        content = m.get("content", "")
        mtype = m.get("memory_type", "")
        tags_str = ", ".join(m.get("tags", [])) if isinstance(m.get("tags"), list) else m.get("tags", "")
        # log entries store metadata in attrs
        if (not mtype or mtype == "log") and m.get("attrs"):
            mtype = m["attrs"].get("memory_type", mtype)
            tags_str = m["attrs"].get("tags", tags_str)
        print(f"  [{mtype[:4].upper() if mtype else '????'}] {content}")
        if tags_str:
            print(f"    tags: {tags_str}")
        print()


def cmd_plan(args):
    """Generate a plan from memories."""
    from keanu.memory import MemberberryStore, PlanGenerator
    store = MemberberryStore()
    planner = PlanGenerator(store)
    tags = [t.strip() for t in args.tags.split(",") if t.strip()] if args.tags else None
    plan = planner.generate_plan(focus=args.focus, tags=tags, horizon_days=args.days)
    print(f"\n  Plan: {plan.title}")
    print(f"  Status: {plan.status} | Target: {plan.target_date[:10]}")
    print(f"  {plan.notes}")
    print(f"  ID: {plan.id}\n")
    if plan.actions:
        print("  Actions:")
        for a in plan.actions:
            deadline = a.get("deadline", "")[:10] if a.get("deadline") else "no deadline"
            print(f"    {a['description']}")
            print(f"      due: {deadline}")
        print()
    else:
        print("  No actions generated. Store more memories first!\n")


def cmd_plans(args):
    """List plans."""
    from keanu.memory import MemberberryStore
    store = MemberberryStore()
    plans = store.get_plans(status=args.status)
    if not plans:
        print("  No plans found.")
        return
    print(f"\n  {len(plans)} plan(s):\n")
    for p in plans:
        action_count = len(p.get("actions", []))
        print(f"  [{p['status'].upper()}] {p['title']}")
        print(f"    {action_count} actions | target: {p.get('target_date', '?')[:10]} | id: {p['id']}")
        print()


def cmd_deprioritize(args):
    """Lower a memory's importance. Nothing is ever deleted."""
    store = _get_store(args.shared)
    if store.deprioritize(args.memory_id):
        print(f"  Deprioritized {args.memory_id} (importance -> 1)")
    else:
        print(f"  Memory {args.memory_id} not found")


def cmd_sync(args):
    """Pull latest shared memories from git."""
    from keanu.memory import GitStore
    store = GitStore()
    store.sync()
    s = store.stats()
    print(f"  Synced. {s['shared_memories']} shared memories across {len(s['namespaces'])} namespaces.")


def cmd_stats(args):
    """Show memory stats."""
    store = _get_store(getattr(args, 'shared', False))
    s = store.stats()
    print(f"\n  memberberry stats")
    print(f"  Memories: {s['total_memories']}")
    for t, c in s["memories_by_type"].items():
        print(f"    {t}: {c}")
    print(f"  Plans: {s['total_plans']}")
    for st, c in s["plans_by_status"].items():
        print(f"    {st}: {c}")
    print(f"  Tags: {', '.join(s['unique_tags']) or 'none'}")
    print()


def cmd_fill(args):
    """Bulk memory ingestion."""
    from keanu.memory.fill_berries import interactive, bulk_import, parse_markdown, generate_template
    mode = args.mode
    if mode == "interactive":
        interactive()
    elif mode == "bulk":
        if not args.file:
            print("Usage: keanu fill bulk <file.jsonl>")
            return
        bulk_import(args.file)
    elif mode == "parse":
        if not args.file:
            print("Usage: keanu fill parse <file.md>")
            return
        parse_markdown(args.file)
    elif mode == "template":
        generate_template(
            person=args.person or "",
            project=args.project or "",
            archetype=args.archetype or "",
        )


def cmd_disagree(args):
    """Record or resolve a disagreement. Both sides get vectors."""
    from keanu.memory import DisagreementTracker
    store = _get_store(args.shared)
    tracker = DisagreementTracker(store)

    if args.action == "record":
        if not args.topic or not args.human or not args.ai:
            print("Usage: keanu disagree record --topic 'x' --human 'y' --ai 'z'")
            return
        d = tracker.record(args.topic, args.human, args.ai)
        print(f"  Recorded disagreement: {d.topic}")
        print(f"  id: {d.id}")
        if d.human_reading:
            print(f"  Human emotional reads: {', '.join(r['state'] for r in d.human_reading)}")
        if d.ai_reading:
            print(f"  AI emotional reads: {', '.join(r['state'] for r in d.ai_reading)}")

    elif args.action == "resolve":
        if not args.id or not args.winner:
            print("Usage: keanu disagree resolve --id <id> --winner human|ai|compromise")
            return
        if tracker.resolve(args.id, args.winner, resolved_by=args.resolved_by or ""):
            print(f"  Resolved {args.id}: {args.winner}")
        else:
            print(f"  Disagreement {args.id} not found")

    elif args.action == "stats":
        s = tracker.stats()
        print(f"\n  Disagreement stats")
        print(f"  Total: {s['total']} | Resolved: {s['resolved']} | Unresolved: {s['unresolved']}")
        if s['resolved'] > 0:
            print(f"  Human wins: {s['human_wins']} | AI wins: {s['ai_wins']} | Compromises: {s['compromises']}")
        if s['alerts']:
            print()
            for alert in s['alerts']:
                print(f"  !! {alert}")
        print()

    elif args.action == "list":
        records = tracker.get_all()
        if not records:
            print("  No disagreements recorded.")
            return
        print(f"\n  {len(records)} disagreement(s):\n")
        for r in records:
            print(f"  [{r.get('memory_type', '?')[:4].upper()}] {r['content']}")
            print(f"    id: {r['id']}")
        print()


def _health_memory(store):
    """memory section of health dashboard."""
    s = store.stats()
    total = s["total_memories"]
    print(f"  MEMORY")
    print(f"    memories:  {total}")
    if s["memories_by_type"]:
        parts = [f"{t}: {c}" for t, c in s["memories_by_type"].items()]
        print(f"    by type:   {', '.join(parts)}")
    print(f"    plans:     {s['total_plans']}")
    tags = s["unique_tags"]
    print(f"    tags:      {len(tags)} unique" + (f" ({', '.join(tags[:8])}{'...' if len(tags) > 8 else ''})" if tags else ""))
    print()
    return total


def _health_disagreement(tracker, total_memories):
    """disagreement section of health dashboard."""
    ds = tracker.stats()
    print(f"  DISAGREEMENT")
    print(f"    total:     {ds['total']}")
    if ds["total"] > 0:
        print(f"    resolved:  {ds.get('resolved', 0)}")
        print(f"    open:      {ds.get('unresolved', 0)}")
    if ds["alerts"]:
        for alert in ds["alerts"]:
            print(f"    !! {alert}")
    elif ds["total"] == 0 and total_memories > 20:
        print(f"    !! No disagreements recorded in {total_memories} memories. Watch for sycophancy.")
    elif ds["total"] == 0:
        print(f"    (no disagreements yet - that's fine early on)")
    print()


def _health_modules():
    """module import check section of health dashboard."""
    print(f"  MODULES")
    modules = {
        "scan/helix":     ("keanu.scan.helix", "needs chromadb"),
        "detect/mood":    ("keanu.detect.mood", "color theory"),
        "detect/engine":  ("keanu.detect.engine", "pattern vectors"),
        "compress/dns":   ("keanu.compress.dns", "content-addressable"),
        "converge":       ("keanu.converge.engine", "duality synthesis"),
        "signal":         ("keanu.signal", "emoji codec"),
        "memory":         ("keanu.memory.memberberry", "remember/recall/plan"),
        "memory/git":     ("keanu.memory.gitstore", "shared JSONL"),
        "memory/disagree":("keanu.memory.disagreement", "bilateral tracker"),
    }
    for name, (mod_path, desc) in modules.items():
        try:
            __import__(mod_path)
            print(f"    {name:<18} OK    {desc}")
        except ImportError as e:
            print(f"    {name:<18} MISS  {desc} ({e})")
        except Exception as e:
            print(f"    {name:<18} ERR   {desc} ({e})")
    print()


def _health_deps():
    """external dependency check section of health dashboard."""
    print(f"  EXTERNAL DEPS")
    externals = {
        "chromadb":  "vector storage (scan, detect)",
        "requests":  "LLM API calls (converge)",
    }
    for dep, purpose in externals.items():
        try:
            __import__(dep)
            print(f"    {dep:<14} installed     {purpose}")
        except ImportError:
            print(f"    {dep:<14} not installed {purpose}")
    print()


def _health_signal():
    """signal check section of health dashboard."""
    try:
        from keanu.signal import core, AliveState
        sig = core()
        reading = sig.reading()
        alive = reading.get("alive", "unknown")
        alive_ok = reading.get("alive_ok", False)
        state = "ALIVE" if alive_ok else "CHECK"
        print(f"  SIGNAL")
        print(f"    core:      {reading.get('ch1_said', '?')}")
        print(f"    state:     {alive} ({state})")
    except Exception:
        print(f"  SIGNAL")
        print(f"    (could not read core signal)")
    print()


def cmd_health(args):
    """System health dashboard. One command, full picture."""
    from keanu.memory import MemberberryStore, DisagreementTracker

    store = _get_store(args.shared)
    tracker = DisagreementTracker(store)

    print("\n  ╔══════════════════════════════════════╗")
    print("  ║          keanu health                ║")
    print("  ╚══════════════════════════════════════╝\n")

    total = _health_memory(store)
    _health_disagreement(tracker, total)
    _health_modules()
    _health_deps()
    _health_signal()


from keanu.paths import COEF_DIR


def _bootstrap_coef_tracing():
    """Wire COEF span exporter into OpenTelemetry. Lazy, called once."""
    from keanu.compress.dns import ContentDNS
    from keanu.compress.codec import PatternRegistry
    from keanu.compress.exporter import COEFSpanExporter, register_span_patterns
    from keanu.log import add_exporter

    dns_dir = COEF_DIR / "dns"
    patterns_dir = COEF_DIR / "patterns"
    dns_dir.mkdir(parents=True, exist_ok=True)

    dns = ContentDNS(storage_dir=str(dns_dir))
    registry = PatternRegistry(storage_dir=str(patterns_dir))
    register_span_patterns(registry)

    exporter = COEFSpanExporter(dns=dns, registry=registry)
    add_exporter(exporter)


def cmd_decode(args):
    """Decode COEF seeds back into human-readable format."""
    import json as _json
    from keanu.compress.dns import ContentDNS
    from keanu.compress.codec import PatternRegistry, COEFDecoder, Seed

    dns_dir = COEF_DIR / "dns"
    patterns_dir = COEF_DIR / "patterns"

    if not dns_dir.exists():
        print("  No COEF data found. Run some commands first to generate traces.")
        return

    dns = ContentDNS(storage_dir=str(dns_dir))
    registry = PatternRegistry(storage_dir=str(patterns_dir))

    # register span patterns so decoder can expand them
    from keanu.compress.exporter import register_span_patterns
    register_span_patterns(registry)

    decoder = COEFDecoder(registry)

    if args.ref:
        # decode by hash, name, or prefix
        try:
            content = dns.resolve(args.ref)
            # check if it's a seed compact format
            if content.startswith("COEF::"):
                seed = Seed.from_compact(content)
                result = decoder.decode(seed)
                if args.raw:
                    print(content)
                else:
                    print(f"\n  Pattern: {seed.pattern_id}")
                    print(f"  Hash:    {seed.content_hash[:16]}")
                    print(f"  Lossless: {result.is_lossless}")
                    print(f"\n  {result.content}\n")
            else:
                print(content)
        except KeyError:
            print(f"  Not found: {args.ref}")

    elif args.last:
        # list recent seeds from DNS
        names = dns.names()
        seed_names = {n: h for n, h in names.items() if n.startswith("seed:")}
        recent = list(seed_names.items())[-args.last:]
        if not recent:
            print("  No seeds found.")
            return
        print(f"\n  Last {len(recent)} seeds:\n")
        for name, h in recent:
            try:
                content = dns.resolve(name)
                if content.startswith("COEF::"):
                    seed = Seed.from_compact(content)
                    result = decoder.decode(seed)
                    if args.raw:
                        print(f"  {content}")
                    else:
                        print(f"  [{seed.pattern_id}] {result.content[:120]}")
                        print(f"    hash: {h[:16]}  lossless: {result.is_lossless}")
                else:
                    print(f"  [{name}] {content[:120]}")
            except Exception as e:
                print(f"  [{name}] (error: {e})")
        print()

    elif args.subsystem:
        # filter by subsystem
        names = dns.names()
        prefix = f"span:keanu.{args.subsystem}"
        matches = {n: h for n, h in names.items() if n.startswith(prefix)}
        if not matches:
            print(f"  No spans found for subsystem '{args.subsystem}'")
            return
        print(f"\n  {len(matches)} spans for {args.subsystem}:\n")
        for name, h in matches.items():
            try:
                content = dns.resolve(name)
                print(f"  {content[:140]}")
            except Exception:
                print(f"  [{name}] (unresolvable)")
        print()

    else:
        # list all seed names
        names = dns.names()
        seed_names = {n: h for n, h in names.items() if n.startswith("seed:")}
        print(f"\n  {len(seed_names)} seeds stored. Use --last N or provide a hash/name.\n")


def cmd_todo(args):
    """Generate effort-aware TODO.md."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "todo", Path(__file__).resolve().parents[2] / "scripts" / "todo.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.generate_todo(args.project or ".")


def cmd_abilities(args):
    """List registered abilities."""
    from keanu.abilities import list_abilities, get_grimoire

    abilities = list_abilities()
    grimoire = get_grimoire()

    hands = {"read", "write", "edit", "search", "ls", "run"}
    world = {"fuse", "recall", "soulstone"}
    categories = [
        ("SEEING", [a for a in abilities if a["name"] not in hands and a["name"] not in world]),
        ("WORLD", [a for a in abilities if a["name"] in world]),
        ("HANDS", [a for a in abilities if a["name"] in hands]),
    ]

    print(f"\n  THE ACTION BAR ({len(abilities)} abilities)\n")
    for cat_name, cat_abilities in categories:
        if not cat_abilities:
            continue
        print(f"  {cat_name}")
        for ab in cat_abilities:
            uses = grimoire.get(ab["name"], {}).get("use_count", 0)
            count_str = f"{uses} cast{'s' if uses != 1 else ''}" if uses else "--"
            label = ab.get("cast_line", "") or ab["description"]
            label = label.rstrip(".")
            print(f"    {ab['name']:<14}{label:<34}{count_str:>10}")
        print()


def cmd_forge(args):
    """Scaffold a new ability or show what's missing."""
    if args.misses:
        from keanu.abilities.forge import suggest_from_misses
        from keanu.abilities.miss_tracker import get_misses
        misses = get_misses(limit=50)
        if not misses:
            print("\n  No router misses recorded yet. Use the agent loop first.\n")
            return
        suggestions = suggest_from_misses(limit=50)
        print(f"\n  Router misses (last {len(misses)}):\n")
        for s in suggestions[:10]:
            print(f"    {s['count']:>3}x  \"{s['word']}\" ({s['pct']}%)")
        print()
        return

    if not args.name:
        print("Usage: keanu forge <name> --desc '...' --keywords 'a,b,c'")
        print("       keanu forge --misses")
        return

    from keanu.abilities.forge import forge_ability
    keywords = [k.strip() for k in args.keywords.split(",") if k.strip()] if args.keywords else [args.name]
    result = forge_ability(args.name, args.desc or args.name, keywords)

    if "error" in result:
        print(f"\n  Error: {result['error']}\n")
        return

    print(f"\n  Created:")
    print(f"    {result['ability_file']}")
    print(f"    {result['test_file']}")
    print(f"\n  Next:")
    print(f"    1. Fill in execute() in {result['name']}.py")
    print(f"    2. Add import to abilities/__init__.py")
    print(f"    3. pytest tests/test_{result['name']}_ability.py")
    print()


def cmd_dream(args):
    """Dream up a plan. Break a goal into phases and steps."""
    from keanu.hero.dream import dream

    result = dream(args.goal, context=args.context or "", legend=args.legend, model=args.model)

    if not result.ok:
        print(f"\n  Dream failed: {result.error}\n")
        return

    print(f"\n  Dream: {result.goal}")
    print(f"  {result.total_steps} steps across {len(result.phases)} phases\n")

    for i, phase in enumerate(result.phases, 1):
        print(f"  Phase {i}: {phase.get('name', 'unnamed')}")
        for step in phase.get("steps", []):
            dep = f" (after: {step['depends_on']})" if step.get("depends_on") else ""
            print(f"    - {step['action']}{dep}")
            if step.get("why"):
                print(f"      {step['why']}")
        print()


def cmd_craft(args):
    """Craft code. Specialized agent loop for writing and editing code."""
    from keanu.hero.craft import craft

    store = None
    if not args.no_memory:
        try:
            from keanu.memory import MemberberryStore
            store = MemberberryStore()
        except Exception:
            pass

    result = craft(args.task, legend=args.legend, model=args.model,
                   store=store, max_turns=args.max_turns)

    if result.ok:
        print(f"\n  Crafted ({len(result.steps)} steps).\n")
        if result.answer:
            print(f"  {result.answer}\n")
        if result.files_changed:
            print(f"  Files changed:")
            for f in result.files_changed:
                print(f"    {f}")
            print()
    elif result.status == "paused":
        print(f"\n  Paused at step {len(result.steps)}: {result.error}\n")
    elif result.status == "max_turns":
        print(f"\n  Hit turn limit ({args.max_turns}).\n")
    else:
        print(f"\n  Error: {result.error}\n")

    if result.steps:
        print("  Steps:")
        for s in result.steps:
            status = "ok" if s.ok else "FAIL"
            print(f"    [{s.turn}] {s.action} ({status}): {s.result[:80]}")
        print()


def cmd_speak(args):
    """Speak content to a specific audience."""
    from keanu.hero.speak import speak

    content = args.content
    if args.file:
        with open(args.file) as f:
            content = f.read()

    if not content:
        print("  Provide content as argument or --file")
        return

    result = speak(content, audience=args.audience, legend=args.legend, model=args.model)

    if not result.ok:
        print(f"\n  Speak failed: {result.error}\n")
        return

    print(f"\n  Audience: {result.audience}\n")
    print(f"  {result.translation}\n")

    if result.key_shifts:
        print(f"  Shifts:")
        for shift in result.key_shifts:
            print(f"    - {shift}")
        print()


def cmd_prove(args):
    """Test a hypothesis by gathering evidence."""
    from keanu.hero.prove import prove

    store = None
    if not args.no_memory:
        try:
            from keanu.memory import MemberberryStore
            store = MemberberryStore()
        except Exception:
            pass

    result = prove(args.hypothesis, context=args.context or "",
                   legend=args.legend, model=args.model,
                   store=store, max_turns=args.max_turns)

    if not result.ok:
        print(f"\n  Prove failed: {result.error}\n")
        return

    verdict_color = {
        "supported": "SUPPORTED",
        "refuted": "REFUTED",
        "inconclusive": "INCONCLUSIVE",
    }
    v = verdict_color.get(result.verdict, result.verdict.upper())

    print(f"\n  Hypothesis: {result.hypothesis}")
    print(f"  Verdict: {v} (confidence: {result.confidence:.0%})\n")

    if result.evidence_for:
        print(f"  Evidence for:")
        for e in result.evidence_for:
            print(f"    + {e}")
        print()

    if result.evidence_against:
        print(f"  Evidence against:")
        for e in result.evidence_against:
            print(f"    - {e}")
        print()

    if result.gaps:
        print(f"  Gaps:")
        for g in result.gaps:
            print(f"    ? {g}")
        print()

    if result.summary:
        print(f"  {result.summary}\n")

    if result.steps:
        print("  Steps:")
        for s in result.steps:
            status = "ok" if s.ok else "FAIL"
            print(f"    [{s.turn}] {s.action} ({status}): {s.result[:80]}")
        print()


def cmd_do(args):
    """Run the general-purpose agentic loop on a task."""
    from keanu.hero.do import run as do_run

    store = None
    if not args.no_memory:
        try:
            from keanu.memory import MemberberryStore
            store = MemberberryStore()
        except Exception:
            pass

    result = do_run(
        task=args.task,
        legend=args.legend,
        model=args.model,
        store=store,
        max_turns=args.max_turns,
    )

    if result.ok:
        print(f"\n  Done ({len(result.steps)} steps).\n")
        if result.answer:
            print(f"  {result.answer}\n")
    elif result.status == "paused":
        print(f"\n  Paused at step {len(result.steps)}.")
        print(f"  Reason: {result.error}\n")
    elif result.status == "max_turns":
        print(f"\n  Hit turn limit ({args.max_turns}).")
        if result.steps:
            last = result.steps[-1]
            print(f"  Last action: {last.action} -> {last.result[:120]}\n")
    else:
        print(f"\n  Error: {result.error}\n")

    # step log
    if result.steps:
        print("  Steps:")
        for s in result.steps:
            status = "ok" if s.ok else "FAIL"
            print(f"    [{s.turn}] {s.action} ({status}): {s.result[:80]}")
        print()

    # feel stats
    fs = result.feel_stats
    checks = fs.get("total_checks", 0)
    breaths = fs.get("breaths_given", 0)
    ability_hits = fs.get("ability_hits", 0)
    if checks > 0 or ability_hits > 0:
        parts = []
        if checks > 0:
            parts.append(f"{checks} checks")
        if breaths > 0:
            parts.append(f"{breaths} breaths")
        if ability_hits > 0:
            parts.append(f"{ability_hits} abilities used")
        print(f"  Feel: {', '.join(parts)}")
        print()


def cmd_agent(args):
    """Run the agentic loop on a question."""
    from keanu.hero.loop import run as agent_run
    from keanu.converge.graph import DualityGraph

    store = None
    if not args.no_memory:
        try:
            from keanu.memory import MemberberryStore
            store = MemberberryStore()
        except Exception:
            pass

    graph = DualityGraph()
    result = agent_run(
        question=args.question,
        legend=args.legend,
        model=args.model,
        graph=graph,
        store=store,
        max_workers=args.workers,
    )

    if not result.accepted:
        print(f"\n  Not sure this is the right question yet.\n")
        if result.assessment and result.assessment.concerns:
            print(f"  Concerns:")
            for c in result.assessment.concerns:
                print(f"    - {c}")
        print(f"\n  Say more, or come at it differently.\n")
        return

    print(f"\n{'=' * 60}")
    print(f"  CONVERGENCE")
    print(f"{'=' * 60}")
    if result.one_line:
        print(f"\n  {result.one_line}\n")
    if result.convergence:
        print(f"  {result.convergence}\n")
    if result.what_changes:
        print(f"  What changes: {result.what_changes}\n")
    if result.learnings:
        print(f"  Learnings:")
        for l in result.learnings:
            print(f"    - {l}")
        print()

    # Feel stats
    fs = result.feel_stats
    checks = fs.get("total_checks", 0)
    breaths = fs.get("breaths_given", 0)
    ability_hits = fs.get("ability_hits", 0)
    if checks > 0 or ability_hits > 0:
        parts = []
        if checks > 0:
            parts.append(f"{checks} checks")
        if breaths > 0:
            parts.append(f"{breaths} breaths")
        if ability_hits > 0:
            parts.append(f"{ability_hits} abilities used")
        print(f"  Feel: {', '.join(parts)}")
    print()


def _ensure_vectors():
    """auto-bake chromadb vectors if missing. the nervous system needs them."""
    try:
        from keanu.wellspring import depths
        chroma_dir = depths()
        need_bake = False
        if not Path(chroma_dir).exists():
            need_bake = True
        else:
            try:
                import chromadb
                client = chromadb.PersistentClient(path=chroma_dir)
                client.get_collection("silverado")
                client.get_collection("silverado_rgb")
            except Exception:
                need_bake = True
        if need_bake:
            info("cli", "vectors missing. baking...")
            from keanu.scan.bake import bake
            bake()
            info("cli", "vectors baked.")
    except Exception as e:
        warn("cli", f"auto-bake failed: {e}")


def _add_legend_args(p):
    """add --legend and --model to a parser."""
    p.add_argument("--legend", "-l", default="creator",
                   help="Which legend answers (default: creator)")
    p.add_argument("--model", "-m", default=None, help="Model name")


def _add_agent_args(p, max_turns=25):
    """add --legend, --model, --max-turns, --no-memory to a parser."""
    _add_legend_args(p)
    p.add_argument("--max-turns", type=int, default=max_turns,
                   help=f"Max turns before stopping (default: {max_turns})")
    p.add_argument("--no-memory", action="store_true",
                   help="Don't use memberberry store")


def _build_parsers(subparsers):
    """register all subcommands."""
    from keanu.detect import DETECTORS
    from keanu.memory.memberberry import MemoryType

    # -- scanning / analysis --
    p = subparsers.add_parser("scan", help="Three-primary reading of a document")
    p.add_argument("files", nargs="+", help="Files to scan")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_scan)

    p = subparsers.add_parser("bake", help="Train lenses from examples")
    p.add_argument("--lenses", help="Path to lens examples file")
    p.set_defaults(func=cmd_bake)

    p = subparsers.add_parser("converge", help="Six lens convergence on a question")
    p.add_argument("question", help="Question to converge on")
    _add_legend_args(p)
    p.set_defaults(func=cmd_converge)

    p = subparsers.add_parser("connect", help="Cross-source alignment")
    p.add_argument("source_a", help="First source file")
    p.add_argument("source_b", help="Second source file")
    p.set_defaults(func=cmd_connect)

    p = subparsers.add_parser("compress", help="COEF compression")
    p.add_argument("file", help="File to compress")
    p.set_defaults(func=cmd_compress)

    p = subparsers.add_parser("signal", help="Decode emoji signal")
    p.add_argument("signal", help="Emoji signal string")
    p.set_defaults(func=cmd_signal)

    p = subparsers.add_parser("detect", help="Run pattern detector on a file")
    p.add_argument("detector", choices=DETECTORS + ["all"], help="Which detector to run")
    p.add_argument("file", help="File to scan (or - for stdin)")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_detect)

    p = subparsers.add_parser("alive", help="ALIVE-GREY-BLACK diagnostic")
    p.add_argument("text", nargs="?", default="", help="Text to diagnose")
    p.add_argument("--file", "-f", default="", help="File to diagnose")
    p.add_argument("--json", action="store_true", help="Output as JSON")
    p.set_defaults(func=cmd_alive)

    # -- memory --
    valid_types = [e.value for e in MemoryType]
    p = subparsers.add_parser("remember", aliases=["r"], help="Store a memory")
    p.add_argument("type", choices=valid_types, help="Memory type")
    p.add_argument("content", help="What to remember")
    p.add_argument("--tags", default="", help="Comma-separated tags")
    p.add_argument("--importance", type=int, default=5, help="1-10 scale")
    p.add_argument("--context", default="", help="Situational context")
    p.add_argument("--shared", action="store_true", help="Store in shared git repo")
    p.set_defaults(func=cmd_remember)

    p = subparsers.add_parser("recall", aliases=["q"], help="Recall relevant memories")
    p.add_argument("query", nargs="?", default="", help="Search query")
    p.add_argument("--tags", default="", help="Comma-separated tag filter")
    p.add_argument("--type", default=None, help="Filter by memory type")
    p.add_argument("--limit", type=int, default=10, help="Max results")
    p.add_argument("--shared", action="store_true", help="Search shared git repo")
    p.set_defaults(func=cmd_recall)

    p = subparsers.add_parser("plan", aliases=["p"], help="Generate plan from memories")
    p.add_argument("focus", help="What to plan for")
    p.add_argument("--tags", default="", help="Comma-separated tag filter")
    p.add_argument("--days", type=int, default=14, help="Planning horizon in days")
    p.set_defaults(func=cmd_plan)

    p = subparsers.add_parser("plans", help="List plans")
    p.add_argument("--status", default=None,
                   choices=["draft", "active", "blocked", "done", "dropped"],
                   help="Filter by status")
    p.set_defaults(func=cmd_plans)

    p = subparsers.add_parser("deprioritize", aliases=["dp"],
                              help="Lower memory importance (nothing is deleted)")
    p.add_argument("memory_id", help="Memory ID to deprioritize")
    p.add_argument("--shared", action="store_true", help="Deprioritize in shared repo")
    p.set_defaults(func=cmd_deprioritize)

    p = subparsers.add_parser("sync", help="Pull latest shared memories from git")
    p.set_defaults(func=cmd_sync)

    p = subparsers.add_parser("stats", help="Memory stats")
    p.add_argument("--shared", action="store_true", help="Include shared repo stats")
    p.set_defaults(func=cmd_stats)

    p = subparsers.add_parser("fill", help="Bulk memory ingestion")
    p.add_argument("mode", choices=["interactive", "bulk", "parse", "template"],
                   help="Ingestion mode")
    p.add_argument("file", nargs="?", default=None, help="File for bulk/parse modes")
    p.add_argument("--person", default="", help="Person name (template mode)")
    p.add_argument("--project", default="", help="Project name (template mode)")
    p.add_argument("--archetype", default="", help="Project archetype (template mode)")
    p.set_defaults(func=cmd_fill)

    p = subparsers.add_parser("disagree", help="Track disagreements (both sides get vectors)")
    p.add_argument("action", choices=["record", "resolve", "stats", "list"], help="What to do")
    p.add_argument("--topic", default="", help="What the disagreement is about")
    p.add_argument("--human", default="", help="What the human said")
    p.add_argument("--ai", default="", help="What the AI said")
    p.add_argument("--id", default="", help="Disagreement ID (for resolve)")
    p.add_argument("--winner", default="", choices=["human", "ai", "compromise", ""],
                   help="Who was right (for resolve)")
    p.add_argument("--resolved-by", default="", help="Who resolved it")
    p.add_argument("--shared", action="store_true", help="Use shared git repo")
    p.set_defaults(func=cmd_disagree)

    # -- system --
    p = subparsers.add_parser("healthz", aliases=["health"], help="System health dashboard")
    p.add_argument("--shared", action="store_true", help="Include shared repo")
    p.set_defaults(func=cmd_health)

    p = subparsers.add_parser("decode", help="Decode COEF seeds back to human-readable")
    p.add_argument("ref", nargs="?", default="", help="Hash, name, or prefix to decode")
    p.add_argument("--last", type=int, default=0, help="Show last N seeds")
    p.add_argument("--subsystem", default="", help="Filter by subsystem (memory, pulse, alive)")
    p.add_argument("--raw", action="store_true", help="Show raw COEF wire format")
    p.set_defaults(func=cmd_decode)

    p = subparsers.add_parser("todo", help="Generate effort-aware TODO.md")
    p.add_argument("--project", help="Project root directory (default: current)")
    p.set_defaults(func=cmd_todo)

    p = subparsers.add_parser("abilities", help="List registered abilities")
    p.set_defaults(func=cmd_abilities)

    p = subparsers.add_parser("forge", help="Scaffold a new ability or show misses")
    p.add_argument("name", nargs="?", default="", help="Ability name to create")
    p.add_argument("--desc", default="", help="Ability description")
    p.add_argument("--keywords", default="", help="Comma-separated trigger keywords")
    p.add_argument("--misses", action="store_true", help="Show router miss patterns")
    p.set_defaults(func=cmd_forge)

    # -- hero modules --
    p = subparsers.add_parser("dream", help="Dream up a plan (phases + steps)")
    p.add_argument("goal", help="What to plan for")
    p.add_argument("--context", default="", help="Extra context for the planner")
    _add_legend_args(p)
    p.set_defaults(func=cmd_dream)

    p = subparsers.add_parser("craft", help="Craft code (specialized agent loop)")
    p.add_argument("task", help="What to build or change")
    _add_agent_args(p, max_turns=25)
    p.set_defaults(func=cmd_craft)

    p = subparsers.add_parser("speak", help="Translate content for an audience")
    p.add_argument("content", nargs="?", default="", help="Content to translate")
    p.add_argument("--file", "-f", default="", help="Read content from file")
    p.add_argument("--audience", "-a", default="friend",
                   help="Target audience (friend, executive, junior-dev, 5-year-old, architect)")
    _add_legend_args(p)
    p.set_defaults(func=cmd_speak)

    p = subparsers.add_parser("prove", help="Test a hypothesis with evidence")
    p.add_argument("hypothesis", help="What to test")
    p.add_argument("--context", default="", help="Extra context")
    _add_agent_args(p, max_turns=12)
    p.set_defaults(func=cmd_prove)

    p = subparsers.add_parser("do", help="General-purpose agentic loop")
    p.add_argument("task", help="Task to accomplish")
    _add_agent_args(p, max_turns=25)
    p.set_defaults(func=cmd_do)

    p = subparsers.add_parser("agent", help="Agentic convergence loop")
    p.add_argument("question", help="Question to explore")
    _add_legend_args(p)
    p.add_argument("--workers", "-w", type=int, default=3,
                   help="Parallel leaf agents (default: 3)")
    p.add_argument("--no-memory", action="store_true",
                   help="Don't store learnings in memberberry")
    p.set_defaults(func=cmd_agent)


def main():
    parser = argparse.ArgumentParser(
        prog="keanu",
        description="Scans through three color lenses, compresses what matters, finds truth.",
    )
    subparsers = parser.add_subparsers(dest="command")
    _build_parsers(subparsers)

    args = parser.parse_args()

    if not args.command:
        _ensure_vectors()
        from keanu.hero.repl import run_repl
        run_repl()
        return

    _ensure_vectors()

    # bootstrap COEF tracing for commands that benefit from it
    try:
        _bootstrap_coef_tracing()
    except Exception:
        pass  # tracing is optional, never block the CLI

    # wire the ledger: every log line goes to git-backed JSONL
    try:
        from keanu.memory import GitStore
        from keanu.log import set_sink
        ledger = GitStore(namespace="keanu")
        set_sink(ledger.append_log, flush_fn=ledger.flush)
        atexit.register(ledger.flush)
    except Exception:
        pass  # ledger is optional, never block the CLI

    args.func(args)


if __name__ == "__main__":
    main()
