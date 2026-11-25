#!/usr/bin/env python3
"""LinkedIn data export -> Obsidian second brain.

    python3 -I scripts/import_linkedin.py --vault ~/Documents/Second-Brain \
        --zip ~/Downloads/Basic_LinkedInDataExport_*.zip ~/Downloads/Complete_LinkedInDataExport_*.zip \
        --config config/topics.example.json [--exclude-lastname Doe] [--dry-run]

(On Windows use `py -3 -I` instead of `python3 -I`.)

What it writes:
  * 02 Areas/Career/CV.md                  profile, education, positions, languages, skills
  * 05 People/<Sector>/<Name>.md           one note per contact: sector, topics, contact history
  * 05 People/<Sector>/<Sector>.md         overview per sector
  * 05 People/Who to Ask.md                index: who to approach about which topic
  * 02 Areas/Career/Recruiter Messages.md, LinkedIn Contacts.md

Safety rules:
  * The export is only read, never extracted (a folder works too, e.g. when Safari unzipped it).
  * Nothing is deleted and no existing folder is recreated (deleting and recreating inside
    iCloud/OneDrive-synced folders produces duplicate "Name 2.md" files).
  * In existing notes the script only touches the frontmatter fields it owns and the block
    between <!-- linkedin:start --> and <!-- linkedin:end -->. Your own notes stay untouched.
  * Message contents are never copied, only date, count, rough topic and whether there was a reply.
  * Running it again with a newer export updates everything (idempotent).

Python standard library only. Works on macOS, Windows and Linux.
"""
import argparse
import collections
import csv
import datetime as dt
import io
import json
import os
import re
import sys
import zipfile
from pathlib import Path

START, END = "<!-- linkedin:start -->", "<!-- linkedin:end -->"
TODAY = dt.date.today().isoformat()

# Patterns match company + position. They cover English and German job titles.
DEFAULT_SECTORS = [
    ["Military & Security", r"bundesheer|bundeswehr|armed forces|army|armee|defen[cs]e|militär|military|polizei|police|\bmiliz"],
    ["Diplomacy & Trade", r"advantage austria|embassy|botschaft|konsulat|consulate|ambassador|diplomat|\bMFA\b|auswärtig|foreign (office|affairs)|state department|united nations|permanent mission|council of europe|conseil de l|\bOSCE\b|\bOSZE\b|trade commission|wirtschaftsdeleg|commercial (attach|counsel)"],
    ["Politics & Government", r"parlament|parliament|congress|senate|bundestag|nationalrat|ministerium|ministry|kanzleramt|regierung|landesrat|partei|\bparty\b|\bpolitic|politik|gemeinderat|city council|bezirk|magistrat|\brepublik|staatssekret|minister|abgeordnet|government|european commission|wirtschaftskammer|chamber of commerce|\bWKO\b|\bIHK\b|industriellenverein|verband|association"],
    ["Law", r"anwalt|rechtsanw|\blaw\b|legal|notar|jurist|kanzlei|attorney|counsel\b"],
    ["Finance & Consulting", r"bank|goldman|\bEY\b|KPMG|PwC|deloitte|mckinsey|\bBCG\b|\bbain\b|capital|financ|treuhand|steuer|\btax\b|invest|fonds|\bfund|audit|revision|consult|advisory|asset manag|leasing|wealth|M&A|versicher|insurance"],
    ["Academia & Research", r"universit|\bWU\b|institut|research|forschung|hochschule|professor|\bETH\b|college|academy of|phd|doktorand"],
    ["Media & Communications", r"media|medien|zeitung|newspaper|presse|press\b|journal|redakt|editor|podcast|verlag|publish|marketing|\bPR\b|kommunikation|communication|\bBBC\b|\bCNN\b|\bORF\b|\bARD\b|\bZDF\b|\bSRF\b"],
    ["Schools & Education", r"schule|gymnas|lycée|lycee|school|bildung|education|akademie|tutor|nachhilfe|teacher|lehrer"],
    ["Real Estate & Construction", r"immobil|real estate|realit|property|\bbau|construction|architekt|architect|interiors|hausverwalt"],
    ["Health & Medicine", r"medic|medizin|ordination|\barzt|ärzt|physician|doctor|klinik|clinic|hospital|spital|pharma|dr\. ?med|psychiatr|rotes kreuz|red cross|pflege|nurse"],
    ["Sports", r"sport|athlet|football|fußball|soccer|basketball|olymp|übungsleiter|\bcoach"],
    ["Tech & IT", r"software|\btech|\bIT\b|\bAWS\b|amazon|google|microsoft|developer|engineer|\bAI\b|\bKI\b|data|cloud|digital"],
    ["Founders & Start-ups", r"founder|gründer|start-?up|\bCEO\b|geschäftsführ|managing director|owner|inhaber|unternehmer|entrepreneur"],
    ["Companies & Trade", r"."],
]
DEFAULT_MESSAGE_TOPICS = [
    ["Recruiting", r"recruit|we're (still )?looking for|we are hiring|wir suchen|sales development|business development representative|open position|offene stelle"],
    ["Interview request", r"\binterview\b"],
    ["Internship", r"praktikum|internship|werkstudent|working student"],
]


# Language of the generated notes ("language" in topics.json). File paths can be overridden with "paths".
L10N = {
    "en": dict(stamp="LinkedIn export, imported {d}", source="Source", who="Who to Ask", career="Career", people="05 People",
               cv_path="02 Areas/Career/CV.md", cv_title="CV", cv_intro="Add your own items (projects, volunteering) outside the LinkedIn block.",
               from_li="From LinkedIn", education="Education", positions="Positions", languages="Languages", skills="Skills",
               present="present", to="to", back="Back to", notes="## Notes", no_details="No details", no_details_li="no details on LinkedIn",
               sector="sector", good_for="## Good contact for", no_topic="no topic assigned yet",
               history="## Contact history (LinkedIn messages)", message="message", messages="messages", topic="topic",
               by_me="started by me", reply="got a reply", no_reply="**no reply**", by_them="started by them", not_answered="**not answered yet**",
               moc_intro="{n} contacts, sorted by organization. Source: {stamp}.",
               who_intro_ai="Generated from the {stamp}. {n} contacts were sorted by Claude (reason in italics), the rest by keyword rules. ",
               who_intro_kw="Generated from the {stamp}. Topics are matched on company and position, so treat them as suggestions. ",
               who_fix="Fix mistakes in .brain/assignments.json or topics.json and import again, not here.",
               asked="## Asked, no reply yet", asked_intro="Candidates for a follow-up.", project_area="Project/area", all_sectors="## All sectors",
               network="## LinkedIn network by sector",
               rec_path="02 Areas/Career/Recruiter Messages.md", rec_title="Recruiter Messages",
               rec_intro="Company and role are in the message on LinkedIn. Add your own assessment below the block.",
               rec_head="| First message | Last | From | Messages | Status |", answered="answered", open="**open**", rec_none="No recruiter messages found.",
               con_path="02 Areas/Career/LinkedIn Contacts.md", con_title="LinkedIn Contacts",
               con_intro="{n} contacts as person notes in [[05 People]], topic index: [[{who}]].",
               skipped="{n} contacts skipped on purpose (no name, or excluded by last name, sector, organization or person).",
               follows="## People you follow (not connected)"),
    "de": dict(stamp="LinkedIn-Export, importiert {d}", source="Quelle", who="Wen fragen", career="Karriere", people="05 People",
               cv_path="02 Areas/Karriere/Lebenslauf.md", cv_title="Lebenslauf", cv_intro="Eigene Ergänzungen (Projekte, Engagement) außerhalb des LinkedIn-Blocks schreiben.",
               from_li="Aus LinkedIn", education="Ausbildung", positions="Stationen", languages="Sprachen", skills="Kenntnisse",
               present="heute", to="bis", back="Zurück zu", notes="## Notizen", no_details="Ohne Angabe", no_details_li="keine Angabe auf LinkedIn",
               sector="Bereich", good_for="## Ansprechpartner für", no_topic="noch kein Thema zugeordnet",
               history="## Kontaktverlauf (LinkedIn-Nachrichten)", message="Nachricht", messages="Nachrichten", topic="Thema",
               by_me="von mir begonnen", reply="Antwort erhalten", no_reply="**keine Antwort**", by_them="vom Gegenüber begonnen", not_answered="**noch nicht beantwortet**",
               moc_intro="{n} Kontakte, sortiert nach Organisation. Quelle: {stamp}.",
               who_intro_ai="Erzeugt aus dem {stamp}. {n} Kontakte hat Claude eingeordnet (Begründung kursiv), der Rest folgt den Suchregeln. ",
               who_intro_kw="Erzeugt aus dem {stamp}. Die Zuordnung läuft über Firma und Position, also nur ein Vorschlag. ",
               who_fix="Fehler in .brain/assignments.json oder topics.json korrigieren und neu importieren, nicht hier.",
               asked="## Angefragt, keine Antwort", asked_intro="Kandidaten für eine Nachfrage.", project_area="Projekt/Bereich", all_sectors="## Alle Bereiche",
               network="## LinkedIn-Netzwerk nach Bereich",
               rec_path="02 Areas/Karriere/Recruiter-Anfragen.md", rec_title="Recruiter-Anfragen",
               rec_intro="Firma und Stelle stehen in der Nachricht auf LinkedIn. Eigene Einschätzung unter dem Block ergänzen.",
               rec_head="| Erste Nachricht | Letzte | Von | Nachrichten | Status |", answered="beantwortet", open="**offen**", rec_none="Keine Recruiter-Nachrichten gefunden.",
               con_path="02 Areas/Karriere/LinkedIn-Kontakte.md", con_title="LinkedIn-Kontakte",
               con_intro="{n} Kontakte als Personennotizen in [[05 People]], Themen-Index: [[{who}]].",
               skipped="{n} Kontakte bewusst ausgelassen (ohne Namen oder per Nachname, Bereich, Organisation oder Person ausgeschlossen).",
               follows="## Gefolgte Personen (ohne Vernetzung)"),
}
SECTORS_DE = {"Military & Security": "Militär & Sicherheit", "Diplomacy & Trade": "Diplomatie & Außenhandel",
              "Politics & Government": "Politik & Verwaltung", "Law": "Recht", "Finance & Consulting": "Finanz & Beratung",
              "Academia & Research": "Wissenschaft & Hochschulen", "Media & Communications": "Medien & Kommunikation",
              "Schools & Education": "Schule & Bildung", "Real Estate & Construction": "Immobilien & Bau",
              "Health & Medicine": "Medizin & Gesundheit", "Sports": "Sport", "Tech & IT": "Tech & IT",
              "Founders & Start-ups": "Gründer & Start-ups", "Companies & Trade": "Unternehmen & Handel"}


# ---------------------------------------------------------------- reading
class Export:
    """Several ZIPs or folders; later ones override files of the same name."""

    def __init__(self, paths):
        self.files = {}
        for p in paths:
            if os.path.isdir(p):  # Safari often unzips downloads automatically
                for f in Path(p).rglob("*.csv"):
                    self.files[f.name.lower()] = (None, str(f))
                continue
            with zipfile.ZipFile(p) as z:
                for n in z.namelist():
                    if n.endswith(".csv"):
                        self.files[n.split("/")[-1].lower()] = (p, n)

    def rows(self, name):
        hit = self.files.get(name.lower())
        if not hit:
            return []
        if hit[0] is None:
            text = Path(hit[1]).read_text(encoding="utf-8-sig", errors="replace")
        else:
            with zipfile.ZipFile(hit[0]) as z:
                text = z.read(hit[1]).decode("utf-8-sig", errors="replace")
        lines = text.splitlines()
        # Connections.csv starts with a few note lines before the header
        for i, l in enumerate(lines[:10]):
            if l.count(",") >= 2 and not l.startswith(("Notes", '"When')):
                lines = lines[i:]
                break
        return list(csv.DictReader(io.StringIO("\n".join(lines))))


def clean(s):
    return re.sub(r"\s+", " ", (s or "").replace("\xa0", " ")).strip()


def norm_url(u):
    u = (u or "").strip().lower().split("?")[0].rstrip("/")
    return re.sub(r"^https?://(www\.)?", "", u)


def safe_name(first, last):
    n = clean(f"{first} {last}")
    n = re.sub(r"\s+[-|–]\s+.*$", "", n)                 # "Name - slogan"
    n = re.sub(r"[\\/:*?\"<>|#^\[\]]", "", n)           # invalid on Windows / in wikilinks
    n = re.sub(r"[^\w\s.\-'()&,]", "", n, flags=re.U)  # emojis
    n = re.sub(r"[぀-ヿ一-鿿가-힯]+", "", n)  # CJK name additions
    return clean(n).strip(". ")


def parse_date(s):
    for f in ("%d %b %Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(s.strip(), f).date().isoformat()
        except ValueError:
            pass
    return ""


# ---------------------------------------------------------------- writing
class Writer:
    def __init__(self, vault, dry):
        self.vault, self.dry, self.changed = vault, dry, []

    def write(self, rel, text):
        p = self.vault / rel
        old = p.read_text(encoding="utf-8") if p.exists() else None
        if old == text:
            return
        self.changed.append(("new" if old is None else "changed", rel))
        if not self.dry:
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(text)


def q(v):
    return json.dumps(v, ensure_ascii=False)


def set_frontmatter(text, fields):
    """Set single-line YAML frontmatter fields, creating the frontmatter if needed."""
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    head, body = (m.group(1).splitlines(), text[m.end():]) if m else ([], text)
    keys = [l.split(":", 1)[0] for l in head]
    for k, v in fields.items():
        line = f"{k}: {v}"
        if k in keys:
            head[keys.index(k)] = line
        else:
            head.append(line)
            keys.append(k)
    return "---\n" + "\n".join(head) + "\n---\n" + body


def set_block(text, block, before=None):
    """Replace the linkedin block, or insert it (before `before`, else at the end)."""
    new = f"{START}\n{block.strip()}\n{END}"
    if START in text and END in text:
        return re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: new, text, flags=re.S)
    if before and before in text:
        return text.replace(before, new + "\n\n" + before, 1)
    return text.rstrip() + "\n\n" + new + "\n"


def read(p, default):
    return p.read_text(encoding="utf-8") if p.exists() else default


# ---------------------------------------------------------------- main
def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault", required=True)
    ap.add_argument("--zip", nargs="+", required=True, help="Basic and/or Complete export as ZIP or unzipped folder (older first)")
    ap.add_argument("--config", help="topics.json (see config/topics.example.json)")
    ap.add_argument("--exclude-lastname", action="append", default=[], help="e.g. family; can be repeated")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    vault = Path(os.path.expanduser(a.vault)).resolve()
    if not (vault / "05 People").is_dir():
        sys.exit(f"{vault} does not look like a second-brain vault (05 People is missing). Run setup_vault.py first.")
    cfg = json.loads(Path(os.path.expanduser(a.config)).read_text(encoding="utf-8")) if a.config else {}
    lang = cfg.get("language", "en")
    S = dict(L10N.get(lang, L10N["en"]))
    S.update({k + "_path": v for k, v in (cfg.get("paths") or {}).items()})   # e.g. "cv": "" disables the CV
    names_map = {**(SECTORS_DE if lang == "de" else {}), **(cfg.get("sector_names") or {})}
    sectors = cfg.get("sectors") or [[names_map.get(n, n), rx] for n, rx in DEFAULT_SECTORS]
    topics = cfg.get("topics", [])
    msg_topics = cfg.get("message_topics") or DEFAULT_MESSAGE_TOPICS
    exclude = {x.lower() for x in a.exclude_lastname + cfg.get("exclude_lastnames", [])}
    excl_sectors = set(cfg.get("exclude_sectors", []))
    excl_people = {x.lower() for x in cfg.get("exclude_people", [])}
    excl_orgs = [x for x in cfg.get("exclude_organizations", []) if x]
    ex = Export([os.path.expanduser(z) for z in a.zip])
    W = Writer(vault, a.dry_run)
    # Claude's own judgement (classify.py) beats the keyword rules for every contact it covers
    ap_file = vault / ".brain" / "assignments.json"
    assigned = json.loads(ap_file.read_text(encoding="utf-8")) if ap_file.exists() else {}
    tby = {t["name"]: t for t in topics}
    stamp = S["stamp"].format(d=TODAY)

    # ---- own profile URL (to tell my messages from theirs)
    me = ""
    for r in ex.rows("Invitations.csv"):
        if r.get("Direction") == "OUTGOING" and r.get("inviterProfileUrl"):
            me = norm_url(r["inviterProfileUrl"])
            break
    msgs = ex.rows("messages.csv")
    if not me and msgs:
        me = norm_url(collections.Counter(m["SENDER PROFILE URL"] for m in msgs).most_common(1)[0][0])

    # ---- CV
    prof = (ex.rows("Profile.csv") or [{}])[0]
    if prof and S["cv_path"]:
        L = [f"{S['source']}: {stamp}.", ""]
        if clean(prof.get("Headline")):
            L.append(f"**Headline:** {clean(prof['Headline'])}  ")
        if clean(prof.get("Summary")):
            L += ["", clean(prof["Summary"]), ""]
        L += ["", f"### {S['education']}"]
        for e in ex.rows("Education.csv"):
            span = f" {S['to']} ".join(x for x in (clean(e.get("Start Date")), clean(e.get("End Date"))) if x)
            extra = "; ".join(x for x in (clean(e.get("Degree Name")), clean(e.get("Activities"))) if x)
            L.append(f"- **{clean(e['School Name'])}**" + (f", {span}" if span else "") + (f". {extra}" if extra else ""))
        L += ["", f"### {S['positions']}"]
        for p in ex.rows("Positions.csv"):
            span = f" {S['to']} ".join(x for x in (clean(p.get("Started On")), clean(p.get("Finished On")) or S["present"]) if x)
            L.append(f"- **{clean(p['Company Name'])}**, {clean(p['Title'])}, {clean(p.get('Location'))}, {span}")
            if clean(p.get("Description")):
                L.append(f"  {clean(p['Description'])}")
        langs = ex.rows("Languages.csv")
        if langs:
            L += ["", f"### {S['languages']}"] + [f"- {clean(l['Name'])}: {clean(l.get('Proficiency'))}" for l in langs]
        skills = [clean(s["Name"]) for s in ex.rows("Skills.csv")]
        if skills:
            L += ["", f"### {S['skills']}", ", ".join(skills)]
        rel = S["cv_path"]
        text = read(vault / rel, f"---\ntype: cv\nstatus: active\ntags: [career, cv]\ncreated: {TODAY}\n---\n# {S['cv_title']}\n\n"
                    f"{S['cv_intro']}\n\n")
        text = set_block(set_frontmatter(text, {"updated": TODAY}), f"## {S['from_li']}\n" + "\n".join(L), before=S["back"])
        if f"[[{S['career']}]]" not in text:
            text = text.rstrip() + f"\n\n{S['back']} [[{S['career']}]]\n"
        W.write(rel, text)

    # ---- contacts
    people_dir = vault / "05 People"
    existing = {}
    for f in people_dir.rglob("*.md"):
        if re.search(r" \d+\.md$", f.name):  # ignore sync-conflict copies like "Name 2.md"
            continue
        existing.setdefault(f.stem, f)
    by_url = {}
    for f in existing.values():
        m = re.search(r'^linkedin: "([^"]+)"', f.read_text(encoding="utf-8"), re.M)
        if m and m.group(1):
            by_url[norm_url(m.group(1))] = f

    people, used, skipped = [], set(), 0
    for r in ex.rows("Connections.csv"):
        first, last = clean(r.get("First Name")), clean(r.get("Last Name"))
        name = safe_name(first, last)
        if not name or last.lower() in exclude:
            skipped += 1
            continue
        org, pos = clean(r.get("Company")).replace("|", "/"), clean(r.get("Position")).replace("|", "/")
        t = f"{org} | {pos}"
        sector = S["no_details"] if not org and not pos else next(n for n, rx in sectors if re.search(rx, t, re.I))
        if (sector in excl_sectors or name.lower() in excl_people
                or any(re.search(rx, org, re.I) for rx in excl_orgs)):
            skipped += 1
            continue
        url = r.get("URL", "")
        hit = assigned.get(norm_url(url)) if url else None
        if hit is not None:
            tp, reason = [tby[n] for n in hit["topics"] if n in tby], hit.get("reason", "")
        else:
            tp, reason = [x for x in topics if (x.get("regex") and re.search(x["regex"], t, re.I)) or sector in x.get("sectors", [])], ""
        path = by_url.get(norm_url(url)) if url else None
        if not path and name in existing:
            path = existing[name]
        if not path:
            n2 = name if name not in used else f"{name} ({org[:30] or 'LinkedIn'})"
            path = people_dir / sector / f"{n2}.md"
        used.add(path.stem)
        people.append(dict(name=path.stem, path=path, sector=sector, topics=tp, reason=reason, org=org, pos=pos, url=url,
                           since=parse_date(r.get("Connected On", "")), convs=[]))
    by_norm = {norm_url(p["url"]): p for p in people if p["url"]}

    # ---- messages (metadata only)
    conv = collections.defaultdict(list)
    for m in msgs:
        conv[m["CONVERSATION ID"]].append(m)
    recruiters = []
    for ms in conv.values():
        ms.sort(key=lambda m: m["DATE"])
        text = " ".join((m.get("CONTENT") or "") + " " + (m.get("SUBJECT") or "") for m in ms)
        tp = next((n for n, rx in msg_topics if re.search(rx, text, re.I)), None)
        mine = lambda m: norm_url(m["SENDER PROFILE URL"]) == me
        info = dict(n=len(ms), first=ms[0]["DATE"][:10], last=ms[-1]["DATE"][:10], tp=tp, by_me=mine(ms[0]),
                    answered=any(not mine(m) for m in ms) if mine(ms[0]) else any(mine(m) for m in ms))
        others = {}
        for m in ms:
            for u, n in zip([m["SENDER PROFILE URL"]] + m["RECIPIENT PROFILE URLS"].split(","),
                            [m["FROM"]] + m["TO"].split(",")):
                if u and norm_url(u) != me:
                    others[norm_url(u)] = clean(n)
        for u, n in others.items():
            if u in by_norm:
                by_norm[u]["convs"].append(info)
            elif tp == "Recruiting" and not info["by_me"]:
                recruiters.append((n, info))

    def conv_line(i):
        s = f"- {i['first']}" + (f" {S['to']} {i['last']}" if i["last"] != i["first"] else "")
        s += f": {i['n']} {S['messages'] if i['n'] > 1 else S['message']}" + (f", {S['topic']}: {i['tp']}" if i["tp"] else "")
        if i["by_me"]:
            s += f", {S['by_me']}, " + (S["reply"] if i["answered"] else S["no_reply"])
        else:
            s += f", {S['by_them']}" + ("" if i["answered"] else f", {S['not_answered']}")
        return s

    for p in people:
        rel = p["path"].relative_to(vault).as_posix()
        text = read(p["path"], f"---\ntype: person\nstatus: contact\ntags: [person, linkedin]\ncreated: {TODAY}\n---\n# {p['name']}\n\n"
                    f"{S['notes']}\n-\n\n{S['back']} [[05 People]]\n")
        fields = {"sector": q(p["sector"]), "topics": q([x["name"] for x in p["topics"]]),
                  "organization": q(p["org"]), "position": q(p["pos"]), "linkedin": q(p["url"]),
                  "connected_on": p["since"] or '""'}
        if p["convs"]:
            fields["last_contact"] = max(i["last"] for i in p["convs"])
        text = set_frontmatter(text, fields)
        role = ", ".join(x for x in (p["pos"], p["org"]) if x) or S["no_details_li"]
        blk = [f"**LinkedIn:** {role} · {S['sector']} [[{p['sector']}]]", "", S["good_for"]]
        blk += [f"- {x.get('link') or x['name']}" + (f" — {p['reason']}" if p["reason"] else "") for x in p["topics"]] or [f"- {S['no_topic']}"]
        if p["convs"]:
            blk += ["", S["history"]] + [conv_line(i) for i in sorted(p["convs"], key=lambda i: i["first"])]
        W.write(rel, set_block(text, "\n".join(blk), before=S["notes"]))

    # ---- overviews
    line = lambda p: (f"- [[{p['name']}]] — " + (", ".join(x for x in (p["pos"], p["org"]) if x) or S["no_details"])
                      + (f" · *{p['reason']}*" if p.get("reason") else ""))
    groups = collections.defaultdict(list)
    for p in people:
        groups[p["sector"]].append(p)
    order = [n for n, _ in sectors] + [S["no_details"]]
    for s in order:
        g = sorted(groups.get(s, []), key=lambda p: (p["org"].lower(), p["name"].lower()))
        if not g:
            continue
        rel = f"05 People/{s}/{s}.md"
        text = read(vault / rel, f"---\ntype: moc\nstatus: active\ntags: [moc, people]\ncreated: {TODAY}\n---\n# {s}\n\n")
        W.write(rel, set_block(text, S["moc_intro"].format(n=len(g), stamp=stamp) + "\n\n"
                               + "\n".join(line(p) for p in g) + f"\n\n{S['back']} [[05 People]] · [[{S['who']}]]"))

    w = ["---", "type: moc", "status: active", "tags: [moc, people, network]", f"updated: {TODAY}", "---", f"# {S['who']}", "",
         (S["who_intro_ai"].format(stamp=stamp, n=len(assigned)) if assigned else S["who_intro_kw"].format(stamp=stamp)) + S["who_fix"], ""]
    open_req = sorted([(p, i) for p in people for i in p["convs"] if i["by_me"] and not i["answered"]], key=lambda x: x[1]["first"])
    if open_req:
        w += [S["asked"], S["asked_intro"], ""]
        w += [f"- [[{p['name']}]] — {i['first']}" + (f", {i['tp']}" if i["tp"] else "") for p, i in open_req] + [""]
    for t in topics:
        g = sorted([p for p in people if t in p["topics"]], key=lambda p: (p["sector"], p["org"].lower()))
        if g:
            w += [f"## {t['name']} ({len(g)})"] + ([f"{S['project_area']}: {t['link']}"] if t.get("link") else []) + [""] + [line(p) for p in g] + [""]
    w += [S["all_sectors"]] + [f"- [[{s}]] ({len(groups[s])})" for s in order if groups.get(s)] + ["", f"{S['back']} [[05 People]]"]
    W.write(f"05 People/{S['who']}.md", "\n".join(w) + "\n")

    rel = "05 People/05 People.md"
    if (vault / rel).exists():
        W.write(rel, set_block(read(vault / rel, ""), S["network"] + "\n" +
                               "\n".join(f"- [[{s}]] ({len(groups[s])})" for s in order if groups.get(s))))

    # ---- career: recruiters, follows
    rel = S["rec_path"]
    if rel:
        text = read(vault / rel, f"---\ntype: list\nstatus: active\ntags: [career]\ncreated: {TODAY}\n---\n# {S['rec_title']}\n\n{S['rec_intro']}\n\n")
        rows = [S["rec_head"], "|---|---|---|---|---|"]
        rows += [f"| {i['first']} | {i['last']} | {n} | {i['n']} | " + (S["answered"] if i["answered"] else S["open"]) + " |"
                 for n, i in sorted(recruiters, key=lambda x: x[1]["first"], reverse=True)]
        W.write(rel, set_block(text, f"{S['source']}: {stamp}.\n\n" + ("\n".join(rows) if recruiters else S["rec_none"])))

    follows = [clean(r["FullName"]) for r in ex.rows("Member_Follows.csv") if r.get("Status") == "Active"]
    rel = S["con_path"]
    if rel:
        text = read(vault / rel, f"---\ntype: moc\nstatus: active\ntags: [career, network, linkedin]\ncreated: {TODAY}\n---\n# {S['con_title']}\n\n")
        blk = [f"{S['source']}: {stamp}. " + S["con_intro"].format(n=len(people), who=S["who"])]
        if skipped:
            blk.append(S["skipped"].format(n=skipped))
        if follows:
            blk += ["", S["follows"], ", ".join(follows)]
        W.write(rel, set_block(text, "\n".join(blk) + f"\n\n{S['back']} [[{S['career']}]]"))

    # ---- report
    print(f"{'(dry run) ' if a.dry_run else ''}{len(people)} contacts, {skipped} skipped, "
          f"{sum(1 for p in people if p['convs'])} with message history, {len(recruiters)} recruiter conversations")
    for s in order:
        if groups.get(s):
            print(f"  {s}: {len(groups[s])}")
    for t in topics:
        print(f"  topic {t['name']}: {sum(1 for p in people if t in p['topics'])}")
    c = collections.Counter(k for k, _ in W.changed)
    print(f"files: {c.get('new', 0)} new, {c.get('changed', 0)} changed")


if __name__ == "__main__":
    main()
