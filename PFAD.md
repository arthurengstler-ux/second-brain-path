# Der Pfad: Schritt für Schritt (Anleitung für Claude Code)

Diese Datei ist für Claude Code geschrieben, aber auch für Menschen lesbar. Claude arbeitet sie
der Reihe nach ab. Nach jedem Schritt fasst Claude in zwei Sätzen zusammen, was passiert ist,
und fragt nur dort nach, wo es um eine echte Entscheidung der Person geht.

`REPO` meint den Ordner, in dem dieses Repository liegt. `VAULT` ist der Ordner des Second Brain.

## Grundregeln für Claude

- **Nichts erfinden.** Lücken als `> [!todo] Zu ergänzen` markieren.
- **Nichts Privates ins Vault**, außer die Person will es ausdrücklich: Familie, Beziehung, Gesundheit, Inhalte privater Nachrichten.
- **Nie Ordner löschen und neu anlegen.** Notizen an Ort und Stelle ändern. Liegt das Vault in einem iCloud-Ordner wie `~/Documents`, erzeugt Löschen und Neuanlegen sonst Kopien der Form „Name 2.md“.
- Downloads wie den LinkedIn-Export nur lesen. Python mit `-I` aufrufen.
- Globale Einstellungen in `~/.claude/` nur nach Rückfrage ändern. Vorher eine Sicherungskopie anlegen.
- Nach jedem Schritt im Vault committen: `git -C VAULT add -A && git -C VAULT commit -m "<Schritt>: <kurz>"`.

## Schritt 0: Kennenlernen (5 Minuten)

Frag in **einer** Nachricht:
1. Wie heißt du? Das erscheint im Sitzungsüberblick, etwa „Max Musters Second Brain“.
2. Wo soll das Vault liegen? Vorschlag: `~/Documents/Second-Brain`.
3. Woran arbeitest du gerade? Projekte mit Ziel und Frist, zum Beispiel eine Abschlussarbeit, eine Bewerbung oder ein Start-up.
4. Welche Dauerthemen gibt es ohne Enddatum? Zum Beispiel Schule, Studium, Job, Politik, Sport.
5. Hast du deinen LinkedIn-Export schon? Wenn nicht, siehe Schritt 3. Er kann parallel laufen.
6. Benutzt du Obsidian? Das ist empfohlen, aber nicht nötig.

## Schritt 1: Vault anlegen

```bash
python3 -I REPO/scripts/setup_vault.py --vault VAULT --owner "<Name>s"
```

Das legt die PARA-Struktur an (`00 Inbox`, `01 Projects`, `02 Areas`, `03 Resources`, `04 Archive`, `05 People`, `99 Templates`), dazu `Home.md`, das Dashboard und ein git-Repo. Bestehende Dateien bleiben unangetastet.

Danach `Home.md` → `## Kurzprofil` mit den Antworten aus Schritt 0 füllen, sachlich, drei bis fünf Sätze.

## Schritt 2: Projekte und Bereiche

Für jedes Projekt aus Schritt 0:
- Ordner `01 Projects/<Projekt>/` mit gleichnamiger Notiz nach `99 Templates/Vorlage Projekt.md`
- im Frontmatter `status` (aktiv, geplant, Idee oder abgeschlossen), `deadline` (`2027-04-30`, `2027-06` oder `2027`) und `next_step` (ein konkreter Satz)
- ein Link in `01 Projects/01 Projects.md`

Für jedes Dauerthema: `02 Areas/<Thema>/<Thema>.md` anlegen und in `02 Areas.md` verlinken.

Dann frag: **Wo liegen die Dateien zu diesen Projekten?** Zum Beispiel `~/Desktop/Uni/Bachelorarbeit` oder Dateinamen mit `BA_`. Trag dafür Regeln in `VAULT/.brain/projects.json` ein. Ein Pfad-Präfix geht als `"match": "~/Desktop/Uni/Bachelorarbeit"`, ein Muster als `"regex": true`. Dann prüfen:

```bash
python3 VAULT/scripts/brain.py docs
```

Pro Projekt entsteht so `Dokumente <Projekt>.md`, eine Liste aller zugehörigen Dateien auf Desktop und in Downloads.

## Schritt 3: LinkedIn-Export holen

Falls noch nicht vorhanden, erklär der Person den Weg:
LinkedIn → **Ich** → **Einstellungen & Datenschutz** → **Datenschutz** → **Kopie Ihrer Daten abrufen**.
- **Basic** (die gewünschten Dateien auswählen, mindestens Verbindungen, Nachrichten, Profil, Positionen, Ausbildung, Kenntnisse) kommt nach etwa 10 Minuten.
- **Vollständiges Archiv** kommt nach bis zu 24 Stunden. Es enthält zusätzlich Einladungen und Follows.

Beides landet als ZIP in `~/Downloads`. Safari entpackt es manchmal automatisch. Ordner funktionieren genauso.

## Schritt 4: Themen festlegen

Erzeuge `VAULT/.brain/themen.json` nach dem Muster von `REPO/config/themen.example.json`:
- **ein Thema pro Projekt und Bereich aus Schritt 2**, mit `link` auf die Notiz, also `[[Projektname]]`
- `regex`: Begriffe, die in Firma oder Position eines hilfreichen Kontakts stehen würden. Denk breit: Bei einer Bachelorarbeit über Energiepolitik passen Energieversorger, Ministerien, Forschungsinstitute und Thinktanks.
- `bereiche`: ganze Bereiche, die immer passen, zum Beispiel `Diplomatie & Außenhandel` für eine Arbeit über Handelspolitik

Frag außerdem: **Gibt es Nachnamen, die ausgelassen werden sollen?** Meist ist das die Familie. Sie kommen nach `exclude_lastnames`.

## Schritt 5: Import

Erst einen Probelauf:

```bash
python3 -I REPO/scripts/import_linkedin.py --vault VAULT --config VAULT/.brain/themen.json \
  --zip ~/Downloads/Basic_LinkedInDataExport_*.zip ~/Downloads/Complete_LinkedInDataExport_* --dry-run
```

Zeig die Zahlen pro Bereich und Thema. Dann ohne `--dry-run` ausführen. Das Skript schreibt:

| Datei | Inhalt |
|---|---|
| `02 Areas/Karriere/Lebenslauf.md` | Profil, Ausbildung, Stationen, Sprachen, Skills |
| `05 People/<Bereich>/<Name>.md` | eine Notiz pro Kontakt: Rolle, Themen, Kontaktverlauf |
| `05 People/<Bereich>/<Bereich>.md` | Übersicht je Bereich |
| `05 People/Wen fragen.md` | Index: wen zu welchem Thema fragen, plus Anfragen ohne Antwort |
| `02 Areas/Karriere/Recruiter-Anfragen.md` | Recruiter-Nachrichten und ihr Status |
| `02 Areas/Karriere/LinkedIn-Kontakte.md` | Zahlen und Personen, denen du folgst |

**Qualitätskontrolle (wichtig):** Lies `Wen fragen.md` und nimm dir pro Thema fünf Stichproben vor. Was eindeutig falsch zugeordnet ist, korrigierst du über die Regex in `themen.json` und lässt den Import erneut laufen. Nicht von Hand in den generierten Listen ändern. Berichte der Person dann:
- die drei interessantesten Kontakte pro Projekt
- Anfragen ohne Antwort, die sich für eine Nachfrage eignen
- offene Recruiter-Anfragen

Bestehende Personennotizen derselben Person (gleicher Name oder gleiche LinkedIn-URL) werden ergänzt, nicht verdoppelt. Kommt später ein neuer Export, einfach erneut importieren. Das Skript ist idempotent.

## Schritt 6: Claude Code verbinden

Das ist der Schritt, der aus einem Notizordner ein Gedächtnis für Claude macht. **Vorher fragen, dann `~/.claude/settings.json` sichern.**

1. Die Hooks aus `REPO/claude/settings.hooks.json` in `~/.claude/settings.json` einfügen, mit `VAULT` als absolutem Pfad:
   - **SessionStart** → `brain.py context` lädt bei jedem Start einen Überblick: aktive Projekte, Fristen, nächste Schritte, letzte Arbeit.
   - **PostToolUse** → `brain.py hook` loggt jede Dateiänderung von Claude mit Projektbezug in `Claude-Aktivität.md`.
2. Den Text aus `REPO/claude/CLAUDE.snippet.md` an `~/.claude/CLAUDE.md` anhängen, ebenfalls mit `VAULT` ersetzt. Er sagt Claude, wann es welche Notiz lesen und wie es Fortschritt nachtragen soll.
3. Test: eine neue Claude-Code-Sitzung starten. Oben muss „<Name>s Second Brain“ mit den Projekten erscheinen.

## Schritt 7: Dashboard (optional, macOS und Obsidian)

- Obsidian → **Ordner als Vault öffnen** → `VAULT`. Unter **Einstellungen → Community-Plugins** den eingeschränkten Modus ausschalten und „Second Brain Dashboard“ aktivieren. Links erscheint ein Gehirn-Symbol, dahinter liegen ein Graph, Projektkarten, Fristen, offene Punkte und der Claude-Verlauf.
- Ohne Obsidian: `python3 VAULT/scripts/brain.py serve` → http://localhost:8765

## Schritt 8: Abschluss

Fasse für die Person zusammen:
- wie viele Notizen und Kontakte entstanden sind
- wo `Wen fragen.md` liegt
- welche drei Dinge aus dem Import sofort nützlich sind
- die Routine: einmal pro Woche die Weekly-Review-Liste in `Home.md` durchgehen. Bei Bedarf alle paar Monate einen neuen LinkedIn-Export holen und Schritt 5 wiederholen.

Letzter Commit im Vault: `Second Brain: Pfad abgeschlossen`.
