#!/usr/bin/env python3
"""Erzeugt einen erfundenen LinkedIn-Export zum Testen: python3 -I tests/make_fake_export.py out.zip"""
import sys, zipfile
ME = "https://www.linkedin.com/in/max-muster-000"
files = {
"Profile.csv": "First Name,Last Name,Maiden Name,Address,Birth Date,Headline,Summary,Industry,Zip Code,Geo Location,Twitter Handles,Websites,Instant Messengers\nMax,Muster,,,,Schüler,,Education,1010,Wien,,,\n",
"Education.csv": "School Name,Start Date,End Date,Notes,Degree Name,Activities\nBeispielgymnasium,Sep 2019,Jun 2027,,Matura,Schulsprecher\n",
"Positions.csv": "Company Name,Title,Description,Location,Started On,Finished On\nBeispiel GmbH,Praktikant,Vertrieb unterstützt,Wien,Jul 2026,Aug 2026\n",
"Languages.csv": "Name,Proficiency\nDeutsch,Native or bilingual proficiency\nEnglisch,Full professional proficiency\n",
"Skills.csv": "Name\nVertrieb\nPräsentation\n",
"Connections.csv": "Notes:\n\"When exporting your connection data, ...\"\n\nFirst Name,Last Name,URL,Email Address,Company,Position,Connected On\n"
  "Erika,Beispiel,https://www.linkedin.com/in/erika-beispiel,,ADVANTAGE AUSTRIA,Trade Commissioner,03 Oct 2026\n"
  "Paul,Probe,https://www.linkedin.com/in/paul-probe,,Universität Zürich,Professor,12 Sep 2026\n"
  "Lena,Test 🚀,https://www.linkedin.com/in/lena-test,,Testlabs,Founder & CEO,01 Aug 2026\n"
  "Anna,Muster,https://www.linkedin.com/in/anna-muster,,Familienbetrieb,Inhaberin,01 Jan 2025\n"
  ",,,,,,09 Feb 2026\n"
  "Tom,Leer,https://www.linkedin.com/in/tom-leer,,,,05 May 2026\n",
"messages.csv": "\"CONVERSATION ID\",\"CONVERSATION TITLE\",\"FROM\",\"SENDER PROFILE URL\",\"TO\",\"RECIPIENT PROFILE URLS\",\"DATE\",\"SUBJECT\",\"CONTENT\",\"FOLDER\"\n"
  f"c1,,Max Muster,{ME},Erika Beispiel,https://www.linkedin.com/in/erika-beispiel,2026-10-08 10:00:00 UTC,,Darf ich Sie für ein Interview zu meiner Abschlussarbeit anfragen?,INBOX\n"
  f"c2,,Max Muster,{ME},Paul Probe,https://www.linkedin.com/in/paul-probe,2026-10-09 10:00:00 UTC,,Sehr geehrter Herr Probe ... Interview?,INBOX\n"
  f"c2,,Paul Probe,https://www.linkedin.com/in/paul-probe,Max Muster,{ME},2026-10-10 10:00:00 UTC,,Gerne!,INBOX\n"
  f"c3,,Rita Recruiter,https://www.linkedin.com/in/rita-recruiter,Max Muster,{ME},2026-11-16 10:00:00 UTC,,We're looking for a Sales Development Representative,INBOX\n",
"Invitations.csv": f"From,To,Sent At,Message,Direction,inviterProfileUrl,inviteeProfileUrl\nMax Muster,Erika Beispiel,\"10/1/26, 1:00 PM\",,OUTGOING,{ME},https://www.linkedin.com/in/erika-beispiel\n",
"Member_Follows.csv": "Date,Status,FullName\n2026-10-19 22:25:06,Active,Erfundene Person\n2026-10-19 22:25:06,Unfollow,Alte Person\n",
}
with zipfile.ZipFile(sys.argv[1], "w") as z:
    for n, c in files.items():
        z.writestr(n, c)
print("geschrieben:", sys.argv[1])
