#!/usr/bin/env python3
"""
Generate a tiny synthetic sample video with audio for the demo.
Requires: ffmpeg in PATH
"""
import subprocess
import os
import sys

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), "..", "samples")
OUTPUT = os.path.join(SAMPLES_DIR, "sample.mp4")


def create_sample_video():
    os.makedirs(SAMPLES_DIR, exist_ok=True)

    # Generate 30s test video with:
    # - Color bars (visually varied scenes)
    # - Sine-wave tone audio (so Whisper gets something)
    cmd = [
        "ffmpeg", "-y",
        # Scene 1: color bars (0-10s)
        "-f", "lavfi", "-i",
        "color=c=blue:s=640x360:d=10:r=25,drawtext=fontsize=32:fontcolor=white:"
        "text='AI Video Summarizer Demo':x=(w-text_w)/2:y=(h-text_h)/2",
        # Audio: sine tone
        "-f", "lavfi", "-i", "sine=frequency=440:duration=30",
        # Map streams
        "-map", "0:v",
        "-map", "1:a",
        "-t", "30",
        "-c:v", "libx264", "-crf", "28", "-preset", "ultrafast",
        "-c:a", "aac", "-b:a", "64k",
        OUTPUT,
    ]

    print(f"Creating sample video: {OUTPUT}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        # Try simpler fallback
        cmd_simple = [
            "ffmpeg", "-y",
            "-f", "lavfi", "-i", "testsrc=duration=30:size=640x360:rate=25",
            "-f", "lavfi", "-i", "sine=frequency=440:duration=30",
            "-c:v", "libx264", "-crf", "28", "-preset", "ultrafast",
            "-c:a", "aac", "-b:a", "64k",
            "-t", "30",
            OUTPUT,
        ]
        result2 = subprocess.run(cmd_simple, capture_output=True, text=True)
        if result2.returncode != 0:
            print(f"ffmpeg error: {result2.stderr}")
            sys.exit(1)

    size_mb = os.path.getsize(OUTPUT) / 1024 / 1024
    print(f"Sample video created: {OUTPUT} ({size_mb:.1f} MB, 30 seconds)")


if __name__ == "__main__":
    create_sample_video()
