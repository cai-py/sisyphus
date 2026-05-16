from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
import cgi
import subprocess
import json
import uuid

ROOT = Path(__file__).parent
UPLOADS = ROOT / "uploads"
FRAMES = ROOT / "frames"

UPLOADS.mkdir(exist_ok=True)
FRAMES.mkdir(exist_ok=True)

class Handler(SimpleHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/upload":
            self.send_error(404)
            return

        form = cgi.FieldStorage(
            fp=self.rfile,
            headers=self.headers,
            environ={
                "REQUEST_METHOD": "POST",
                "CONTENT_TYPE": self.headers.get("Content-Type"),
            },
        )

        file_item = form["video"]
        run_id = str(uuid.uuid4())[:8]
        video_path = UPLOADS / f"{run_id}.webm"
        frame_dir = FRAMES / run_id
        frame_dir.mkdir(exist_ok=True)

        with open(video_path, "wb") as f:
            f.write(file_item.file.read())

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

HTTPServer(("127.0.0.1", 3000), Handler).serve_forever()
