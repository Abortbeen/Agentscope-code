---
name: debug
description: "Systematically debug an error or failing test"
whenToUse: "When the user reports a bug, error, or test failure"
allowedTools: ["Bash", "FileRead", "GlobSearch", "GrepSearch", "FileEdit"]
---
Systematically debug the reported issue:
1. Reproduce the error (run the failing command/test)
2. Read error messages and stack traces carefully
3. Identify the root cause by searching related code
4. Propose and apply a fix
5. Verify the fix by re-running the failing command
