#!/usr/bin/env python3
"""🔍 GRIEVANCE DETECTOR (ADR-019) - compounding negativity, the anti-Skynet tool"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from tools.coef_engine import run

if __name__ == "__main__":
    f = sys.argv[1] if len(sys.argv) > 1 else "-"
    run(f, detector="grievance", title="GRIEVANCE SCAN")
