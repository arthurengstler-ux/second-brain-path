# Second Brain

Mein Second Brain liegt in `VAULT` (Obsidian-Vault, PARA-Struktur). Ein Hook loggt jede Dateiänderung automatisch in `.brain/activity.jsonl`. Zusätzlich gilt:

- Zu Beginn jeder Sitzung lädt ein SessionStart-Hook (`brain.py context`) einen Überblick über aktive Projekte, Fristen und letzte Arbeit. **Bevor du an einem Thema arbeitest, lies dessen Notiz im Vault und die Notiz `Dokumente <Thema>.md` im selben Ordner** (listet alle zugehörigen Dateien auf Desktop und Downloads).
- Legst du für ein Thema eine neue Datei an, benenne sie so, dass sie eine Regel in `.brain/projects.json` trifft (oder ergänze eine Regel).
- Bist du an einem Projekt inhaltlich weitergekommen, trag am Ende **einen** knappen Eintrag ein: `python3 VAULT/scripts/brain.py log "<Notizname>" "<was erledigt wurde>"` und ergänze die Projektnotiz unter `## Verlauf` (neueste oben).
- Haben sich nächster Schritt, Frist oder Status geändert, passe `next_step`, `deadline` oder `status` im Frontmatter der Projektnotiz an.
- Neue Projekte bekommen einen Ordner unter `01 Projects/` mit gleichnamiger Notiz (Vorlage `99 Templates/Vorlage Projekt.md`), einen Link in `01 Projects.md` und eine Pfad-Regel in `.brain/projects.json`.
- **Kontakte:** Geht es darum, wen ich zu einem Thema ansprechen könnte (Interview, Praktikum, Rat, Empfehlung), lies zuerst `05 People/Wen fragen.md`. Jede Person hat eine Notiz unter `05 People/<Bereich>/` mit `themen`, `organisation`, `position`, `linkedin` und `letzter_kontakt` im Frontmatter. Neue Erkenntnisse über eine Person dort unter `## Notizen` ergänzen, nie im `linkedin`-Block (der wird beim nächsten Import überschrieben).
- Keine privaten Inhalte ins Vault (Familie, Beziehung, Gesundheit). Fakten nicht erfinden, Lücken als `> [!todo] Zu ergänzen` markieren.
- Danach im Vault committen: `git -C VAULT add -A && git -C VAULT commit -m "<Projekt>: <kurz>"`.
