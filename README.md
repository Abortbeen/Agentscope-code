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

### Binary (no Python required)

Download from [Releases](https://github.com/Abortbeen/Agentscope-code/releases):

```bash
# Linux
chmod +x agentscope-code-linux-x64
./agentscope-code-linux-x64

# macOS
chmod +x agentscope-code-macos-arm64
./agentscope-code-macos-arm64
```

### pip install

```bash
pip install agentscope-code

# Set your API key
export ANTHROPIC_API_KEY=your-key-here
# or
export OPENAI_API_KEY=your-key-here

# Run (two equivalent commands, like `claude`)
agentscope-code
asc
```

### From source

```bash
git clone https://github.com/Abortbeen/Agentscope-code.git
cd Agentscope-code
pip install .

# Now you have the CLI commands
agentscope-code
asc
```

## Launch Modes

```bash
# Basic REPL (all equivalent)
agentscope-code
asc
python -m codeagent run

# With AgentScope Studio (web UI for monitoring)
asc run --studio auto              # Auto-launch Studio
asc run --studio http://host       # Connect to existing Studio
asc run --studio-port 7860         # Custom Studio port

# With A2A (Agent-to-Agent) protocol server
asc run --a2a                      # Enable A2A server
asc run --a2a-port 7861            # Custom A2A port

# Studio + A2A together
asc run --studio auto --a2a

# Specify model and provider
asc run --model claude-sonnet-4-20250514 --provider anthropic
asc run --model gpt-4o --provider openai
asc run --model qwen-max --provider dashscope

# Non-interactive mode (single prompt)
asc run --prompt "fix the bug in main.py"
asc "explain this codebase"

# Resume a previous session
asc run --resume <session-id>

# Setup and migration
asc setup                          # Interactive setup wizard
asc migrate                        # Migrate from Claude Code config
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
1. **Environment variables** — `CODEAGENT_MODEL`, `CODEAGENT_PROVIDER`
2. **Project config** — `.agent/settings.json` (per-project)
3. **Global config** — `~/.config/codeagent/settings.json` (all projects)

Run `asc setup` for interactive configuration, or create `.agent/settings.json` manually:

```bash
# Initialize project config
asc init
# Creates: .agent/settings.json, .agent/agents/, .agent/skills/
```

### Model Provider Examples

<details>
<summary><b>Anthropic (Claude)</b></summary>

```bash
export ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx
```

`.agent/settings.json`:
```json
{
  "model": {
    "provider": "anthropic",
    "model_name": "claude-sonnet-4-20250514",
    "max_tokens": 8192
  }
}
```

Available models: `claude-opus-4-20250514`, `claude-sonnet-4-20250514`, `claude-3-5-haiku-20241022`

</details>

<details>
<summary><b>OpenAI (GPT)</b></summary>

```bash
export OPENAI_API_KEY=sk-xxxxxxxxxxxx
```

`.agent/settings.json`:
```json
{
  "model": {
    "provider": "openai",
    "model_name": "gpt-4o",
    "max_tokens": 8192
  }
}
```

Available models: `gpt-4o`, `gpt-4o-mini`, `gpt-4-turbo`

</details>

<details>
<summary><b>DashScope (Qwen)</b></summary>

```bash
export DASHSCOPE_API_KEY=sk-xxxxxxxxxxxx
```

`.agent/settings.json`:
```json
{
  "model": {
    "provider": "dashscope",
    "model_name": "qwen-max",
    "max_tokens": 8192
  }
}
```

Available models: `qwen-max`, `qwen-plus`, `qwen-turbo`

</details>

<details>
<summary><b>Google Gemini</b></summary>

```bash
export GOOGLE_API_KEY=AIzaxxxxxxxxxxxx
```

`.agent/settings.json`:
```json
{
  "model": {
    "provider": "gemini",
    "model_name": "gemini-2.0-flash",
    "max_tokens": 8192
  }
}
```

</details>

<details>
<summary><b>Ollama (Local Models)</b></summary>

No API key needed. Start Ollama first: `ollama serve`

`.agent/settings.json`:
```json
{
  "model": {
    "provider": "ollama",
    "model_name": "llama3",
    "base_url": "http://localhost:11434"
  }
}
```

</details>

<details>
<summary><b>Custom API Endpoint (OpenAI-compatible)</b></summary>

For any OpenAI-compatible API (vLLM, LiteLLM, Azure, etc.):

```bash
export OPENAI_API_KEY=your-api-key
```

`.agent/settings.json`:
```json
{
  "model": {
    "provider": "openai",
    "model_name": "your-model-name",
    "base_url": "https://your-api-endpoint.com/v1",
    "max_tokens": 8192,
    "temperature": 0.0
  }
}
```

</details>

### Full Configuration Reference

`.agent/settings.json` supports all options:

```json
{
  "model": {
    "provider": "anthropic",
    "model_name": "claude-sonnet-4-20250514",
    "max_tokens": 8192,
    "temperature": 0.0,
    "stream": true,
    "base_url": null
  },
  "permissions": {
    "mode": "default",
    "allow_rules": [
      {"tool": "Bash", "pattern": "git *"},
      {"tool": "Bash", "pattern": "npm *"}
    ],
    "deny_rules": [
      {"tool": "Bash", "pattern": "rm -rf /*"}
    ],
    "sensitive_files": [".env", "*.pem", "*.key", "credentials*"]
  },
  "hooks": [],
  "skills": {
    "extra_dirs": [],
    "disabled": []
  },
  "session": {
    "storage_dir": null,
    "max_sessions": 50
  },
  "memory": {
    "memory_file": "AGENT.md",
    "compression_threshold": 100000
  },
  "ui": {
    "theme": "monokai",
    "show_tokens": true,
    "show_cost": true,
    "markdown_output": true
  },
  "studio": {
    "enabled": false,
    "url": null,
    "auto_launch": false,
    "port": 7860
  },
  "a2a": {
    "enabled": false,
    "host": "0.0.0.0",
    "port": 7861
  }
}
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `DASHSCOPE_API_KEY` | DashScope (Qwen) API key |
| `GOOGLE_API_KEY` | Google Gemini API key |
| `CODEAGENT_MODEL` | Override model name |
| `CODEAGENT_PROVIDER` | Override provider |
| `CODEAGENT_PERMISSION_MODE` | Override permission mode |

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
