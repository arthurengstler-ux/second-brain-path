#!/usr/bin/env python3
"""Runs the whole path on made-up data in a temporary folder. Touches nothing of yours.

    python3 -I tests/smoke_test.py        (Windows: py -3 -I tests/smoke_test.py)

Builds a fake home folder with a fake Claude Code history and a fake LinkedIn export, then runs
setup_vault -> sources scan/decide/apply -> import_linkedin (twice) -> brain.py context/docs/build/hook,
and checks the results. Exit code 0 = everything works.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PY = sys.executable
ok = True


def run(*args, stdin=None):
    r = subprocess.run([PY, "-I", *map(str, args)], capture_output=True, text=True, encoding="utf-8", input=stdin)
    if r.returncode != 0:
        print("FAILED:", " ".join(map(str, args)), "\n", r.stdout, r.stderr)
        sys.exit(1)
    return r.stdout


def check(cond, what):
    global ok
    print(("  ok    " if cond else "  FAIL  ") + what)
    ok = ok and cond


tmp = Path(tempfile.mkdtemp(prefix="sbp-smoke-"))
try:
    home, vault = tmp / "home", tmp / "home" / "Documents" / "Second-Brain"
    thesis = home / "Desktop" / "Uni" / "Thesis"
    secret = home / "Desktop" / "Private" / "Diary"
    for d in (thesis, secret):
        d.mkdir(parents=True)
    (thesis / "draft.docx").write_text("x", encoding="utf-8")
    (thesis / "BA_sources.pdf").write_text("x", encoding="utf-8")
    # fake Claude Code history: two sessions with titles and file edits, one memory file
    proj = home / ".claude" / "projects" / "-home"
    (proj / "memory").mkdir(parents=True)
    for sid, title, path, day in [("s1", "Thesis literature review", thesis / "draft.docx", "2026-11-20"),
                                  ("s2", "Diary cleanup", secret / "notes.md", "2026-11-21")]:
        lines = [{"type": "ai-title", "aiTitle": title, "sessionId": sid},
                 {"type": "assistant", "timestamp": f"{day}T10:00:00Z", "cwd": str(home),
                  "message": {"content": [{"type": "tool_use", "name": "Edit", "input": {"file_path": str(path)}}]}}]
        (proj / f"{sid}.jsonl").write_text("\n".join(json.dumps(l) for l in lines), encoding="utf-8")
    (proj / "memory" / "writing-style.md").write_text("---\nname: writing-style\ndescription: How I write\n---\nShort sentences.\n", encoding="utf-8")

    print("setup_vault")
    run(REPO / "scripts/setup_vault.py", "--vault", vault, "--owner", "Alex Sample's")
    check((vault / "Home.md").exists() and (vault / ".obsidian/plugins/brain-dashboard/main.js").exists(), "vault and Obsidian plugin created")

    print("sources.py")
    out = run(REPO / "scripts/sources.py", "scan", "--vault", vault, "--claude-dir", home / ".claude", "--home", home)
    cands = json.loads((vault / ".brain/candidates.json").read_text(encoding="utf-8"))
    idx = {c["name"]: i + 1 for i, c in enumerate(cands)}
    check("Thesis" in idx and "Diary" in idx and "writing-style" in idx, "candidates found: Thesis, Diary, memory file")
    check("Short sentences" not in out, "memory contents not printed during scan")
    run(REPO / "scripts/sources.py", "decide", "--vault", vault, f"{idx['Thesis']}=project:Bachelor thesis",
        f"{idx['Diary']}=private", f"{idx['writing-style']}=keep")
    run(REPO / "scripts/sources.py", "apply", "--vault", vault)
    note = vault / "01 Projects/Bachelor thesis/Bachelor thesis.md"
    check(note.exists() and "Thesis literature review" in note.read_text(encoding="utf-8"), "project note with session list")
    check(not any("Diary" in p.read_text(encoding="utf-8") for p in vault.rglob("*.md")), "private topic not written anywhere in the vault")
    check((vault / "03 Resources/Claude Memory/writing-style.md").exists(), "kept memory file copied")

    print("sources.py with a Claude app export")
    run(REPO / "tests/make_fake_claude_app_export.py", tmp / "claude-app.zip")
    out = run(REPO / "scripts/sources.py", "scan", "--vault", vault, "--claude-dir", home / ".claude", "--home", home,
              "--claude-export", tmp / "claude-app.zip")
    check("SECRET" not in out, "chat and document contents not printed")
    cands = json.loads((vault / ".brain/candidates.json").read_text(encoding="utf-8"))
    idx = {c["name"]: i + 1 for i, c in enumerate(cands)}
    check(cands[idx["Thesis"] - 1]["decision"] == "project", "earlier decisions kept on re-scan")
    run(REPO / "scripts/sources.py", "decide", "--vault", vault,
        f"{idx['Bachelor thesis']}=project:Bachelor thesis",
        f"{idx['Cover letter for an internship']},{idx['Internship interview prep']}=project:Internship search",
        str(idx["Doctor's appointment questions"]) + "=private")
    run(REPO / "scripts/sources.py", "apply", "--vault", vault)
    text = note.read_text(encoding="utf-8")
    check("Thesis literature review (Claude Code)" in text and "Structure of chapter 2 (Claude app)" in text,
          "Claude Code folder and app project merged into one note")
    intern = vault / "01 Projects/Internship search/Internship search.md"
    check(intern.exists() and "Cover letter" in intern.read_text(encoding="utf-8") and "interview prep" in intern.read_text(encoding="utf-8"),
          "two app chats merged into one project")
    allmd = " ".join(p.read_text(encoding="utf-8") for p in vault.rglob("*.md"))
    check("Doctor" not in allmd and "SECRET" not in allmd, "private chat and all contents kept out of the vault")
    run(REPO / "scripts/sources.py", "scan", "--vault", vault, "--claude-dir", home / ".claude", "--home", home)
    cands = json.loads((vault / ".brain/candidates.json").read_text(encoding="utf-8"))
    check(any(c["id"].startswith("app-chat:") and c["decision"] == "private" for c in cands), "app candidates survive a re-scan without the export")

    print("import_linkedin.py")
    run(REPO / "tests/make_fake_export.py", tmp / "export.zip")
    cfg = json.loads((REPO / "config/topics.example.json").read_text(encoding="utf-8"))
    cfg["exclude_people"] = ["Tom Empty"]
    (tmp / "topics.json").write_text(json.dumps(cfg), encoding="utf-8")
    args = (REPO / "scripts/import_linkedin.py", "--vault", vault, "--zip", tmp / "export.zip",
            "--config", tmp / "topics.json", "--exclude-lastname", "Sample")
    run(*args)
    second = run(*args)
    check("0 new, 0 changed" in second, "second import changes nothing (idempotent)")
    who = (vault / "05 People/Who to Ask.md").read_text(encoding="utf-8")
    check("Erika Example" in who and "Asked, no reply yet" in who, "Who to Ask with follow-up list")
    names = {p.stem for p in (vault / "05 People").rglob("*.md")}
    check("Anna Sample" not in names and "Tom Empty" not in names, "excluded people not imported")
    check((vault / "02 Areas/Career/CV.md").exists(), "CV written")

    print("classify.py (Claude sorts contacts)")
    check("Paul Probe" in who.split("## University application")[-1], "before: keyword rule puts the professor under University application")
    run(REPO / "scripts/classify.py", "prepare", "--vault", vault, "--zip", tmp / "export.zip", "--config", tmp / "topics.json")
    batch = (vault / ".brain/classify/batch-01.md").read_text(encoding="utf-8")
    check("Erika" not in batch and "Probe" not in batch, "batches contain no names")
    ids = {l.split(" | ")[2]: l.split(" | ")[0] for l in batch.splitlines() if " | " in l and l[0].isdigit()}
    # what Claude would write: the trade commissioner fits the thesis, the professor fits nothing
    (vault / ".brain/classify/batch-01.answers.json").write_text(json.dumps(
        {ids["ADVANTAGE AUSTRIA"]: {"topics": ["Thesis"], "reason": "trade commissioner, sees export rules first-hand"}}), encoding="utf-8")
    run(REPO / "scripts/classify.py", "merge", "--vault", vault, "--config", tmp / "topics.json")
    run(*args)
    who = (vault / "05 People/Who to Ask.md").read_text(encoding="utf-8")
    check("sees export rules first-hand" in who, "Claude's reason shown in Who to Ask")
    check("Paul Probe" not in who.split("## All sectors")[0], "contact Claude found unfitting is no longer suggested")

    print("brain.py")
    brain = vault / "scripts/brain.py"
    env_home = {"HOME": str(home), "USERPROFILE": str(home)}
    r = subprocess.run([PY, str(brain), "context"], capture_output=True, text=True, encoding="utf-8", env={**os.environ, **env_home})
    check(r.returncode == 0 and "Alex Sample's Second Brain" in r.stdout and "Bachelor thesis" in r.stdout, "session overview lists the project")
    r = subprocess.run([PY, str(brain), "docs"], capture_output=True, text=True, encoding="utf-8", env={**os.environ, **env_home})
    check(r.returncode == 0 and (vault / "01 Projects/Bachelor thesis/Documents Bachelor thesis.md").exists(), "documents note per project")
    for f, should in [(secret / "notes.md", False), (thesis / "draft.docx", True)]:
        act = vault / ".brain/activity.jsonl"
        before = act.read_text(encoding="utf-8") if act.exists() else ""
        hook = json.dumps({"tool_input": {"file_path": str(f)}, "session_id": "t-" + f.name, "tool_name": "Write"})
        subprocess.run([PY, str(brain), "hook"], input=hook, text=True, encoding="utf-8", env={**os.environ, **env_home})
        after = act.read_text(encoding="utf-8") if act.exists() else ""
        check((after != before) == should, f"hook {'logs' if should else 'skips'} {f.parent.name}/{f.name}")
    r = subprocess.run([PY, str(brain), "build"], capture_output=True, text=True, encoding="utf-8")
    check(r.returncode == 0 and (vault / "Brain.html").exists(), "dashboard snapshot builds")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\nALL GOOD" if ok else "\nSOMETHING FAILED")
sys.exit(0 if ok else 1)
