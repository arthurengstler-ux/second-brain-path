# Second brain

My second brain lives in `VAULT` (Obsidian vault, PARA structure). A hook logs every file change to `.brain/activity.jsonl`. In addition:

- At the start of every session a SessionStart hook (`brain.py context`) loads an overview of active projects, deadlines and recent work. **Before working on a topic, read its note in the vault and the note `Documents <topic>.md` in the same folder** (it lists all related files on Desktop, Downloads and Documents).
- When you create a new file for a topic, name it so it matches a rule in `.brain/projects.json` (or add a rule).
- When you made real progress on a project, add **one** short entry at the end: `PYTHON VAULT/scripts/brain.py log "<note name>" "<what was done>"` and add it to the project note under `## Log` (newest first).
- If the next step, a deadline or the status changed, update `next_step`, `deadline` or `status` (active, planned, idea, done) in the project note's frontmatter.
- New projects get a folder under `01 Projects/` with a note of the same name (template `99 Templates/Template Project.md`), a link in `01 Projects.md` and a path rule in `.brain/projects.json`.
- **Contacts:** When the question is who I could approach about something (interview, internship, advice, intro), read `05 People/Who to Ask.md` first. Every person has a note under `05 People/<sector>/` with `topics`, `organization`, `position`, `linkedin` and `last_contact` in the frontmatter. Add new information about a person under `## Notes`, never inside the `linkedin` block (it is overwritten on the next import).
- No private content in the vault (family, relationships, health). Never invent facts; mark gaps as `> [!todo] To fill in`.
- Afterwards commit in the vault: `git -C VAULT add -A && git -C VAULT commit -m "<project>: <short>"`.
