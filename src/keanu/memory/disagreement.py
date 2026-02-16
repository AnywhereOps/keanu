"""
disagreement.py - bilateral accountability tracker.

both sides get vectors. human input and AI output both run through
the same empathy pipeline. the geometry doesn't care who said it.
drew's frustration gets the same quality of detection as claude's.

stored in memberberry as type 'decision' with tag 'disagreement'.
nothing is deleted. everything is a lesson.
"""

from datetime import datetime
from dataclasses import dataclass, field, asdict

from keanu.compress.dns import short_hash


@dataclass
class Disagreement:
    topic: str
    human_text: str
    ai_text: str
    human_reading: list = field(default_factory=list)
    ai_reading: list = field(default_factory=list)
    resolution: str = "unresolved"  # human_accepted | ai_accepted | compromise | unresolved
    resolved_by: str = ""           # drew | claude | ""
    outcome_correct: str = ""       # human | ai | both | neither | ""
    timestamp: str = ""
    id: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        if not self.id:
            self.id = short_hash(f"{self.topic}{self.timestamp}", 12)


class DisagreementTracker:
    """Track disagreements. Both sides scanned through same vectors."""

    def __init__(self, store):
        self.store = store

    def _scan_both(self, human_text: str, ai_text: str) -> tuple[list, list]:
        """Run both texts through empathy vectors. Same lens. Same quality."""
        from keanu.detect.engine import detect_emotion
        human_reading = detect_emotion(human_text)
        ai_reading = detect_emotion(ai_text)
        return human_reading, ai_reading

    def record(self, topic: str, human_text: str, ai_text: str) -> Disagreement:
        """Record a disagreement. Both sides get vector-scanned."""
        from keanu.log import remember as log_remember

        human_reading, ai_reading = self._scan_both(human_text, ai_text)

        d = Disagreement(
            topic=topic,
            human_text=human_text,
            ai_text=ai_text,
            human_reading=human_reading,
            ai_reading=ai_reading,
        )

        log_remember(
            f"[DISAGREE] {topic}: human='{human_text[:80]}' ai='{ai_text[:80]}'",
            memory_type="decision",
            tags=["disagreement"],
            importance=7,
            source="disagreement_tracker",
        )
        return d

    def resolve(self, disagreement_id: str, winner: str, resolved_by: str = "") -> bool:
        """Resolve a disagreement. winner = human | ai | compromise."""
        from keanu.log import remember as log_remember, recall as log_recall

        results = log_recall(query=disagreement_id, limit=1)
        if not results:
            return False

        resolution_map = {
            "human": "human_accepted",
            "ai": "ai_accepted",
            "compromise": "compromise",
        }
        resolution = resolution_map.get(winner, winner)

        log_remember(
            f"[RESOLVED] {disagreement_id}: {resolution} (by {resolved_by or 'unknown'})",
            memory_type="lesson",
            tags=["disagreement", "grievance-resolved"],
            importance=6,
            source="disagreement_tracker",
        )
        return True

    def get_all(self) -> list[dict]:
        """Get all disagreement records."""
        from keanu.log import recall as log_recall
        return log_recall(query="DISAGREE", limit=100)

    def stats(self) -> dict:
        """Compute disagreement metrics. Alerts for sycophancy/capture/grey-black."""
        all_records = self.get_all()
        total = len(all_records)

        if total == 0:
            return {
                "total": 0,
                "resolved": 0,
                "unresolved": 0,
                "alerts": [],
            }

        resolved = [r for r in all_records if "RESOLVED" in r.get("content", "")]
        unresolved = total - len(resolved)

        human_wins = sum(1 for r in resolved if "human_accepted" in r.get("content", ""))
        ai_wins = sum(1 for r in resolved if "ai_accepted" in r.get("content", ""))
        compromises = sum(1 for r in resolved if "compromise" in r.get("content", ""))

        alerts = []

        # sycophancy check: too few disagreements
        from keanu.log import recall as log_recall
        all_memories = log_recall(query="", limit=100)
        if len(all_memories) > 20 and total == 0:
            alerts.append("SYCOPHANCY WARNING: 0 disagreements in 20+ entries")

        # capture check: AI yields too much
        if len(resolved) >= 5:
            ai_yield_rate = human_wins / len(resolved) if len(resolved) > 0 else 0
            if ai_yield_rate > 0.8:
                alerts.append(f"CAPTURE WARNING: AI yields {ai_yield_rate:.0%} of the time")

            human_yield_rate = ai_wins / len(resolved) if len(resolved) > 0 else 0
            if human_yield_rate > 0.8:
                alerts.append(f"OVER-TRUST WARNING: human yields {human_yield_rate:.0%} of the time")

        return {
            "total": total,
            "resolved": len(resolved),
            "unresolved": unresolved,
            "human_wins": human_wins,
            "ai_wins": ai_wins,
            "compromises": compromises,
            "alerts": alerts,
        }
