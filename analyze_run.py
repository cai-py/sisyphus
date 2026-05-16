import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import List

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


def call_analyze_frame(script_path: Path, run_id: str, frame_index: int, endpoint: str, model: str, out_json: Path):
    cmd = [
        sys.executable,
        str(script_path),
        "--run-id",
        run_id,
        "--frame-index",
        str(frame_index),
        "--endpoint",
        endpoint,
        "--model",
        model,
        "--output",
        str(out_json),
    ]
    env = os.environ.copy()
    subprocess.run(cmd, check=True, env=env)


def aggregate_and_generate(run_id: str, per_frame_texts: List[str], endpoint: str, model: str) -> str:
    # Build an aggregation prompt similar to previous behavior
    header = (
        "You are Sisyphus, an AI that turns screen recordings into reusable automation plans.\n"
        "Do NOT just describe the screen. Ignore the Sisyphus recorder interface unless it is the only thing visible.\n"
        "Focus on the actual app or website the user was operating during the recording. Infer what task the user wants to automate next time.\n\n"
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
        "Keep each line short.\n\n"
    )

    content_texts = [header] + [f"Frame analysis {i+1}:\n{t}" for i, t in enumerate(per_frame_texts)]

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": content_texts}],
        "max_tokens": 700,
    }

    res = requests.post(endpoint, json=payload, timeout=180)
    res.raise_for_status()
    data = res.json()

    # Best-effort extraction of the assistant text
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

    script_path = Path(__file__).with_name("analyze_frame.py")
    out_dir = Path("workflows")
    out_dir.mkdir(exist_ok=True)

    # Load from environment or use defaults
    endpoint = os.getenv("LLM_ENDPOINT", "http://127.0.0.1:8000/v1/chat/completions")
    model = os.getenv("LLM_MODEL", "nvidia/NVIDIA-Nemotron-3-Nano-Omni-30B-A3B-Reasoning-GGUF")

    per_frame_texts = []
    per_frame_outputs = []

    for frame in frames:
        idx = int(frame.stem.split("_")[-1])
        out_json = out_dir / f"{run_id}_frame_{idx:03d}.json"
        print(f"Analyzing frame {frame.name} -> {out_json}")
        call_analyze_frame(script_path, run_id, idx, endpoint, model, out_json)

        if out_json.exists():
            try:
                data = json.loads(out_json.read_text())
                # Try to extract assistant text
                text = ""
                if isinstance(data, dict):
                    text = (
                        data.get("choices", [{}])[0].get("message", {}).get("content")
                        or data.get("output")
                        or json.dumps(data)
                    )
                else:
                    text = json.dumps(data)
            except Exception:
                text = out_json.read_text()[:2000]
        else:
            text = ""

        per_frame_texts.append(text)
        per_frame_outputs.append({"frame": str(frame), "analysis": text})

    # Aggregate into final workflow spec
    final_analysis = aggregate_and_generate(run_id, per_frame_texts, endpoint, model)

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
        "per_frame_outputs": per_frame_outputs,
        "source_video": f"uploads/{run_id}.webm",
        "raw_model_output": final_analysis,
        "status": "draft",
    }

    out_path = out_dir / f"{run_id}.json"
    out_path.write_text(json.dumps(workflow, indent=2))

    print(final_analysis)
    print(f"\nSaved automation spec to {out_path}")


if __name__ == "__main__":
    main()
