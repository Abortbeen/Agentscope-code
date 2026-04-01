---
name: simplify
description: "Review and simplify recently changed code"
whenToUse: "After implementation is complete, to reduce complexity"
allowedTools: ["FileRead", "FileEdit", "GlobSearch", "GrepSearch"]
---
Review recently changed code for simplification opportunities:
1. Look for code duplication
2. Identify overly complex logic
3. Check for unused imports/variables
4. Suggest and apply simplifications
5. Ensure changes don't break functionality
