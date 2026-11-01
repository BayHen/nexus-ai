"""Check initial line coverage targets for security-critical backend modules."""

from __future__ import annotations

import json
import sys
from pathlib import Path

TARGETS = {
    "src/nexus/modules/auth/": 80.0,
    "src/nexus/modules/organizations/": 80.0,
    "src/nexus/modules/orders/": 75.0,
    "src/nexus/modules/payments/": 75.0,
    "src/nexus/modules/knowledge/": 70.0,
    "src/nexus/modules/business_agent/": 70.0,
}


def main() -> int:
    report = json.loads(Path("coverage.json").read_text(encoding="utf-8"))
    files: dict[str, dict[str, object]] = report["files"]
    failed = False
    for prefix, target in TARGETS.items():
        statements = covered = 0
        for filename, details in files.items():
            normalized = filename.replace("\\", "/")
            if normalized.startswith(prefix):
                summary = details["summary"]
                statements += int(summary["num_statements"])
                covered += int(summary["covered_lines"])
        percentage = 100.0 if statements == 0 else covered * 100 / statements
        status = "PASS" if percentage >= target else "FAIL"
        print(f"{status} {prefix}: {percentage:.2f}% (target {target:.0f}%)")
        failed |= percentage < target
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
