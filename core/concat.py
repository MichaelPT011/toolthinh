"""FFmpeg based concat helpers."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ConcatClip:
    path: str
    order: int = 0
    trim_start: float = 0.0
    trim_end: float = 0.0


@dataclass
class ConcatJob:
    clips: list[ConcatClip] = field(default_factory=list)
    output_path: str = ""
    sync_duration: bool = False
    target_duration: float = 0.0


class ConcatEngine:
    """Concatenate, trim, and retime videos with ffmpeg."""

    def __init__(self) -> None:
        self.ffmpeg_path = self._find_ffmpeg()

    @staticmethod
    def _find_ffmpeg() -> str | None:
        found = shutil.which("ffmpeg")
        if found:
            return found
        for path in [Path("C:/ffmpeg/bin/ffmpeg.exe"), Path.home() / "ffmpeg" / "bin" / "ffmpeg.exe"]:
            if path.exists():
                return str(path)
        return None

    def is_available(self) -> bool:
        return self.ffmpeg_path is not None

    def get_duration(self, video_path: str) -> float:
        if not self.ffmpeg_path:
            raise RuntimeError("ffmpeg is not available")
        ffprobe = self.ffmpeg_path.replace("ffmpeg", "ffprobe")
        cmd = [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())

    def run_concat_job(self, job: ConcatJob) -> str:
        if not self.ffmpeg_path:
            raise RuntimeError("ffmpeg is not available")

        sorted_clips = sorted(job.clips, key=lambda clip: clip.order)
        temp_files: list[str] = []
        try:
            processed: list[str] = []
            for clip in sorted_clips:
                if clip.trim_start > 0 or clip.trim_end > 0:
                    trimmed = self._trim(clip)
                    temp_files.append(trimmed)
                    processed.append(trimmed)
                else:
                    processed.append(clip.path)

            if job.sync_duration and job.target_duration > 0:
                synced: list[str] = []
                for path in processed:
                    synced_path = self._sync_duration(path, job.target_duration)
                    temp_files.append(synced_path)
                    synced.append(synced_path)
                processed = synced

            self._concat_reencode(processed, job.output_path)
            return job.output_path
        finally:
            for temp_path in temp_files:
                Path(temp_path).unlink(missing_ok=True)

    def _trim(self, clip: ConcatClip) -> str:
        out_path = tempfile.mktemp(suffix=".mp4")
        cmd = [self.ffmpeg_path, "-y"]
        if clip.trim_start > 0:
            cmd += ["-ss", str(clip.trim_start)]
        cmd += ["-i", clip.path]
        if clip.trim_end > 0:
            cmd += ["-t", str(max(clip.trim_end - clip.trim_start, 0.1))]
        cmd += ["-c:v", "libx264", "-c:a", "aac", out_path]
        subprocess.run(cmd, check=True, capture_output=True)
        return out_path

    def _sync_duration(self, video_path: str, target: float) -> str:
        current = self.get_duration(video_path)
        factor = current / target if target > 0 else 1.0
        factor = max(factor, 0.1)
        out_path = tempfile.mktemp(suffix=".mp4")
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i",
            video_path,
            "-filter_complex",
            f"[0:v]setpts={1 / factor}*PTS[v];[0:a]atempo={factor}[a]",
            "-map",
            "[v]",
            "-map",
            "[a]",
            out_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return out_path

    def _concat_reencode(self, video_paths: list[str], output_path: str) -> None:
        if not video_paths:
            raise ValueError("No videos selected")
        inputs: list[str] = []
        filter_parts: list[str] = []
        for index, path in enumerate(video_paths):
            inputs += ["-i", path]
            filter_parts.append(f"[{index}:v][{index}:a]")
        filter_str = "".join(filter_parts) + f"concat=n={len(video_paths)}:v=1:a=1[outv][outa]"
        cmd = [
            self.ffmpeg_path,
            "-y",
            *inputs,
            "-filter_complex",
            filter_str,
            "-map",
            "[outv]",
            "-map",
            "[outa]",
            "-c:v",
            "libx264",
            "-c:a",
            "aac",
            output_path,
        ]
        subprocess.run(cmd, check=True, capture_output=True)

