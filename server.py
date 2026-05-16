import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import subprocess
import json
import uuid
import io

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent
UPLOADS = ROOT / "uploads"
FRAMES = ROOT / "frames"

UPLOADS.mkdir(exist_ok=True)
FRAMES.mkdir(exist_ok=True)

SERVER_HOST = os.getenv("SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("SERVER_PORT", "3000"))


def parse_multipart_form(headers: dict, body: bytes) -> dict:
    """Simple multipart form data parser for file uploads."""
    content_type = headers.get("Content-Type", "")
    if "boundary=" not in content_type:
        raise ValueError("No boundary in multipart form data")

    boundary = content_type.split("boundary=")[1].split(";")[0].strip('"')
    boundary_bytes = f"--{boundary}".encode()
    end_boundary = f"--{boundary}--".encode()

    parts = {}
    current_pos = 0

    while current_pos < len(body):
        start = body.find(boundary_bytes, current_pos)
        if start == -1:
            break

        # Find the end of headers (double CRLF)
        headers_end = body.find(b"\r\n\r\n", start)
        if headers_end == -1:
            break

        # Extract headers
        header_section = body[start + len(boundary_bytes) : headers_end].decode("utf-8", errors="ignore")
        
        # Find content disposition to get field name and filename
        name = None
        filename = None
        for line in header_section.split("\r\n"):
            if "Content-Disposition:" in line:
                if 'name="' in line:
                    name = line.split('name="')[1].split('"')[0]
                if "filename=" in line:
                    filename = line.split("filename=")[1].split(";")[0].strip('"')

        # Find data end (next boundary or end)
        data_start = headers_end + 4
        next_boundary = body.find(b"\r\n--", data_start)
        if next_boundary == -1:
            next_boundary = body.find(end_boundary, data_start)
        
        if next_boundary == -1:
            data_end = len(body)
        else:
            data_end = next_boundary

        data = body[data_start:data_end]
        if data.endswith(b"\r\n"):
            data = data[:-2]

        if name:
            if filename:
                parts[name] = {"filename": filename, "data": data}
            else:
                parts[name] = data.decode("utf-8", errors="ignore")

        current_pos = data_end

    return parts


class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/upload":
            self.send_error(404)
            return

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            form_data = parse_multipart_form(dict(self.headers), body)
        except Exception as e:
            self.send_error(400, f"Failed to parse form data: {e}")
            return

        if "video" not in form_data:
            self.send_error(400, "No 'video' field in form data")
            return

        video_data = form_data["video"]["data"]
        run_id = str(uuid.uuid4())[:8]
        video_path = UPLOADS / f"{run_id}.webm"
        frame_dir = FRAMES / run_id
        frame_dir.mkdir(exist_ok=True)

        with open(video_path, "wb") as f:
            f.write(video_data)

        subprocess.run([
            "ffmpeg",
            "-y",
            "-i", str(video_path),
            "-vf", "fps=1/2",
            str(frame_dir / "frame_%03d.jpg")
        ], check=True)

        frames = sorted(str(p.relative_to(ROOT)) for p in frame_dir.glob("*.jpg"))

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({
            "run_id": run_id,
            "video": str(video_path.relative_to(ROOT)),
            "frames": frames
        }).encode())

if __name__ == "__main__":
    print(f"Starting server on {SERVER_HOST}:{SERVER_PORT}")
    HTTPServer((SERVER_HOST, SERVER_PORT), Handler).serve_forever()
