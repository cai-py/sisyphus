# Sisyphus: Screen Recording to AI Automation Workflow

Sisyphus turns screen recordings into reusable automation plans using a local LLM.

## Project Overview

- **`server.py`**: HTTP server that accepts video uploads, extracts frames at 0.5 fps, and returns frame metadata
- **`analyze_frame.py`**: Sends a single frame to a local LLM endpoint for analysis
- **`analyze_run.py`**: Orchestrates frame selection from a recorded run and generates a structured workflow spec
- **`index.html`**: Web UI for uploading videos and viewing results

## Setup

### Prerequisites

- Python 3.8+
- `ffmpeg` (for video frame extraction)
- Local LLM endpoint available at `http://127.0.0.1:8000/v1/chat/completions` (or configured URL)

### Installation

1. **Clone or sync the repo** to your AI computer:
   ```bash
   git clone <repo-url>
   cd sisyphus
   ```

2. **Create a `.env` file** from the template:
   ```bash
   cp .env.example .env
   ```

3. **Edit `.env`** if needed (e.g., if the LLM endpoint or model differs):
   ```
   LLM_ENDPOINT=http://127.0.0.1:8000/v1/chat/completions
   LLM_MODEL=nvidia/NVIDIA-Nemotron-3-Nano-Omni-30B-A3B-Reasoning-GGUF
   SERVER_HOST=127.0.0.1
   SERVER_PORT=3000
   ```

4. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Running

### 1. Start the Upload Server

On the AI computer:
```bash
python3 server.py
```

This starts an HTTP server on `127.0.0.1:3000` that accepts video uploads and extracts frames.

### 2. Upload a Video

Using `curl` or the web UI (`index.html`):
```bash
curl -F "video=@test.webm" http://127.0.0.1:3000/upload
```

The response will include:
- `run_id`: A unique identifier for this video
- `frames`: List of extracted frame paths
- `video`: Path to the uploaded video

Example response:
```json
{
  "run_id": "a39a84a0",
  "video": "uploads/a39a84a0.webm",
  "frames": ["frames/a39a84a0/frame_001.jpg", "frames/a39a84a0/frame_002.jpg", ...]
}
```

### 3. Analyze a Single Frame (Optional)

```bash
python3 analyze_frame.py \
  --run-id a39a84a0 \
  --frame-index 1 \
  --endpoint http://127.0.0.1:8000/v1/chat/completions \
  --model "nvidia/NVIDIA-Nemotron-3-Nano-Omni-30B-A3B-Reasoning-GGUF" \
  --output workflows/frame_output.json
```

### 4. Generate Full Workflow Spec

```bash
python3 analyze_run.py a39a84a0
```

This will:
1. Select key frames across the video
2. Call `analyze_frame.py` for each frame
3. Aggregate results into a single workflow specification
4. Save to `workflows/a39a84a0.json`

Example workflow output:
```json
{
  "run_id": "a39a84a0",
  "workflow_name": "Login to Gmail",
  "intent": "Automate daily email check-in",
  "trigger_command": "/run_login",
  "inputs_needed": "email, password",
  "automation_steps": [
    "Navigate to gmail.com",
    "Enter email and click Next",
    "Enter password and click Next",
    "Verify 2FA code"
  ],
  "best_execution_method": "browser",
  "frames_analyzed": [...],
  "status": "draft"
}
```

## Development Workflow

### On Your Local Machine

1. Make code changes locally
2. Commit and push to Git:
   ```bash
   git add analyze_frame.py analyze_run.py server.py ...
   git commit -m "Update: ..."
   git push
   ```

### On the AI Computer

1. Pull the latest changes:
   ```bash
   git pull
   ```

2. Test or re-run scripts with updated code

## Project Structure

```
sisyphus/
├── analyze_frame.py       # Single-frame LLM analysis
├── analyze_run.py         # Multi-frame aggregation & workflow generation
├── server.py              # Video upload & frame extraction server
├── index.html             # Web UI (optional)
├── requirements.txt       # Python dependencies
├── .env.example           # Configuration template
├── frames/                # Extracted frame directories (run-id indexed)
├── uploads/               # Uploaded video files (run-id indexed)
└── workflows/             # Generated workflow specs (run-id indexed)
```

## Next Steps

- Integrate with openclaw for automated task execution
- Improve UI element detection (OCR, visual bounding boxes)
- Add more sophisticated action synthesis (Playwright, Selenium, etc.)
- Support for multi-step workflows with branching logic

---

**Built for the ASUS DGX Spark Hackathon**
