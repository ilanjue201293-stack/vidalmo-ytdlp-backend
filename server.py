import re
import subprocess
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl

app = FastAPI(title="Vidalmo yt-dlp backend")

YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "music.youtube.com",
}


class DownloadRequest(BaseModel):
    url: HttpUrl
    format: str = "mp4"
    quality: str = "1080p"


@app.get("/health")
def health():
    return {"status": "ok", "service": "vidalmo-ytdlp"}


@app.post("/download")
def download(payload: DownloadRequest):
    if payload.url.host not in YOUTUBE_HOSTS:
        raise HTTPException(400, "Seuls les liens YouTube sont acceptés")

    if payload.format not in {"mp4", "mp3"}:
        raise HTTPException(400, "Format invalide")

    match = re.fullmatch(r"(144|240|360|480|720|1080|1440|2160)p", payload.quality)
    if not match:
        raise HTTPException(400, "Qualité invalide")

    folder = Path(tempfile.mkdtemp(prefix="vidalmo-"))
    output = folder / "vidalmo.%(ext)s"

    if payload.format == "mp3":
        command = [
            "yt-dlp",
            "--no-playlist",
            "--max-filesize", "200M",
            "--no-check-certificates",
            "-x",
            "--audio-format", "mp3",
            "--audio-quality", "192K",
            "-o", str(output),
            str(payload.url),
        ]
        media_type = "audio/mpeg"
    else:
        height = match.group(1)
        command = [
            "yt-dlp",
            "--no-playlist",
            "--max-filesize", "200M",
            "--no-check-certificates",
            "-f", f"bestvideo[height<={height}]+bestaudio/best[height<={height}]/best",
            "--merge-output-format", "mp4",
            "-o", str(output),
            str(payload.url),
        ]
        media_type = "video/mp4"

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=300,
    )

    if result.returncode != 0:
        error = (result.stderr or result.stdout or "Erreur yt-dlp")[-1000:]
        raise HTTPException(502, error)

    files = [file for file in folder.iterdir() if file.is_file()]
    if not files:
        raise HTTPException(502, "Aucun fichier généré")

    file = files[0]
    return FileResponse(file, media_type=media_type, filename=file.name)
