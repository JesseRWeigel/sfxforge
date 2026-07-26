#!/usr/bin/env python3
"""Exercise the CLI, audio files, varied banks, and browser server."""

from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import tempfile
import wave
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.http_harness import request  # noqa: E402


def run_cli(*arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "sfxforge", *arguments],
        cwd=PROJECT_ROOT,
        check=True,
        text=True,
        capture_output=True,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="sfxforge-smoke-") as temporary:
        root = Path(temporary)
        first = root / "impact-a.wav"
        second = root / "impact-b.wav"
        common = (
            "render",
            "--kind",
            "impact",
            "--seed",
            "3600",
            "--duration",
            "0.14",
        )
        run_cli(*common, "--output", str(first))
        run_cli(*common, "--output", str(second))
        with wave.open(str(first), "rb") as wav_file:
            assert wav_file.getnchannels() == 1
            assert wav_file.getsampwidth() == 2
            assert wav_file.getframerate() == 44_100
            assert wav_file.getnframes() == 6_174
        assert first.read_bytes() == second.read_bytes()
        print("SMOKE: CLI rendered valid 44.1 kHz mono PCM WAV")
        print("SMOKE: seed 3600 reproduced byte-identical audio")

        bank = root / "wood-bank"
        run_cli(
            "bank",
            "--kind",
            "footstep",
            "--surface",
            "wood",
            "--seed",
            "720",
            "--count",
            "6",
            "--duration",
            "0.12",
            "--output",
            str(bank),
        )
        manifest = json.loads((bank / "manifest.json").read_text(encoding="utf-8"))
        wav_paths = sorted(bank.glob("*.wav"))
        hashes = {hashlib.sha256(path.read_bytes()).hexdigest() for path in wav_paths}
        assert manifest["count"] == 6
        assert len(wav_paths) == 6
        assert len(hashes) == 6
        print("SMOKE: WAV bank exported 6 distinct seeded wood footsteps")

        page_response = request("/")
        assert page_response.status == 200
        assert b"Shape game sounds" in page_response.body
        presets_response = request("/api/presets")
        presets = json.loads(presets_response.body)
        assert set(presets["presets"]) == {"impact", "pickup", "ui_click", "footstep"}

        wav_response = request(
            "/api/render",
            {
                "kind": "ui_click",
                "seed": 42,
                "duration": 0.08,
                "brightness": 0.7,
                "resonance": 0.4,
                "variation": 0.2,
            },
        )
        assert wav_response.status == 200
        assert wav_response.headers["content-type"] == "audio/wav"
        with wave.open(io.BytesIO(wav_response.body), "rb") as wav_file:
            assert wav_file.getnframes() > 0

        archive_response = request(
            "/api/bank",
            {
                "kind": "pickup",
                "seed": 11,
                "count": 3,
                "duration": 0.08,
            },
        )
        assert archive_response.status == 200
        assert archive_response.headers["content-type"] == "application/zip"
        with zipfile.ZipFile(io.BytesIO(archive_response.body)) as archive:
            assert len([name for name in archive.namelist() if name.endswith(".wav")]) == 3
            assert "manifest.json" in archive.namelist()
        print("SMOKE: browser assets, WAV route, and ZIP bank route responded correctly")
        print("SMOKE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
