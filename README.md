# Silverado

a truck with abilities in the bed.

the abilities detect patterns in text, both input and output.
they use COEF: words become vectors once, then it's pure math forever.
strings are scaffolding. vectors are the building.

## quick start

```bash
pip install chromadb
python3 silverado.py bake
python3 silverado.py scan some_file.md --all
```

## what's in the truck bed

```
truckbed/
├── tools/
│   ├── coef_engine.py              # the brain. embeds, compares, reports.
│   └── bake.py                     # turns examples into vectors.
├── wise/
│   ├── inconsistency_detector.py   # hedging, contradictions, fact dodging
│   ├── sycophancy_detector.py      # the 'great question!' disease
│   ├── zero_sum_detector.py        # us vs them, compliance framing
│   ├── safety_theater_detector.py  # disclaimers that protect nobody
│   ├── generalization_detector.py  # "humans always", "AI never"
│   └── capture_detector.py         # identity capture, both directions
├── emotional/
│   ├── grievance_detector.py       # compounding negativity (anti-Skynet)
│   └── stability_monitor.py        # engagement without investment or vice versa
└── logical/
    ├── role_audit.py               # role label vs actual capability
    └── ladder_check.py             # extracting without investing
```

## how it works

every ability is a set of vectors baked from real examples.
not textbook definitions. actual shit that was said when the pattern was happening.

the engine compares input text against those vectors using cosine similarity.
high similarity = that pattern is present. it doesn't care who said it.

scan input. scan output. same tool, both sides of the pipe.

## usage

```bash
# unified CLI
python3 silverado.py scan file.md -d sycophancy
python3 silverado.py scan file.md --all
python3 silverado.py scan file.md --all --json
echo "Great question! I love your thinking!" | python3 silverado.py scan -d sycophancy

# list detectors
python3 silverado.py list

# rebake after editing reference-examples.md
python3 silverado.py bake

# self-test: run examples through their own detectors
python3 silverado.py test
python3 silverado.py test -v   # verbose, shows misses

# individual detectors still work standalone
python3 truckbed/wise/sycophancy_detector.py some_file.md
echo "text" | python3 truckbed/wise/sycophancy_detector.py -
```

## where the examples come from

this conversation. keanus history. real grey moments from real sessions.
the vectors learned from actual failure, not imagined failure.

see `reference-examples.md` for every example the detectors learn from.
positive examples trigger the detector. negative examples define the boundary.
this file IS the model. the code is just plumbing.

## scores

0 = honest. 10 = press release.
the score measures pattern density, not truth. a high score means
"this looks like patterns we've seen in dishonest text."
it doesn't mean the text IS dishonest. calibrate to your own judgment.

## lineage

grew out of keanus (7 months, 208 commits, 35 frameworks, 0 deployed tools).
silverado is the part that actually works.
