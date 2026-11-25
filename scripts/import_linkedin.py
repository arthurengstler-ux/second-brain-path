#!/usr/bin/env python3
"""LinkedIn-Datenexport -> Obsidian-Second-Brain.

    python3 -I scripts/import_linkedin.py --vault ~/Documents/Second-Brain \
        --zip ~/Downloads/Basic_LinkedInDataExport_*.zip ~/Downloads/Complete_LinkedInDataExport_*.zip \
        --config config/themen.json [--exclude-lastname Muster] [--dry-run]

Was passiert:
  * 02 Areas/Karriere/Lebenslauf.md      Profil, Ausbildung, Stationen, Sprachen, Skills
  * 05 People/<Bereich>/<Name>.md         eine Notiz pro Kontakt, mit Bereich, Themen, Kontaktverlauf
  * 05 People/<Bereich>/<Bereich>.md      Übersicht je Bereich
  * 05 People/Wen fragen.md               Index: wen zu welchem Thema ansprechen
  * 02 Areas/Karriere/Recruiter-Anfragen.md, LinkedIn-Kontakte.md

Sicherheitsregeln:
  * Das ZIP wird nur gelesen, nie entpackt.
  * Es wird nichts gelöscht und kein Ordner neu angelegt, der schon existiert
    (wichtig bei iCloud-synchronisierten Ordnern: Löschen + Neuanlegen erzeugt „Name 2.md“-Kopien).
  * In bestehenden Notizen ändert das Skript nur Frontmatter-Felder, die es selbst setzt,
    und den Block zwischen <!-- linkedin:start --> und <!-- linkedin:end -->. Eigene Notizen bleiben stehen.
  * Nachrichteninhalte werden nicht übernommen, nur Datum, Anzahl, Thema und ob geantwortet wurde.
  * Erneut ausführen mit neuerem Export aktualisiert alles (idempotent).

Nur Python-Standardbibliothek.
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

DEFAULT_BEREICHE = [
    ["Militär & Sicherheit", r"bundesheer|bundeswehr|armed forces|armee|defen[cs]e|militär|military|polizei|police|\bmiliz"],
    ["Diplomatie & Außenhandel", r"advantage austria|embassy|botschaft|konsulat|consulate|ambassador|diplomat|\bMFA\b|auswärtig|foreign (office|affairs)|united nations|permanent mission|council of europe|conseil de l|\bOSCE\b|\bOSZE\b|trade commission|wirtschaftsdeleg|commercial (attach|counsel)"],
    ["Politik & Verwaltung", r"parlament|parliament|bundestag|nationalrat|ministerium|ministry|kanzleramt|regierung|landesrat|partei|\bpolitic|politik|gemeinderat|bezirk|magistrat|stadt wien|\brepublik|staatssekret|minister|abgeordnet|government|european commission|wirtschaftskammer|\bWKO\b|\bIHK\b|industriellenverein|verband"],
    ["Recht", r"anwalt|rechtsanw|\blaw\b|legal|notar|jurist|kanzlei"],
    ["Finanz & Beratung", r"bank|goldman|\bEY\b|KPMG|PwC|deloitte|mckinsey|\bBCG\b|\bbain\b|capital|financ|treuhand|steuer|\btax\b|invest|fonds|\bfund|audit|revision|consult|advisory|asset manag|leasing|wealth|M&A|versicher|insurance"],
    ["Wissenschaft & Hochschulen", r"universit|\bWU\b|institut|research|forschung|hochschule|professor|\bETH\b|college|academy of"],
    ["Medien & Kommunikation", r"media|medien|zeitung|presse|journal|redakt|podcast|verlag|marketing|\bPR\b|kommunikation|communication|\bORF\b|\bARD\b|\bZDF\b|\bSRF\b"],
    ["Schule & Bildung", r"schule|gymnas|lycée|lycee|school|bildung|akademie|tutor|nachhilfe|teacher|lehrer"],
    ["Immobilien & Bau", r"immobil|real estate|realit|property|\bbau|architekt|interiors|hausverwalt"],
    ["Medizin & Gesundheit", r"medic|medizin|ordination|\barzt|ärzt|klinik|clinic|hospital|spital|pharma|dr\. ?med|psychiatr|rotes kreuz|red cross|pflege"],
    ["Sport", r"sport|athlet|football|fußball|olymp|übungsleiter|\bcoach"],
    ["Tech & IT", r"software|\btech|\bIT\b|\bAWS\b|amazon|google|microsoft|developer|engineer|\bAI\b|\bKI\b|data|cloud|digital"],
    ["Gründer & Start-ups", r"founder|gründer|start-?up|\bCEO\b|geschäftsführ|managing director|owner|inhaber|unternehmer|entrepreneur"],
    ["Unternehmen & Handel", r"."],
]
DEFAULT_NACHRICHTEN = [
    ["Recruiting", r"recruit|we're (still )?looking for|wir suchen|sales development|business development representative|open position|offene stelle"],
    ["Interview-Anfrage", r"\binterview\b"],
    ["Praktikum/Internship", r"praktikum|internship|werkstudent"],
]


# ---------------------------------------------------------------- Einlesen
class Export:
    """Mehrere ZIPs; spätere überschreiben gleichnamige Dateien früherer."""

    def __init__(self, paths):
        self.files = {}
        for p in paths:
            if os.path.isdir(p):   # Safari entpackt ZIPs oft automatisch
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
        # Connections.csv hat vor dem Header ein paar Hinweiszeilen
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


def fname(first, last):
    n = clean(f"{first} {last}")
    n = re.sub(r"\s+[-|–]\s+.*$", "", n)                 # „Name - Slogan“
    n = re.sub(r"[\\/:*?\"<>|#^\[\]]", "", n)
    n = re.sub(r"[^\w\s.\-'()&,]", "", n, flags=re.U)  # Emojis
    n = re.sub(r"[぀-ヿ一-鿿가-힯]+", "", n)  # CJK-Zusätze
    return clean(n).strip(".")


def de(d):
    return f"{d[8:10]}.{d[5:7]}.{d[:4]}" if len(d) >= 10 else d


def parse_date(s):
    for f in ("%d %b %Y", "%Y-%m-%d"):
        try:
            return dt.datetime.strptime(s.strip(), f).date().isoformat()
        except ValueError:
            pass
    return ""


# ---------------------------------------------------------------- Notizen schreiben
class Writer:
    def __init__(self, vault, dry):
        self.vault, self.dry, self.changed = vault, dry, []

    def write(self, rel, text):
        p = self.vault / rel
        old = p.read_text(encoding="utf-8") if p.exists() else None
        if old == text:
            return
        self.changed.append(("neu" if old is None else "geändert", rel))
        if not self.dry:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")


def q(v):
    return json.dumps(v, ensure_ascii=False)


def set_frontmatter(text, fields):
    """Setzt Felder im YAML-Frontmatter (einzeilig), legt Frontmatter bei Bedarf an."""
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        head, body = [], text
    else:
        head, body = m.group(1).splitlines(), text[m.end():]
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
    """Ersetzt den linkedin-Block oder fügt ihn ein (vor `before`, sonst ans Ende)."""
    new = f"{START}\n{block.strip()}\n{END}"
    if START in text and END in text:
        return re.sub(re.escape(START) + r".*?" + re.escape(END), lambda _: new, text, flags=re.S)
    if before and before in text:
        return text.replace(before, new + "\n\n" + before, 1)
    return text.rstrip() + "\n\n" + new + "\n"


# ---------------------------------------------------------------- Hauptteil
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--vault", required=True)
    ap.add_argument("--zip", nargs="+", required=True, help="Basic- und/oder Complete-Export als ZIP oder entpackter Ordner (älter zuerst)")
    ap.add_argument("--config", help="themen.json (siehe config/themen.example.json)")
    ap.add_argument("--exclude-lastname", action="append", default=[], help="z. B. Familie; mehrfach möglich")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    vault = Path(os.path.expanduser(a.vault)).resolve()
    if not (vault / "05 People").is_dir():
        sys.exit(f"{vault} sieht nicht nach einem Second-Brain-Vault aus (05 People fehlt). Erst setup_vault.py ausführen.")
    cfg = json.loads(Path(a.config).read_text(encoding="utf-8")) if a.config else {}
    bereiche = cfg.get("bereiche") or DEFAULT_BEREICHE
    themen = cfg.get("themen", [])
    msg_topics = cfg.get("nachrichten_themen") or DEFAULT_NACHRICHTEN
    exclude = {x.lower() for x in a.exclude_lastname + cfg.get("exclude_lastnames", [])}
    ex = Export([os.path.expanduser(z) for z in a.zip])
    W = Writer(vault, a.dry_run)
    stamp = f"LinkedIn-Export, importiert {de(TODAY)}"

    # ---- eigene Profil-URL (für Nachrichten)
    me = ""
    for r in ex.rows("Invitations.csv"):
        if r.get("Direction") == "OUTGOING" and r.get("inviterProfileUrl"):
            me = norm_url(r["inviterProfileUrl"])
            break
    msgs = ex.rows("messages.csv")
    if not me and msgs:
        me = norm_url(collections.Counter(m["SENDER PROFILE URL"] for m in msgs).most_common(1)[0][0])

    # ---- Lebenslauf
    prof = (ex.rows("Profile.csv") or [{}])[0]
    if prof:
        L = [f"Quelle: {stamp}.", ""]
        if clean(prof.get("Headline")):
            L.append(f"**Headline:** {clean(prof['Headline'])}  ")
        if clean(prof.get("Summary")):
            L += ["", clean(prof["Summary"]), ""]
        L += ["", "### Ausbildung"]
        for e in ex.rows("Education.csv"):
            span = " bis ".join(x for x in (clean(e.get("Start Date")), clean(e.get("End Date"))) if x)
            extra = "; ".join(x for x in (clean(e.get("Degree Name")), clean(e.get("Activities"))) if x)
            L.append(f"- **{clean(e['School Name'])}**" + (f", {span}" if span else "") + (f". {extra}" if extra else ""))
        L += ["", "### Stationen"]
        for p in ex.rows("Positions.csv"):
            span = " bis ".join(x for x in (clean(p.get("Started On")), clean(p.get("Finished On")) or "heute") if x)
            L.append(f"- **{clean(p['Company Name'])}**, {clean(p['Title'])}, {clean(p.get('Location'))}, {span}")
            if clean(p.get("Description")):
                L.append(f"  {clean(p['Description'])}")
        langs = ex.rows("Languages.csv")
        if langs:
            L += ["", "### Sprachen"] + [f"- {clean(l['Name'])}: {clean(l.get('Proficiency'))}" for l in langs]
        skills = [clean(s["Name"]) for s in ex.rows("Skills.csv")]
        if skills:
            L += ["", "### Skills", ", ".join(skills)]
        rel = "02 Areas/Karriere/Lebenslauf.md"
        p = vault / rel
        text = p.read_text(encoding="utf-8") if p.exists() else (
            f"---\ntype: lebenslauf\nstatus: aktiv\ntags: [karriere, lebenslauf]\ncreated: {TODAY}\n---\n# Lebenslauf\n\n"
            "Eigene Ergänzungen (Projekte, Engagement) außerhalb des LinkedIn-Blocks schreiben.\n\n")
        text = set_block(set_frontmatter(text, {"updated": TODAY}), "## Aus LinkedIn\n" + "\n".join(L), before="Zurück zu")
        if "[[Karriere]]" not in text:
            text = text.rstrip() + "\n\nZurück zu [[Karriere]]\n"
        W.write(rel, text)

    # ---- Kontakte
    people_dir = vault / "05 People"
    existing = {}
    for f in people_dir.rglob("*.md"):
        if re.search(r" \d+\.md$", f.name):   # iCloud-Konfliktkopien ignorieren
            continue
        existing.setdefault(f.stem, f)
    by_url = {}
    for stem, f in existing.items():
        m = re.search(r'^linkedin: "([^"]+)"', f.read_text(encoding="utf-8"), re.M)
        if m and m.group(1):
            by_url[norm_url(m.group(1))] = f

    people, used, skipped = [], set(), 0
    for r in ex.rows("Connections.csv"):
        first, last = clean(r.get("First Name")), clean(r.get("Last Name"))
        name = fname(first, last)
        if not name:
            skipped += 1
            continue
        if last.lower() in exclude:
            skipped += 1
            continue
        org, pos = clean(r.get("Company")).replace("|", "/"), clean(r.get("Position")).replace("|", "/")
        t = f"{org} | {pos}"
        b = "Ohne Angabe" if not org and not pos else next(n for n, rx in bereiche if re.search(rx, t, re.I))
        th = [x for x in themen if (x.get("regex") and re.search(x["regex"], t, re.I)) or b in x.get("bereiche", [])]
        url = r.get("URL", "")
        path = by_url.get(norm_url(url)) if url else None
        if not path and name in existing:
            path = existing[name]
        if not path:
            n2 = name if name not in used else f"{name} ({org[:30] or 'LinkedIn'})"
            path = people_dir / b / f"{n2}.md"
        used.add(path.stem)
        people.append(dict(name=path.stem, path=path, bereich=b, themen=th, org=org, pos=pos, url=url,
                           since=parse_date(r.get("Connected On", "")), convs=[]))
    by_norm = {norm_url(p["url"]): p for p in people if p["url"]}

    # ---- Nachrichten (nur Metadaten)
    conv = collections.defaultdict(list)
    for m in msgs:
        conv[m["CONVERSATION ID"]].append(m)
    recruiters = []
    for cid, ms in conv.items():
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
        s = f"- {de(i['first'])}" + (f" bis {de(i['last'])}" if i["last"] != i["first"] else "")
        s += f": {i['n']} Nachricht{'en' if i['n'] > 1 else ''}" + (f", Thema {i['tp']}" if i["tp"] else "")
        if i["by_me"]:
            s += ", von mir begonnen, " + ("Antwort erhalten" if i["answered"] else "**keine Antwort**")
        else:
            s += ", vom Gegenüber begonnen" + ("" if i["answered"] else ", **noch nicht beantwortet**")
        return s

    for p in people:
        rel = p["path"].relative_to(vault)
        text = p["path"].read_text(encoding="utf-8") if p["path"].exists() else (
            f"---\ntype: person\nstatus: kontakt\ntags: [person, linkedin]\ncreated: {TODAY}\n---\n# {p['name']}\n\n"
            f"## Notizen\n-\n\nZurück zu [[05 People]]\n")
        fields = {"bereich": q(p["bereich"]), "themen": q([x["name"] for x in p["themen"]]),
                  "organisation": q(p["org"]), "position": q(p["pos"]), "linkedin": q(p["url"]),
                  "verbunden_seit": p["since"] or '""'}
        if p["convs"]:
            fields["letzter_kontakt"] = max(i["last"] for i in p["convs"])
        text = set_frontmatter(text, fields)
        rolle = ", ".join(x for x in (p["pos"], p["org"]) if x) or "keine Angabe auf LinkedIn"
        blk = [f"**LinkedIn:** {rolle} · Bereich [[{p['bereich']}]]", "", "## Ansprechpartner für"]
        blk += [f"- {x.get('link') or x['name']}" for x in p["themen"]] or ["- noch kein Thema zugeordnet"]
        if p["convs"]:
            blk += ["", "## Kontaktverlauf (LinkedIn-Nachrichten)"] + [conv_line(i) for i in sorted(p["convs"], key=lambda i: i["first"])]
        text = set_block(text, "\n".join(blk), before="## Notizen")
        W.write(str(rel), text)

    # ---- Übersichten
    line = lambda p: f"- [[{p['name']}]] — " + (", ".join(x for x in (p["pos"], p["org"]) if x) or "ohne Angabe")
    groups = collections.defaultdict(list)
    for p in people:
        groups[p["bereich"]].append(p)
    order = [n for n, _ in bereiche] + ["Ohne Angabe"]
    for b in order:
        g = sorted(groups.get(b, []), key=lambda p: (p["org"].lower(), p["name"].lower()))
        if not g:
            continue
        rel = f"05 People/{b}/{b}.md"
        p = vault / rel
        text = p.read_text(encoding="utf-8") if p.exists() else (
            f"---\ntype: moc\nstatus: aktiv\ntags: [moc, people]\ncreated: {TODAY}\n---\n# {b}\n\n")
        W.write(rel, set_block(text, f"{len(g)} Kontakte, sortiert nach Organisation. Quelle: {stamp}.\n\n" + "\n".join(line(p) for p in g)
                               + "\n\nZurück zu [[05 People]] · [[Wen fragen]]"))

    w = ["---", "type: moc", "status: aktiv", "tags: [moc, people, netzwerk]", f"updated: {TODAY}", "---", "# Wen fragen", "",
         f"Automatisch erzeugt aus dem {stamp}. Zuordnung über Firma und Position, also ein Vorschlag. "
         "Fehler in der Personennotiz korrigieren (Frontmatter `themen`), nicht hier.", ""]
    open_req = sorted([(p, i) for p in people for i in p["convs"] if i["by_me"] and not i["answered"]], key=lambda x: x[1]["first"])
    if open_req:
        w += ["## Angefragt, keine Antwort", "Kandidaten für eine Nachfrage.", ""]
        w += [f"- [[{p['name']}]] — {de(i['first'])}" + (f", {i['tp']}" if i["tp"] else "") for p, i in open_req] + [""]
    for t in themen:
        g = sorted([p for p in people if t in p["themen"]], key=lambda p: (p["bereich"], p["org"].lower()))
        if g:
            w += [f"## {t['name']} ({len(g)})"] + ([f"Projekt/Bereich: {t['link']}"] if t.get("link") else []) + [""] + [line(p) for p in g] + [""]
    w += ["## Alle Bereiche"] + [f"- [[{b}]] ({len(groups[b])})" for b in order if groups.get(b)] + ["", "Zurück zu [[05 People]]"]
    W.write("05 People/Wen fragen.md", "\n".join(w) + "\n")

    rel = "05 People/05 People.md"
    p = vault / rel
    if p.exists():
        W.write(rel, set_block(p.read_text(encoding="utf-8"), "## LinkedIn-Netzwerk nach Bereich\n" +
                               "\n".join(f"- [[{b}]] ({len(groups[b])})" for b in order if groups.get(b))))

    # ---- Karriere: Recruiter, Follows
    rel = "02 Areas/Karriere/Recruiter-Anfragen.md"
    p = vault / rel
    text = p.read_text(encoding="utf-8") if p.exists() else (
        f"---\ntype: liste\nstatus: aktiv\ntags: [karriere]\ncreated: {TODAY}\n---\n# Recruiter-Anfragen\n\n"
        "Firma und Stelle stehen in der Nachricht auf LinkedIn. Eigene Einschätzung unter dem Block ergänzen.\n\n")
    rows = ["| Erste Nachricht | Letzte | Von | Nachrichten | Status |", "|---|---|---|---|---|"]
    rows += [f"| {de(i['first'])} | {de(i['last'])} | {n} | {i['n']} | " + ("beantwortet" if i["answered"] else "**offen**") + " |"
             for n, i in sorted(recruiters, key=lambda x: x[1]["first"], reverse=True)]
    W.write(rel, set_block(text, f"Quelle: {stamp}.\n\n" + ("\n".join(rows) if recruiters else "Keine Recruiter-Nachrichten gefunden.")))

    follows = [clean(r["FullName"]) for r in ex.rows("Member_Follows.csv") if r.get("Status") == "Active"]
    rel = "02 Areas/Karriere/LinkedIn-Kontakte.md"
    p = vault / rel
    text = p.read_text(encoding="utf-8") if p.exists() else (
        f"---\ntype: moc\nstatus: aktiv\ntags: [karriere, netzwerk, linkedin]\ncreated: {TODAY}\n---\n# LinkedIn-Kontakte\n\n")
    blk = [f"Quelle: {stamp}. {len(people)} Kontakte als Personennotizen in [[05 People]], Themen-Index [[Wen fragen]]."]
    if skipped:
        blk.append(f"{skipped} Kontakte bewusst ausgelassen (ohne Namen oder per --exclude-lastname).")
    if follows:
        blk += ["", "## Gefolgte Personen (ohne Vernetzung)", ", ".join(follows)]
    W.write(rel, set_block(text, "\n".join(blk) + "\n\nZurück zu [[Karriere]]"))

    # ---- Bericht
    print(f"{'(Probelauf) ' if a.dry_run else ''}{len(people)} Kontakte, {skipped} ausgelassen, "
          f"{sum(1 for p in people if p['convs'])} mit Nachrichtenverlauf, {len(recruiters)} Recruiter-Gespräche")
    for b in order:
        if groups.get(b):
            print(f"  {b}: {len(groups[b])}")
    for t in themen:
        print(f"  Thema {t['name']}: {sum(1 for p in people if t in p['themen'])}")
    c = collections.Counter(k for k, _ in W.changed)
    print(f"Dateien: {c.get('neu', 0)} neu, {c.get('geändert', 0)} geändert")


if __name__ == "__main__":
    main()
