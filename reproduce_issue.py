import sys
import os

print(f"Python executable: {sys.executable}")
print(f"Python version: {sys.version}")
print(f"Current working directory: {os.getcwd()}")
print(f"sys.path: {sys.path}")

try:
    import langgraph
    print(f"langgraph version: {langgraph.__version__}")
    print(f"langgraph path: {langgraph.__file__}")
except ImportError as e:
    print(f"Failed to import langgraph: {e}")
except Exception as e:
    print(f"Error importing langgraph: {e}")

try:
    from langgraph.graph import StateGraph, END
    print("Successfully imported StateGraph and END from langgraph.graph")
except ImportError as e:
    print(f"Failed to import StateGraph/END: {e}")
except Exception as e:
    print(f"Error importing StateGraph/END: {e}")

try:
    import bot.client
    print("Successfully imported bot.client")
except ImportError as e:
    print(f"Failed to import bot.client: {e}")
except Exception as e:
    print(f"Error importing bot.client: {e}")
