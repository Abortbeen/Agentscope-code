---
name: verify
description: "Verify implementation by running tests and checking for errors"
whenToUse: "After completing code changes, to verify they work correctly"
allowedTools: ["Bash", "FileRead", "GlobSearch", "GrepSearch"]
---
Run tests and verification checks for recent code changes:
1. Find and run relevant test files
2. Check for linting errors  
3. Verify the build succeeds
4. Report any failures with context
