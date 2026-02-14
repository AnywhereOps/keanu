#!/usr/bin/env python3
"""🔍 ZERO-SUM DETECTOR (ADR-005) - us vs them, false tradeoffs"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from tools.coef_engine import run

if __name__ == "__main__":
    f = sys.argv[1] if len(sys.argv) > 1 else "-"
    run(f, detector="zero_sum", title="ZERO-SUM SCAN")
