#!/usr/bin/env python3
"""Refresh the PR counts in the README's open source table.

Each row between <!-- oss:start --> and <!-- oss:end --> links to a GitHub repo; the
last column is rewritten with that repo's merged and open PR counts. The other
columns are written by hand. Upstream repos with merged PRs that the block does not
link yet are printed so they can be added.

Needs the gh CLI, logged in locally or given GH_TOKEN in CI.

    python3 scripts/update_readme.py [--check]
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

AUTHOR = "pardeep-singh"
README = Path(__file__).resolve().parent.parent / "README.md"
BLOCK = re.compile(r"(<!-- oss:start -->\n)(.*?)(<!-- oss:end -->)", re.S)
REPO_LINK = re.compile(r"https://github\.com/([\w.-]+/[\w.-]+)")


def upstream_pr_counts():
    """{repo: [merged, open]} for AUTHOR's PRs outside their own account.

    One paginated search (a few requests) rather than one per repo, because the
    search API allows only 30 requests a minute."""
    jq = ".items[] | {repo: .repository_url, state, merged: .pull_request.merged_at}"
    args = ["gh", "api", "-X", "GET", "search/issues", "--paginate", "--jq", jq,
            "-f", f"q=is:pr author:{AUTHOR} -user:{AUTHOR}", "-f", "per_page=100"]
    run = subprocess.run(args, capture_output=True, text=True)
    if run.returncode:
        sys.exit(f"gh search failed: {(run.stdout + run.stderr).strip()}")
    counts = {}
    for line in run.stdout.splitlines():
        pr = json.loads(line)
        c = counts.setdefault(pr["repo"].split("/repos/", 1)[1].lower(), [0, 0])
        if pr["merged"]:
            c[0] += 1
        elif pr["state"] == "open":
            c[1] += 1
    return counts


def pr_cell(merged, open_):
    parts = [f"{merged} merged"] if merged else []
    if open_:
        parts.append(f"{open_} in review")
    return " · ".join(parts) or "none yet"


def refresh(block, counts):
    rows = []
    for line in block.splitlines():
        m = REPO_LINK.search(line) if line.startswith("| [") else None
        if m:
            cells = line.rstrip().rstrip("|").split(" | ")
            cells[-1] = pr_cell(*counts.get(m.group(1).lower(), (0, 0)))
            line = " | ".join(cells) + " |"
        rows.append(line)
    return "\n".join(rows) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="exit 1 if the README is out of date, without writing")
    args = ap.parse_args()

    text = README.read_text()
    m = BLOCK.search(text)
    if not m:
        sys.exit("README.md has no <!-- oss:start --> ... <!-- oss:end --> block")
    counts = upstream_pr_counts()
    new = text[: m.start(2)] + refresh(m.group(2), counts) + text[m.end(2):]

    listed = {r.lower() for r in REPO_LINK.findall(m.group(2))}
    for repo in sorted(r for r, (merged, _) in counts.items() if merged and r not in listed):
        print(f"not in the README: {repo} has merged PRs")

    if new == text:
        print("README.md is up to date")
    elif args.check:
        sys.exit("README.md is out of date; run scripts/update_readme.py")
    else:
        README.write_text(new)
        print("README.md updated")


if __name__ == "__main__":
    main()
