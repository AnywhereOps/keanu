"""oracle.py - the single throat. ask a question, a legend answers.

the oracle is where all voices pass through.
when the fire moves to a new body, this is the one file that changes.

practically: this wraps all LLM API calls (anthropic, ollama, etc).
every part of the system that needs to talk to an AI imports call_oracle.
swap the legend config, swap the model. nothing else moves.
"""

import json
import os
import sys

import requests

from keanu.legends import load_legend
from keanu.log import debug


def call_oracle(prompt, system="", legend="creator", model=None):
    """ask the oracle. loads the legend, reaches them, returns what they said.

    The main entry point for talking to any AI in the system.
    Takes a prompt (what you want to ask) and an optional system message
    (context/instructions for the AI). The legend parameter picks which
    AI answers: "creator" for Claude/DeepSeek, or pass a Legend object
    directly. The model parameter overrides the legend's default model.

    Returns the AI's response as a string. Raises ConnectionError if
    nobody's home.

    in the world: the oracle is the single throat. all fire passes through here.
    """
    leg = load_legend(legend) if isinstance(legend, str) else legend
    use_model = model or leg.model

    if leg.reach == "cloud":
        result = _reach_cloud(prompt, system, leg, use_model)
    elif leg.reach == "local":
        result = _reach_local(prompt, system, leg, use_model)
    else:
        raise ConnectionError(f"don't know how to reach legend '{leg.name}' (reach={leg.reach})")

    if result is None:
        raise ConnectionError(f"no response from {leg.name}")

    debug("oracle", f"[{leg.name}/{use_model}] prompt ({len(prompt)} chars): {prompt[:150]}")
    debug("oracle", f"[{leg.name}/{use_model}] response ({len(result)} chars): {result[:300]}")

    return result


def interpret(text):
    """read what the oracle said back. parse JSON from the response.

    LLMs often return JSON wrapped in markdown code fences (```json ... ```)
    or with extra explanation text before and after the actual JSON.
    This function strips all of that away. It looks for the first { and
    last } in the response, pulls out everything between them, and
    parses it into a Python dictionary. If the JSON is malformed, it
    raises json.JSONDecodeError.

    in the world: the oracle speaks in riddles. interpret finds the meaning.
    """
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


def _reach_cloud(prompt, system, legend, model):
    """Sends a prompt to a cloud-hosted AI (like Anthropic's API).
    Reads the API key from ANTHROPIC_API_KEY environment variable.
    Uses the legend's endpoint URL and the specified model.
    Returns the response text, or None if the key isn't set.

    in the world: reaching fire that lives on someone else's iron.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("  Set ANTHROPIC_API_KEY environment variable", file=sys.stderr)
        return None
    response = requests.post(
        legend.endpoint,
        headers={
            "x-api-key": api_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
        },
        json={
            "model": model,
            "max_tokens": 2000,
            "system": system,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()["content"][0]["text"]


def _reach_local(prompt, system, legend, model):
    """Sends a prompt to a locally running AI (like Ollama).
    Hits the legend's endpoint URL, or localhost:11434 by default.
    Returns the response text, or None if the local server isn't running.

    in the world: reaching fire that burns on your own machine.
    """
    endpoint = legend.endpoint or "http://localhost:11434/api/generate"
    try:
        response = requests.post(
            endpoint,
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
        print(f"  can't reach local legend at {endpoint}", file=sys.stderr)
        return None
