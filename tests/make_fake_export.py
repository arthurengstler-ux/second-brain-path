#!/usr/bin/env python3
"""Creates a made-up LinkedIn export for testing: python3 -I tests/make_fake_export.py out.zip"""
import sys, zipfile
ME = "https://www.linkedin.com/in/max-sample-000"
files = {
"Profile.csv": "First Name,Last Name,Maiden Name,Address,Birth Date,Headline,Summary,Industry,Zip Code,Geo Location,Twitter Handles,Websites,Instant Messengers\nMax,Sample,,,,Student,,Education,10001,New York,,,\n",
"Education.csv": "School Name,Start Date,End Date,Notes,Degree Name,Activities\nExample High School,Sep 2019,Jun 2027,,High School Diploma,Student council\n",
"Positions.csv": "Company Name,Title,Description,Location,Started On,Finished On\nExample Inc.,Intern,Supported the sales team,New York,Jul 2026,Aug 2026\n",
"Languages.csv": "Name,Proficiency\nEnglish,Native or bilingual proficiency\nSpanish,Full professional proficiency\n",
"Skills.csv": "Name\nSales\nPresenting\n",
"Connections.csv": "Notes:\n\"When exporting your connection data, ...\"\n\nFirst Name,Last Name,URL,Email Address,Company,Position,Connected On\n"
  "Erika,Example,https://www.linkedin.com/in/erika-example,,ADVANTAGE AUSTRIA,Trade Commissioner,03 Oct 2026\n"
  "Paul,Probe,https://www.linkedin.com/in/paul-probe,,University of Zurich,Professor,12 Sep 2026\n"
  "Lena,Test 🚀,https://www.linkedin.com/in/lena-test,,Testlabs,Founder & CEO,01 Aug 2026\n"
  "Anna,Sample,https://www.linkedin.com/in/anna-sample,,Family Business,Owner,01 Jan 2025\n"
  ",,,,,,09 Feb 2026\n"
  "Tom,Empty,https://www.linkedin.com/in/tom-empty,,,,05 May 2026\n",
"messages.csv": "\"CONVERSATION ID\",\"CONVERSATION TITLE\",\"FROM\",\"SENDER PROFILE URL\",\"TO\",\"RECIPIENT PROFILE URLS\",\"DATE\",\"SUBJECT\",\"CONTENT\",\"FOLDER\"\n"
  f"c1,,Max Sample,{ME},Erika Example,https://www.linkedin.com/in/erika-example,2026-10-08 10:00:00 UTC,,Could I interview you for my thesis?,INBOX\n"
  f"c2,,Max Sample,{ME},Paul Probe,https://www.linkedin.com/in/paul-probe,2026-10-09 10:00:00 UTC,,Dear Mr Probe, would you have time for an interview?,INBOX\n"
  f"c2,,Paul Probe,https://www.linkedin.com/in/paul-probe,Max Sample,{ME},2026-10-10 10:00:00 UTC,,Happy to!,INBOX\n"
  f"c3,,Rita Recruiter,https://www.linkedin.com/in/rita-recruiter,Max Sample,{ME},2026-11-16 10:00:00 UTC,,We're looking for a Sales Development Representative,INBOX\n",
"Invitations.csv": f"From,To,Sent At,Message,Direction,inviterProfileUrl,inviteeProfileUrl\nMax Sample,Erika Example,\"10/1/26, 1:00 PM\",,OUTGOING,{ME},https://www.linkedin.com/in/erika-example\n",
"Member_Follows.csv": "Date,Status,FullName\n2026-10-19 22:25:06,Active,Made Up Person\n2026-10-19 22:25:06,Unfollow,Old Person\n",
}
with zipfile.ZipFile(sys.argv[1], "w") as z:
    for n, c in files.items():
        z.writestr(n, c)
print("written:", sys.argv[1])
