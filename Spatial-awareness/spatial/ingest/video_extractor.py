"""Video frame extraction using FFmpeg."""

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

from spatial.utils.logging_config import get_logger
from spatial.utils.platform_compat import find_binary

log = get_logger("ingest.video")


@dataclass
class ExtractionResult:
    """Result of video frame extraction."""
    frames: list[str]       # Paths to extracted frame images
    frame_count: int
    video_duration: float   # seconds
    video_fps: float
    resolution: tuple[int, int]  # (width, height)


class VideoExtractor:
    """Extract frames from video files using FFmpeg."""

    def __init__(self, ffmpeg_path: str | None = None):
        self.ffmpeg = ffmpeg_path or find_binary("ffmpeg", "FFMPEG_PATH")
        if not self.ffmpeg:
            raise FileNotFoundError(
                "FFmpeg not found. Install FFmpeg and ensure it's on PATH, "
                "or set FFMPEG_PATH environment variable."
            )
        self.ffprobe = self.ffmpeg.replace("ffmpeg", "ffprobe")

    def probe_video(self, video_path: str) -> dict:
        """Get video metadata using ffprobe."""
        cmd = [
            self.ffprobe, "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            video_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            raise RuntimeError(f"ffprobe failed: {result.stderr}")
        return json.loads(result.stdout)

    def get_video_info(self, video_path: str) -> dict:
        """Extract key video properties."""
        probe = self.probe_video(video_path)
        video_stream = next(
            (s for s in probe.get("streams", []) if s["codec_type"] == "video"),
            None,
        )
        if not video_stream:
            raise ValueError(f"No video stream found in {video_path}")

        # Parse fps from r_frame_rate (e.g., "30000/1001")
        fps_parts = video_stream.get("r_frame_rate", "30/1").split("/")
        fps = float(fps_parts[0]) / float(fps_parts[1]) if len(fps_parts) == 2 else 30.0

        duration = float(probe.get("format", {}).get("duration", 0))
        width = int(video_stream.get("width", 0))
        height = int(video_stream.get("height", 0))

        return {
            "duration": duration,
            "fps": fps,
            "width": width,
            "height": height,
            "codec": video_stream.get("codec_name", "unknown"),
            "total_frames": int(video_stream.get("nb_frames", duration * fps)),
        }

    def extract_frames(
        self,
        video_path: str,
        output_dir: str,
        fps: float = 2.0,
        strategy: str = "uniform",
        max_frames: int | None = None,
        max_image_size: int = 3200,
        quality: int = 2,
    ) -> ExtractionResult:
        """
        Extract frames from a video file.

        Args:
            video_path: Path to input video file.
            output_dir: Directory to save extracted frames.
            fps: Frames per second to extract (for uniform strategy).
            strategy: Extraction strategy - "uniform", "keyframe", or "adaptive".
            max_frames: Maximum number of frames to extract.
            max_image_size: Maximum image dimension (longest edge).
            quality: JPEG quality (1=best, 31=worst).

        Returns:
            ExtractionResult with frame paths and video metadata.
        """
        video_path = os.path.abspath(video_path)
        output_dir = os.path.abspath(output_dir)
        os.makedirs(output_dir, exist_ok=True)

        if not os.path.isfile(video_path):
            raise FileNotFoundError(f"Video not found: {video_path}")

        info = self.get_video_info(video_path)
        log.info(
            "Video: %dx%d, %.1f fps, %.1f sec, codec=%s",
            info["width"], info["height"], info["fps"], info["duration"], info["codec"],
        )

        # Build FFmpeg filter chain
        vf_filters = self._build_filters(strategy, fps, max_image_size, info)
        output_pattern = os.path.join(output_dir, "frame_%06d.jpg")

        cmd = [
            self.ffmpeg, "-i", video_path,
            "-vf", ",".join(vf_filters),
            "-q:v", str(quality),
            "-vsync", "vfr",
        ]

        if max_frames:
            cmd.extend(["-frames:v", str(max_frames)])

        cmd.append(output_pattern)

        log.info("Extracting frames (strategy=%s, fps=%.1f)...", strategy, fps)
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=3600,
        )
        if result.returncode != 0:
            raise RuntimeError(f"FFmpeg frame extraction failed: {result.stderr[-500:]}")

        # Collect extracted frame paths
        frames = sorted(
            str(p) for p in Path(output_dir).glob("frame_*.jpg")
        )

        log.info("Extracted %d frames to %s", len(frames), output_dir)

        return ExtractionResult(
            frames=frames,
            frame_count=len(frames),
            video_duration=info["duration"],
            video_fps=info["fps"],
            resolution=(info["width"], info["height"]),
        )

    def _build_filters(
        self,
        strategy: str,
        fps: float,
        max_image_size: int,
        info: dict,
    ) -> list[str]:
        """Build FFmpeg video filter chain."""
        filters = []

        # Frame selection based on strategy
        if strategy == "uniform":
            filters.append(f"fps={fps}")
        elif strategy == "keyframe":
            # Extract only scene changes (good for walkthrough videos)
            filters.append("select='gt(scene,0.3)'")
        elif strategy == "adaptive":
            # Combination: scene change OR minimum fps
            min_fps = max(0.5, fps / 2)
            filters.append(
                f"select='gt(scene,0.2)+not(mod(n,{int(info['fps'] / min_fps)}))'",
            )
        else:
            raise ValueError(f"Unknown strategy: {strategy}")

        # Scale down if needed (preserve aspect ratio)
        w, h = info["width"], info["height"]
        if max(w, h) > max_image_size:
            if w >= h:
                filters.append(f"scale={max_image_size}:-2")
            else:
                filters.append(f"scale=-2:{max_image_size}")

        return filters

    def extract_frames_from_images(
        self,
        image_dir: str,
        output_dir: str,
        max_image_size: int = 3200,
    ) -> ExtractionResult:
        """
        Copy and normalize images from a directory (for image-only input).

        Args:
            image_dir: Directory containing input images.
            output_dir: Directory to save normalized images.
            max_image_size: Maximum image dimension.

        Returns:
            ExtractionResult with image paths.
        """
        import shutil
        from PIL import Image

        os.makedirs(output_dir, exist_ok=True)
        extensions = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif"}

        source_images = sorted(
            p for p in Path(image_dir).iterdir()
            if p.suffix.lower() in extensions
        )

        if not source_images:
            raise FileNotFoundError(f"No images found in {image_dir}")

        frames = []
        for i, src in enumerate(source_images):
            dst = os.path.join(output_dir, f"frame_{i+1:06d}.jpg")
            img = Image.open(src)

            # Auto-orient from EXIF
            from PIL import ImageOps
            img = ImageOps.exif_transpose(img)

            # Resize if needed
            w, h = img.size
            if max(w, h) > max_image_size:
                ratio = max_image_size / max(w, h)
                img = img.resize(
                    (int(w * ratio), int(h * ratio)), Image.LANCZOS
                )

            img.save(dst, "JPEG", quality=95)
            frames.append(dst)

        log.info("Processed %d images to %s", len(frames), output_dir)

        return ExtractionResult(
            frames=frames,
            frame_count=len(frames),
            video_duration=0,
            video_fps=0,
            resolution=Image.open(frames[0]).size if frames else (0, 0),
        )
