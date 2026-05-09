from agents.orchestrator import orchestrator
import traceback

try:
    print("Testing handle_question...")
    result = orchestrator.handle_question("hello", search_enabled=False, thinking_enabled=False, history="")
    print("SUCCESS")
    print(result)
except Exception as e:
    print("ERROR:")
    traceback.print_exc()
