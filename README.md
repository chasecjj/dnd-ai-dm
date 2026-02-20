# D&D AI Dungeon Master

Discord-based AI Dungeon Master for D&D 5e campaigns. A multi-agent LangGraph pipeline processes player actions through Router, Rules Lawyer, Storyteller, and Chronicler nodes — narrating the story via Google Gemini, tracking state in an Obsidian vault (narrative) and optional MongoDB (mechanical), and syncing live with Foundry VTT for battle maps, tokens, and dice.

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
| [Getting Started](docs/GETTING_STARTED.md) | New DMs | Installation, environment setup, first run |
| [DM Guide](docs/DM_GUIDE.md) | DMs | Full command and button reference, session lifecycle |
| [Player Guide](docs/PLAYER_GUIDE.md) | Players | How to play, dice rolling, secret actions |
| [Session Walkthrough](docs/SESSION_WALKTHROUGH.md) | Everyone | Simulated full session showing what "working" looks like |

## Architecture

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
