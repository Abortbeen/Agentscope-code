# Agentscope-Code

An AI coding agent built on [AgentScope](https://github.com/modelscope/agentscope) with Claude Code-style UI and oh-my-claudecode integration.

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

# Run
python -m codeagent
```

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
