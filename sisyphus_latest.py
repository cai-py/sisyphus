import json
from pathlib import Path

workflow_files = sorted(Path("workflows").glob("*.json"), key=lambda p: p.stat().st_mtime)

if not workflow_files:
    print("No Sisyphus workflows found yet.")
    raise SystemExit

latest = workflow_files[-1]
data = json.loads(latest.read_text())

print("Sisyphus workflow ready")
print()
print(f"Run ID: {data.get('run_id')}")
print()
print(data.get("analysis", "No analysis found."))
print()
print(f"Saved file: {latest}")
