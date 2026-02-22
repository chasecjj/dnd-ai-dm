# D&D AI Dungeon Master

AI-powered Dungeon Master for D&D 5e campaigns over Discord. The AI runs the game autonomously — narrating scenes, adjudicating rules, and responding to players in real time. A human admin monitors via the Admin Console and intervenes only when needed. A multi-agent LangGraph pipeline processes player actions through Router, Rules Lawyer, Storyteller, and Chronicler nodes, powered by Google Gemini. Persistent state lives in an Obsidian vault (narrative) and optional MongoDB (mechanical), with live Foundry VTT integration for battle maps, tokens, and dice.

## Quick Start

```bash
git clone <your-repo-url>
cd "Antigravity Projects"
python -m venv .venv && .venv\Scripts\activate   # Windows
# source .venv/bin/activate                       # macOS/Linux
pip install -r requirements.txt
cp .env.example .env                              # then fill in your tokens
python orchestration/main.py                      # or: start_bot.bat (Windows)
```

See [docs/GETTING_STARTED.md](docs/GETTING_STARTED.md) for full setup instructions.

## Documentation

| Guide | Audience | Description |
|-------|----------|-------------|
| [Getting Started](docs/GETTING_STARTED.md) | New admins | Installation, environment setup, first run |
| [Campaign Setup](docs/CAMPAIGN_SETUP.md) | Admins | Creating a campaign, populating the vault, file formats |
| [Admin Guide](docs/DM_GUIDE.md) | Admins | Monitoring dashboard, intervention tools, session lifecycle |
| [Player Guide](docs/PLAYER_GUIDE.md) | Players | How to play with an AI DM, dice rolling, secret actions |
| [Session Walkthrough](docs/SESSION_WALKTHROUGH.md) | Everyone | Simulated full session showing what "working" looks like |

## Architecture

The AI is the DM; the human is an admin who monitors and assists. Auto Mode is the primary gameplay mode; Queue Mode is the override for complex scenes.

Three-layer design:

- **Discord Layer** (`bot/`) — message routing, channel handling, UI views
- **Pipeline Layer** (`pipeline/`) — LangGraph state graph: Router → Board Monitor → Rules Lawyer → Storyteller → Scene Sync → Chronicler
- **Data Layer** (`tools/` + `models/`) — Pydantic-validated Obsidian vault I/O and MongoDB CRUD

## Requirements

- Python 3.12+
- Discord bot token ([Developer Portal](https://discord.com/developers/applications))
- Google Gemini API key ([AI Studio](https://aistudio.google.com/apikey))
- (Optional) Foundry VTT + Three Hats Relay for live maps, dice, and tokens
- (Optional) MongoDB for mechanical state storage (falls back to vault-only mode)
