"""
D&D AI Dungeon Master — Entry Point

This file is a thin wrapper that delegates to bot/client.py.
All logic has been moved to the bot/ package (Phase 2 refactor).

Renamed from bot.py → main.py to avoid shadowing the 'bot' package.
Python adds the script's directory to sys.path[0], so a file named
'bot.py' in orchestration/ would mask the top-level 'bot/' package.

To run: python orchestration/main.py
   or:  python -m bot.client
"""

from bot.client import run

if __name__ == "__main__":
    run()
