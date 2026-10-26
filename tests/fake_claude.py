#!/usr/bin/python3 -I
"""Stand-in for `claude -p` used by the tests.

Records each call (argv, cwd, prompt) as a JSON file in $FAKE_CLAUDE_LOG and
answers with the verdict configured for the package in $FAKE_CLAUDE_VERDICTS,
a JSON object mapping package base -> verdict ("*" is the fallback).

Besides "safe", "caution" and "block", these special verdicts simulate
failures: "crash" (exit 1, no output), "garbage" (non-JSON output),
"api-error" (is_error: true) and "bogus" (a verdict outside the schema).
"""

import json
import os
import re
import sys
import uuid
from pathlib import Path

prompt = sys.stdin.read()
m = re.search(r"^Package base: (.+)$", prompt, re.M)
base = m.group(1) if m else "?"

log = Path(os.environ["FAKE_CLAUDE_LOG"])
log.mkdir(parents=True, exist_ok=True)
(log / f"{base}-{uuid.uuid4().hex}.json").write_text(
    json.dumps({"base": base, "argv": sys.argv[1:], "cwd": os.getcwd(), "prompt": prompt}))

verdicts = json.loads(os.environ.get("FAKE_CLAUDE_VERDICTS", "{}"))
verdict = verdicts.get(base, verdicts.get("*", "safe"))

if verdict == "crash":
    sys.exit(1)
if verdict == "garbage":
    print("this is not json")
    sys.exit(0)

out = {"type": "result", "subtype": "success", "is_error": False, "total_cost_usd": 0.0,
       "result": "", "structured_output": None}
if verdict == "api-error":
    out.update(is_error=True, subtype="error_during_execution")
else:
    findings = [] if verdict == "safe" else [
        {"severity": "high", "file": "PKGBUILD", "detail": f"fake {verdict} finding"}]
    out["structured_output"] = {"verdict": verdict, "summary": "" if verdict == "safe"
                                else f"fake {verdict} summary", "findings": findings}
print(json.dumps(out))
