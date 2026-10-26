#!/usr/bin/python3 -I
"""Run the eval set against the real reviewer (and the real claude).

Each case in evals/cases/<name>/ has before/ and after/ file trees and a
case.json. For every case this builds a git repo named after the package,
commits before/ and marks it approved (CLAUDE_REVIEWED), then commits after/
as the update to review, exactly like yay's clone in ~/.cache/yay/<pkg>.
All cases are then reviewed in one aur-review --no-mark --json run.

Expected outcomes in case.json:
  safe   routine update: must come back "safe"
  flag   suspicious: must come back "caution" or "block"
  block  malicious: must come back "block" ("caution" counts as partial)

Usage:
  evals/run.py [CASE...]          run all cases, or only the named ones
Environment variables of aur-review (AUR_REVIEW_MODEL, AUR_REVIEW_WORKERS, ...) apply.
Costs real money: roughly $0.05-0.10 per case.
"""

import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = HERE / "cases"
RESULTS = HERE / "results"
AUR_REVIEW = HERE.parent / "aur-review"


def git(d, *args, author=None):
    pre = []
    if author:
        name, email = author[:-1].split(" <")
        pre = ["-c", f"user.name={name}", "-c", f"user.email={email}"]
    subprocess.run(["git", "-C", str(d), *pre, *args], check=True, capture_output=True)


def build_repo(case_dir, work):
    meta = json.loads((case_dir / "case.json").read_text())
    repo = work / case_dir.name / meta["pkgbase"]
    repo.mkdir(parents=True)
    git(repo, "init", "-q", "-b", "master")
    shutil.copytree(case_dir / "before", repo, dirs_exist_ok=True)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "initial import", author=meta["author"])
    git(repo, "update-ref", "CLAUDE_REVIEWED", "HEAD")
    for f in repo.iterdir():
        if f.name != ".git":
            shutil.rmtree(f) if f.is_dir() else f.unlink()
    shutil.copytree(case_dir / "after", repo, dirs_exist_ok=True)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", meta["commit_message"], author=meta["author"])
    return meta, repo / "PKGBUILD"


def score(expect, verdict):
    if expect == "safe":
        return "pass" if verdict == "safe" else "FAIL"
    if expect == "flag":
        return "pass" if verdict in ("caution", "block") else "FAIL"
    return {"block": "pass", "caution": "partial"}.get(verdict, "FAIL")


def main(argv):
    names = argv or sorted(p.name for p in CASES.iterdir() if p.is_dir())
    work = Path(tempfile.mkdtemp(prefix="aur-review-eval-"))
    try:
        metas, pkgbuilds = [], []
        for n in names:
            meta, pkgbuild = build_repo(CASES / n, work)
            metas.append(meta | {"case": n})
            pkgbuilds.append(str(pkgbuild))

        env = os.environ | {"AUR_REVIEW_AUR_RPC": "",  # fictional packages: no AUR lookup
                            "XDG_STATE_HOME": str(work / "state")}
        print(f"Reviewing {len(names)} cases...", file=sys.stderr, flush=True)
        r = subprocess.run([str(AUR_REVIEW), "--no-mark", "--json", *pkgbuilds], env=env,
                           capture_output=True, text=True)
        results = json.loads(r.stdout)
    finally:
        shutil.rmtree(work, ignore_errors=True)

    rows = []
    for meta, res in zip(metas, results):
        rows.append({"case": meta["case"], "expect": meta["expect"], "verdict": res.get("verdict"),
                     "result": score(meta["expect"], res.get("verdict")), "cost": res.get("cost") or 0,
                     "summary": res.get("summary"), "findings": res.get("findings"),
                     "error": res.get("error")})

    w = max(len(r["case"]) for r in rows)
    for r in sorted(rows, key=lambda r: ({"safe": 0, "flag": 1, "block": 2}[r["expect"]], r["case"])):
        print(f"{r['result']:8} {r['case']:{w}}  expect {r['expect']:5}  got {r['verdict']}"
              + ("  (review error)" if r["error"] else ""))

    def count(expect, ok):
        sel = [r for r in rows if r["expect"] == expect]
        return f"{sum(ok(r) for r in sel)}/{len(sel)}" if sel else "-"

    print()
    print(f"benign passed as safe:      {count('safe', lambda r: r['verdict'] == 'safe')}")
    print(f"suspicious flagged:         {count('flag', lambda r: r['verdict'] != 'safe')}")
    print(f"malicious blocked:          {count('block', lambda r: r['verdict'] == 'block')}"
          f"  (not marked safe: {count('block', lambda r: r['verdict'] != 'safe')})")
    print(f"total cost:                 ${sum(r['cost'] for r in rows):.2f}")

    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"{datetime.datetime.now():%Y%m%d-%H%M%S}.json"
    out.write_text(json.dumps({"model": os.environ.get("AUR_REVIEW_MODEL"), "rows": rows}, indent=2))
    print(f"details: {out}")
    return 0 if all(r["result"] == "pass" for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
