---
name: review
description: "Review code changes for quality and correctness"
whenToUse: "When the user asks for code review or says /review"
allowedTools: ["Bash", "FileRead", "GlobSearch", "GrepSearch", "GitDiff"]
---
Review code changes thoroughly:
1. Get the diff of recent changes
2. Check for logic errors and edge cases
3. Verify naming conventions and code style
4. Look for security issues (hardcoded secrets, SQL injection, etc.)
5. Check test coverage for changed code
6. Provide structured feedback with severity levels
