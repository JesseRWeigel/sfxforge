import hashlib
import io
import json
import math
import random
import tempfile
import unittest
import wave
import zipfile
from pathlib import Path

from sfxforge.engine import (
    build_bank_archive,
    export_bank,
    granular_scatter,
    modal_resonator,
    render_wav_bytes,
    shaped_noise,
    synthesize,
)
from sfxforge.presets import PRESETS, SURFACES


class SynthesisTests(unittest.TestCase):
    def test_all_effects_produce_finite_non_silent_audio(self) -> None:
        for index, kind in enumerate(PRESETS):
            with self.subTest(kind=kind):
                samples = synthesize(
                    kind,
                    seed=100 + index,
                    sample_rate=8_000,
                    parameters={"duration": 0.08},
                )
                self.assertEqual(len(samples), 640)
                self.assertTrue(all(math.isfinite(sample) for sample in samples))
                self.assertGreater(max(abs(sample) for sample in samples), 0.1)
                self.assertLessEqual(max(abs(sample) for sample in samples), 1.0)

    def test_same_seed_produces_identical_wav(self) -> None:
        first = render_wav_bytes(
            "footstep",
            seed=8472,
            sample_rate=12_000,
            parameters={"duration": 0.12, "surface": "wood"},
        )
        second = render_wav_bytes(
            "footstep",
            seed=8472,
            sample_rate=12_000,
            parameters={"duration": 0.12, "surface": "wood"},
        )
        self.assertEqual(hashlib.sha256(first).digest(), hashlib.sha256(second).digest())

    def test_different_seeds_produce_distinct_variations(self) -> None:
        hashes = {
            hashlib.sha256(
                render_wav_bytes(
                    "footstep",
                    seed=seed,
                    sample_rate=8_000,
                    parameters={"duration": 0.08, "surface": "dirt"},
                )
            ).hexdigest()
            for seed in range(20)
        }
        self.assertEqual(len(hashes), 20)

    def test_one_hundred_footsteps_are_distinct(self) -> None:
        hashes = {
            hashlib.sha256(
                render_wav_bytes(
                    "footstep",
                    seed=seed,
                    sample_rate=8_000,
                    parameters={"duration": 0.04, "surface": "dirt"},
                )
            ).hexdigest()
            for seed in range(100)
        }
        self.assertEqual(len(hashes), 100)

    def test_every_surface_changes_footstep_audio(self) -> None:
        hashes = {
            hashlib.sha256(
                render_wav_bytes(
                    "footstep",
                    seed=19,
                    sample_rate=8_000,
                    parameters={"duration": 0.08, "surface": surface},
                )
            ).hexdigest()
            for surface in SURFACES
        }
        self.assertEqual(len(hashes), len(SURFACES))

    def test_wav_is_mono_16_bit_pcm_at_requested_rate(self) -> None:
        wav_bytes = render_wav_bytes(
            "ui_click",
            seed=3,
            sample_rate=22_050,
            parameters={"duration": 0.1},
        )
        with wave.open(io.BytesIO(wav_bytes), "rb") as wav_file:
            self.assertEqual(wav_file.getnchannels(), 1)
            self.assertEqual(wav_file.getsampwidth(), 2)
            self.assertEqual(wav_file.getframerate(), 22_050)
            self.assertEqual(wav_file.getnframes(), 2_205)

    def test_noise_shaping_and_resonator_are_active(self) -> None:
        noise = shaped_noise(600, random.Random(4), 8_000, 900, 80)
        resonated = modal_resonator(noise, 340, 0.12, 8_000)
        self.assertEqual(len(noise), len(resonated))
        self.assertNotEqual(noise, resonated)
        self.assertGreater(sum(abs(value) for value in resonated), 0.01)

    def test_granular_scatter_is_seeded_and_populated(self) -> None:
        first = granular_scatter(1_200, random.Random(99), 8_000, 9, 1_200, 0.4)
        second = granular_scatter(1_200, random.Random(99), 8_000, 9, 1_200, 0.4)
        self.assertEqual(first, second)
        self.assertGreater(sum(value != 0.0 for value in first), 50)

    def test_invalid_effect_surface_and_sample_rate_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "unknown effect"):
            synthesize("laser")
        with self.assertRaisesRegex(ValueError, "unknown surface"):
            synthesize("footstep", parameters={"surface": "water"})
        with self.assertRaisesRegex(ValueError, "sample rate"):
            synthesize("impact", sample_rate=100)


class BankTests(unittest.TestCase):
    def test_archive_contains_wavs_and_seed_manifest(self) -> None:
        archive_bytes = build_bank_archive(
            "pickup",
            count=4,
            seed=250,
            sample_rate=8_000,
            parameters={"duration": 0.07},
        )
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            names = archive.namelist()
            self.assertEqual(
                names,
                [
                    "pickup_001.wav",
                    "pickup_002.wav",
                    "pickup_003.wav",
                    "pickup_004.wav",
                    "manifest.json",
                ],
            )
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["format"], "sfxforge-bank-v1")
            self.assertEqual(manifest["count"], 4)
            self.assertEqual([item["seed"] for item in manifest["files"]], [250, 251, 252, 253])
            self.assertEqual(
                set(manifest["parameters"]),
                {"duration", "brightness", "resonance", "variation"},
            )
            self.assertTrue(archive.read("pickup_001.wav").startswith(b"RIFF"))

    def test_directory_reexport_removes_files_from_previous_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary) / "bank"
            export_bank("impact", 3, destination, seed=10)
            unrelated = destination / "notes.txt"
            unrelated.write_text("keep", encoding="utf-8")
            export_bank("impact", 1, destination, seed=20)

            self.assertEqual(
                sorted(path.name for path in destination.glob("*.wav")),
                ["impact_001.wav"],
            )
            self.assertEqual(json.loads((destination / "manifest.json").read_text())["count"], 1)
            self.assertEqual(unrelated.read_text(encoding="utf-8"), "keep")

    def test_manifest_records_effective_clamped_parameters(self) -> None:
        archive_bytes = build_bank_archive(
            "footstep",
            count=1,
            parameters={"duration": 9, "brightness": -2, "surface": "metal"},
        )
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            parameters = json.loads(archive.read("manifest.json"))["parameters"]
        self.assertEqual(
            parameters,
            {
                "brightness": 0.0,
                "duration": 3.0,
                "resonance": PRESETS["footstep"]["resonance"],
                "surface": "metal",
                "variation": PRESETS["footstep"]["variation"],
            },
        )

    def test_bank_size_has_a_safe_limit(self) -> None:
        with self.assertRaisesRegex(ValueError, "between 1 and 256"):
            build_bank_archive("impact", 257)


if __name__ == "__main__":
    unittest.main()
