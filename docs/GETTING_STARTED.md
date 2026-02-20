# Getting Started — D&D AI Dungeon Master

This guide covers everything you need to run the bot, set up your Discord server, and start playing.

---

## Prerequisites Checklist

Before you can run a session, you need all of the following:

### Accounts & API Keys

| Item | Where to get it | Cost |
|------|-----------------|------|
| **Discord Bot Token** | [Discord Developer Portal](https://discord.com/developers/applications) → New Application → Bot → Token | Free |
| **Google Gemini API Key** | [Google AI Studio](https://aistudio.google.com/apikey) | Free tier available |
| **Foundry VTT** (optional) | [foundryvtt.com](https://foundryvtt.com/) — needed for live battle maps, dice, tokens | $50 one-time |
| **MongoDB** (optional) | [MongoDB Atlas](https://www.mongodb.com/atlas) free tier, or local install | Free tier available |

### Software

| Item | Version | Install |
|------|---------|---------|
| **Python** | 3.12+ | [python.org](https://www.python.org/downloads/) |
| **Git** | Any recent | [git-scm.com](https://git-scm.com/) |
| **Docker** (optional) | For Foundry relay | [docker.com](https://www.docker.com/) |

### Discord Server Setup

You need **3 text channels** in your Discord server (create them manually):

| Channel | Purpose | Who uses it |
|---------|---------|-------------|
| **Game Table** | Where the game happens. Players type actions, AI posts narrative. | Everyone |
| **War Room** | Session prep, worldbuilding, brainstorming. No players during sessions. | DM only |
| **Moderator Log** | Error messages, Rules Lawyer details, debug output. | DM only (bot posts here) |

**How to get channel IDs:** Enable Developer Mode in Discord (Settings → Advanced → Developer Mode). Then right-click any channel → Copy Channel ID.

---

## Installation

### 1. Clone the repo

```bash
git clone <your-repo-url>
cd "Antigravity Projects"
```

### 2. Create a virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Create the `.env` file

Create a file called `.env` in the project root with these values:

```env
# === REQUIRED ===
DISCORD_BOT_TOKEN=your_bot_token_here
GEMINI_API_KEY=your_gemini_api_key_here
GAME_TABLE_CHANNEL_ID=123456789012345678
WAR_ROOM_CHANNEL_ID=123456789012345679
MODERATOR_LOG_CHANNEL_ID=123456789012345680

# === PLAYER MAP (REQUIRED for game play) ===
# Format: discord_username:CharacterName,discord_username2:CharacterName2
# Use the player's Discord username (lowercase), NOT their display name
PLAYER_MAP=john:Frognar,jane:Kallisar,bob:Theron

# === OPTIONAL: Foundry VTT ===
FOUNDRY_API_KEY=your_foundry_api_key
FOUNDRY_RELAY_URL=http://localhost:3010
FOUNDRY_CLIENT_ID=ai-dm

# === OPTIONAL: MongoDB ===
MONGODB_URI=mongodb://localhost:27017/dnd_ai_dm
```

### 5. Set up character files in the vault

For each player character, create a markdown file in `campaign_vault/01 - Party/`:

**Example: `campaign_vault/01 - Party/Frognar.md`**
```markdown
---
name: Frognar
player: John
race: Half-Orc
class: Barbarian
level: 3
hp_current: 28
hp_max: 28
ac: 16
conditions: []
---

# Frognar

A fierce half-orc barbarian from the northern wastes...
```

### 6. Set up the world clock

Create `campaign_vault/06 - World State/World Clock.md`:
```markdown
---
session_number: 1
current_date: "1st of Hammer, 1492 DR"
time_of_day: morning
current_location: The Yawning Portal
---
```

### 7. Run the bot

```bash
python orchestration/main.py
```

Or on Windows:
```bash
start_bot.bat
```

You should see:
```
D&D AI System Online. Vault-backed state is active.
```

---

## Discord Bot Permissions

When adding the bot to your server, it needs these permissions:

- **Send Messages**
- **Read Messages / View Channels**
- **Create Private Threads**
- **Send Messages in Threads**
- **Manage Messages** (for reactions)
- **Add Reactions**
- **Embed Links**
- **Attach Files**
- **Use Slash Commands**

**Invite URL template:**
```
https://discord.com/api/oauth2/authorize?client_id=YOUR_BOT_CLIENT_ID&permissions=397553172480&scope=bot+applications.commands
```

Replace `YOUR_BOT_CLIENT_ID` with your bot's Application ID from the Discord Developer Portal.

---

## Optional: Foundry VTT Setup

If you want live battle maps, dice rolling through Foundry, and token management:

### 1. Install the Three Hats Relay

The relay bridges HTTP requests to Foundry's WebSocket API:

```bash
cd foundryvtt-relay
docker compose up -d
```

This runs the relay on `localhost:3010`.

### 2. Configure Foundry VTT

- Install and run Foundry VTT normally
- Make sure it's accessible from the machine running the bot
- Set `FOUNDRY_API_KEY`, `FOUNDRY_RELAY_URL`, and `FOUNDRY_CLIENT_ID` in your `.env`

### 3. Verify connection

After starting the bot, type `!foundry` in any channel. You should see a green "Connected" status.

---

## Optional: MongoDB Setup

Without MongoDB, the bot runs in "vault-only mode" — all state lives in the Obsidian vault markdown files. This works fine for most games.

MongoDB adds:
- Faster mechanical state queries (HP, conditions, quest status)
- Separate mechanical vs narrative truth stores

To enable: set `MONGODB_URI` in your `.env`. The bot connects automatically on startup and falls back to vault-only if unavailable.
