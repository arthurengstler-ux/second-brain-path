#!/usr/bin/env python3
"""Second Brain: graph, dashboard server and Claude Code hook.

  python3 scripts/brain.py serve     dashboard with controls on http://localhost:8765
  python3 scripts/brain.py build     rebuild Brain.html (read-only snapshot)
  python3 scripts/brain.py hook      called by Claude Code after every Write/Edit
  python3 scripts/brain.py log PROJECT "text"   add a manual entry to the activity log
  python3 scripts/brain.py docs      scan Desktop/Downloads, write a "Documents <project>" note per project
  python3 scripts/brain.py context   short overview for the start of a Claude session

Python standard library only. Works on macOS, Windows and Linux.
"""
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

VAULT = Path(__file__).resolve().parent.parent
META = VAULT / ".brain"
ACTIVITY = META / "activity.jsonl"
CONFIG = META / "projects.json"
TEMPLATE = VAULT / "scripts" / "dashboard.html"
SNAPSHOT = VAULT / "Brain.html"
ACTIVITY_NOTE = VAULT / "Claude Activity.md"
DOCS = META / "docs.json"
PORT = int(os.environ.get("BRAIN_PORT", "8765"))
SKIP_DIRS = {".git", ".obsidian", ".brain", "scripts", ".trash"}
STATUSES = ["active", "planned", "idea", "done"]
WIKILINK = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
LOCK = threading.Lock()


# ------------------------------------------------------------------ Platform
def open_file(path):
    """Open a file with the default app on macOS, Windows or Linux."""
    if sys.platform == "darwin":
        subprocess.Popen(["open", path])
    elif os.name == "nt":
        os.startfile(path)  # noqa: S606
    else:
        subprocess.Popen(["xdg-open", path])


# ------------------------------------------------------------------ Parsing
def split_frontmatter(text):
    if text.startswith("---\n"):
        end = text.find("\n---", 4)
        if end != -1:
            return text[4:end], text[end + 4:].lstrip("\n")
    return "", text


def parse_frontmatter(raw):
    data = {}
    for line in raw.splitlines():
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if not m:
            continue
        k, v = m.group(1), m.group(2).strip()
        if v.startswith("[") and v.endswith("]"):
            v = [x.strip().strip("\"'") for x in v[1:-1].split(",") if x.strip()]
        else:
            v = v.strip("\"'")
        data[k] = v
    return data


def iter_notes():
    for p in sorted(VAULT.rglob("*.md")):
        rel = p.relative_to(VAULT)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        yield p, rel


def first_paragraph(body):
    for block in re.split(r"\n\s*\n", body):
        b = block.strip()
        if not b or b.startswith(("#", ">", "|", "---")):
            continue
        b = WIKILINK.sub(lambda m: m.group(1), b)
        b = re.sub(r"[*`_]", "", b)
        return b[:400]
    return ""


def load_activity(limit=None):
    if not ACTIVITY.exists():
        return []
    rows = []
    for line in ACTIVITY.read_text(encoding="utf-8").splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            pass
    return rows[-limit:] if limit else rows


def build_graph():
    notes, by_name = [], {}
    for p, rel in iter_notes():
        text = p.read_text(encoding="utf-8", errors="replace")
        raw, body = split_frontmatter(text)
        meta = parse_frontmatter(raw)
        name = p.stem
        parts = rel.parts
        todos = []
        for i, line in enumerate(body.splitlines()):
            if "[!todo]" in line:
                nxt = body.splitlines()[i + 1] if i + 1 < len(body.splitlines()) else ""
                todos.append({"kind": "todo", "text": nxt.lstrip("> ").strip()})
        checks = []
        for i, line in enumerate(text.splitlines()):
            m = re.match(r"^\s*- \[( |x)\] (.+)$", line)
            if m and m.group(2).strip():
                checks.append({"line": i, "done": m.group(1) == "x",
                               "text": WIKILINK.sub(lambda mm: mm.group(1), m.group(2)).strip()})
        node = {
            "id": name,
            "path": str(rel),
            "area": parts[0] if len(parts) > 1 else "Home",
            "folder": str(rel.parent),
            "type": meta.get("type", ""),
            "status": meta.get("status", ""),
            "deadline": meta.get("deadline", ""),
            "next": meta.get("next_step", ""),
            "tags": meta.get("tags", []),
            "summary": first_paragraph(body),
            "todos": todos,
            "checks": checks,
            "mtime": p.stat().st_mtime,
            "links": sorted(set(l.strip() for l in WIKILINK.findall(body))),
            "template": parts[0] == "99 Templates",
            "meta": name in ("Claude Activity",),
        }
        notes.append(node)
        by_name[name] = node
    edges = []
    for n in notes:
        for l in n["links"]:
            if l in by_name and l != n["id"]:
                edges.append({"source": n["id"], "target": l})
    # every note under 01 Projects/<X>/ belongs to project X
    for n in notes:
        parts = Path(n["path"]).parts
        n["project"] = parts[1] if parts[0] == "01 Projects" and len(parts) > 2 else ""
    activity = load_activity(300)
    version = max([n["mtime"] for n in notes] + [ACTIVITY.stat().st_mtime if ACTIVITY.exists() else 0])
    try:
        docs = json.loads(DOCS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        docs = {}
    return {"notes": notes, "edges": edges, "activity": activity, "statuses": STATUSES, "docs": docs,
            "vault": VAULT.name, "version": version,
            "generated": dt.datetime.now().strftime("%d.%m.%Y %H:%M")}


# ------------------------------------------------------------------ Schreiben
def safe_path(rel):
    p = (VAULT / rel).resolve()
    if VAULT.resolve() not in p.parents or p.suffix != ".md":
        raise ValueError("path outside the vault")
    return p


def set_frontmatter(rel, key, value):
    p = safe_path(rel)
    text = p.read_text(encoding="utf-8")
    raw, body = split_frontmatter(text)
    lines = raw.splitlines() if raw else []
    pat = re.compile(rf"^{re.escape(key)}:")
    lines = [l for l in lines if not pat.match(l)]
    if value:
        lines.append(f"{key}: {value}")
    p.write_text("---\n" + "\n".join(lines) + "\n---\n\n" + body, encoding="utf-8")


def toggle_check(rel, line_no):
    p = safe_path(rel)
    lines = p.read_text(encoding="utf-8").split("\n")
    line = lines[line_no]
    if "- [ ]" in line:
        lines[line_no] = line.replace("- [ ]", "- [x]", 1)
    elif "- [x]" in line:
        lines[line_no] = line.replace("- [x]", "- [ ]", 1)
    p.write_text("\n".join(lines), encoding="utf-8")


def add_log_entry(rel, text):
    """Append a dated entry under '## Log' (creates the section if missing)."""
    p = safe_path(rel)
    content = p.read_text(encoding="utf-8").rstrip("\n")
    entry = f"- {dt.date.today().strftime('%Y-%m-%d')}: {text.strip()}"
    if "\n## Log" in content:
        head, tail = content.split("\n## Log", 1)
        tail_lines = tail.split("\n")
        # find end of section
        idx = len(tail_lines)
        for i, l in enumerate(tail_lines[1:], 1):
            if l.startswith("## "):
                idx = i
                break
        while idx > 1 and not tail_lines[idx - 1].strip():
            idx -= 1
        tail_lines.insert(idx, entry)
        content = head + "\n## Log" + "\n".join(tail_lines)
    else:
        content += "\n\n## Log\n" + entry
    p.write_text(content + "\n", encoding="utf-8")


def new_inbox(title, text):
    title = re.sub(r'[\\/:*?"<>|#\[\]]', "", title).strip() or dt.datetime.now().strftime("Note %Y-%m-%d %H%M")
    p = VAULT / "00 Inbox" / f"{title}.md"
    i = 2
    while p.exists():
        p = VAULT / "00 Inbox" / f"{title} {i}.md"
        i += 1
    p.write_text(f"---\ntype: inbox\nstatus: idea\ntags: [inbox]\ncreated: {dt.date.today()}\n---\n\n# {p.stem}\n\n{text.strip()}\n",
                 encoding="utf-8")
    return str(p.relative_to(VAULT))


# ------------------------------------------------------------------ Activity
def load_config():
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"rules": []}


def map_project(path):
    path = os.path.expanduser(path or "")
    try:
        rel = Path(path).resolve().relative_to(VAULT.resolve())
        parts = rel.parts
        if parts and parts[0] == "01 Projects" and len(parts) > 1:
            return parts[1]
        if len(parts) > 2 and parts[0] == "02 Areas":
            return parts[2] if len(parts) > 3 else parts[1]
        return "Second Brain"
    except ValueError:
        pass
    return rule_project(path) or ""


def rule_project(path, rules=None):
    """Project according to rules; '' = deliberately excluded, None = no rule."""
    path = path.replace("\\", "/")  # Windows: compare with forward slashes
    for rule in (rules if rules is not None else load_config().get("rules", [])):
        pat = rule["match"] if rule.get("regex") else os.path.expanduser(rule["match"]).replace("\\", "/")
        if rule.get("regex"):
            if re.search(pat, path):
                return rule["project"]
        elif path.startswith(pat):
            return rule["project"]
    return None


# ------------------------------------------------------------------ Documents
def scan_docs():
    cfg = load_config()
    scan, rules = cfg.get("scan", {}), cfg.get("rules", [])
    exts = {"." + e.lower() for e in scan.get("extensions", [])}
    skip = set(scan.get("skip_dirs", []))
    maxd = int(scan.get("max_depth", 4))
    vault = VAULT.resolve()
    found = {}
    for root in scan.get("roots", []):
        root = Path(os.path.expanduser(root))
        if not root.is_dir():
            continue
        base = len(root.parts)
        for dirpath, dirnames, filenames in os.walk(root):
            dp = Path(dirpath)
            depth = len(dp.parts) - base
            dirnames[:] = [d for d in dirnames if d not in skip and not d.startswith(".")
                           and depth < maxd and (dp / d).resolve() != vault]
            for fn in filenames:
                p = dp / fn
                if fn.startswith(("~$", ".")) or p.suffix.lower() not in exts:
                    continue
                proj = rule_project(str(p), rules)
                if not proj:
                    continue
                try:
                    mt = p.stat().st_mtime
                except OSError:
                    continue
                found.setdefault(proj, []).append({
                    "path": str(p), "name": fn, "mtime": mt,
                    "dir": str(dp).replace(str(Path.home()), "~"),
                    "backup": bool(re.search(r"(?i)backup", fn))})
    for v in found.values():
        v.sort(key=lambda d: -d["mtime"])
    META.mkdir(exist_ok=True)
    DOCS.write_text(json.dumps(found, ensure_ascii=False), encoding="utf-8")
    write_doc_notes(found)
    return found


def _doc_rows(items, prefix=""):
    out = [prefix + "| File | Folder | Modified |", prefix + "|---|---|---|"]
    for d in items:
        url = "file://" + urllib.parse.quote(d["path"])
        name = d["name"].replace("|", "/").replace("[", "(").replace("]", ")")
        out.append(f"{prefix}| [{name}]({url}) | `{d['dir']}` | {dt.datetime.fromtimestamp(d['mtime']).strftime('%Y-%m-%d')} |")
    return out


def write_doc_notes(found):
    where = {p.stem: p.parent for p, _ in iter_notes()}
    wanted = set()
    for proj, items in found.items():
        folder = where.get(proj)
        if folder is None:
            continue
        target = folder / f"Documents {proj}.md"
        wanted.add(target)
        main = [d for d in items if not d["backup"]]
        backups = [d for d in items if d["backup"]]
        lines = ["---", "type: documents", "status: active", "tags: [documents]", f"created: {dt.date.today().isoformat()}", "---", "",
                 f"# Documents {proj}", "",
                 f"Belongs to [[{proj}]]. Generated from Desktop and Downloads, mapping in `.brain/projects.json`. "
                 "Do not edit by hand, it is overwritten on the next scan. Click a name to open the file.", ""]
        lines += _doc_rows(main)
        if backups:
            lines += ["", f"> [!note]- Backups ({len(backups)})"] + _doc_rows(backups, "> ")
        text = "\n".join(lines) + "\n"
        if not target.exists() or target.read_text(encoding="utf-8") != text:
            target.write_text(text, encoding="utf-8")
    for p, _ in list(iter_notes()):
        if p.name.startswith("Documents ") and p not in wanted and "type: documents" in p.read_text(encoding="utf-8")[:80]:
            p.unlink()


def context():
    """Short overview that the SessionStart hook loads into every Claude session."""
    try:
        scan_docs()
    except Exception:  # noqa: BLE001
        pass
    g = build_graph()
    notes = g["notes"]
    act = g["activity"]
    last = {}
    for r in act:
        last[r.get("project")] = r["ts"][:10]
    out = [f"## {load_config().get('owner', 'My')} Second Brain ({dt.date.today().isoformat()})",
           f"Vault: {VAULT}. Before working on one of these topics, read its note and the note 'Documents <topic>' "
           "(same folder, lists all related files). Rules for updating: ~/.claude/CLAUDE.md.", "",
           "Active projects:"]
    for n in notes:
        parts = Path(n["path"]).parts
        if parts[0] == "01 Projects" and len(parts) == 3 and n["type"] == "project" and n["status"] != "done":
            bits = [f"- {n['id']} [{n['status']}]"]
            if n["deadline"]:
                bits.append(f"deadline {n['deadline']}")
            if n["next"]:
                bits.append(f"next step: {n['next']}")
            if n["id"] in last:
                bits.append(f"Claude last {last[n['id']]}")
            nd = len(g["docs"].get(n["id"], []))
            if nd:
                bits.append(f"{nd} documents")
            out.append(" · ".join(bits))
    today = dt.date.today().isoformat()
    def end(d):  # 2027 -> 2027-12-31, 2027-06 -> 2027-06-31
        return (d + "-12-31")[:10] if len(d) == 4 else (d + "-31")[:10] if len(d) == 7 else d
    fr = sorted((end(n["deadline"]), n["deadline"], n["id"], n["next"]) for n in notes
                if n["deadline"] and end(n["deadline"]) >= today and not n["template"])
    if fr:
        out += ["", "Upcoming deadlines (\"2027\" = sometime in 2027):"] + [f"- {d} {i}" + (f" ({x})" if x else "") for _, d, i, x in fr[:7]]
    inbox = [n["id"] for n in notes if n["area"] == "00 Inbox" and n["type"] != "moc"]
    if inbox:
        out += ["", "Inbox: " + ", ".join(inbox[:8])]
    if act:
        out += ["", "Recently worked on: " + "; ".join(
            f"{r['project']}: {r.get('text') or Path(r.get('file','')).name}" for r in act[-5:])]
    print("\n".join(out))


def record(project, file, tool, session, text=""):
    META.mkdir(exist_ok=True)
    rows = load_activity(400)
    for r in reversed(rows[-200:]):
        if r.get("session") == session and r.get("file") == file and session:
            return False  # same file already logged in this session
    row = {"ts": dt.datetime.now().isoformat(timespec="seconds"), "project": project,
           "file": file, "tool": tool, "session": session, "text": text}
    with ACTIVITY.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return True


def write_activity_note():
    rows = load_activity(60)
    lines = ["---", "type: log", "status: active", "tags: [claude, log]", f"created: {dt.date.today().isoformat()}", "---", "",
             "# Claude Activity", "",
             "Written automatically whenever Claude Code changes a file. Do not edit by hand.", "",
             "| Time | Project | File / entry |", "|---|---|---|"]
    names = {p.stem for p, _ in iter_notes()}
    for r in reversed(rows):
        t = dt.datetime.fromisoformat(r["ts"]).strftime("%Y-%m-%d %H:%M")
        proj = f"[[{r['project']}]]" if r.get("project") in names else (r.get("project") or "–")
        what = r.get("text") or ("`" + r.get("file", "").replace(str(Path.home()), "~") + "`")
        lines.append(f"| {t} | {proj} | {what.replace('|', '/')} |")
    ACTIVITY_NOTE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_hook():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return
    ti = data.get("tool_input") or {}
    file = ti.get("file_path") or ti.get("notebook_path") or ""
    if not file:
        return
    file = os.path.abspath(os.path.expanduser(file))
    if file in (str(ACTIVITY_NOTE), str(SNAPSHOT)) or "/.brain/" in file.replace("\\", "/"):
        return
    project = map_project(file) or map_project(data.get("cwd", "")) or "Other"
    if record(project, file, data.get("tool_name", ""), data.get("session_id", "")):
        write_activity_note()
        build_snapshot()


# ------------------------------------------------------------------ HTML
def render(live):
    html = TEMPLATE.read_text(encoding="utf-8")
    payload = json.dumps(build_graph(), ensure_ascii=False).replace("</", "<\\/")
    return html.replace("/*__DATA__*/null", payload).replace("/*__LIVE__*/false", "true" if live else "false")


def build_snapshot():
    SNAPSHOT.write_text(render(False), encoding="utf-8")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *a):
        if "/api/version" in (a[0] if a else ""):
            return
        try:
            META.mkdir(exist_ok=True)
            with (META / "server.log").open("a", encoding="utf-8") as f:
                f.write(dt.datetime.now().strftime("%H:%M:%S ") + (fmt % a) + "\n")
        except OSError:
            pass

    def _send(self, code, body, ctype="application/json; charset=utf-8"):
        b = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path in ("/", "/index.html"):
            return self._send(200, render(True), "text/html; charset=utf-8")
        if path == "/api/graph":
            return self._send(200, json.dumps(build_graph(), ensure_ascii=False))
        if path == "/api/version":
            g = build_graph()
            code = max(TEMPLATE.stat().st_mtime, Path(__file__).stat().st_mtime)
            return self._send(200, json.dumps({"version": g["version"], "code": code}))
        self._send(404, "{}")

    def do_POST(self):
        # only accept requests from our own page
        origin = self.headers.get("Origin", "")
        if origin and not re.match(r"^http://(localhost|127\.0\.0\.1):%d$" % PORT, origin):
            return self._send(403, '{"error":"origin"}')
        length = int(self.headers.get("Content-Length", 0))
        try:
            req = json.loads(self.rfile.read(length) or b"{}")
            path = urllib.parse.urlparse(self.path).path
            with LOCK:
                if path == "/api/set":
                    key = req["key"]
                    if key not in ("status", "deadline", "next_step"):
                        raise ValueError("field not allowed")
                    set_frontmatter(req["path"], key, str(req.get("value", "")).strip())
                elif path == "/api/check":
                    toggle_check(req["path"], int(req["line"]))
                elif path == "/api/log":
                    add_log_entry(req["path"], req["text"])
                    record(Path(req["path"]).stem, str(VAULT / req["path"]), "Dashboard", "", req["text"])
                    write_activity_note()
                elif path == "/api/open":
                    known = {d["path"] for v in json.loads(DOCS.read_text(encoding="utf-8")).values() for d in v}
                    if req["path"] not in known:
                        raise ValueError("file not in index")
                    open_file(req["path"])
                    return self._send(200, '{"ok":true}')
                elif path == "/api/inbox":
                    rel = new_inbox(req.get("title", ""), req.get("text", ""))
                    return self._send(200, json.dumps({"ok": True, "path": rel}))
                else:
                    return self._send(404, "{}")
                build_snapshot()
            self._send(200, '{"ok":true}')
        except Exception as e:  # noqa: BLE001
            self._send(400, json.dumps({"error": str(e)}))


def _rescan_loop():
    while True:
        try:
            with LOCK:
                scan_docs()
        except Exception:  # noqa: BLE001
            pass
        time.sleep(300)


def serve():
    threading.Thread(target=_rescan_loop, daemon=True).start()
    build_snapshot()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Second Brain running on http://localhost:{PORT}  (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "serve":
        serve()
    elif cmd == "build":
        write_activity_note()
        build_snapshot()
        print(f"written: {SNAPSHOT}")
    elif cmd == "hook":
        try:
            run_hook()
        except Exception:  # Hook darf Claude nie blockieren
            pass
    elif cmd == "docs":
        f = scan_docs()
        print("\n".join(f"{k}: {len(v)}" for k, v in sorted(f.items())))
    elif cmd == "context":
        context()
    elif cmd == "log" and len(sys.argv) >= 4:
        record(sys.argv[2], "", "manuell", "", " ".join(sys.argv[3:]))
        write_activity_note()
        build_snapshot()
    else:
        print(__doc__)
