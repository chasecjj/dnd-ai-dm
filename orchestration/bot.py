"""
D&D AI Dungeon Master — Entry Point (Legacy)

This file is a thin wrapper that delegates to bot/client.py.
All logic has been moved to the bot/ package (Phase 2 refactor).

IMPORTANT: This file is named bot.py but lives in orchestration/.
Python adds the script's parent directory to sys.path[0], which
means 'import bot' would find THIS file instead of the top-level
bot/ package. We fix this by removing orchestration/ from sys.path
and ensuring the project root is present before any imports.

Preferred entry point: python orchestration/main.py
   or:  python -m bot.client
"""

import sys
import os

# Fix sys.path so 'bot' resolves to the bot/ PACKAGE, not this file.
_this_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_this_dir)

# Remove the orchestration/ directory from path (Python auto-adds it)
if _this_dir in sys.path:
    sys.path.remove(_this_dir)

# Ensure project root is at the front
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from bot.client import run

if __name__ == "__main__":
    run()
