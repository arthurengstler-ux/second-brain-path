#!/usr/bin/env python3
"""Let Claude decide which contacts fit which topic, instead of keyword rules.

    PY -I scripts/classify.py prepare --vault VAULT --zip <LinkedIn export(s)> --config VAULT/.brain/topics.json
    (Claude reads VAULT/.brain/classify/batch-*.md and writes batch-*.answers.json next to each)
    PY -I scripts/classify.py merge   --vault VAULT --config VAULT/.brain/topics.json

prepare  writes the contacts in batches of 80 lines: "id | position | organization". Names are left out on purpose:
         the decision only needs role and organization. Exclusions from topics.json are applied first.
merge    checks Claude's answers and writes VAULT/.brain/assignments.json. import_linkedin.py then uses these
         assignments (with a short reason per person) instead of the keyword rules for every contact listed there.

Python standard library only. Works on macOS, Windows and Linux.
"""
import argparse
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # our own folder, for import_linkedin helpers
from import_linkedin import DEFAULT_SECTORS, Export, clean, norm_url, safe_name  # noqa: E402

BATCH = 80
HEADER = """# Contact batch {n} of {total}

You are sorting someone's LinkedIn contacts into the topics of their second brain.
For each line decide which topics this person could **realistically** help with: an intro, an interview,
advice, an internship. Judge by role and organization, not by single keywords
(a car dealer's "mobility advisor" does not fit a topic on public transport; an ambassador fits foreign policy
even if the word "trade" is missing). Most contacts fit no topic. That is fine, leave them out.

## Topics
{topics}

## Your answer
Write `{answers}` in this folder, a JSON object with one entry per contact that fits at least one topic:

```json
{{"17": {{"topics": ["Thesis"], "reason": "trade commissioner, knows US tariffs first-hand"}}}}
```

- `topics`: only names from the list above, spelled exactly
- `reason`: at most 12 words, factual, no names

## Contacts (id | position | organization)
"""


def load_cfg(p):
    return json.loads(Path(os.path.expanduser(p)).read_text(encoding="utf-8")) if p else {}


def cmd_prepare(a, vault, out):
    cfg = load_cfg(a.config)
    topics = cfg.get("topics", [])
    if not topics:
        sys.exit("topics.json has no topics yet: define them first (PATH.md step 5)")
    sectors = cfg.get("sectors") or DEFAULT_SECTORS
    ex_last = {x.lower() for x in cfg.get("exclude_lastnames", [])}
    ex_people = {x.lower() for x in cfg.get("exclude_people", [])}
    ex_orgs = [x for x in cfg.get("exclude_organizations", []) if x]
    ex_sectors = set(cfg.get("exclude_sectors", []))
    rows = []
    for r in Export([os.path.expanduser(z) for z in a.zip]).rows("Connections.csv"):
        first, last = clean(r.get("First Name")), clean(r.get("Last Name"))
        name = safe_name(first, last)
        org, pos = clean(r.get("Company")), clean(r.get("Position"))
        if not name or not r.get("URL") or (not org and not pos) or last.lower() in ex_last or name.lower() in ex_people:
            continue
        sector = next(n for n, rx in sectors if re.search(rx, f"{org} | {pos}", re.I))
        if sector in ex_sectors or any(re.search(rx, org, re.I) for rx in ex_orgs):
            continue
        rows.append(dict(url=r["URL"], pos=pos.replace("|", "/"), org=org.replace("|", "/")))
    out.mkdir(parents=True, exist_ok=True)
    tlist = "\n".join(f"- **{t['name']}**: {t.get('description') or t.get('link') or ''}".rstrip(": ") for t in topics)
    batches = [rows[i:i + BATCH] for i in range(0, len(rows), BATCH)]
    index = {}
    for n, b in enumerate(batches, 1):
        lines = []
        for r in b:
            i = str(len(index) + 1)
            index[i] = r["url"]
            lines.append(f"{i} | {r['pos'] or '-'} | {r['org'] or '-'}")
        f = out / f"batch-{n:02d}.md"
        with open(f, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(HEADER.format(n=n, total=len(batches), topics=tlist, answers=f"batch-{n:02d}.answers.json") + "\n".join(lines) + "\n")
    (out / "index.json").write_text(json.dumps(index, indent=0), encoding="utf-8")
    print(f"{len(rows)} contacts in {len(batches)} batches: {out}")
    print("Next: read each batch-NN.md, write batch-NN.answers.json, then run: classify.py merge")


def cmd_merge(a, vault, out):
    cfg = load_cfg(a.config)
    names = {t["name"] for t in cfg.get("topics", [])}
    index = json.loads((out / "index.json").read_text(encoding="utf-8"))
    result, problems, missing = {}, [], []
    for b in sorted(out.glob("batch-*.md")):
        ans = b.with_name(b.stem + ".answers.json")
        if not ans.exists():
            missing.append(ans.name)
            continue
        try:
            data = json.loads(ans.read_text(encoding="utf-8"))
        except ValueError as e:
            problems.append(f"{ans.name}: not valid JSON ({e})")
            continue
        # every contact Claude has seen counts as decided, even with no topic (no fallback to keyword rules)
        for line in b.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^(\d+) \| ", line)
            if m and m.group(1) in index:
                result.setdefault(norm_url(index[m.group(1)]), {"topics": [], "reason": ""})
        for i, v in data.items():
            if str(i) not in index:
                problems.append(f"{ans.name}: unknown id {i}")
                continue
            tps = [t for t in v.get("topics", []) if t in names]
            bad = [t for t in v.get("topics", []) if t not in names]
            if bad:
                problems.append(f"{ans.name}: id {i} has unknown topics {bad}")
            result[norm_url(index[str(i)])] = {"topics": tps, "reason": str(v.get("reason", ""))[:120] if tps else ""}
    if missing:
        print("missing answers:", ", ".join(missing))
    for p in problems:
        print("problem:", p)
    (vault / ".brain" / "assignments.json").write_text(json.dumps(result, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    per = {t: sum(1 for v in result.values() if t in v["topics"]) for t in sorted(names)}
    hits = sum(1 for v in result.values() if v["topics"])
    print(f"{len(result)} of {len(index)} contacts sorted by Claude, {hits} fit a topic: " + ", ".join(f"{k} {v}" for k, v in per.items()))
    print("Next: run import_linkedin.py again. It now uses VAULT/.brain/assignments.json.")
    sys.exit(1 if problems or missing else 0)


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["prepare", "merge"])
    ap.add_argument("--vault", required=True)
    ap.add_argument("--zip", nargs="+", help="LinkedIn export(s), ZIP or folder (prepare only)")
    ap.add_argument("--config", required=True)
    a = ap.parse_args()
    vault = Path(os.path.expandvars(os.path.expanduser(a.vault))).resolve()
    out = vault / ".brain" / "classify"
    if a.command == "prepare":
        if not a.zip:
            sys.exit("prepare needs --zip")
        cmd_prepare(a, vault, out)
    else:
        cmd_merge(a, vault, out)


if __name__ == "__main__":
    main()
