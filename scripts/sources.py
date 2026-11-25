#!/usr/bin/env python3
"""Find projects and topics in what you already did with Claude Code, then let you choose what goes in.

    PY -I scripts/sources.py scan   --vault VAULT [--claude-dir ~/.claude] [--home ~] [--claude-export data-....zip]
    PY -I scripts/sources.py decide --vault VAULT 1=project 2=area 3=private 4=drop 5=project:"New name" 6-9,12=project:"New name"
    PY -I scripts/sources.py apply  --vault VAULT

scan    reads Claude Code's local history (~/.claude/projects/*/*.jsonl) and lists candidates:
        folders and git repos Claude worked in, session titles and dates, memory files, CLAUDE.md.
        Only metadata is read: titles, dates, file paths. Conversation contents are never read.
        --claude-export adds the Claude app / claude.ai data export (Settings > Privacy > Export data,
        a ZIP sent by email): app projects and chat titles with dates. Chat contents are never read.
        Results go to VAULT/.brain/candidates.json. Earlier decisions are kept on re-scan.
decide  stores your choice per candidate number:
          project[:Name]  -> note in 01 Projects
          area[:Name]     -> note in 02 Areas
          keep            -> (memory / instructions) copy into 03 Resources/Claude Memory
          private         -> never written to the vault; paths are excluded from logging and doc scans
          drop            -> ignore
        Several numbers with the same name are merged into one note: 6-9,12=project:"Thesis"
apply   writes the chosen notes and rules. Never deletes anything. Safe to run again.

Python standard library only. Works on macOS, Windows and Linux.
"""
import argparse
import collections
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path

START, END = "<!-- claude-history:start -->", "<!-- claude-history:end -->"
TODAY = dt.date.today()
CONTAINERS = {"desktop", "documents", "downloads", "dokumente", "schreibtisch", "onedrive", "icloud drive"}
SKIP_PARTS = {"library", "appdata", ".claude", ".cache", "node_modules", ".git", "tmp", "temp"}
PATH_RE = re.compile(r"(?:~|/Users/[^/\s'\"]+|/home/[^/\s'\"]+|[A-Za-z]:\\\\Users\\\\[^\\\\\s'\"]+)[^\s'\"|;&<>]*")


def utf8_stdout():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


def posix(p):
    return str(p).replace("\\", "/")


# ---------------------------------------------------------------- scan helpers
def git_root(p, cache={}):
    d = p if p.is_dir() else p.parent
    key = str(d)
    if key in cache:
        return cache[key]
    root = None
    for cand in [d, *d.parents]:
        if (cand / ".git").exists():
            root = cand
            break
        if cand == cand.parent:
            break
    cache[key] = root
    return root


def group_for(path, home, vault):
    """Map a touched file/dir to a candidate folder, or None if it should be ignored."""
    try:
        p = Path(path).expanduser()
        try:
            p = p.resolve()  # /var -> /private/var on macOS, short names on Windows
        except OSError:
            pass
        rel = p.relative_to(home)
    except (ValueError, RuntimeError):
        return None
    parts = [x for x in rel.parts]
    if not parts or any(x.lower() in SKIP_PARTS or x.startswith(".") for x in parts):
        return None
    try:
        p.relative_to(vault)
        return None  # the vault itself
    except ValueError:
        pass
    root = git_root(p) if p.exists() else None
    if root and root != home:
        try:
            root.relative_to(home)
            return root
        except ValueError:
            pass
    if parts[0].lower() in CONTAINERS:
        # Desktop/School/Thesis/file.docx -> Desktop/School/Thesis ; Desktop/file.docx -> None
        depth = 3 if len(parts) > 3 else len(parts) - 1
        return home.joinpath(*parts[:depth]) if depth >= 2 else None
    return home / parts[0] if len(parts) > 1 else None


def read_session(f, home):
    """Return metadata of one Claude Code session file: title, dates, paths. No message text."""
    title, stamps, paths, cwd = None, [], collections.Counter(), None
    with open(f, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                d = json.loads(line)
            except ValueError:
                continue
            if d.get("timestamp"):
                stamps.append(d["timestamp"][:10])
            if d.get("cwd") and not cwd:
                cwd = d["cwd"]
            if d.get("type") == "ai-title" and isinstance(d.get("aiTitle"), str):
                title = d["aiTitle"]
            m = d.get("message")
            if not (isinstance(m, dict) and isinstance(m.get("content"), list)):
                continue
            for c in m["content"]:
                if not (isinstance(c, dict) and c.get("type") == "tool_use" and isinstance(c.get("input"), dict)):
                    continue
                inp = c["input"]
                for k in ("file_path", "notebook_path", "path"):
                    if isinstance(inp.get(k), str):
                        paths[inp[k]] += 3   # edits/reads weigh more than mentions
                if isinstance(inp.get("command"), str):
                    for m2 in PATH_RE.findall(inp["command"]):
                        paths[m2.replace("\\\\", "\\").rstrip(".,)")] += 1
    return dict(id=Path(f).stem, title=title, first=min(stamps) if stamps else "", last=max(stamps) if stamps else "",
                paths=paths, cwd=cwd)


def read_claude_export(path):
    """Claude app / claude.ai export (ZIP or folder): returns (projects, conversations). Metadata only."""
    files = {}
    if os.path.isdir(path):
        for f in Path(path).rglob("*.json"):
            files[f.name.lower()] = f.read_bytes
    else:
        import zipfile
        z = zipfile.ZipFile(path)
        for n in z.namelist():
            if n.lower().endswith(".json"):
                files[n.split("/")[-1].lower()] = (lambda n=n: z.read(n))
    load = lambda name: json.loads(files[name]().decode("utf-8")) if name in files else []
    projects, convs = [], []
    for p in load("projects.json") or []:
        if isinstance(p, dict) and p.get("uuid"):
            projects.append(dict(uuid=p["uuid"], name=p.get("name") or "(untitled project)",
                                 description=(p.get("description") or "").strip(), docs=len(p.get("docs") or []),
                                 created=(p.get("created_at") or "")[:10], updated=(p.get("updated_at") or "")[:10]))
    for c in load("conversations.json") or []:
        if not isinstance(c, dict) or not c.get("uuid"):
            continue
        pr = c.get("project")
        proj = c.get("project_uuid") or (pr.get("uuid") if isinstance(pr, dict) else None)
        convs.append(dict(uuid=c["uuid"], title=(c.get("name") or "").strip() or "(untitled chat)",
                          first=(c.get("created_at") or "")[:10], last=(c.get("updated_at") or c.get("created_at") or "")[:10],
                          messages=len(c.get("chat_messages") or []), project=proj))
    return projects, convs


def frontmatter(text):
    m = re.match(r"^---\n(.*?)\n---\n?", text, re.S)
    meta = {}
    if m:
        for l in m.group(1).splitlines():
            if ":" in l:
                k, v = l.split(":", 1)
                meta[k.strip()] = v.strip().strip('"')
    return meta, text[m.end():] if m else text


# ---------------------------------------------------------------- commands
def cmd_scan(a, vault, cfile):
    home = Path(os.path.expanduser(a.home)).resolve()
    cdir = Path(os.path.expanduser(a.claude_dir))
    old = {c["id"]: c for c in json.loads(cfile.read_text(encoding="utf-8"))} if cfile.exists() else {}
    groups = collections.defaultdict(lambda: dict(sessions=[], weight=0))
    loose = []
    for f in sorted(cdir.glob("projects/*/*.jsonl")):
        s = read_session(f, home)
        if not s["first"]:
            continue
        score = collections.Counter()
        for p, w in s["paths"].items():
            g = group_for(p, home, vault)
            if g:
                score[g] += w
        if s["cwd"]:
            g = group_for(s["cwd"] + "/x", home, vault)
            if g:
                score[g] += 2
        sess = dict(id=s["id"], title=s["title"] or "(untitled)", first=s["first"], last=s["last"], src="code")
        if score:
            top = score.most_common(1)[0][0]
            groups[top]["sessions"].append(sess)
            groups[top]["weight"] += score[top]
            for g, w in score.items():   # secondary folders still become candidates
                if g != top and w >= 3:
                    groups[g]["weight"] += w
        else:
            loose.append(sess)

    cands = []
    for g, info in sorted(groups.items(), key=lambda x: -x[1]["weight"]):
        if not g.is_dir() or (not info["sessions"] and info["weight"] < 6):
            continue  # deleted folders and passing mentions
        ses = sorted(info["sessions"], key=lambda s: s["first"])
        cands.append(dict(id="folder:" + posix(g.relative_to(home)), kind="git repo" if (g / ".git").exists() else "folder",
                          name=g.name, path="~/" + posix(g.relative_to(home)), sessions=ses,
                          first=ses[0]["first"] if ses else "", last=ses[-1]["last"] if ses else "", weight=info["weight"]))
    for s in loose:
        cands.append(dict(id="session:" + s["id"], kind="session", name=s["title"], path="", sessions=[s],
                          first=s["first"], last=s["last"], weight=0))
    for f in sorted(cdir.glob("projects/*/memory/*.md")):
        if f.name == "MEMORY.md":
            continue
        meta, _ = frontmatter(f.read_text(encoding="utf-8", errors="replace"))
        cands.append(dict(id="memory:" + f.stem, kind="memory", name=meta.get("name", f.stem),
                          path=posix(f), description=meta.get("description", ""), sessions=[], first="", last="", weight=0))
    for exp in a.claude_export or []:
        projects, convs = read_claude_export(os.path.expanduser(exp))
        by_proj = collections.defaultdict(list)
        for c in convs:
            by_proj[c["project"]].append(dict(id=c["uuid"], title=c["title"], first=c["first"], last=c["last"], src="app"))
        for p in projects:
            ses = sorted(by_proj.pop(p["uuid"], []), key=lambda s: s["first"])
            cands.append(dict(id="app-project:" + p["uuid"], kind="app project", name=p["name"], path="",
                              description=p["description"][:300], docs=p["docs"], sessions=ses,
                              first=ses[0]["first"] if ses else p["created"], last=ses[-1]["last"] if ses else p["updated"], weight=0))
        for ses in by_proj.values():   # chats outside a project (or unknown project)
            for s in sorted(ses, key=lambda s: s["first"]):
                cands.append(dict(id="app-chat:" + s["id"], kind="app chat", name=s["title"], path="", sessions=[s],
                                  first=s["first"], last=s["last"], weight=0))
    if not a.claude_export:   # re-scan without the export: keep app candidates from before
        cands += [c for c in old.values() if c["id"].startswith("app-")]
    g = cdir / "CLAUDE.md"
    if g.exists():
        cands.append(dict(id="instructions:global", kind="instructions", name="Global CLAUDE.md", path=posix(g),
                          sessions=[], first="", last="", weight=0))
    for c in cands:
        prev = old.get(c["id"], {})
        c["decision"] = prev.get("decision", "")
        if prev.get("target_name"):
            c["target_name"] = prev["target_name"]
    cfile.parent.mkdir(exist_ok=True)
    cfile.write_text(json.dumps(cands, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    show(cands)


def show(cands):
    print(f"{'#':>3}  {'decision':<9} {'kind':<12} {'name':<34} {'sessions':>8}  {'last':<10}  path / titles")
    for i, c in enumerate(cands, 1):
        titles = "; ".join(s["title"] for s in c["sessions"][-3:])
        extra = c.get("path") or ""
        if c["kind"] in ("memory", "app project") and c.get("description"):
            extra = c["description"][:70] + ("  · " + titles[:60] if titles else "")
        elif titles:
            extra = (extra + "  · " if extra else "") + titles[:90]
        name = c.get("target_name") or c["name"]
        print(f"{i:>3}  {c['decision'] or '-':<9} {c['kind']:<12} {name[:34]:<34} {len(c['sessions']):>8}  {c['last']:<10}  {extra}")
    print("\nNext: sources.py decide --vault VAULT 1=project 2=area 3=private 4=drop  (then: sources.py apply)")
    if any(c["kind"] == "app chat" for c in cands):
        print("Merge chats into one note by giving them the same name: 12,15-18=project:\"Thesis\"")


def cmd_decide(a, vault, cfile):
    cands = json.loads(cfile.read_text(encoding="utf-8"))
    for item in a.choices:
        m = re.match(r"^([\d,\- ]+)=(project|area|keep|private|drop)(?::(.+))?$", item)
        if not m:
            sys.exit(f"cannot read '{item}'. Use e.g. 3=project, 3=project:\"Better name\" or 4-7,9=drop")
        nums = []
        for part in m.group(1).replace(" ", "").split(","):
            lo, _, hi = part.partition("-")
            if not lo.isdigit() or (hi and not hi.isdigit()):
                sys.exit(f"cannot read '{part}' in '{item}'")
            nums += range(int(lo), int(hi or lo) + 1)
        for i in nums:
            if not 1 <= i <= len(cands):
                sys.exit(f"there is no candidate {i}")
            decide_one(cands, i, m)
    cfile.write_text(json.dumps(cands, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    show(cands)


def decide_one(cands, i, m):
    c = cands[i - 1]
    if m.group(2) in ("project", "area") and c["kind"] in ("memory", "instructions"):
        sys.exit(f"#{i} is a {c['kind']} file: use keep, private or drop")
    if m.group(2) == "keep" and c["kind"] not in ("memory", "instructions"):
        sys.exit(f"#{i}: 'keep' is for memory/instructions files; use project or area")
    c["decision"] = m.group(2)
    if m.group(3):
        c["target_name"] = m.group(3).strip().strip('"')


def safe(name):
    return re.sub(r"\s+", " ", re.sub(r'[\\/:*?"<>|#^\[\]]', "", name)).strip(". ") or "Untitled"


def set_block(text, block):
    new = f"{START}\n{block.strip()}\n{END}"
    if START in text and END in text:
        return re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: new, text, flags=re.S)
    if "\n## Log" in text:
        return text.replace("\n## Log", "\n" + new + "\n\n## Log", 1)
    return text.rstrip() + "\n\n" + new + "\n"


def write(p, text):
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def link_in(index, name):
    if index.exists():
        t = index.read_text(encoding="utf-8")
        if f"[[{name}]]" not in t:
            write(index, t.rstrip() + f"\n- [[{name}]]\n")


def cmd_apply(a, vault, cfile):
    cands = json.loads(cfile.read_text(encoding="utf-8"))
    cfg_p = vault / ".brain" / "projects.json"
    cfg = json.loads(cfg_p.read_text(encoding="utf-8")) if cfg_p.exists() else {"rules": []}
    priv_p = vault / ".brain" / "private.json"
    priv = json.loads(priv_p.read_text(encoding="utf-8")) if priv_p.exists() else {"names": [], "paths": []}
    existing = {p.stem: p for p in vault.rglob("*.md") if ".obsidian" not in p.parts}
    done = collections.Counter()

    def add_rule(match, project):
        r = {"match": match, "project": project}
        rules = [x for x in cfg["rules"] if x.get("match") != match]
        # private rules first so they always win
        cfg["rules"] = ([r] + rules) if project == "" else (rules + [r])

    merged = {}   # several candidates with the same decision and name become one note
    for c in cands:
        if c.get("decision") in ("project", "area"):
            key = (c["decision"], safe(c.get("target_name") or c["name"]))
            if key in merged:
                m = merged[key]
                m["sessions"] = sorted(m["sessions"] + c["sessions"], key=lambda s: s["first"])
                m["paths"] += [c["path"]] if c["path"] else []
                m["app_projects"] += [c["name"]] if c["kind"] == "app project" else []
                m["last"] = max(m["last"], c["last"])
                c["_merged"] = True
            else:
                merged[key] = c
                c["paths"] = [c["path"]] if c["path"] else []
                c["app_projects"] = [c["name"]] if c["kind"] == "app project" else []
    for c in cands:
        d = c.get("decision")
        name = safe(c.get("target_name") or c["name"])
        if c.pop("_merged", False):
            done[d] += 1
            continue
        if d == "private":
            if c["path"] and c["kind"] not in ("memory", "instructions"):
                add_rule(c["path"], "")
                priv["paths"] = sorted(set(priv["paths"]) | {c["path"]})
            priv["names"] = sorted(set(priv["names"]) | {name})
            done["private"] += 1
        elif d in ("project", "area"):
            folder = "01 Projects" if d == "project" else "02 Areas"
            note = existing.get(name) or vault / folder / name / f"{name}.md"
            if note.exists():
                text = note.read_text(encoding="utf-8")
            else:
                recent = c["last"] and (TODAY - dt.date.fromisoformat(c["last"])).days <= 30
                typ = "project" if d == "project" else "area"
                text = (f"---\ntype: {typ}\nstatus: {'active' if recent else 'planned'}\ndeadline: \"\"\nnext_step: \"\"\n"
                        f"tags: [{typ}]\ncreated: {TODAY.isoformat()}\nsource: claude-history\n---\n\n# {name}\n\n"
                        "## Goal\n> [!todo] To fill in\n> What is this about, and what does done look like?\n\n## Next step\n\n## Log\n")
                existing[name] = note
                link_in(vault / folder / f"{folder}.md", name)
            blk = ["## Claude sessions"]
            blk += [f"Folder: `{p}`" for p in c["paths"]]
            blk += [f"Claude app project: {p}" for p in c["app_projects"]]
            src = {"code": "Claude Code", "app": "Claude app"}
            blk += [f"- {s['first']}" + (f" to {s['last']}" if s["last"] != s["first"] else "") + f": {s['title']}"
                    + (f" ({src[s['src']]})" if s.get("src") in src else "") for s in c["sessions"]]
            write(note, set_block(text, "\n".join(blk)))
            for p in c["paths"]:
                add_rule(p, name)
            done[d] += 1
        elif d == "keep":
            src = Path(os.path.expanduser(c["path"]))
            if src.exists():
                meta, body = frontmatter(src.read_text(encoding="utf-8", errors="replace"))
                out = vault / "03 Resources" / "Claude Memory" / f"{name}.md"
                write(out, f"---\ntype: claude-memory\nstatus: active\ntags: [claude, memory]\ncreated: {TODAY.isoformat()}\n"
                           f"source: \"{c['path']}\"\n---\n# {name}\n\n{body.strip()}\n")
                link_in(vault / "03 Resources" / "03 Resources.md", "Claude Memory")
                idx = vault / "03 Resources" / "Claude Memory" / "Claude Memory.md"
                if not idx.exists():
                    write(idx, f"---\ntype: moc\nstatus: active\ntags: [moc, claude]\ncreated: {TODAY.isoformat()}\n---\n"
                               "# Claude Memory\n\nCopied from Claude Code's memory and instructions files.\n\n")
                link_in(idx, name)
                done["keep"] += 1
    write(cfg_p, json.dumps(cfg, indent=2, ensure_ascii=False) + "\n")
    write(priv_p, json.dumps(priv, indent=2, ensure_ascii=False) + "\n")
    for c in cands:
        c.pop("paths", None), c.pop("app_projects", None)
    open_ = sum(1 for c in cands if not c.get("decision"))
    print(", ".join(f"{v} {k}" for k, v in done.items()) or "nothing to apply", f"· {open_} candidates still undecided")


def main():
    utf8_stdout()
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["scan", "decide", "apply", "show"])
    ap.add_argument("choices", nargs="*")
    ap.add_argument("--vault", required=True)
    ap.add_argument("--claude-dir", default="~/.claude")
    ap.add_argument("--home", default="~")
    ap.add_argument("--claude-export", action="append", help="Claude app / claude.ai export, ZIP or folder (repeatable)")
    a = ap.parse_intermixed_args()
    vault = Path(os.path.expandvars(os.path.expanduser(a.vault))).resolve()
    cfile = vault / ".brain" / "candidates.json"
    if a.command != "scan" and not cfile.exists():
        sys.exit("run 'sources.py scan' first")
    {"scan": cmd_scan, "decide": cmd_decide, "apply": cmd_apply,
     "show": lambda a, v, c: show(json.loads(c.read_text(encoding="utf-8")))}[a.command](a, vault, cfile)


if __name__ == "__main__":
    main()
