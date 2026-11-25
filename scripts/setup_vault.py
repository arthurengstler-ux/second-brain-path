#!/usr/bin/env python3
"""Legt einen neuen Second-Brain-Vault aus vault-template/ an.

    python3 -I scripts/setup_vault.py --vault ~/Documents/Second-Brain --owner "Max Muster"

Bestehende Dateien werden nie überschrieben. Danach: git init + erster Commit.
"""
import argparse, datetime as dt, json, os, shutil, subprocess, sys
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--vault", required=True)
ap.add_argument("--owner", default="Mein", help="erscheint im Sitzungsüberblick, z. B. 'Max Musters'")
a = ap.parse_args()

src = Path(__file__).resolve().parent.parent / "vault-template"
dst = Path(os.path.expanduser(a.vault)).resolve()
today = dt.date.today().isoformat()
new = kept = 0
for f in sorted(src.rglob("*")):
    if f.is_dir():
        continue
    rel = f.relative_to(src)
    out = dst / rel
    if out.exists():
        kept += 1
        continue
    out.parent.mkdir(parents=True, exist_ok=True)
    if f.suffix in (".md", ".json") and rel.parts[0] != "99 Templates":
        text = f.read_text(encoding="utf-8").replace("{{date}}", today)
        if rel.name == "projects.json":
            cfg = json.loads(text); cfg["owner"] = a.owner; text = json.dumps(cfg, indent=2, ensure_ascii=False) + "\n"
        out.write_text(text, encoding="utf-8")
    else:
        shutil.copy2(f, out)
    new += 1
print(f"Vault: {dst}  ({new} Dateien angelegt, {kept} bestehende unverändert gelassen)")
if not (dst / ".git").exists():
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=dst, check=True)
    subprocess.run(["git", "add", "-A"], cwd=dst, check=True)
    subprocess.run(["git", "commit", "-qm", "Second Brain angelegt"], cwd=dst)
    print("git-Repo angelegt und erster Commit gemacht.")
