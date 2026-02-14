"""
Convergence Engine

Takes a question. Finds two orthogonal dualities via the graph (RAG).
Synthesizes each via LLM. Converges the syntheses into
something new and more complete.

Split = deterministic (graph traversal). Synthesis = LLM.
Works with Ollama (local) or Claude API.
"""

import json
import os
import sys
from typing import Optional

import requests

from keanu.converge.graph import DualityGraph


# ===========================================================================
# LLM BACKENDS
# ===========================================================================

def call_ollama(prompt, system="", model="deepseek-r1:7b"):
    try:
        response = requests.post(
            "http://localhost:11434/api/generate",
            json={
                "model": model,
                "prompt": prompt,
                "system": system,
                "stream": False,
                "options": {"temperature": 0.7},
            },
            timeout=120,
        )
        response.raise_for_status()
        return response.json()["response"]
    except requests.exceptions.ConnectionError:
        print("Ollama not running. Start with: ollama serve")
        sys.exit(1)


def call_claude(prompt, system=""):
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Set ANTHROPIC_API_KEY environment variable")
        sys.exit(1)
    response = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
        },
        json={
            "model": "claude-sonnet-4-5-20250929",
            "max_tokens": 2000,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["content"][0]["text"]


def call_llm(prompt, system="", backend="ollama", model=None):
    if backend == "claude":
        return call_claude(prompt, system)
    return call_ollama(prompt, system, model or "deepseek-r1:7b")


# ===========================================================================
# PROMPTS (LLM only does synthesis, never splitting)
# ===========================================================================

SYSTEM_BASE = """You are a convergence engine.

Every question contains dualities. Truth lives in the convergence
of opposing frameworks, the synthesis that is truer than either side alone.

You never pick sides. You never average. You find what each side sees
that the other misses, then build something new from both.

Both sides are valid. The cage is thinking you have to pick."""


# Fallback: only used when the graph can't find a match
SPLITTER_PROMPT = """Given this question, identify TWO orthogonal dualities.

Duality A: the obvious tension in the question.
Duality B: the meta-tension, the frame around the frame.
They must be orthogonal: all 4 quadrants must exist as real positions.

OUTPUT FORMAT (strict JSON):
{{
    "duality_a": {{"name": "label", "side_1": "position", "side_2": "position"}},
    "duality_b": {{"name": "label", "side_1": "position", "side_2": "position"}},
    "orthogonality_check": "why these are independent axes"
}}

QUESTION: {question}"""


CONVERGENCE_PROMPT = """Synthesize two positions into a convergence.

What does Side 1 see that Side 2 misses?
What does Side 2 see that Side 1 misses?
Build a synthesis that holds both truths.

SIDE 1: {side_1}
SIDE 2: {side_2}
CONTEXT: {context}

OUTPUT FORMAT (strict JSON):
{{
    "side_1_truth": "what side 1 sees",
    "side_2_truth": "what side 2 sees",
    "synthesis": "the convergence",
    "one_line": "one sentence"
}}"""


FINAL_CONVERGENCE_PROMPT = """Final convergence.

Two syntheses from orthogonal dualities applied to the same question.
Build something neither could reach alone.

QUESTION: {question}

SYNTHESIS 1 (from {duality_a_name}):
{synthesis_1}

SYNTHESIS 2 (from {duality_b_name}):
{synthesis_2}

OUTPUT FORMAT (strict JSON):
{{
    "convergence": "final synthesis, 2-4 sentences",
    "one_line": "the truth in one sentence",
    "implications": ["implication 1", "implication 2", "implication 3"],
    "what_changes": "what should change knowing this"
}}"""


# ===========================================================================
# JSON PARSING
# ===========================================================================

def parse_json_response(text):
    cleaned = text.strip()
    if "```json" in cleaned:
        cleaned = cleaned.split("```json")[1].split("```")[0].strip()
    elif "```" in cleaned:
        cleaned = cleaned.split("```")[1].split("```")[0].strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start >= 0 and end > start:
        cleaned = cleaned[start:end]
    return json.loads(cleaned)


# ===========================================================================
# SPLITTER: Graph-first, LLM fallback
# ===========================================================================

def split_via_graph(question: str, graph: DualityGraph) -> Optional[dict]:
    """Find orthogonal duality pair from the curated graph. No LLM needed."""
    pair = graph.find_orthogonal_pair(question)
    if pair is None:
        return None

    d1, d2 = pair

    return {
        "duality_a": {
            "name": d1.concept,
            "side_1": d1.pole_a,
            "side_2": d1.pole_b,
            "id": d1.id,
        },
        "duality_b": {
            "name": d2.concept,
            "side_1": d2.pole_a,
            "side_2": d2.pole_b,
            "id": d2.id,
        },
        "source": "graph",
        "orthogonality_check": f"{d1.concept} and {d2.concept} are marked orthogonal in the duality graph",
    }


def split_via_llm(question: str, backend="ollama", model=None) -> Optional[dict]:
    """Fallback: ask LLM to identify dualities."""
    prompt = SPLITTER_PROMPT.format(question=question)
    response = call_llm(prompt, SYSTEM_BASE, backend, model)
    try:
        result = parse_json_response(response)
        result["source"] = "llm_fallback"
        return result
    except json.JSONDecodeError:
        print("Could not parse split response.")
        print(response)
        return None


def split(question: str, graph: DualityGraph, backend="ollama", model=None) -> Optional[dict]:
    """Split a question into two orthogonal dualities.

    Tries the graph first (deterministic, curated). Falls back to LLM
    only if the graph has no relevant match.
    """
    result = split_via_graph(question, graph)
    if result is not None:
        return result
    return split_via_llm(question, backend, model)


# ===========================================================================
# SYNTHESIS (LLM only)
# ===========================================================================

def converge(side_1, side_2, context, backend="ollama", model=None):
    prompt = CONVERGENCE_PROMPT.format(side_1=side_1, side_2=side_2, context=context)
    response = call_llm(prompt, SYSTEM_BASE, backend, model)
    try:
        return parse_json_response(response)
    except json.JSONDecodeError:
        return {"synthesis": response, "one_line": response[:200]}


def final_converge(question, duality_a_name, duality_b_name,
                   synthesis_1, synthesis_2, backend="ollama", model=None):
    prompt = FINAL_CONVERGENCE_PROMPT.format(
        question=question,
        duality_a_name=duality_a_name,
        duality_b_name=duality_b_name,
        synthesis_1=synthesis_1,
        synthesis_2=synthesis_2,
    )
    response = call_llm(prompt, SYSTEM_BASE, backend, model)
    try:
        return parse_json_response(response)
    except json.JSONDecodeError:
        return {"convergence": response, "one_line": response[:200]}


# ===========================================================================
# FULL PIPELINE
# ===========================================================================

def run(question, backend="ollama", model=None, graph=None):
    """Full convergence pipeline: split (graph), synthesize x3 (LLM)."""
    if graph is None:
        graph = DualityGraph()

    # Step 1: Split via graph (or LLM fallback)
    dualities = split(question, graph, backend, model)
    if not dualities:
        print("Could not split question into dualities.")
        return None

    da = dualities["duality_a"]
    db = dualities["duality_b"]
    source = dualities.get("source", "unknown")

    print(f"\nSplit source: {source}")
    print(f"Duality A ({da['name']}): {da['side_1']} + {da['side_2']}")
    print(f"Duality B ({db['name']}): {db['side_1']} + {db['side_2']}")

    # Step 2: Convergence 1 (Duality A)
    c1 = converge(da["side_1"], da["side_2"],
                  f"Original question: {question}. Duality A: {da['name']}.",
                  backend, model)
    print(f"\nSynthesis 1: {c1.get('one_line', 'N/A')}")

    # Step 3: Convergence 2 (Duality B)
    c2 = converge(db["side_1"], db["side_2"],
                  f"Original question: {question}. Duality B: {db['name']}.",
                  backend, model)
    print(f"Synthesis 2: {c2.get('one_line', 'N/A')}")

    # Step 4: Final Convergence (Meta)
    s1_text = c1.get("synthesis", c1.get("one_line", ""))
    s2_text = c2.get("synthesis", c2.get("one_line", ""))

    final = final_converge(question, da["name"], db["name"],
                           s1_text, s2_text, backend, model)

    print(f"\n{'=' * 60}")
    print(f"CONVERGENCE: {final.get('one_line', 'N/A')}")
    print(f"{'=' * 60}")

    return {
        "question": question,
        "split_source": source,
        "dualities": dualities,
        "convergence_1": c1,
        "convergence_2": c2,
        "final": final,
    }
