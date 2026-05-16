import base64
import json
import re
import sys
from pathlib import Path
import requests

run_id = sys.argv[1]
frame_dir = Path("frames") / run_id

if not frame_dir.exists():
    raise FileNotFoundError(f"Could not find {frame_dir}")

all_frames = sorted(frame_dir.glob("*.jpg"))

if len(all_frames) <= 6:
    frames = all_frames
else:
    # sample across the whole recording instead of only the beginning
    idxs = [
        0,
        len(all_frames) // 5,
        (len(all_frames) * 2) // 5,
        (len(all_frames) * 3) // 5,
        (len(all_frames) * 4) // 5,
        len(all_frames) - 1,
    ]
    frames = [all_frames[i] for i in idxs]

content = [
    {
        "type": "text",
        "text": """
You are Sisyphus, an AI that turns screen recordings into reusable automation plans.

Do NOT just describe the screen.
Ignore the Sisyphus recorder interface unless it is the only thing visible.
Focus on the actual app or website the user was operating during the recording.
Infer what task the user wants to automate next time.

Return brief plain text using exactly this format:

Workflow name: ...
Intent: ...
Trigger command: /...
Inputs needed: ...
Automation step 1: ...
Automation step 2: ...
Automation step 3: ...
Best execution method: browser | api | openclaw | manual_review
Missing info: ...

Keep each line short.
"""
    }
]

for frame in frames:
    img_b64 = base64.b64encode(frame.read_bytes()).decode("utf-8")
    content.append({"type": "text", "text": f"Frame: {frame.name}"})
    content.append({
        "type": "image_url",
        "image_url": {
            "url": f"data:image/jpeg;base64,{img_b64}"
        }
    })

payload = {
    "model": "nvidia/NVIDIA-Nemotron-3-Nano-Omni-30B-A3B-Reasoning-GGUF",
    "messages": [{"role": "user", "content": content}],
    "max_tokens": 500
}

res = requests.post(
    "http://127.0.0.1:8000/v1/chat/completions",
    headers={"Content-Type": "application/json"},
    data=json.dumps(payload),
    timeout=180
)

print("STATUS:", res.status_code)

data = res.json()
analysis = data["choices"][0]["message"]["content"].strip()

def grab(label, default=""):
    m = re.search(rf"^{re.escape(label)}:\s*(.*)$", analysis, re.MULTILINE)
    return m.group(1).strip() if m else default

steps = []
for i in range(1, 6):
    step = grab(f"Automation step {i}")
    if step:
        steps.append(step)

workflow = {
    "run_id": run_id,
    "workflow_name": grab("Workflow name", "Untitled workflow"),
    "intent": grab("Intent"),
    "trigger_command": grab("Trigger command", f"/run_{run_id}"),
    "inputs_needed": grab("Inputs needed"),
    "automation_steps": steps,
    "best_execution_method": grab("Best execution method", "manual_review"),
    "missing_info": grab("Missing info"),
    "frames_analyzed": [str(f) for f in frames],
    "source_video": f"uploads/{run_id}.webm",
    "raw_model_output": analysis,
    "status": "draft"
}

out_dir = Path("workflows")
out_dir.mkdir(exist_ok=True)
out_path = out_dir / f"{run_id}.json"
out_path.write_text(json.dumps(workflow, indent=2))

print(analysis)
print(f"\nSaved automation spec to {out_path}")
