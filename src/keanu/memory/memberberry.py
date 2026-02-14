#!/usr/bin/env python3
"""
memberberry.py - "Oh, 'member? I 'member!"

A memory recall engine that remembers what you care about
and turns it into executable plans. No superintelligence,
no alignment theory, no scope creep. Just: remember, recall, plan, do.

Author: Drew Kemp-Dahlberg + Claude
Purpose: Live your best life by never forgetting what matters.
"""

import json
import os
import re
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum


# ============================================================
# CONFIGURATION
# ============================================================

MEMBERBERRY_DIR = Path.home() / ".memberberry"
MEMORIES_FILE = MEMBERBERRY_DIR / "memories.json"
PLANS_FILE = MEMBERBERRY_DIR / "plans.json"
CONFIG_FILE = MEMBERBERRY_DIR / "config.json"

DEFAULT_CONFIG = {
    "max_recall": 10,
    "decay_days": 90,         # memories lose relevance after this
    "plan_horizon_days": 14,  # default planning window
    "priority_tags": ["health", "faith", "career", "relationships", "finance", "build"],
}


# ============================================================
# DATA MODELS
# ============================================================

class MemoryType(str, Enum):
    GOAL = "goal"
    FACT = "fact"
    DECISION = "decision"
    INSIGHT = "insight"
    PREFERENCE = "preference"
    COMMITMENT = "commitment"
    LESSON = "lesson"


class PlanStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    BLOCKED = "blocked"
    DONE = "done"
    DROPPED = "dropped"


@dataclass
class Memory:
    content: str
    memory_type: str  # MemoryType value
    tags: list = field(default_factory=list)
    source: str = ""  # where this came from (conversation, manual, etc.)
    created_at: str = ""
    last_recalled: str = ""
    recall_count: int = 0
    importance: int = 5  # 1-10 scale
    id: str = ""
    linked_memories: list = field(default_factory=list)
    context: str = ""  # situational context when memory was created

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.id:
            raw = f"{self.content}{self.created_at}"
            self.id = hashlib.sha256(raw.encode()).hexdigest()[:12]

    def relevance_score(self, query_tags: list = None, query_text: str = "") -> float:
        """Calculate how relevant this memory is right now."""
        score = 0.0

        # Base importance (normalized to 0-1)
        score += self.importance / 10.0

        # Tag overlap
        if query_tags:
            overlap = len(set(self.tags) & set(query_tags))
            score += overlap * 0.3

        # Text match (simple keyword overlap, no ML needed for MVP)
        if query_text:
            query_words = set(query_text.lower().split())
            content_words = set(self.content.lower().split())
            context_words = set(self.context.lower().split())
            all_memory_words = content_words | context_words
            word_overlap = len(query_words & all_memory_words)
            if word_overlap > 0:
                score += min(word_overlap * 0.2, 1.0)

        # Recency boost (memories accessed recently are hotter)
        if self.last_recalled:
            days_since = (datetime.now() - datetime.fromisoformat(self.last_recalled)).days
            if days_since < 7:
                score += 0.3
            elif days_since < 30:
                score += 0.15

        # Decay penalty (old untouched memories fade)
        days_old = (datetime.now() - datetime.fromisoformat(self.created_at)).days
        if days_old > 90 and self.recall_count < 3:
            score *= 0.5

        # Type bonuses (commitments and decisions matter more for planning)
        type_weights = {
            "goal": 0.3,
            "commitment": 0.25,
            "decision": 0.2,
            "insight": 0.15,
            "lesson": 0.15,
            "preference": 0.1,
            "fact": 0.05,
        }
        score += type_weights.get(self.memory_type, 0)

        return round(score, 3)


@dataclass
class Action:
    description: str
    deadline: str = ""
    status: str = "pending"
    memory_refs: list = field(default_factory=list)  # memory IDs this came from
    id: str = ""

    def __post_init__(self):
        if not self.id:
            raw = f"{self.description}{datetime.now().isoformat()}"
            self.id = hashlib.sha256(raw.encode()).hexdigest()[:8]


@dataclass
class Plan:
    title: str
    actions: list = field(default_factory=list)  # list of Action dicts
    tags: list = field(default_factory=list)
    status: str = "draft"
    created_at: str = ""
    target_date: str = ""
    memory_refs: list = field(default_factory=list)
    notes: str = ""
    id: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
        if not self.id:
            raw = f"{self.title}{self.created_at}"
            self.id = hashlib.sha256(raw.encode()).hexdigest()[:12]


# ============================================================
# STORAGE LAYER
# ============================================================

class MemberberryStore:
    """Simple JSON-backed storage. No database needed for MVP.
    Upgrade path: SQLite -> Postgres -> whatever, the interface stays the same."""

    def __init__(self):
        MEMBERBERRY_DIR.mkdir(parents=True, exist_ok=True)
        self.memories: list[dict] = self._load(MEMORIES_FILE)
        self.plans: list[dict] = self._load(PLANS_FILE)
        self.config: dict = self._load_config()

    def _load(self, path: Path) -> list:
        if path.exists():
            with open(path, "r") as f:
                return json.load(f)
        return []

    def _load_config(self) -> dict:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        # Write defaults
        with open(CONFIG_FILE, "w") as f:
            json.dump(DEFAULT_CONFIG, f, indent=2)
        return DEFAULT_CONFIG.copy()

    def _save_memories(self):
        # Strip transient fields before saving
        clean = [{k: v for k, v in m.items() if not k.startswith("_")} for m in self.memories]
        with open(MEMORIES_FILE, "w") as f:
            json.dump(clean, f, indent=2)

    def _save_plans(self):
        with open(PLANS_FILE, "w") as f:
            json.dump(self.plans, f, indent=2)

    # -- Memory operations --

    def remember(self, memory: Memory) -> str:
        """Store a new memory. Returns the memory ID."""
        self.memories.append(asdict(memory))
        self._save_memories()
        return memory.id

    def recall(self, query: str = "", tags: list = None,
               memory_type: str = None, limit: int = None) -> list[dict]:
        """Recall relevant memories based on query, tags, or type."""
        limit = limit or self.config.get("max_recall", 10)
        candidates = []

        for m_dict in self.memories:
            # Strip any transient fields before hydrating
            clean = {k: v for k, v in m_dict.items() if not k.startswith("_")}
            m = Memory(**clean)

            # Filter by type if specified
            if memory_type and m.memory_type != memory_type:
                continue

            score = m.relevance_score(query_tags=tags, query_text=query)
            candidates.append((score, m_dict))

        # Sort by relevance, highest first
        candidates.sort(key=lambda x: x[0], reverse=True)

        # Update recall timestamps for returned memories
        results = []
        for score, m_dict in candidates[:limit]:
            m_dict["last_recalled"] = datetime.now().isoformat()
            m_dict["recall_count"] = m_dict.get("recall_count", 0) + 1
            m_dict["_relevance_score"] = score
            results.append(m_dict)

        self._save_memories()
        return results

    def forget(self, memory_id: str) -> bool:
        """Remove a memory by ID."""
        before = len(self.memories)
        self.memories = [m for m in self.memories if m.get("id") != memory_id]
        if len(self.memories) < before:
            self._save_memories()
            return True
        return False

    def get_all_tags(self) -> list[str]:
        """Get all unique tags across memories."""
        tags = set()
        for m in self.memories:
            tags.update(m.get("tags", []))
        return sorted(tags)

    # -- Plan operations --

    def create_plan(self, plan: Plan) -> str:
        """Store a new plan. Returns the plan ID."""
        self.plans.append(asdict(plan))
        self._save_plans()
        return plan.id

    def get_plans(self, status: str = None, tags: list = None) -> list[dict]:
        """Get plans, optionally filtered."""
        results = self.plans
        if status:
            results = [p for p in results if p.get("status") == status]
        if tags:
            tag_set = set(tags)
            results = [p for p in results if tag_set & set(p.get("tags", []))]
        return results

    def update_plan_status(self, plan_id: str, status: str) -> bool:
        """Update a plan's status."""
        for p in self.plans:
            if p.get("id") == plan_id:
                p["status"] = status
                self._save_plans()
                return True
        return False

    def stats(self) -> dict:
        """Quick stats on the memory store."""
        type_counts = {}
        for m in self.memories:
            t = m.get("memory_type", "unknown")
            type_counts[t] = type_counts.get(t, 0) + 1

        plan_counts = {}
        for p in self.plans:
            s = p.get("status", "unknown")
            plan_counts[s] = plan_counts.get(s, 0) + 1

        return {
            "total_memories": len(self.memories),
            "memories_by_type": type_counts,
            "total_plans": len(self.plans),
            "plans_by_status": plan_counts,
            "unique_tags": self.get_all_tags(),
        }


# ============================================================
# PLAN GENERATOR
# ============================================================

class PlanGenerator:
    """Turns recalled memories into actionable plans.

    This is the 'so what' engine. Memories are useless if they
    don't become actions. This takes what you know and makes
    it something you DO.
    """

    def __init__(self, store: MemberberryStore):
        self.store = store

    def generate_plan(self, focus: str, tags: list = None,
                      horizon_days: int = 14) -> Plan:
        """Generate a plan from relevant memories.

        Args:
            focus: What are you trying to do? (natural language)
            tags: Optional tag filters
            horizon_days: How far out to plan
        """
        # Recall everything relevant
        memories = self.store.recall(query=focus, tags=tags, limit=20)

        # Extract goals, commitments, and decisions
        goals = [m for m in memories if m.get("memory_type") == "goal"]
        commitments = [m for m in memories if m.get("memory_type") == "commitment"]
        decisions = [m for m in memories if m.get("memory_type") == "decision"]
        insights = [m for m in memories if m.get("memory_type") == "insight"]
        lessons = [m for m in memories if m.get("memory_type") == "lesson"]

        # Build actions from memories
        actions = []

        # Goals become primary actions
        for g in goals:
            actions.append(asdict(Action(
                description=f"[GOAL] {g['content']}",
                deadline=(datetime.now() + timedelta(days=horizon_days)).isoformat(),
                memory_refs=[g["id"]],
            )))

        # Commitments become time-sensitive actions
        for c in commitments:
            actions.append(asdict(Action(
                description=f"[COMMIT] {c['content']}",
                deadline=(datetime.now() + timedelta(days=7)).isoformat(),
                memory_refs=[c["id"]],
            )))

        # Decisions get review actions (did you follow through?)
        for d in decisions:
            actions.append(asdict(Action(
                description=f"[REVIEW] Check: did you follow through on '{d['content']}'?",
                deadline=(datetime.now() + timedelta(days=3)).isoformat(),
                memory_refs=[d["id"]],
            )))

        # Lessons become guardrails (things to avoid or remember)
        for l in lessons:
            actions.append(asdict(Action(
                description=f"[GUARDRAIL] Remember: {l['content']}",
                memory_refs=[l["id"]],
            )))

        # Create the plan
        all_tags = list(set(tags or []) | set(t for m in memories for t in m.get("tags", [])))
        memory_ids = [m["id"] for m in memories]

        plan = Plan(
            title=f"Plan: {focus}",
            actions=actions,
            tags=all_tags[:10],
            status="draft",
            target_date=(datetime.now() + timedelta(days=horizon_days)).isoformat(),
            memory_refs=memory_ids,
            notes=f"Generated from {len(memories)} memories. "
                  f"{len(goals)} goals, {len(commitments)} commitments, "
                  f"{len(decisions)} decisions to review, {len(lessons)} guardrails.",
        )

        self.store.create_plan(plan)
        return plan


# ============================================================
# CLI INTERFACE
# ============================================================

class MemberberryCLI:
    """Command line interface. Simple. Fast. Phone-friendly output."""

    def __init__(self):
        self.store = MemberberryStore()
        self.planner = PlanGenerator(self.store)

    def run(self, args: list = None):
        """Main CLI entry point."""
        import sys
        args = args or sys.argv[1:]

        if not args:
            self._help()
            return

        cmd = args[0].lower()
        rest = args[1:]

        commands = {
            "remember": self._cmd_remember,
            "r": self._cmd_remember,
            "recall": self._cmd_recall,
            "q": self._cmd_recall,
            "plan": self._cmd_plan,
            "p": self._cmd_plan,
            "plans": self._cmd_plans,
            "forget": self._cmd_forget,
            "stats": self._cmd_stats,
            "tags": self._cmd_tags,
            "dump": self._cmd_dump,
            "help": self._help,
        }

        handler = commands.get(cmd)
        if handler:
            handler(rest)
        else:
            print(f"Unknown command: {cmd}")
            self._help()

    def _help(self, args=None):
        print("""
memberberry.py - "Oh, 'member? I 'member!"

COMMANDS:
  remember <type> <content>   Store a memory
    types: goal, fact, decision, insight, preference, commitment, lesson
    flags: --tags tag1,tag2  --importance 1-10  --context "situational note"

  recall <query>              Recall relevant memories
    flags: --tags tag1,tag2  --type <memory_type>  --limit N

  plan <focus>                Generate a plan from memories
    flags: --tags tag1,tag2  --days N (planning horizon)

  plans                       List all plans
    flags: --status draft|active|blocked|done|dropped

  forget <memory_id>          Remove a memory
  stats                       Show memory stats
  tags                        List all tags
  dump                        Export all memories as JSON

SHORTCUTS:
  r  = remember
  q  = recall (query)
  p  = plan

EXAMPLES:
  memberberry.py r goal "Ship memberberry v1" --tags build,career --importance 9
  memberberry.py q "what am I building" --tags build
  memberberry.py p "next week priorities" --tags career,build --days 7
  memberberry.py plans --status active
        """)

    def _parse_flags(self, args: list) -> tuple[str, dict]:
        """Separate content from flags."""
        content_parts = []
        flags = {}
        i = 0
        while i < len(args):
            if args[i].startswith("--"):
                key = args[i][2:]
                if i + 1 < len(args) and not args[i + 1].startswith("--"):
                    flags[key] = args[i + 1]
                    i += 2
                else:
                    flags[key] = True
                    i += 1
            else:
                content_parts.append(args[i])
                i += 1
        return " ".join(content_parts), flags

    def _cmd_remember(self, args):
        if len(args) < 2:
            print("Usage: memberberry.py remember <type> <content> [--tags x,y] [--importance N]")
            return

        memory_type = args[0]
        content, flags = self._parse_flags(args[1:])

        if memory_type not in [e.value for e in MemoryType]:
            print(f"Invalid type: {memory_type}")
            print(f"Valid types: {', '.join(e.value for e in MemoryType)}")
            return

        tags = flags.get("tags", "").split(",") if flags.get("tags") else []
        importance = int(flags.get("importance", 5))
        context = flags.get("context", "")
        source = flags.get("source", "cli")

        memory = Memory(
            content=content,
            memory_type=memory_type,
            tags=[t.strip() for t in tags if t.strip()],
            importance=min(max(importance, 1), 10),
            context=context,
            source=source,
        )

        mid = self.store.remember(memory)
        print(f"Remembered [{memory_type}] {content}")
        print(f"  id: {mid} | importance: {importance} | tags: {', '.join(tags) or 'none'}")

    def _cmd_recall(self, args):
        content, flags = self._parse_flags(args)
        tags = flags.get("tags", "").split(",") if flags.get("tags") else None
        memory_type = flags.get("type")
        limit = int(flags.get("limit", 10))

        results = self.store.recall(
            query=content,
            tags=tags,
            memory_type=memory_type,
            limit=limit,
        )

        if not results:
            print("No memories found. Store some first!")
            return

        print(f"\n  Recalled {len(results)} memories for: '{content or 'all'}'\n")
        for m in results:
            score = m.get("_relevance_score", 0)
            tags_str = ", ".join(m.get("tags", []))
            print(f"  [{m['memory_type'][:4].upper()}] {m['content']}")
            print(f"    score: {score} | importance: {m.get('importance', '?')} | "
                  f"tags: {tags_str or 'none'} | id: {m['id']}")
            if m.get("context"):
                print(f"    context: {m['context']}")
            print()

    def _cmd_plan(self, args):
        content, flags = self._parse_flags(args)
        if not content:
            print("Usage: memberberry.py plan <focus> [--tags x,y] [--days N]")
            return

        tags = flags.get("tags", "").split(",") if flags.get("tags") else None
        days = int(flags.get("days", 14))

        plan = self.planner.generate_plan(focus=content, tags=tags, horizon_days=days)

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

    def _cmd_plans(self, args):
        _, flags = self._parse_flags(args)
        status = flags.get("status")
        tags = flags.get("tags", "").split(",") if flags.get("tags") else None

        plans = self.store.get_plans(status=status, tags=tags)
        if not plans:
            print("No plans found.")
            return

        print(f"\n  {len(plans)} plan(s):\n")
        for p in plans:
            action_count = len(p.get("actions", []))
            print(f"  [{p['status'].upper()}] {p['title']}")
            print(f"    {action_count} actions | target: {p.get('target_date', '?')[:10]} | id: {p['id']}")
            print()

    def _cmd_forget(self, args):
        if not args:
            print("Usage: memberberry.py forget <memory_id>")
            return
        mid = args[0]
        if self.store.forget(mid):
            print(f"Forgot memory {mid}")
        else:
            print(f"Memory {mid} not found")

    def _cmd_stats(self, args=None):
        s = self.store.stats()
        print(f"\n  memberberry stats")
        print(f"  Memories: {s['total_memories']}")
        for t, c in s["memories_by_type"].items():
            print(f"    {t}: {c}")
        print(f"  Plans: {s['total_plans']}")
        for st, c in s["plans_by_status"].items():
            print(f"    {st}: {c}")
        print(f"  Tags: {', '.join(s['unique_tags']) or 'none'}")
        print()

    def _cmd_tags(self, args=None):
        tags = self.store.get_all_tags()
        if tags:
            print(f"Tags: {', '.join(tags)}")
        else:
            print("No tags yet.")

    def _cmd_dump(self, args=None):
        print(json.dumps(self.store.memories, indent=2))


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":
    cli = MemberberryCLI()
    cli.run()
