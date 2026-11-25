# The path, step by step (instructions for Claude Code)

This file is written for Claude Code, but people can read it too. Claude works through it in order.
After each step Claude sums up in two sentences what happened, and only asks where the person
has to make a real decision.

`REPO` is the folder this repository lives in. `VAULT` is the folder of the second brain.
`PY` is the Python command for this machine (see step 0).

## Ground rules for Claude

- **Never invent facts.** Mark gaps as `> [!todo] To fill in`.
- **The person decides what goes in.** Nothing from their history or network lands in the vault without being shown first. Anything marked private stays out for good (`VAULT/.brain/private.json`).
- **Nothing private in the vault** unless the person explicitly wants it: family, relationships, health, contents of conversations or messages.
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
5. Do you already have your LinkedIn export? If not, see step 4. It can run in parallel.
6. Have you used the Claude app or claude.ai in the browser? If yes, **request the export now** (see “Claude app export” below), because it arrives by email and can take a while. Both exports can be requested right at the start and run in the background while you work through steps 1 to 3.

## Step 1: Create the vault and open it in Obsidian

```bash
PY -I REPO/scripts/setup_vault.py --vault VAULT --owner "<Name>'s"
```

This creates the PARA structure (`00 Inbox`, `01 Projects`, `02 Areas`, `03 Resources`, `04 Archive`, `05 People`, `99 Templates`), `Home.md`, the dashboard, the Obsidian plugin and a git repository. Existing files are left alone.

Fill `Home.md` → `## Profile` with the answers from step 0: factual, three to five sentences.

Then have the person open the vault in Obsidian:
**Obsidian → Open folder as vault → VAULT.** Then **Settings → Community plugins → Turn on community plugins**, and enable **“Second Brain Dashboard”**. A brain icon appears on the left. It opens the graph, project cards, deadlines, open items and the Claude history.

## Step 2: Bring in what you already did with Claude

There are two sources. Use whichever the person has, or both.

**Claude Code** keeps its history on the computer (`~/.claude/projects/`). Nothing to request.

**Claude app export.** The Claude desktop app, the mobile app and claude.ai in the browser keep chats on Anthropic's servers, not on the computer. **No command can read them directly, so the person has to request an export.** Explain it like this:

1. Open claude.ai in the browser or the Claude desktop app.
2. Click your name or initials (bottom left) → **Settings** → **Privacy** → **Export data**.
3. Anthropic sends an email with a download link. Download the ZIP (it is called something like `data-2026-11-25-....zip`) and save it, usually in Downloads. Download it soon, the link does not stay valid forever.
4. On a Team or Enterprise plan, only owners or admins may be able to export. Then use Claude Code history only, or ask the admin.

The ZIP contains `conversations.json` (all chats) and `projects.json` (app projects). The script reads only titles, dates and which project a chat belongs to. Chat texts and project files are never read into the vault. Safari may unzip it automatically; the folder works too.

Then scan (leave out `--claude-export` if there is no app export):

```bash
PY -I REPO/scripts/sources.py scan --vault VAULT --claude-export <Downloads>/data-<date>.zip
```

This lists **candidates**:
- folders and git repos Claude Code worked in, with session titles and dates
- Claude Code sessions that could not be tied to a folder
- **app projects** from the Claude app, with the titles of their chats
- **single app chats** outside a project
- memory files and the global `CLAUDE.md`

Only metadata is read: titles, dates, file paths. Conversation contents are never read or copied.

**Many single chats?** Group them before asking: read the titles, suggest a handful of topics (e.g. “Internship search: 12, 15–18”) and ask the person to confirm. Chats about health, family or relationships: suggest `private` or `drop`, never a project.

**Show the list to the person exactly as printed, then ask for a decision on every line.** Offer these choices and explain them in one sentence each:

| Choice | Effect |
|---|---|
| `project` (optionally `project:New name`) | note in `01 Projects` with the session list, files of that folder get linked to it |
| `area` | the same, in `02 Areas` (no end date) |
| `keep` | memory or instruction file is copied to `03 Resources/Claude Memory` |
| `private` | never written to the vault; the folder is excluded from logging and document scans |
| `drop` | ignored |

Merge the answers with the step 0 answers (a project from step 0 that matches a candidate is the same project; use the person's name for it). Then:

```bash
PY -I REPO/scripts/sources.py decide --vault VAULT 1=project 2=project:"Thesis" 3=private 4=drop 9=keep 12,15-18=project:"Internship search"
PY -I REPO/scripts/sources.py apply  --vault VAULT
```

Several numbers with the same name become one note. A Claude Code folder and an app project about the same thing can be merged that way, too. Running `scan` again later keeps earlier decisions and only adds new candidates; app candidates are kept even if the export is not passed again.

## Step 3: Projects and areas

For every project from step 0 that does not have a note yet:
- create a folder `01 Projects/<Project>/` with a note of the same name based on `99 Templates/Template Project.md`
- add a link in `01 Projects/01 Projects.md`

For **every** project note, set in the frontmatter `status` (active, planned, idea or done), `deadline` (`2027-04-30`, `2027-06` or `2027`) and `next_step` (one concrete sentence). Ask the person where you cannot tell. Fill `## Goal`.

For every ongoing area: create `02 Areas/<Area>/<Area>.md` and link it in `02 Areas.md`.

Then ask: **Where are the files for these projects?** E.g. `~/Desktop/Uni/Thesis` or file names starting with `BA_`. Add rules to `VAULT/.brain/projects.json`. A path prefix works as `"match": "~/Desktop/Uni/Thesis"`, a pattern with `"regex": true`. Private rules (`"project": ""`) from step 2 stay first. Then check:

```bash
PY VAULT/scripts/brain.py docs
```

This creates a note `Documents <Project>.md` per project, listing all related files on Desktop, Downloads and Documents.

## Step 4: Get the LinkedIn export

If it is not there yet, explain the way:
LinkedIn → **Me** → **Settings & Privacy** → **Data privacy** → **Get a copy of your data**.
- The **smaller archive** (pick connections, messages, profile, positions, education, skills) arrives after about 10 minutes.
- The **full archive** arrives within 24 hours. It also contains invitations and follows.

Both land as ZIP files in Downloads. Safari sometimes unzips them automatically. Folders work just as well.

## Step 5: Topics and what to leave out

Create `VAULT/.brain/topics.json` following `REPO/config/topics.example.json`:
- **one topic per project and area from steps 2 and 3**, with `link` pointing to the note, i.e. `[[Project name]]`. Leave out topics marked private.
- `regex`: words that would appear in the company or position of a helpful contact. Think broadly: for a thesis on energy policy, energy companies, ministries, research institutes and think tanks all fit.
- `sectors`: whole sectors that always fit, e.g. `Diplomacy & Trade` for a thesis on trade policy

Then do a dry run (step 6, `--dry-run`) and show the person the numbers per sector and topic. **Ask what to leave out:**
- `exclude_lastnames`: usually family
- `exclude_people`: individual people, full name
- `exclude_organizations`: employers or companies (regex), e.g. a former employer
- `exclude_sectors`: whole sectors, e.g. `Health & Medicine`
- topics the person does not want: remove them from `topics`

## Step 6: Import

```bash
PY -I REPO/scripts/import_linkedin.py --vault VAULT --config VAULT/.brain/topics.json \
  --zip <Downloads>/Basic_LinkedInDataExport_<date>.zip <Downloads>/Complete_LinkedInDataExport_<date>.zip --dry-run
```

When the numbers look right, run it again without `--dry-run`. The script writes:

| File | Content |
|---|---|
| `02 Areas/Career/CV.md` | profile, education, positions, languages, skills |
| `05 People/<Sector>/<Name>.md` | one note per contact: role, topics, contact history |
| `05 People/<Sector>/<Sector>.md` | overview per sector |
| `05 People/Who to Ask.md` | index: who to ask about which topic, plus requests without a reply |
| `02 Areas/Career/Recruiter Messages.md` | recruiter messages and their status |
| `02 Areas/Career/LinkedIn Contacts.md` | numbers and people you follow |

**Quality check (important):** Read `Who to Ask.md` and spot-check five people per topic. Fix clear mismatches through `topics.json` and run the import again. Do not edit the generated lists by hand. If something should have been excluded but was already imported, tell the person which notes to delete; the script itself never deletes. Then report:
- the three most interesting contacts per project
- requests without a reply that are worth a follow-up
- open recruiter messages

Existing notes of the same person (same name or same LinkedIn URL) are updated, never duplicated. When a newer export comes in, just import again. The script is idempotent.

## Step 7: Connect Claude Code

This is the step that turns a folder of notes into a memory for Claude. **Ask first, then back up `~/.claude/settings.json`.**

1. Merge the hooks into `~/.claude/settings.json`, with `VAULT` replaced by the absolute path:
   - macOS and Linux: `REPO/claude/settings.hooks.json`
   - Windows: `REPO/claude/settings.hooks.windows.json` (uses `py -3`)

   **SessionStart** → `brain.py context` loads an overview at every start: active projects, deadlines, next steps, recent work.
   **PostToolUse** → `brain.py hook` logs every file Claude changes, with its project, to `Claude Activity.md`. Private folders are never logged.
2. Append `REPO/claude/CLAUDE.snippet.md` to `~/.claude/CLAUDE.md`, replacing `VAULT` and `PYTHON`. This tells Claude when to read which note, how to record progress and what to keep out.
3. Test: start a new Claude Code session. “<Name>'s second brain” with the projects must appear at the top.

If the person moves the vault later, the paths in `~/.claude/settings.json` and `~/.claude/CLAUDE.md` must be updated too.

## Step 8: Wrap-up

Sum up for the person:
- how many notes and contacts were created, and what was left out
- where `Who to Ask.md` is
- three things that are useful right away
- the routine: once a week, go through the weekly review list in `Home.md`. Every few months, run `sources.py scan` again (with a fresh Claude app export if the person uses the app) and get a new LinkedIn export (steps 2 and 6).

Final commit in the vault: `Second brain: path completed`.
