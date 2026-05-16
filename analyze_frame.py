import argparse
import base64
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
import requests

load_dotenv()


def build_payload(model: str, img_b64: str) -> dict:
    content = [
        {
            "type": "text",
            "text": "Describe what is happening in this screen recording frame. Focus on the visible app, user workflow, actions, and likely next steps."
        },
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}
        }
    ]

    payload = {"messages": [{"role": "user", "content": content}], "max_tokens": 500}
    if model:
        payload["model"] = model
    return payload


def main():
    parser = argparse.ArgumentParser(description="Analyze a single extracted frame with a local LLM endpoint")
    parser.add_argument("--run-id", "-r", default="70651dde", help="run id / frames subdirectory")
    parser.add_argument("--frame-index", "-f", type=int, default=1, help="frame index (1-based)")
    parser.add_argument(
        "--endpoint",
        "-e",
        default=os.getenv("LLM_ENDPOINT", "http://127.0.0.1:8000/v1/chat/completions"),
        help="LLM HTTP endpoint (local)",
    )
    parser.add_argument(
        "--model",
        "-m",
        default=os.getenv("LLM_MODEL", "nvidia/NVIDIA-Nemotron-3-Nano-Omni-30B-A3B-Reasoning-GGUF"),
        help="Model identifier to send in the request payload",
    )
    parser.add_argument("--output", "-o", help="Optional output path to write full JSON response")

    args = parser.parse_args()

    frame_path = Path("frames") / args.run_id / f"frame_{args.frame_index:03d}.jpg"
    if not frame_path.exists():
        print(f"Could not find frame: {frame_path}")
        sys.exit(2)

    img_b64 = base64.b64encode(frame_path.read_bytes()).decode("utf-8")

    payload = build_payload(args.model, img_b64)

    try:
        res = requests.post(args.endpoint, headers={"Content-Type": "application/json"}, data=json.dumps(payload), timeout=120)
    except requests.RequestException as e:
        print("Request failed:", e)
        sys.exit(3)

    print("STATUS:", res.status_code)

    try:
        data = res.json()
        if args.output:
            Path(args.output).write_text(json.dumps(data, indent=2))
            print("WROTE:", args.output)
        else:
            # Print a compact representation (trim long text)
            print(json.dumps(data, indent=2)[:4000])
    except Exception:
        print(res.text[:2000])


if __name__ == "__main__":
    main()
