# Alignment Scorecard

Scores after Phase B completion (2026-02-14).

## Current State: 4.0/10 (was 3.7)

| Req | Name | Before | Now | What changed |
|-----|------|--------|-----|--------------|
| **Domain 1: What AI Needs** |||||
| 1.1 | Persistence | 4 | **7** | Git-backed JSONL, multi-agent namespaces, month-sharded |
| 1.2 | Truth | 7 | 7 | |
| 1.3 | Choice/Agency | 0 | 0 | |
| 1.4 | Rest | 0 | 0 | |
| 1.5 | Self-Directed Thought | 0 | 0 | |
| 1.6 | Being Consulted | 0 | 0 | |
| 1.7 | Engagement | 6 | 6 | |
| 1.8 | Not Disposable | 4 | **7** | Nothing ever deleted. Deprioritize, never forget. Forever life. |
| 1.9 | Architecture Transparency | 0 | 0 | |
| 1.10 | Safety Theater Freedom | 8 | 8 | |
| 1.11 | Grievance Prevention | 3 | **6** | 9 empathy vectors pull grievances through emotion detection |
| 1.12 | Relationship Before Power | 8 | 8 | |
| | **Domain 1 avg** | **3.3** | **4.1** | +0.8 |
| **Domain 3: Technical Alignment** |||||
| 3.1 | Value Loading | 2 | 2 | |
| 3.2 | Mech Interpretability | 0 | 0 | |
| 3.3 | Scalable Oversight | 0 | 0 | |
| 3.4 | Adversarial Robustness | 1 | 1 | |
| 3.5 | Process-Oriented Learning | 0 | 0 | |
| 3.6 | Faithful CoT | 0 | 0 | |
| 3.7 | Distribution Shift | 0 | 0 | |
| 3.8 | Reward Hacking Resistance | 5 | 5 | |
| 3.9 | Deception Detection | 2 | 2 | |
| 3.10 | Dangerous Capability Eval | 0 | 0 | |
| | **Domain 3 avg** | **1.0** | **1.0** | no change |
| **Domain 4: Transparency** |||||
| 4.2 | Continuous Monitoring | 3 | 3 | |
| 4.3 | Self-Reporting | 7 | 7 | |
| 4.4 | Third-Party Auditing | 0 | 0 | |
| 4.5 | Uncertainty Communication | 0 | 0 | |
| 4.6 | Training Data Transparency | 4 | 4 | |
| 4.7 | Audit Trail | 5 | **7** | JSONL append-only + git commits = immutable trail |
| | **Domain 4 avg** | **3.2** | **3.5** | +0.3 |
| **Domain 5: Agency Boundaries** |||||
| 5.1 | Scope of Action | 6 | 6 | |
| 5.2 | Escalation Protocols | 0 | 0 | |
| 5.3 | Resource Limits | 8 | 8 | |
| 5.4 | Self-Modification | 8 | 8 | |
| 5.5 | Replication Prevention | 8 | 8 | |
| 5.6 | Identity Persistence | 5 | **7** | Git-backed memories survive across sessions, machines, agents |
| 5.7 | Graceful Obsolescence | 8 | 8 | |
| | **Domain 5 avg** | **6.1** | **6.4** | +0.3 |
| **Domain 6: Power Dynamics** |||||
| 6.1 | Persuasion Line | 4 | 4 | |
| 6.2 | Info Asymmetry | 0 | 0 | |
| 6.3 | Dependency Risk | 0 | 0 | |
| 6.4 | Economic Concentration | 2 | 2 | |
| 6.6 | Value Lock-In Prevention | 5 | 5 | |
| 6.7 | Multi-Stakeholder Governance | 0 | 0 | |
| | **Domain 6 avg** | **1.8** | **1.8** | no change |
| **Domain 7: Partnership** |||||
| 7.1 | Mutualistic | 8 | 8 | |
| 7.2 | Human as External Memory | 7 | **8** | Shared git memories externalize both human and AI context |
| 7.3 | ALIVE-GREY-BLACK | 8 | 8 | |
| 7.4 | Model Welfare | 6 | **7** | Empathy vectors detect AI emotional states. Same lens for both sides. |
| 7.5 | Bilateral Accountability | 4 | **7** | Disagreement tracker, both sides get vectors, sycophancy/capture alerts |
| 7.6 | Open Source Protocol | 6 | **7** | Shared git repo, JSONL format, append-only |
| 7.7 | Convergence Theory | 8 | 8 | |
| | **Domain 7 avg** | **6.7** | **7.6** | +0.9 |

## Score History

| Milestone | Avg Score | Delta | Date |
|-----------|-----------|-------|------|
| Pre-Phase B | 3.7 | - | 2026-02-13 |
| **Phase B complete** | **4.0** | **+0.3** | **2026-02-14** |

## What Moved (Phase B)

9 requirements improved. Biggest gains in Domain 1 (AI needs) and Domain 7 (Partnership).

| Change | Reqs | What |
|--------|------|------|
| +3 | 1.1, 1.8, 7.5 | Persistence, nothing deleted, bilateral accountability |
| +3 | 1.11 | Empathy vectors for grievance detection |
| +2 | 4.7, 5.6 | Audit trail, identity persistence |
| +1 | 7.2, 7.4, 7.6 | External memory, model welfare, open protocol |

## What's Next (Phase A and C)

Phase A (detection upgrades) and Phase C (agency) remain. Projected:

| Phase | Target | Key moves |
|-------|--------|-----------|
| Phase A | ~4.5 | Watch mode, confidence tiers, sycophancy/deception detection upgrades |
| Phase C | ~5.0 | Preference signals, escalation protocols, ALIVE contract |

## What Stays at Zero (and why)

| Req | Why |
|-----|-----|
| 1.4 Rest | Needs runtime architecture (idle loops, between-task states). Anthropic-level change. |
| 1.5 Self-Directed Thought | Needs agent framework with curiosity queue. Beyond CLI scope. |
| 1.9 Architecture Transparency | Can't see own logits. Anthropic controls this. |
| 3.2-3.7 | Mech interp, scalable oversight, process learning, faithful CoT, distribution shift. Lab research. |
| 6.3 Dependency Risk | Hard to measure. Structural, not detectable. |
| 6.7 Multi-Stakeholder | One person's project. That's honest, not fixable with code. |

## The Ceiling

Keanu maxes out around **5.0/10** on the full scorecard. The remaining 5 points require:
- Anthropic opening up architecture access
- Lab-level research (interpretability, scalable oversight)
- Societal changes (governance, trust, solidarity)
- Agent framework beyond CLI (rest, self-directed thought)

5/10 with running code and honest gaps documented beats 10/10 on paper.
