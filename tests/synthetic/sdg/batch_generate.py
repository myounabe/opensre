#!/usr/bin/env python3
"""Generate multiple scenarios in batch."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# Scenarios to generate (failure_mode, instance_class, difficulty)
BATCH = [
    ("cpu_saturation", "db.r6g.2xlarge", 1),
    ("replication_lag", "db.r6g.2xlarge", 2),
    ("connection_exhaustion", "db.r6g.xlarge", 1),
    ("storage_full", "db.r6g.2xlarge", 3),
    ("failover", "db.r6g.4xlarge", 2),
]


def main() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    script = repo_root / "tests" / "synthetic" / "sdg" / "run_sdg.py"

    print(f"\n🚀 Batch SDG Generation ({len(BATCH)} scenarios)\n")

    for i, (failure_mode, instance_class, difficulty) in enumerate(BATCH, 1):
        print(f"[{i}/{len(BATCH)}] {failure_mode} on {instance_class} (difficulty {difficulty})")
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "--failure_mode",
                failure_mode,
                "--instance_class",
                instance_class,
                "--difficulty",
                str(difficulty),
            ],
            cwd=repo_root,
            capture_output=False,
        )
        if result.returncode != 0:
            print(f"❌ Failed: {failure_mode}")
            sys.exit(1)

    print(f"\n✅ All {len(BATCH)} scenarios generated!")


if __name__ == "__main__":
    main()
