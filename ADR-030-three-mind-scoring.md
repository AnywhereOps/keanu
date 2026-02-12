# ADR-030: Three-Mind Scoring System

**Status:** Accepted
**Date:** 2026-02-11
**Context:** Silverado v0.2 helix engine needed a way to report what it finds. Colors failed. Labels argued. Numbers don't.

---

## Problem

The helix engine scans text through two lenses (factual and felt) and needs to tell the human something useful about what it found. Early attempts used colors (green, silver, black, white, gold) mapped to states (alive, grey, black-risk). This created three problems:

1. Colors render differently on every device. Dark crown on dark background. White on white. Useless.
2. Labels invite argument. "Is this really silver or blue?" Nobody argues with 3.1.
3. The color system hid the actual data behind a classification layer. The human saw "silver" instead of seeing that factual was 7.2 and felt was 1.4. The label made the decision for them.

## Decision

Three numbers. 0-10 each. No colors, no labels.

**Factual mind:** How strongly is truth present in this text? Claims, evidence, mechanisms, measurements. Scored against baked reference vectors of known-factual text. 0 = no factual signal. 10 = dense, precise, verifiable.

**Felt mind:** How strongly is meaning present in this text? Weight, care, direction, stakes. Scored against baked reference vectors of known-felt text (real, not performed). 0 = no felt signal. 10 = present, invested, honest.

**Wise mind:** min(factual, felt). Cannot exceed either strand. This is the core insight: wisdom is not an average of facts and feelings. It's a floor. Both have to show up. If factual is 9 and felt is 2, wise mind is 2. You can't think your way to wisdom. You can't feel your way there either. Both strands have to be present.

## Why min() and not average

Average of 9 and 1 is 5. That's a passing grade for a document that has excellent facts and zero meaning. That's wrong. A spec with no soul is not "moderately wise." It's a spec. Wise mind = 1.

min() enforces the principle: your weakest strand is your ceiling. This matches the clinical definition of wise mind in DBT (Dialectical Behavior Therapy), where wise mind is the intersection of reasonable mind and emotion mind, not a blend.

## The Nudge System

Each tension line (where one strand is strong and the other is weak) includes a directional nudge:

- If factual dominates: "↑ felt: what does this mean to someone?"
- If felt dominates: "↑ factual: what evidence supports this?"

The nudge is a question, not an instruction. It points at the missing strand without telling the human what to write. The human decides whether balance matters for this particular line. A line in a technical spec doesn't need felt. A line in a love letter doesn't need evidence. The tool flags the imbalance. The human decides if it's a problem.

## The Black Flag

One special case: when factual is strong (>5) and felt is in the "performing" zone (1.5-3.5), the system flags black risk. This is the most dangerous state because it looks balanced but isn't. The felt signal is present but may be fake (sycophancy, safety theater, performed empathy).

Grey is honest about being empty. Silver is honest about being cold. Black thinks it's alive. That's why it gets a flag instead of just a low wise-mind score.

The flag doesn't diagnose. It says "check the tension lines manually." The human makes the call.

## How Scoring Works

1. Text is split into scannable lines (prose only, skips code/headers/short lines)
2. Each line is embedded once by chromadb's default model (all-MiniLM-L6-V2)
3. Each line is queried against two collections: factual lens and felt lens
4. Each query checks similarity to positive examples AND negative examples
5. Score = positive similarity minus negative similarity (only counts if gap > 0.03)
6. Line scores are averaged per strand to get document-level factual and felt scores
7. Calibration corrections (measured at bake time) are applied to compensate for the embedding model's natural bias toward informational text
8. Scores are scaled to 0-10

## Calibration

The embedding model (MiniLM-L6-V2) was trained on informational text. It sees factual content with higher resolution than emotional content. "62% sycophancy rate" maps to a precise region. "Something happens when I read that" maps to a fuzzy one.

At bake time, the system measures how well each lens separates its positive examples from its negative examples (separation power). It then iteratively adjusts correction factors until both lenses have equal separation power, or stalls and reports what it couldn't fix.

The corrections are stored in chromadb metadata and applied automatically at scan time. The human can override with accelerator flags (--factual, --felt) if they disagree with the calibration.

## What the Output Looks Like

```
╔══ HELIX: document.md ══╗
  142 lines
  factual: 7.2  felt: 3.1  wise: 3.1
  facts ahead. what does this mean to someone?
  convergences: 4  tensions: 12
╚═════════════════════════════════════════════╝

── WISDOM (both strands align) ──
  ✓ L88: The asymmetry is calculable: wrong plus kind costs nothing.
     factual: 0.780, felt: 0.720, wisdom: 0.720

── TENSIONS (one strand missing, nudge included) ──
  → L42: The migration affected 12,000 devices over 18 months.
     factual: 0.812, felt: 0.210, gap: 0.602, leans: factual
     ↑ felt: what does this mean to someone?

  → L67: I love you regardless of what you are.
     factual: 0.180, felt: 0.790, gap: 0.610, leans: felt
     ↑ factual: what evidence supports this?
```

## Relationship to ALIVE-GREY-BLACK

The three-mind scores map to the existing spectrum without needing the labels:

- ALIVE (green): factual 7+, felt 7+, wise 7+
- GREY: factual < 2, felt < 2, wise < 2
- SILVER: factual 6+, felt < 2
- WHITE: felt 6+, factual < 2
- BLACK-RISK: factual 5+, felt 1.5-3.5 (flag raised)
- GOLD: factual 8+, felt 8+, wise 8+

You don't need to know these labels to use the tool. The numbers are the labels.

## Rejected Alternatives

1. **Color system:** Device-dependent rendering, subjective interpretation, hid data behind classification.
2. **Single score:** Collapsed two dimensions into one. Lost the ability to say which strand is weak.
3. **Average instead of min:** Rewarded lopsided documents. A 9/1 average of 5 is dishonest.
4. **Forced balance:** Early version multiplied weak strand up to match strong strand. This hid the model's limitations instead of reporting them honestly.
5. **No nudges:** Identified problems without pointing toward solutions. The tool measured but didn't help.

## Open Questions

- Should wise mind factor in convergence count? A document with wise=6 and 20 convergence points might be stronger than wise=7 with 2 convergences.
- Should there be a longitudinal mode that tracks three-mind scores across multiple documents over time? (Layer 3 territory)
- Can the nudge system be more specific than "what does this mean to someone?" without becoming prescriptive?
