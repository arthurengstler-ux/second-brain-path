#!/usr/bin/env python3
"""Create a new second-brain vault from vault-template/.

    python3 -I scripts/setup_vault.py --vault ~/Documents/Second-Brain --owner "Jane Doe's"
    (Windows: py -3 -I scripts/setup_vault.py --vault "%USERPROFILE%\\Documents\\Second-Brain" --owner "Jane Doe's")

Existing files are never overwritten. Afterwards: git init + first commit.
Python standard library only. Works on macOS, Windows and Linux.
"""
import argparse, datetime as dt, json, os, shutil, subprocess
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--vault", required=True)
ap.add_argument("--owner", default="My", help="shown in the session overview, e.g. \"Jane Doe's\"")
a = ap.parse_args()

src = Path(__file__).resolve().parent.parent / "vault-template"
dst = Path(os.path.expandvars(os.path.expanduser(a.vault))).resolve()
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
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(text)
    else:
        shutil.copy2(f, out)
    new += 1
print(f"Vault: {dst}  ({new} files created, {kept} existing files left untouched)")
if not (dst / ".git").exists():
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=dst, check=True)
    subprocess.run(["git", "add", "-A"], cwd=dst, check=True)
    subprocess.run(["git", "commit", "-qm", "Second brain created"], cwd=dst)
    print("git repository created with a first commit.")
