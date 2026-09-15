import os
import re
import subprocess
import tempfile
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl

app = FastAPI(title="Vidalmo yt-dlp backend")


class DownloadRequest(BaseModel):
    url: HttpUrl
    format: str = "mp4"
    quality: str = "1080p"


YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "music.youtube.com",
}


def safe_quality(value: str) -> str:
    match = re.fullmatch(r"(144|240|360|480|720|1080|1440|2160)p", value)
    if not match:
        raise HTTPException(status_code=400, detail="Qualité invalide")
    return match.group(1)


@app.get("/health")
def health():
    return {"status": "ok", "service": "vidalmo-ytdlp"}


@app.post("/download")
def download(payload: DownloadRequest):
    url = str(payload.url)

    if payload.url.host not in YOUTUBE_HOSTS:
        raise HTTPException(
            status_code=400,
            detail="Seuls les liens YouTube sont acceptés",
        )

    if payload.format not in {"mp4", "mp3"}:
        raise HTTPException(status_code=400, detail="Format invalide")

    quality = safe_quality(payload.quality)
    temp_dir = Path(tempfile.mkdtemp(prefix="vidalmo-"))
    output = temp_dir / "download.%(ext)s"

    if payload.format == "mp3":
        format_selector = "bestaudio/best"
        extra = [
            "-x",
            "--audio-format",
            "mp3",
            "--audio-quality",
            "192K",
        ]
    else:
        format_selector = (
            f"bestvideo[height<={quality}]+bestaudio/"
            f"best[height<={quality}]/best"
        )
        extra = ["--merge-output-format", "mp4"]

    command = [
        "yt-dlp",
        "--no-playlist",
        "--max-filesize",
        "200M",
        "--restrict-filenames",
        "-f",
        format_selector,
        "-o",
        str(output),
        *extra,
        url,
    ]

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=180,
    )

    if result.returncode != 0:
        raise HTTPException(
            status_code=502,
            detail="Le téléchargement YouTube a échoué",
        )

    files = [file for file in temp_dir.iterdir() if file.is_file()]

    if not files:
        raise HTTPException(
            status_code=502,
            detail="Aucun fichier généré",
        )

    file = files[0]
    media_type = (
        "audio/mpeg" if payload.format == "mp3" else "video/mp4"
    )

    return FileResponse(
        file,
        media_type=media_type,
        filename=f"vidalmo.{file.suffix.lstrip('.')}",
    )
