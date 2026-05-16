import base64
import json
import sys
from pathlib import Path
import requests

run_id = sys.argv[1] if len(sys.argv) > 1 else "70651dde"
frame_path = Path("frames") / run_id / "frame_001.jpg"

if not frame_path.exists():
    raise FileNotFoundError(f"Could not find {frame_path}")

img_b64 = base64.b64encode(frame_path.read_bytes()).decode("utf-8")

payload = {
    "model": "nvidia/NVIDIA-Nemotron-3-Nano-Omni-30B-A3B-Reasoning-GGUF",
    "messages": [
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "Describe what is happening in this screen recording frame. Focus on the visible app, user workflow, actions, and likely next steps."
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/jpeg;base64,{img_b64}"
                    }
                }
            ]
        }
    ],
    "max_tokens": 500
}

res = requests.post(
    "http://127.0.0.1:8000/v1/chat/completions",
    headers={"Content-Type": "application/json"},
    data=json.dumps(payload),
    timeout=120
)

print("STATUS:", res.status_code)

try:
    data = res.json()
    print(data["choices"][0]["message"]["content"])
except Exception:
    print(res.text[:2000])
