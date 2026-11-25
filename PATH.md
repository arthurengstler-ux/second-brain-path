# The path, step by step (instructions for Claude Code)

This file is written for Claude Code, but people can read it too. Claude works through it in order.
After each step Claude sums up in two sentences what happened, and only asks where the person
has to make a real decision.

`REPO` is the folder this repository lives in. `VAULT` is the folder of the second brain.
`PY` is the Python command for this machine (see step 0).

## Ground rules for Claude

- **Never invent facts.** Mark gaps as `> [!todo] To fill in`.
- **Nothing private in the vault** unless the person explicitly wants it: family, relationships, health, contents of private messages.
- **Never delete and recreate folders.** Edit notes in place. In synced folders (iCloud on macOS, OneDrive on Windows) delete-and-recreate produces duplicate “Name 2.md” files.
- Treat downloads such as the LinkedIn export as read-only data. Run Python with `-I`.
- Only change global settings in `~/.claude/` after asking, and back them up first.
- Commit in the vault after every step: `git -C VAULT add -A && git -C VAULT commit -m "<step>: <short>"`.
- Use forward slashes in paths inside notes and config. They work on every OS.

## Step 0: Check the machine and get to know the person (5 minutes)

**First, quietly check the tools.** The person should not have to deal with this.

| | macOS | Windows | Linux |
|---|---|---|---|
| Python (`PY`) | `python3` (ships with the Xcode command line tools) | `py -3` (Python launcher) | `python3` |
| check | `python3 --version` | `py -3 --version` | `python3 --version` |
| install if missing | `xcode-select --install` | `winget install Python.Python.3.12` | `sudo apt install python3` (or dnf/pacman) |
| git | `xcode-select --install` | `winget install Git.Git` | `sudo apt install git` |
| Obsidian | `brew install --cask obsidian` or obsidian.md | `winget install Obsidian.Obsidian` | Flatpak `md.obsidian.Obsidian` or AppImage from obsidian.md |
| default vault path | `~/Documents/Second-Brain` | `%USERPROFILE%\Documents\Second-Brain` | `~/Documents/Second-Brain` |

Only if something is missing: say what you want to install, ask once, then install it.
**Obsidian is required.** The vault is meant to be read and used in Obsidian, and the dashboard runs inside it.

Then ask in **one** message:
1. What is your name? It appears in the session overview, e.g. “Jane Doe's second brain”.
2. Where should the vault live? Suggest the default path from the table.
3. What are you working on right now? Projects with a goal and a deadline, e.g. a thesis, an application, a start-up.
4. Which ongoing areas do you have, without an end date? E.g. school, university, job, politics, sports.
5. Do you already have your LinkedIn export? If not, see step 3. It can run in parallel.

## Step 1: Create the vault and open it in Obsidian

```bash
PY -I REPO/scripts/setup_vault.py --vault VAULT --owner "<Name>'s"
```

This creates the PARA structure (`00 Inbox`, `01 Projects`, `02 Areas`, `03 Resources`, `04 Archive`, `05 People`, `99 Templates`), `Home.md`, the dashboard, the Obsidian plugin and a git repository. Existing files are left alone.

Fill `Home.md` → `## Profile` with the answers from step 0: factual, three to five sentences.

Then have the person open the vault in Obsidian:
**Obsidian → Open folder as vault → VAULT.** Then **Settings → Community plugins → Turn on community plugins**, and enable **“Second Brain Dashboard”**. A brain icon appears on the left. It opens the graph, project cards, deadlines, open items and the Claude history.

## Step 2: Projects and areas

For every project from step 0:
- create a folder `01 Projects/<Project>/` with a note of the same name based on `99 Templates/Template Project.md`
- in the frontmatter set `status` (active, planned, idea or done), `deadline` (`2027-04-30`, `2027-06` or `2027`) and `next_step` (one concrete sentence)
- add a link in `01 Projects/01 Projects.md`

For every ongoing area: create `02 Areas/<Area>/<Area>.md` and link it in `02 Areas.md`.

Then ask: **Where are the files for these projects?** E.g. `~/Desktop/Uni/Thesis` or file names starting with `BA_`. Add rules to `VAULT/.brain/projects.json`. A path prefix works as `"match": "~/Desktop/Uni/Thesis"`, a pattern with `"regex": true`. Then check:

```bash
PY VAULT/scripts/brain.py docs
```

This creates a note `Documents <Project>.md` per project, listing all related files on Desktop, Downloads and Documents.

## Step 3: Get the LinkedIn export

If it is not there yet, explain the way:
LinkedIn → **Me** → **Settings & Privacy** → **Data privacy** → **Get a copy of your data**.
- The **smaller archive** (pick connections, messages, profile, positions, education, skills) arrives after about 10 minutes.
- The **full archive** arrives within 24 hours. It also contains invitations and follows.

Both land as ZIP files in Downloads. Safari sometimes unzips them automatically. Folders work just as well.

## Step 4: Define the topics

Create `VAULT/.brain/topics.json` following `REPO/config/topics.example.json`:
- **one topic per project and area from step 2**, with `link` pointing to the note, i.e. `[[Project name]]`
- `regex`: words that would appear in the company or position of a helpful contact. Think broadly: for a thesis on energy policy, energy companies, ministries, research institutes and think tanks all fit.
- `sectors`: whole sectors that always fit, e.g. `Diplomacy & Trade` for a thesis on trade policy

Also ask: **Are there last names to leave out?** Usually family. They go into `exclude_lastnames`.

## Step 5: Import

Dry run first:

```bash
PY -I REPO/scripts/import_linkedin.py --vault VAULT --config VAULT/.brain/topics.json \
  --zip <Downloads>/Basic_LinkedInDataExport_<date>.zip <Downloads>/Complete_LinkedInDataExport_<date>.zip --dry-run
```

Show the numbers per sector and topic. Then run it without `--dry-run`. The script writes:

| File | Content |
|---|---|
| `02 Areas/Career/CV.md` | profile, education, positions, languages, skills |
| `05 People/<Sector>/<Name>.md` | one note per contact: role, topics, contact history |
| `05 People/<Sector>/<Sector>.md` | overview per sector |
| `05 People/Who to Ask.md` | index: who to ask about which topic, plus requests without a reply |
| `02 Areas/Career/Recruiter Messages.md` | recruiter messages and their status |
| `02 Areas/Career/LinkedIn Contacts.md` | numbers and people you follow |

**Quality check (important):** Read `Who to Ask.md` and spot-check five people per topic. Fix clear mismatches through the regex in `topics.json` and run the import again. Do not edit the generated lists by hand. Then report to the person:
- the three most interesting contacts per project
- requests without a reply that are worth a follow-up
- open recruiter messages

Existing notes of the same person (same name or same LinkedIn URL) are updated, never duplicated. When a newer export comes in, just import again. The script is idempotent.

## Step 6: Connect Claude Code

This is the step that turns a folder of notes into a memory for Claude. **Ask first, then back up `~/.claude/settings.json`.**

1. Merge the hooks into `~/.claude/settings.json`, with `VAULT` replaced by the absolute path:
   - macOS and Linux: `REPO/claude/settings.hooks.json`
   - Windows: `REPO/claude/settings.hooks.windows.json` (uses `py -3`)

   **SessionStart** → `brain.py context` loads an overview at every start: active projects, deadlines, next steps, recent work.
   **PostToolUse** → `brain.py hook` logs every file Claude changes, with its project, to `Claude Activity.md`.
2. Append `REPO/claude/CLAUDE.snippet.md` to `~/.claude/CLAUDE.md`, replacing `VAULT` and `PYTHON`. This tells Claude when to read which note and how to record progress.
3. Test: start a new Claude Code session. “<Name>'s second brain” with the projects must appear at the top.

## Step 7: Wrap-up

Sum up for the person:
- how many notes and contacts were created
- where `Who to Ask.md` is
- three things from the import that are useful right away
- the routine: once a week, go through the weekly review list in `Home.md`. Every few months, get a new LinkedIn export and repeat step 5.

Final commit in the vault: `Second brain: path completed`.
