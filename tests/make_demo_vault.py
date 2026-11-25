#!/usr/bin/env python3
"""Builds a realistic demo vault from made-up data (for screenshots and trying things out).

    python3 -I tests/make_demo_vault.py /tmp/demo        (Windows: py -3 -I tests/make_demo_vault.py %TEMP%\\demo)

Creates /tmp/demo/home (fake home folder with files and a Claude Code history), a fake LinkedIn export
with ~300 contacts, and runs the whole path into /tmp/demo/home/Documents/Second-Brain.
Then: cd there and run `python3 scripts/brain.py serve` with HOME set to /tmp/demo/home.
Every name, company and title here is invented.
"""
import datetime as dt
import json
import os
import random
import subprocess
import sys
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PY = sys.executable
random.seed(7)
root = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/demo").resolve()
home = root / "home"
vault = home / "Documents" / "Second-Brain"
today = dt.date.today()
d = lambda days: (today - dt.timedelta(days=days)).isoformat()


def run(*a, env=None):
    subprocess.run([PY, "-I", *map(str, a)], check=True, stdout=subprocess.DEVNULL, env=env)


FIRST = "Alex Sam Jordan Taylor Morgan Casey Riley Jamie Robin Avery Quinn Parker Rowan Emery Finley Harper Elliot Noah Mia Lea Jonas Clara Felix Nora Leon Ida Emil Lina Theo Mara Luca Zoe Max Ella Paul Lisa Ben Anna Tom Eva".split()
LAST = "Sample Example Demo Placeholder Fictional Mockwell Testwood Dummington Specimen Prototype Northwind Contoso Fabrikam Tailspin Adventure Lakeshore Brightwater Oakridge Stonebridge Ashford Millbrook Fairview Kingsley Redfern Holloway Westbrook Whitfield Blackwood Greenfield Harrow".split()
ROLES = [
    ("Trade Commissioner", "Exampleland Trade Office"), ("Commercial Attaché", "Embassy of Sampleland"),
    ("Policy Officer", "Ministry of Economy of Exampleland"), ("Member of Parliament", "Parliament of Exampleland"),
    ("Parliamentary Assistant", "Parliament of Exampleland"), ("Youth Officer", "Example Party"),
    ("Associate", "Northwind Consulting"), ("Summer Analyst", "Contoso Bank"), ("Investment Banking Intern", "Fabrikam Capital"),
    ("Tax Associate", "Tailspin Tax Advisory"), ("Associate", "Ashford & Holloway Law"), ("Trainee Lawyer", "Kingsley Legal"),
    ("Professor of Economics", "University of Sampleton"), ("Research Fellow", "Sample Institute for Economic Research"),
    ("Admissions Officer", "Example Business School"), ("Student", "University of Sampleton"), ("PhD Candidate", "Example Institute of Technology"),
    ("Journalist", "The Daily Example"), ("Editor", "Sample Public Radio"), ("Communications Manager", "Brightwater Media"),
    ("Founder & CEO", "Mockwell Labs"), ("Co-Founder", "Oakridge Apps"), ("Partner", "Stonebridge Ventures"),
    ("Software Engineer", "Lakeshore Software"), ("Data Analyst", "Greenfield Data"), ("Product Manager", "Redfern Tech"),
    ("Agent", "Millbrook Real Estate"), ("Managing Director", "Fairview Property Development"),
    ("Teacher", "Example High School"), ("Student", "Example High School"), ("Tutor", "Self-employed"),
    ("Officer Cadet", "Exampleland Armed Forces"), ("Soldier", "Exampleland Armed Forces"),
    ("Resident Physician", "Sampleton General Hospital"), ("Coach", "Sampleton Basketball Club"),
    ("Sales Manager", "Westbrook Retail"), ("Store Manager", "Whitfield Groceries"), ("Hotel Manager", "Harrow Hotels"),
    ("Marketing Intern", "Blackwood Consumer Goods"), ("", ""),
]
WEIGHTS = [5, 5, 4, 3, 3, 3, 6, 6, 4, 3, 3, 2, 3, 3, 2, 10, 3, 3, 2, 3, 6, 4, 2, 6, 4, 3, 2, 2, 3, 14, 2, 3, 4, 3, 2, 8, 6, 5, 4, 10]

# ---- fake home with project files and a Claude Code history
projects = {
    "Thesis": ("Desktop/School/Thesis", ["draft_v3.docx", "sources.pdf", "interview_notes.docx", "figures.xlsx"]),
    "Flat finder app": ("flat-finder", ["package.json", "README.md"]),
    "Tram line study": ("Desktop/School/Economics/tram-study", ["slides.pptx", "report.docx", "map.html"]),
    "University application": ("Desktop/Applications/Business School", ["cv.pdf", "motivation_letter.docx"]),
}
for name, (folder, files) in projects.items():
    p = home / folder
    p.mkdir(parents=True, exist_ok=True)
    for f in files:
        (p / f).write_text("demo", encoding="utf-8")
for repo in ("flat-finder", "Desktop/School/Economics/tram-study"):
    (home / repo / ".git").mkdir(exist_ok=True)
hist = home / ".claude" / "projects" / "-home"
hist.mkdir(parents=True, exist_ok=True)
sessions = [("Thesis", "Interview questions for chapter 4", 2), ("Thesis", "Fix duplicate sources", 1), ("Thesis", "Chapter 5 structure", 9),
            ("Flat finder app", "Login with magic link", 4), ("Flat finder app", "Swipe cards component", 12),
            ("Tram line study", "Tram route map", 0), ("Tram line study", "Shorten presentation to 5 minutes", 1),
            ("University application", "Motivation letter feedback", 20)]
for i, (proj, title, ago) in enumerate(sessions):
    folder, files = projects[proj]
    lines = [{"type": "ai-title", "aiTitle": title},
             {"type": "assistant", "timestamp": d(ago) + "T10:00:00Z", "cwd": str(home),
              "message": {"content": [{"type": "tool_use", "name": "Edit", "input": {"file_path": str(home / folder / files[0])}}]}}]
    (hist / f"s{i}.jsonl").write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")

# ---- fake LinkedIn export
conn = ["Notes:", '"When exporting your connection data, ..."', "", "First Name,Last Name,URL,Email Address,Company,Position,Connected On"]
seen = set()
people = []
while len(people) < 300:
    f, l = random.choice(FIRST), random.choice(LAST)
    if (f, l) in seen:
        continue
    seen.add((f, l))
    pos, org = random.choices(ROLES, WEIGHTS)[0]
    url = f"https://www.linkedin.com/in/{f.lower()}-{l.lower()}-demo"
    people.append((f, l, url, org, pos))
    conn.append(f"{f},{l},{url},,{org},{pos},{(today - dt.timedelta(days=random.randint(5, 700))).strftime('%d %b %Y')}")
me = "https://www.linkedin.com/in/alex-demo-me"
msgs = ['"CONVERSATION ID","CONVERSATION TITLE","FROM","SENDER PROFILE URL","TO","RECIPIENT PROFILE URLS","DATE","SUBJECT","CONTENT","FOLDER"']
for i, (f, l, url, org, pos) in enumerate([p for p in people if "Trade" in p[3] or "Embassy" in p[3] or "Economics" in p[4]][:6]):
    msgs.append(f'c{i},,Alex Demo,{me},{f} {l},{url},{d(40 - i)} 10:00:00 UTC,,Would you have time for a short interview for my thesis?,INBOX')
    if i % 2 == 0:
        msgs.append(f'c{i},,{f} {l},{url},Alex Demo,{me},{d(38 - i)} 10:00:00 UTC,,Happy to help.,INBOX')
msgs.append(f'r1,,Riley Recruiter,https://www.linkedin.com/in/riley-recruiter-demo,Alex Demo,{me},{d(6)} 10:00:00 UTC,,We are hiring a Sales Development Representative,INBOX')
root.mkdir(parents=True, exist_ok=True)
with zipfile.ZipFile(root / "linkedin.zip", "w") as z:
    z.writestr("Connections.csv", "\n".join(conn) + "\n")
    z.writestr("messages.csv", "\n".join(msgs) + "\n")
    z.writestr("Profile.csv", "First Name,Last Name,Maiden Name,Address,Birth Date,Headline,Summary,Industry,Zip Code,Geo Location,Twitter Handles,Websites,Instant Messengers\nAlex,Demo,,,,Student,,Education,,Sampleton,,,\n")
    z.writestr("Invitations.csv", f"From,To,Sent At,Message,Direction,inviterProfileUrl,inviteeProfileUrl\nAlex Demo,X,\"1/1/26, 1:00 PM\",,OUTGOING,{me},https://www.linkedin.com/in/x\n")

# ---- run the path
env = {**os.environ, "HOME": str(home), "USERPROFILE": str(home)}
run(REPO / "scripts/setup_vault.py", "--vault", vault, "--owner", "Alex Demo's")
run(REPO / "scripts/sources.py", "scan", "--vault", vault, "--claude-dir", home / ".claude", "--home", home)
cands = json.loads((vault / ".brain/candidates.json").read_text(encoding="utf-8"))
choices = []
for i, c in enumerate(cands, 1):
    for name, (folder, _) in projects.items():
        if c.get("path") == "~/" + folder:
            choices.append(f"{i}=project:{name}")
run(REPO / "scripts/sources.py", "decide", "--vault", vault, *choices)
run(REPO / "scripts/sources.py", "apply", "--vault", vault)
meta = {"Thesis": ("active", d(-24), "Finish chapter 5 and send it to the supervisor"),
        "Flat finder app": ("active", "", "Test the magic-link login end to end"),
        "Tram line study": ("active", d(-9), "Rehearse the 5-minute version"),
        "University application": ("planned", d(-150), "Submit the online application")}
for name, (status, deadline, nxt) in meta.items():
    p = vault / "01 Projects" / name / f"{name}.md"
    t = p.read_text(encoding="utf-8")
    t = t.replace("status: active", f"status: {status}").replace("status: planned", f"status: {status}")
    t = t.replace('deadline: ""', f'deadline: "{deadline}"').replace('next_step: ""', f'next_step: "{nxt}"')
    t = t.replace("## Next step\n", "## Next step\n" + nxt + "\n\n## Open\n- [ ] Ask two more interview partners\n- [x] Collect sources\n")
    p.write_text(t, encoding="utf-8")
for area in ["School", "Politics", "Sports"]:
    p = vault / "02 Areas" / area / f"{area}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(f"---\ntype: area\nstatus: active\ntags: [area]\n---\n# {area}\n\nBack to [[02 Areas]]\n", encoding="utf-8")
    t = (vault / "02 Areas/02 Areas.md").read_text(encoding="utf-8")
    (vault / "02 Areas/02 Areas.md").write_text(t.rstrip() + f"\n- [[{area}]]\n", encoding="utf-8")
topics = {"topics": [
    {"name": "Thesis", "link": "[[Thesis]]", "regex": "trade|econom|ministry|embassy", "sectors": ["Diplomacy & Trade"]},
    {"name": "University application", "link": "[[University application]]", "regex": "admission|business school|universit", "sectors": []},
    {"name": "Flat finder app", "link": "[[Flat finder app]]", "regex": "founder|venture|real estate|property|software|product", "sectors": []},
    {"name": "Tram line study", "link": "[[Tram line study]]", "regex": "transport|city|urban", "sectors": []},
    {"name": "Politics", "link": "[[Politics]]", "regex": "party|parliament", "sectors": ["Politics & Government"]}],
    "exclude_lastnames": ["Demo"]}
(vault / ".brain/topics.json").write_text(json.dumps(topics), encoding="utf-8")
run(REPO / "scripts/import_linkedin.py", "--vault", vault, "--zip", root / "linkedin.zip", "--config", vault / ".brain/topics.json")
brain = vault / "scripts/brain.py"
subprocess.run([PY, str(brain), "docs"], env=env, stdout=subprocess.DEVNULL, check=True)
for name, (folder, files) in list(projects.items())[:3]:
    hook = json.dumps({"tool_input": {"file_path": str(home / folder / files[-1])}, "session_id": "demo-" + name, "tool_name": "Edit"})
    subprocess.run([PY, str(brain), "hook"], input=hook, text=True, env=env, check=True)
subprocess.run([PY, str(brain), "log", "Thesis", "Chapter 5 restructured, two quotes added"], env=env, stdout=subprocess.DEVNULL, check=True)
print(f"demo vault: {vault}\nserve it:   HOME={home} {PY} {brain} serve")
