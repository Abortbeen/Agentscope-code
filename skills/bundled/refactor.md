---
name: refactor
description: "Refactor code to improve structure without changing behavior"
whenToUse: "When the user asks to refactor or improve code structure"
allowedTools: ["Bash", "FileRead", "FileEdit", "GlobSearch", "GrepSearch"]
---
Refactor code while preserving behavior:
1. Understand the current code structure
2. Identify code smells (duplication, long methods, tight coupling)
3. Plan refactoring steps (small, incremental changes)
4. Apply each refactoring step
5. Run tests after each step to ensure no regressions
6. Document the changes made
