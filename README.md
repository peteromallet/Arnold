# Arnold - Discord Task Bot

A Discord bot that manages development tasks using natural language. Talk to it like a human - it uses Claude AI to understand you, creates/updates tasks in Supabase, and can automatically execute them using Claude Code.

## Features

- **Natural language task management** - Just describe what you need
- **Voice notes** - Send audio messages, they get transcribed automatically
- **Auto-execution** - Claude Code picks up tasks and implements them
- **Git integration** - Commits and pushes changes to GitHub
- **Dev notes** - Claude Code documents what it changed

## Quick Start

```bash
npm install
cp .env.example .env  # Fill in your keys
npm start
```

## Environment Variables

### Required
| Variable | Description |
|----------|-------------|
| `DISCORD_TOKEN` | Discord bot token |
| `DISCORD_USER_ID` | Your Discord user ID (restricts who can use the bot) |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key |

### For Executor
| Variable | Description | Default |
|----------|-------------|---------|
| `GITHUB_API_KEY` | GitHub PAT for pushing commits | - |
| `GITHUB_REPO_OWNER` | GitHub username/org | peteromallet |
| `GITHUB_REPO_NAME` | Repository name | Reigh |
| `GITHUB_REPO_BRANCH` | Branch to work on | main |
| `WORKSPACE_DIR` | Where to clone the repo | /tmp/workspace |
| `CLAUDE_PATH` | Full path to claude CLI | claude |
| `GIT_USER_NAME` | Git commit author | Arnold Bot |
| `GIT_USER_EMAIL` | Git commit email | bot@example.com |

### Optional
| Variable | Description |
|----------|-------------|
| `GROQ_API_KEY` | Groq API key for voice transcription |

## Usage

DM the bot or use `!task` prefix in a server. Just talk naturally:

```
"add a task to fix the login bug"
"start working on tasks"
"what's the status?"
"find the homepage task and mark it done"
"stop"
```

The bot understands context and can chain actions (search → update → reply).

## How the Executor Works

1. Tell Arnold to "start" or "go"
2. It polls Supabase for tasks with status `todo`
3. For each task:
   - Pulls latest from git
   - Runs Claude Code with the task details
   - Claude Code reads `structure.md` to understand the codebase
   - Makes changes, runs build, commits
   - Pushes to GitHub
   - Saves dev notes and commit hash to the task
4. Notifies you in Discord when done or stuck

## Task Schema

```sql
CREATE TABLE dev_tasks (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  title TEXT NOT NULL,
  description TEXT,
  status TEXT DEFAULT 'backlog' CHECK (status IN ('backlog', 'todo', 'in_progress', 'stuck', 'done', 'cancelled')),
  area TEXT,
  notes TEXT,
  commit_hash TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  completed_at TIMESTAMPTZ
);
```

| Status | Meaning |
|--------|---------|
| `backlog` | For later |
| `todo` | Queued for execution |
| `in_progress` | Currently being worked on |
| `stuck` | Failed, needs attention |
| `done` | Completed |
| `cancelled` | Won't do |

## Discord Bot Setup

1. [Discord Developer Portal](https://discord.com/developers/applications) → New Application
2. Bot → Add Bot → Enable **Message Content Intent**
3. Copy token → `DISCORD_TOKEN`
4. OAuth2 → URL Generator → Scopes: `bot` → Permissions: `Send Messages`, `Read Message History`
5. Invite bot using generated URL

**Get your User ID:** Discord Settings → App Settings → Advanced → Developer Mode → Right-click yourself → Copy User ID

## Deploy to Railway

1. Push to GitHub (don't commit `.env`)
2. [Railway](https://railway.app) → New Project → Deploy from GitHub
3. Add environment variables in Railway dashboard
4. Railway auto-detects Node.js and runs `npm start`

**Note:** On Railway, the executor clones the target repo into `WORKSPACE_DIR`. Set `CLAUDE_PATH` to the installed location (usually works without setting it).

## Architecture

```
Arnold (this bot)          Target Repo (e.g., Reigh)
├── src/
│   ├── bot.js            → Discord message handling
│   ├── taskParser.js     → Claude AI for understanding messages
│   ├── executor.js       → Runs Claude Code on tasks
│   ├── supabase.js       → Database operations
│   └── transcribe.js     → Voice note transcription
│
│   Clones & works on:
│   └── /tmp/workspace/Reigh/
│       ├── structure.md  ← Claude Code reads this first
│       └── structure_docs/
```

## License

MIT
