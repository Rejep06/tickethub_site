#!/usr/bin/env python3
"""Read a simple generated env value without executing the env file as shell code."""
from pathlib import Path
import sys
key = sys.argv[1]
for line in (Path(__file__).resolve().parents[1] / '.env.production').read_text().splitlines():
    if line.startswith(key + '='):
        print(line.partition('=')[2].strip().strip('"').strip("'"))
        break
else:
    raise SystemExit('Missing key: ' + key)
