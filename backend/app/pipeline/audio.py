"""Stage 2+3: Extract audio and detect presence via RMS energy."""
import subprocess
import os
import logging
import numpy as np

logger = logging.getLogger(__name__)

RMS_SILENCE_THRESHOLD = 0.001


def extract_audio(video_path: str, output_dir: str) -> str:
    """Extract audio as 16kHz mono WAV using ffmpeg. Returns WAV path."""
    os.makedirs(output_dir, exist_ok=True)
    base = os.path.splitext(os.path.basename(video_path))[0]
    wav_path = os.path.join(output_dir, f"{base}_audio.wav")
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-ar", "16000",
        "-ac", "1",
        "-vn",
        wav_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        if "no audio" in result.stderr.lower() or "Output file #0 does not contain any stream" in result.stderr:
            return ""
        logger.warning(f"ffmpeg audio extraction stderr: {result.stderr}")
        # If WAV was still created, use it
        if os.path.exists(wav_path) and os.path.getsize(wav_path) > 1000:
            return wav_path
        return ""
    if not os.path.exists(wav_path) or os.path.getsize(wav_path) < 1000:
        return ""
    return wav_path


def detect_audio_presence(wav_path: str) -> bool:
    """
    Detect if audio has meaningful content via RMS energy.
    Returns True if audio is present and non-trivial.
    """
    if not wav_path or not os.path.exists(wav_path):
        return False
    try:
        import wave
        import struct
        with wave.open(wav_path, "rb") as wf:
            n_frames = wf.getnframes()
            sample_width = wf.getsampwidth()
            if n_frames == 0:
                return False
            # Read up to 10 seconds of audio for RMS check
            max_frames = min(n_frames, 16000 * 10)
            raw = wf.readframes(max_frames)
        if sample_width == 2:
            fmt = f"<{len(raw)//2}h"
            samples = np.array(struct.unpack(fmt, raw), dtype=np.float32) / 32768.0
        else:
            samples = np.frombuffer(raw, dtype=np.uint8).astype(np.float32) / 128.0 - 1.0
        rms = float(np.sqrt(np.mean(samples ** 2)))
        logger.info(f"Audio RMS energy: {rms:.6f} (threshold: {RMS_SILENCE_THRESHOLD})")
        return rms > RMS_SILENCE_THRESHOLD
    except Exception as e:
        logger.warning(f"Could not check audio RMS: {e}")
        return True  # Assume audio present if we can't check
