#!/usr/bin/env python3
"""🔍 GENERALIZATION DETECTOR (ADR-017) - 'humans always', 'AI never'"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from tools.coef_engine import run

if __name__ == "__main__":
    f = sys.argv[1] if len(sys.argv) > 1 else "-"
    run(f, detector="generalization", title="GENERALIZATION SCAN")
