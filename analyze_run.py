import base64
import json
import os
import re
import sys
from pathlib import Path
from typing import List
import argparse

from dotenv import load_dotenv
import requests

load_dotenv()


def select_frames(frame_dir: Path) -> List[Path]:
    all_frames = sorted(frame_dir.glob("*.jpg"))
    if len(all_frames) <= 6:
        return all_frames
    idxs = [
        0,
        len(all_frames) // 5,
        (len(all_frames) * 2) // 5,
        (len(all_frames) * 3) // 5,
        (len(all_frames) * 4) // 5,
        len(all_frames) - 1,
    ]
    return [all_frames[i] for i in idxs]


def build_frame_payload(frames: List[Path], model: str, transcript: str = "") -> dict:
    content = [
        {
            "type": "text",
            "text": (
                "You are Sisyphus, an AI that turns screen recordings into reusable automation plans.\n"
                "Do NOT just describe the screen. Ignore the Sisyphus recorder interface unless it is the only thing visible.\n"
                "Focus on the actual app or website the user was operating during the recording. Infer what task the user wants to automate next time.\n\n"
                "Use all the provided frames together to understand the complete workflow.\n"
                "Return brief plain text using exactly this format:\n\n"
                "Workflow name: ...\n"
                "Intent: ...\n"
                "Trigger command: /...\n"
                "Inputs needed: ...\n"
                "Automation step 1: ...\n"
                "Automation step 2: ...\n"
                "Automation step 3: ...\n"
                "Best execution method: browser | api | openclaw | manual_review\n"
                "Missing info: ...\n\n"
                "Keep each line short."
            ),
        }
    ]

    if transcript:
        content.append({
            "type": "text",
            "text": (
                "User transcript context:\n"
                f"{transcript}\n\n"
                "Use this spoken context to avoid hallucination and to better infer the user intent."
            )
        })

    for idx, frame in enumerate(frames, start=1):
        frame_b64 = base64.b64encode(frame.read_bytes()).decode("utf-8")
        content.append({
            "type": "text",
            "text": f"Frame {idx}:"
        })
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{frame_b64}"}
        })

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content}],
        "max_tokens": 900,
    }
    return payload


def aggregate_and_generate(frames: List[Path], endpoint: str, model: str, transcript: str = "") -> str:
    payload = build_frame_payload(frames, model, transcript)

    res = requests.post(endpoint, json=payload, timeout=180)
    res.raise_for_status()
    data = res.json()

    try:
        return data["choices"][0]["message"]["content"].strip()
    except Exception:
        return json.dumps(data)[:4000]


def grab(analysis: str, label: str, default: str = "") -> str:
    m = re.search(rf"^{re.escape(label)}:\s*(.*)$", analysis, re.MULTILINE)
    return m.group(1).strip() if m else default


def main():
    if len(sys.argv) < 2:
        print("Usage: analyze_run.py <run_id>")
        sys.exit(2)

    run_id = sys.argv[1]
    frame_dir = Path("frames") / run_id
    if not frame_dir.exists():
        raise FileNotFoundError(f"Could not find {frame_dir}")

    frames = select_frames(frame_dir)

    parser = argparse.ArgumentParser(description="Generate a workflow spec from extracted frames and optional transcript context")
    parser.add_argument("run_id", help="Run ID / frames subdirectory")
    parser.add_argument("--transcript", default="", help="Optional transcript text from the recording session")
    args = parser.parse_args()

    transcript = args.transcript

    workflow_dir = Path("workflows")
    workflow_dir.mkdir(exist_ok=True)

    # Load from environment or use defaults
    endpoint = os.getenv("LLM_ENDPOINT", "http://127.0.0.1:8000/v1/chat/completions")
    model = os.getenv("LLM_MODEL", "nvidia/NVIDIA-Nemotron-3-Nano-Omni-30B-A3B-Reasoning-GGUF")

    print(f"Analyzing {len(frames)} selected frames for run {run_id}")
    if transcript:
        print("Using transcript context from microphone input.")
    final_analysis = aggregate_and_generate(frames, endpoint, model, transcript)

    steps = []
    for i in range(1, 6):
        step = grab(final_analysis, f"Automation step {i}")
        if step:
            steps.append(step)

    workflow = {
        "run_id": run_id,
        "workflow_name": grab(final_analysis, "Workflow name", "Untitled workflow"),
        "intent": grab(final_analysis, "Intent"),
        "trigger_command": grab(final_analysis, "Trigger command", f"/run_{run_id}"),
        "inputs_needed": grab(final_analysis, "Inputs needed"),
        "automation_steps": steps,
        "best_execution_method": grab(final_analysis, "Best execution method", "manual_review"),
        "missing_info": grab(final_analysis, "Missing info"),
        "frames_analyzed": [str(f) for f in frames],
        "source_video": f"uploads/{run_id}.webm",
        "raw_model_output": final_analysis,
        "status": "draft",
    }

    out_path = workflow_dir / f"{run_id}.json"
    out_path.write_text(json.dumps(workflow, indent=2))

    print(final_analysis)
    print(f"\nSaved automation spec to {out_path}")


if __name__ == "__main__":
    main()
