import sys
import traceback
import os

# Add current directory to sys.path
sys.path.append(os.getcwd())

print(f"CWD: {os.getcwd()}")
print(f"Path: {sys.path}")

try:
    import bot.client
    print("Success: bot.client imported")
except ImportError:
    traceback.print_exc()
except Exception:
    traceback.print_exc()
