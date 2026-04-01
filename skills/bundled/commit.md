---
name: commit
description: "Create a well-structured git commit"
whenToUse: "When the user says /commit or asks to commit changes"
allowedTools: ["Bash", "GitStatus", "GitDiff", "GitLog", "GitCommit"]
---
Create a git commit following best practices:
1. Run git status and git diff to understand changes
2. Draft a concise commit message (why, not what)
3. Stage relevant files (avoid .env, credentials)
4. Create the commit with Co-Authored-By attribution
5. Show the commit result
