import os
import sys

sys.path.append(os.getcwd())

try:
    print("Importing drift_runner...")
    import hefesto.core.drift_runner

    print("drift_runner imported.")

    print("Importing cli.main...")
    import hefesto.cli.main

    print("cli.main imported.")

except Exception as e:
    print(f"ERROR: {e}")
    import traceback

    traceback.print_exc()
