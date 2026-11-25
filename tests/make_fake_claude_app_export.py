#!/usr/bin/env python3
"""Creates a made-up Claude app / claude.ai data export for testing: python3 -I tests/make_fake_claude_app_export.py out.zip

Same file names and fields as the real export (Settings > Privacy > Export data).
"""
import json, sys, zipfile

projects = [{"uuid": "p-1", "name": "Bachelor thesis", "description": "Sources and outline for my thesis",
             "created_at": "2026-09-01T10:00:00Z", "updated_at": "2026-11-20T10:00:00Z",
             "docs": [{"uuid": "d-1", "filename": "outline.md", "content": "SECRET DOC CONTENT"}]}]
conversations = [
    {"uuid": "c-1", "name": "Structure of chapter 2", "created_at": "2026-10-02T10:00:00Z", "updated_at": "2026-10-03T10:00:00Z",
     "project": {"uuid": "p-1"}, "chat_messages": [{"sender": "human", "text": "SECRET MESSAGE TEXT"}]},
    {"uuid": "c-2", "name": "Cover letter for an internship", "created_at": "2026-11-05T10:00:00Z", "updated_at": "2026-11-05T11:00:00Z",
     "chat_messages": [{"sender": "human", "text": "SECRET MESSAGE TEXT"}]},
    {"uuid": "c-3", "name": "Internship interview prep", "created_at": "2026-11-07T10:00:00Z", "updated_at": "2026-11-07T11:00:00Z",
     "chat_messages": []},
    {"uuid": "c-4", "name": "Doctor's appointment questions", "created_at": "2026-11-09T10:00:00Z", "updated_at": "2026-11-09T10:30:00Z",
     "chat_messages": [{"sender": "human", "text": "SECRET MESSAGE TEXT"}]},
]
with zipfile.ZipFile(sys.argv[1], "w") as z:
    z.writestr("conversations.json", json.dumps(conversations))
    z.writestr("projects.json", json.dumps(projects))
    z.writestr("users.json", json.dumps([{"uuid": "u-1", "full_name": "Alex Sample"}]))
print("written:", sys.argv[1])
