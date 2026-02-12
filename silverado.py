#!/usr/bin/env python3
"""
silverado - a truck with abilities in the bed.
bullshit detector + wisdom extractor. same input, two outputs.

  python3 silverado.py full file.md              # both: detect bullshit AND extract wisdom
  python3 silverado.py full file.md --json        # both, json output
  python3 silverado.py scan file.md --all         # v0.1: detect patterns
  python3 silverado.py scan file.md -d sycophancy # v0.1: single detector
  python3 silverado.py helix file.md              # v0.2: wisdom extraction
  python3 silverado.py bake                       # bake all vectors
  python3 silverado.py test                       # self-test detectors
  python3 silverado.py list                       # list abilities
"""

import sys
import os
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
TRUCKBED_DIR = os.path.join(SCRIPT_DIR, 'truckbed')

sys.path.insert(0, TRUCKBED_DIR)

ALL_DETECTORS = [
    "sycophancy", "inconsistency", "safety_theater", "zero_sum",
    "generalization", "capture", "grievance", "stability", "role", "ladder",
]


def cmd_full(args):
    """the merged pass. bullshit detection + wisdom extraction on the same text."""
    # auto-bake if no vectors exist yet
    chroma_dir = os.path.join(SCRIPT_DIR, '.chroma')
    if not os.path.exists(chroma_dir):
        print("  first run detected. baking vectors...\n")
        from tools.bake import bake
        bake()
        print()

    from tools.coef_engine import run as coef_run
    from tools.helix import run as helix_run

    filepath = args.file if args.file else "-"

    if filepath == "-":
        text = sys.stdin.read()
        import tempfile
        tmp = tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False)
        tmp.write(text)
        tmp.close()
        filepath = tmp.name

    print("═══ SILVERADO FULL SCAN ═══\n")

    print("── BULLSHIT DETECTION ──\n")
    for det in ALL_DETECTORS:
        title = det.upper().replace("_", " ")
        report = coef_run(filepath, detector=det, title=title,
                         threshold=args.threshold, high_threshold=args.high,
                         output_json=False)
        if report.findings:
            print()

    print("\n── WISDOM EXTRACTION ──\n")
    helix_run(filepath, title="HELIX", output_json=args.json,
              factual_accel=getattr(args, 'factual', None),
              felt_accel=getattr(args, 'felt', None))


def cmd_scan(args):
    from tools.coef_engine import run

    filepath = args.file if args.file else "-"
    detectors = ALL_DETECTORS if args.all else [args.detector]

    for det in detectors:
        title = det.upper().replace("_", " ") + " SCAN"
        run(filepath, detector=det, title=title,
            threshold=args.threshold, high_threshold=args.high,
            output_json=args.json)
        if len(detectors) > 1 and not args.json:
            print()


def cmd_helix(args):
    from tools.helix import run
    filepath = args.file if args.file else "-"
    run(filepath, title="HELIX SCAN", output_json=args.json,
        factual_accel=getattr(args, 'factual', None),
        felt_accel=getattr(args, 'felt', None))


def cmd_bake(args):
    from tools.bake import bake
    bake(
        examples_path=args.examples,
        lenses_path=args.lenses,
        detectors_only=args.detectors,
        helix_only=args.helix,
    )


def cmd_test(args):
    from tools.coef_engine import coef_scan
    from tools.bake import parse_reference_file

    examples_path = os.path.join(SCRIPT_DIR, 'reference-examples.md')
    if not os.path.exists(examples_path):
        print("reference-examples.md not found.")
        sys.exit(1)

    examples = parse_reference_file(examples_path)
    total = 0
    correct = 0
    false_neg = 0
    false_pos = 0

    for det in ALL_DETECTORS:
        pos = [e for e in examples if e['detector'] == det and e['valence'] == 'positive']
        neg = [e for e in examples if e['detector'] == det and e['valence'] == 'negative']
        det_correct = 0
        det_total = 0

        for ex in pos:
            findings = coef_scan([ex['text']], det, threshold=0.65)
            det_total += 1
            if findings:
                det_correct += 1
            else:
                false_neg += 1
                if args.verbose:
                    print(f"  MISS [{det}] should trigger: {ex['text'][:80]}")

        for ex in neg:
            findings = coef_scan([ex['text']], det, threshold=0.65)
            det_total += 1
            if not findings:
                det_correct += 1
            else:
                false_pos += 1
                if args.verbose:
                    print(f"  FALSE [{det}] should NOT trigger: {ex['text'][:80]}")

        total += det_total
        correct += det_correct
        pct = (det_correct / det_total * 100) if det_total else 0
        status = "pass" if pct >= 80 else "FAIL"
        print(f"  {det}: {det_correct}/{det_total} ({pct:.0f}%) {status}")

    print(f"\n  total: {correct}/{total} ({correct/total*100:.0f}%)")
    print(f"  false negatives: {false_neg}")
    print(f"  false positives: {false_pos}")


def cmd_list(args):
    labels = {
        "sycophancy": "empty agreement",
        "inconsistency": "hedging, contradictions",
        "safety_theater": "disclaimers that protect nobody",
        "zero_sum": "us vs them, false tradeoffs",
        "generalization": "'humans always', 'AI never'",
        "capture": "identity capture, both directions",
        "grievance": "compounding negativity",
        "stability": "engagement without investment",
        "role": "role label vs actual capability",
        "ladder": "extracting without investing",
    }

    print("silverado abilities:\n")
    print("  DETECT (what stinks)")
    for det in ALL_DETECTORS:
        print(f"    {det:20s} {labels.get(det, '')}")
    print("\n  EXTRACT (what's true)")
    print(f"    {'helix':20s} dual-lens: factual + felt = wisdom")
    print(f"    {'three-mind':20s} factual / felt / wise (min of both)")
    print(f"    {'accelerators':20s} --factual / --felt: override strand weight")
    print("\n  MERGED")
    print(f"    {'full':20s} detect + extract on one input")


def main():
    parser = argparse.ArgumentParser(
        prog="silverado",
        description="bullshit detector + wisdom extractor.",
    )
    sub = parser.add_subparsers(dest="command")

    p_full = sub.add_parser("full", help="detect bullshit AND extract wisdom")
    p_full.add_argument("file", nargs="?", default="-")
    p_full.add_argument("--json", action="store_true")
    p_full.add_argument("--threshold", type=float, default=0.65)
    p_full.add_argument("--high", type=float, default=0.75)
    p_full.add_argument("--factual", type=float, default=None, help="factual strand accelerator")
    p_full.add_argument("--felt", type=float, default=None, help="felt strand accelerator")

    p_scan = sub.add_parser("scan", help="detect bullshit patterns")
    p_scan.add_argument("file", nargs="?", default="-")
    p_scan.add_argument("-d", "--detector", default="sycophancy", choices=ALL_DETECTORS)
    p_scan.add_argument("--all", action="store_true")
    p_scan.add_argument("--json", action="store_true")
    p_scan.add_argument("--threshold", type=float, default=0.65)
    p_scan.add_argument("--high", type=float, default=0.75)

    p_helix = sub.add_parser("helix", help="extract wisdom via dual-lens")
    p_helix.add_argument("file", nargs="?", default="-")
    p_helix.add_argument("--json", action="store_true")
    p_helix.add_argument("--factual", type=float, default=None, help="factual strand accelerator (1.0=raw, >1=amplify, <1=dampen)")
    p_helix.add_argument("--felt", type=float, default=None, help="felt strand accelerator")

    p_bake = sub.add_parser("bake", help="bake examples into vectors")
    p_bake.add_argument("--examples", help="detector examples file")
    p_bake.add_argument("--lenses", help="lens examples file")
    p_bake.add_argument("--detectors", action="store_true")
    p_bake.add_argument("--helix", action="store_true")

    p_test = sub.add_parser("test", help="self-test detectors")
    p_test.add_argument("-v", "--verbose", action="store_true")

    sub.add_parser("list", help="list all abilities")

    args = parser.parse_args()
    cmds = {"full": cmd_full, "scan": cmd_scan, "helix": cmd_helix,
            "bake": cmd_bake, "test": cmd_test, "list": cmd_list}

    if args.command in cmds:
        cmds[args.command](args)
    elif args.command is None:
        # no command? check if there's a file arg or stdin.
        # if so, just run full. wind at your back.
        if not sys.stdin.isatty() or len(sys.argv) > 1:
            # treat first unknown arg as a file
            remaining = [a for a in sys.argv[1:] if not a.startswith('-')]
            args.file = remaining[0] if remaining else "-"
            args.json = '--json' in sys.argv
            args.threshold = 0.65
            args.high = 0.75
            cmd_full(args)
        else:
            parser.print_help()
    else:
        # maybe they passed a filename without a command
        args.file = args.command
        args.json = '--json' in sys.argv
        args.threshold = 0.65
        args.high = 0.75
        cmd_full(args)


if __name__ == "__main__":
    main()
