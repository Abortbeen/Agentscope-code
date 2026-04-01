# Agentscope-Code

An AI coding agent built on [AgentScope](https://github.com/modelscope/agentscope) with Claude Code-style UI and oh-my-claudecode integration.


<img width="726" height="465" alt="微信图片_2026-04-01_210346_822" src="https://github.com/user-attachments/assets/22cd17e8-f68c-435e-8a1e-210a2c70bc5b" />

##Built-in Observability UI
<img width="1257" height="1001" alt="微信图片_2026-04-01_212923_171" src="https://github.com/user-attachments/assets/9ceb8b61-62da-4265-899a-f0ab43ddc029" />

<img width="1257" height="1001" alt="微信图片_2026-04-01_212951_813" src="https://github.com/user-attachments/assets/d2f7a7a9-939e-4175-afbf-0ba873b8d431" />

## Features

- **Claude Code-style TUI** — Braille spinner, separator lines, multi-line status bar, Shift+Tab mode cycling
- **19 Specialized Agents** — architect, analyst, debugger, designer, executor, planner, critic, and more (from oh-my-claudecode)
- **35 Skills** — autopilot, ralph, ultrawork, ultraqa, plan, trace, team, deepinit, and more
- **Multi-provider Support** — OpenAI, Anthropic, DashScope, Gemini, Ollama
- **Full Tool Suite** — Bash, FileRead/Write/Edit, Glob, Grep, WebFetch, WebSearch, Git, Notebook, Agent spawning, Team coordination, Task board
- **Slash Command Autocomplete** — Tab completion with dropdown preview for commands, skills, and agents
- **Permission System** — Auto/Plan/Manual modes with configurable allow/deny rules
- **Session Management** — Save, resume, and list conversation sessions
- **Hook Engine** — PreToolUse, PostToolUse, PreReply, PostReply hooks
- **A2A Protocol** — Agent-to-Agent communication server
- **Cost Tracking** — Real-time token count and cost estimation in status bar
- **Project Memory** — AGENT.md / CLAUDE.md context injection

## Quick Start

```bash
# Install dependencies
pip install agentscope prompt_toolkit rich

# Set your API key
export ANTHROPIC_API_KEY=your-key-here
# or
export OPENAI_API_KEY=your-key-here

# Run (default REPL)
python -m codeagent

# Or with explicit run subcommand
python -m codeagent run
```

## Launch Modes

```bash
# Basic REPL
python -m codeagent run

# With AgentScope Studio (web UI for monitoring)
python -m codeagent run --studio auto          # Auto-launch Studio
python -m codeagent run --studio http://host    # Connect to existing Studio
python -m codeagent run --studio-port 7860      # Custom Studio port

# With A2A (Agent-to-Agent) protocol server
python -m codeagent run --a2a                   # Enable A2A server
python -m codeagent run --a2a-port 7861         # Custom A2A port

# Studio + A2A together
python -m codeagent run --studio auto --a2a

# Specify model and provider
python -m codeagent run --model claude-sonnet-4-20250514 --provider anthropic
python -m codeagent run --model gpt-4o --provider openai
python -m codeagent run --model qwen-max --provider dashscope

# Non-interactive mode (single prompt)
python -m codeagent run --prompt "fix the bug in main.py"
python -m codeagent "explain this codebase"

# Resume a previous session
python -m codeagent run --resume <session-id>

# Setup and migration
python -m codeagent setup                       # Interactive setup wizard
python -m codeagent migrate                     # Migrate from Claude Code config
```

## TUI (Terminal UI)

Agentscope-Code features a Claude Code-style terminal interface built with `prompt_toolkit` and `rich`:

- **Real-time spinner** with 50+ random verbs (Brewing, Cogitating, Clauding...)
- **Separator lines** above prompt for clean conversation boundaries
- **Multi-line status bar** showing:
  - Git branch
  - Model name, session duration, token usage, cost
  - Context usage bar (`ctx:[██░░░░░░░░]15%`)
  - Tool count
  - Current mode with `shift+tab to cycle`
- **Mode cycling** — `Shift+Tab` switches between Auto / Plan / Manual
- **Slash command autocomplete** — type `/` then `Tab` to complete commands, skills, agents
- **Tool call visualization** — Claude Code-style with `●` prefix and `⎿` tree connectors:
  ```
  ● Reading 1 file...
    ⎿  base_worker.py
  ● Running...
    ⎿  $ python test.py
  ● Editing main.py...
    ⎿  /path/to/main.py
  ```
- **Processing timer** — `✻ Brewed for 12s` after each response
- **Response prefix** — `●` bullet for agent output (Claude Code style)

## Configuration

Configuration is loaded from (highest priority first):
1. Environment variables (`CODEAGENT_MODEL`, `CODEAGENT_PROVIDER`)
2. Project config (`.agent/settings.json`)
3. Global config (`~/.config/codeagent/settings.json`)

Example `.agent/settings.json`:
```json
{
  "model": {
    "provider": "anthropic",
    "model_name": "claude-sonnet-4-20250514"
  },
  "permissions": {
    "mode": "default"
  }
}
```

## Commands

| Command | Description |
|---------|-------------|
| `/help` | Show available commands |
| `/agents` | List available agent types |
| `/skills` | List available skills |
| `/tools` | List available tools |
| `/model` | Show or switch model |
| `/init` | Initialize project config |
| `/doctor` | Run diagnostics |
| `/cost` | Show detailed cost breakdown |
| `/compact` | Compress conversation memory |
| `/sessions` | List recent sessions |

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `Shift+Tab` | Cycle mode: Auto / Plan / Manual |
| `Tab` | Accept slash command completion |
| `Ctrl+C` x2 | Exit |
| `Ctrl+D` | Exit |

## Agent Types

Bundled agents from oh-my-claudecode:

| Agent | Model | Description |
|-------|-------|-------------|
| analyst | opus | Requirements analysis |
| architect | opus | Architecture & debugging (read-only) |
| code-reviewer | opus | Code review with severity ratings |
| critic | opus | Plan review & evaluation |
| planner | opus | Strategic planning |
| debugger | sonnet | Root-cause analysis |
| designer | sonnet | UI/UX design |
| executor | sonnet | Task execution |
| git-master | sonnet | Git operations |
| test-engineer | sonnet | Test strategy |
| writer | haiku | Documentation |
| explore | haiku | Codebase search |
| ... | | 19 agents total |

## Architecture

```
codeagent/
├── agent/          # CodingAgent, AgentDefinitionLoader, SystemPrompt
├── agents/         # 19 bundled agent definitions (.md)
├── cli/            # REPL, TUI renderer, commands, slash completion
├── config/         # Settings schema, hierarchical config loader
├── hooks/          # Hook engine (Pre/Post ToolUse/Reply)
├── memory/         # Project memory (AGENT.md/CLAUDE.md)
├── observability/  # Token tracking, cost display, tracing
├── permissions/    # Permission checker, rules
├── scheduler/      # Background tasks, cron
├── session/        # Session save/resume
├── skills/         # Skill registry, loader, 35 bundled skills
├── tools/          # All tool implementations
└── utils/          # Git, frontmatter, token counter
```

## License

MIT
