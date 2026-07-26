"""Small, dependency-free procedural audio engine."""

from __future__ import annotations

import io
import json
import math
import random
import struct
import wave
import zipfile
from pathlib import Path
from typing import Iterable

from .presets import PRESETS, SURFACES

MIN_SAMPLE_RATE = 8_000
MAX_SAMPLE_RATE = 96_000


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _one_pole_lowpass(samples: Iterable[float], cutoff: float, sample_rate: int) -> list[float]:
    cutoff = max(20.0, min(cutoff, sample_rate * 0.45))
    alpha = 1.0 - math.exp(-2.0 * math.pi * cutoff / sample_rate)
    output: list[float] = []
    state = 0.0
    for sample in samples:
        state += alpha * (sample - state)
        output.append(state)
    return output


def _one_pole_highpass(samples: list[float], cutoff: float, sample_rate: int) -> list[float]:
    low = _one_pole_lowpass(samples, cutoff, sample_rate)
    return [sample - low_sample for sample, low_sample in zip(samples, low)]


def shaped_noise(
    length: int,
    rng: random.Random,
    sample_rate: int,
    cutoff: float,
    highpass: float = 0.0,
) -> list[float]:
    """Create filtered white noise using one-pole low-pass and high-pass stages."""
    source = [rng.uniform(-1.0, 1.0) for _ in range(length)]
    filtered = _one_pole_lowpass(source, cutoff, sample_rate)
    if highpass > 0.0:
        filtered = _one_pole_highpass(filtered, highpass, sample_rate)
    return filtered


def modal_resonator(
    excitation: list[float],
    frequency: float,
    decay: float,
    sample_rate: int,
) -> list[float]:
    """Pass an excitation through a stable damped two-pole resonator."""
    frequency = max(20.0, min(frequency, sample_rate * 0.45))
    decay = max(0.012, decay)
    radius = math.exp(-1.0 / (decay * sample_rate))
    coefficient = 2.0 * radius * math.cos(2.0 * math.pi * frequency / sample_rate)
    radius_squared = radius * radius
    output = [0.0] * len(excitation)
    previous = 0.0
    previous_two = 0.0
    for index, sample in enumerate(excitation):
        current = sample + coefficient * previous - radius_squared * previous_two
        output[index] = current * (1.0 - radius)
        previous_two = previous
        previous = current
    return output


def granular_scatter(
    length: int,
    rng: random.Random,
    sample_rate: int,
    count: int,
    center_frequency: float,
    spread: float,
    latest_start: float = 0.8,
) -> list[float]:
    """Scatter short windowed grains across a buffer using deterministic randomness."""
    output = [0.0] * length
    for _ in range(max(1, count)):
        grain_seconds = rng.uniform(0.006, 0.032)
        grain_length = max(3, int(grain_seconds * sample_rate))
        start_limit = max(1, int(max(0.0, latest_start) * max(0, length - grain_length)))
        start = rng.randrange(start_limit) if start_limit > 1 else 0
        frequency = max(40.0, center_frequency * rng.uniform(1.0 - spread, 1.0 + spread))
        phase = rng.random() * math.tau
        amplitude = rng.uniform(0.12, 0.44)
        use_noise = rng.random() < 0.42
        for offset in range(min(grain_length, length - start)):
            position = offset / max(1, grain_length - 1)
            window = math.sin(math.pi * position) ** 2
            carrier = rng.uniform(-1.0, 1.0) if use_noise else math.sin(
                phase + math.tau * frequency * offset / sample_rate
            )
            output[start + offset] += carrier * window * amplitude
    return output


def _add(target: list[float], source: list[float], gain: float = 1.0) -> None:
    for index in range(min(len(target), len(source))):
        target[index] += source[index] * gain


def _fade_and_normalize(samples: list[float], sample_rate: int) -> list[float]:
    fade_samples = min(len(samples) // 4, max(8, int(sample_rate * 0.008)))
    for index in range(fade_samples):
        samples[index] *= index / fade_samples
        samples[-1 - index] *= index / fade_samples
    peak = max((abs(sample) for sample in samples), default=0.0)
    if peak > 0.0:
        gain = 0.94 / peak
        samples = [math.tanh(sample * gain * 1.15) / math.tanh(1.15) * 0.94 for sample in samples]
    return samples


def _resolved_parameters(
    kind: str,
    parameters: dict[str, float | str] | None,
) -> dict[str, float | str]:
    if kind not in PRESETS:
        raise ValueError(f"unknown effect kind: {kind}")
    settings = dict(PRESETS[kind])
    settings.update(parameters or {})
    resolved: dict[str, float | str] = {
        "duration": max(0.03, min(3.0, float(settings["duration"]))),
        "brightness": _clamp(float(settings["brightness"])),
        "resonance": _clamp(float(settings["resonance"])),
        "variation": _clamp(float(settings["variation"])),
    }
    if kind == "footstep":
        surface = str(settings.get("surface", "dirt"))
        if surface not in SURFACES:
            raise ValueError(f"unknown surface: {surface}")
        resolved["surface"] = surface
    return resolved


def _impact(
    length: int,
    rng: random.Random,
    sample_rate: int,
    brightness: float,
    resonance: float,
    variation: float,
) -> list[float]:
    output = [0.0] * length
    noise = shaped_noise(
        length,
        rng,
        sample_rate,
        900.0 + brightness * 9_500.0,
        30.0,
    )
    for index in range(length):
        time = index / sample_rate
        noise[index] *= math.exp(-time * (24.0 - variation * 7.0))
    _add(output, noise, 0.92)

    impulse_length = max(2, int(sample_rate * 0.012))
    impulse = [0.0] * length
    for index in range(impulse_length):
        impulse[index] = rng.uniform(-1.0, 1.0) * math.exp(-index / max(1, impulse_length / 4))
    base = rng.uniform(68.0, 112.0) * (0.82 + brightness * 0.36)
    for ratio, gain in ((1.0, 1.0), (2.17, 0.58), (3.63, 0.31), (6.1, 0.14)):
        mode = modal_resonator(
            impulse,
            base * ratio * rng.uniform(0.96, 1.04),
            0.08 + resonance * (0.5 / math.sqrt(ratio)),
            sample_rate,
        )
        _add(output, mode, gain * 30.0)

    debris = granular_scatter(
        length,
        rng,
        sample_rate,
        4 + int(variation * 10),
        1_100.0 + brightness * 3_800.0,
        0.72,
        0.52,
    )
    _add(output, debris, 0.2 + variation * 0.28)
    return output


def _pickup(
    length: int,
    rng: random.Random,
    sample_rate: int,
    brightness: float,
    resonance: float,
    variation: float,
) -> list[float]:
    output = [0.0] * length
    duration = length / sample_rate
    start_frequency = rng.uniform(360.0, 470.0) * (0.88 + brightness * 0.24)
    end_frequency = start_frequency * rng.uniform(2.1, 2.75)
    phase = rng.random() * math.tau
    for index in range(length):
        position = index / max(1, length - 1)
        envelope = math.sin(math.pi * position) ** 0.7 * math.exp(-position * 0.65)
        frequency = start_frequency * ((end_frequency / start_frequency) ** position)
        phase += math.tau * frequency / sample_rate
        shimmer = math.sin(phase) + 0.28 * math.sin(phase * 2.01)
        output[index] = shimmer * envelope * 0.46

    grains = granular_scatter(
        length,
        rng,
        sample_rate,
        6 + int(variation * 12),
        end_frequency * (1.2 + brightness * 0.9),
        0.58,
        0.9,
    )
    _add(output, grains, 0.28 + resonance * 0.26)

    excitation = [0.0] * length
    strike = min(length, max(2, int(sample_rate * 0.005)))
    for index in range(strike):
        excitation[index] = rng.uniform(-1.0, 1.0) * (1.0 - index / strike)
    bell = modal_resonator(
        excitation,
        end_frequency * rng.uniform(1.45, 1.65),
        0.09 + resonance * 0.34,
        sample_rate,
    )
    _add(output, bell, 9.5)
    return output


def _ui_click(
    length: int,
    rng: random.Random,
    sample_rate: int,
    brightness: float,
    resonance: float,
    variation: float,
) -> list[float]:
    output = [0.0] * length
    frequency = rng.uniform(720.0, 980.0) * (0.72 + brightness * 0.6)
    phase = rng.random() * math.tau
    noise = shaped_noise(
        length,
        rng,
        sample_rate,
        1_800.0 + brightness * 11_000.0,
        160.0,
    )
    for index in range(length):
        time = index / sample_rate
        tone_envelope = math.exp(-time * (42.0 - resonance * 22.0))
        noise_envelope = math.exp(-time * (105.0 - variation * 24.0))
        tone = math.sin(phase + math.tau * frequency * time)
        output[index] = tone * tone_envelope * 0.62 + noise[index] * noise_envelope * 0.52
    return output


def _footstep(
    length: int,
    rng: random.Random,
    sample_rate: int,
    brightness: float,
    resonance: float,
    variation: float,
    surface: str,
) -> list[float]:
    surface_data = SURFACES[surface]
    output = [0.0] * length
    color = float(surface_data["noise_color"])
    cutoff = 650.0 + color * 8_500.0 + brightness * 2_100.0
    noise = shaped_noise(length, rng, sample_rate, cutoff, 28.0 + color * 170.0)
    attack = rng.uniform(0.006, 0.019)
    decay = float(surface_data["decay"]) * rng.uniform(0.86, 1.17)
    for index in range(length):
        time = index / sample_rate
        envelope = min(1.0, time / attack) * math.exp(-time / decay)
        noise[index] *= envelope
    _add(output, noise, 0.78)

    impulse = [0.0] * length
    contact = min(length, max(2, int(sample_rate * 0.016)))
    for index in range(contact):
        impulse[index] = rng.uniform(-1.0, 1.0) * math.exp(-index / max(1, contact / 3.0))
    body_frequency = float(surface_data["body_frequency"]) * rng.uniform(
        1.0 - variation * 0.13,
        1.0 + variation * 0.13,
    )
    body = modal_resonator(
        impulse,
        body_frequency,
        0.045 + resonance * float(surface_data["decay"]),
        sample_rate,
    )
    _add(output, body, 20.0 + resonance * 14.0)

    grains = granular_scatter(
        length,
        rng,
        sample_rate,
        int(surface_data["grain_count"]) + rng.randrange(0, 4),
        float(surface_data["grain_frequency"]) * (0.8 + brightness * 0.38),
        0.62 + variation * 0.2,
        0.78,
    )
    _add(output, grains, 0.22 + variation * 0.25)
    return output


def synthesize(
    kind: str,
    seed: int = 0,
    sample_rate: int = 44_100,
    parameters: dict[str, float | str] | None = None,
) -> list[float]:
    """Synthesize one mono sound effect as floating-point samples."""
    if not MIN_SAMPLE_RATE <= sample_rate <= MAX_SAMPLE_RATE:
        raise ValueError(f"sample rate must be between {MIN_SAMPLE_RATE} and {MAX_SAMPLE_RATE}")

    settings = _resolved_parameters(kind, parameters)
    duration = float(settings["duration"])
    brightness = float(settings["brightness"])
    resonance = float(settings["resonance"])
    variation = float(settings["variation"])
    surface = str(settings.get("surface", "dirt"))

    length = max(1, int(round(duration * sample_rate)))
    rng = random.Random(int(seed))
    if kind == "impact":
        samples = _impact(length, rng, sample_rate, brightness, resonance, variation)
    elif kind == "pickup":
        samples = _pickup(length, rng, sample_rate, brightness, resonance, variation)
    elif kind == "ui_click":
        samples = _ui_click(length, rng, sample_rate, brightness, resonance, variation)
    else:
        samples = _footstep(
            length,
            rng,
            sample_rate,
            brightness,
            resonance,
            variation,
            surface,
        )
    return _fade_and_normalize(samples, sample_rate)


def samples_to_wav_bytes(samples: list[float], sample_rate: int = 44_100) -> bytes:
    """Encode floating-point mono samples as signed 16-bit PCM WAV."""
    buffer = io.BytesIO()
    pcm = bytearray()
    for sample in samples:
        pcm.extend(struct.pack("<h", int(_clamp(sample, -1.0, 1.0) * 32_767)))
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(bytes(pcm))
    return buffer.getvalue()


def render_wav_bytes(
    kind: str,
    seed: int = 0,
    sample_rate: int = 44_100,
    parameters: dict[str, float | str] | None = None,
) -> bytes:
    """Synthesize and encode one effect."""
    return samples_to_wav_bytes(
        synthesize(kind, seed=seed, sample_rate=sample_rate, parameters=parameters),
        sample_rate,
    )


def build_bank_archive(
    kind: str,
    count: int,
    seed: int = 0,
    sample_rate: int = 44_100,
    parameters: dict[str, float | str] | None = None,
) -> bytes:
    """Build an in-memory ZIP bank containing WAV files and a JSON manifest."""
    if not 1 <= count <= 256:
        raise ValueError("bank count must be between 1 and 256")
    parameter_values = _resolved_parameters(kind, parameters)
    manifest = {
        "format": "sfxforge-bank-v1",
        "kind": kind,
        "base_seed": int(seed),
        "count": count,
        "sample_rate": sample_rate,
        "parameters": parameter_values,
        "files": [],
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for index in range(count):
            item_seed = int(seed) + index
            filename = f"{kind}_{index + 1:03d}.wav"
            wav_bytes = render_wav_bytes(
                kind,
                seed=item_seed,
                sample_rate=sample_rate,
                parameters=parameter_values,
            )
            archive.writestr(filename, wav_bytes)
            manifest["files"].append({"file": filename, "seed": item_seed})
        archive.writestr("manifest.json", json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    return buffer.getvalue()


def export_bank(
    kind: str,
    count: int,
    destination: str | Path,
    seed: int = 0,
    sample_rate: int = 44_100,
    parameters: dict[str, float | str] | None = None,
) -> Path:
    """Write a directory of WAV files plus a manifest and return its path."""
    if not 1 <= count <= 256:
        raise ValueError("bank count must be between 1 and 256")
    destination_path = Path(destination)
    destination_path.mkdir(parents=True, exist_ok=True)
    parameter_values = _resolved_parameters(kind, parameters)
    old_manifest_path = destination_path / "manifest.json"
    try:
        old_manifest = json.loads(old_manifest_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError):
        old_manifest = {}
    old_files = old_manifest.get("files", []) if isinstance(old_manifest, dict) else []
    if isinstance(old_files, list):
        for item in old_files:
            if not isinstance(item, dict) or not isinstance(item.get("file"), str):
                continue
            old_name = Path(item["file"])
            if old_name.name == str(old_name) and old_name.suffix.lower() == ".wav":
                (destination_path / old_name).unlink(missing_ok=True)
    manifest = {
        "format": "sfxforge-bank-v1",
        "kind": kind,
        "base_seed": int(seed),
        "count": count,
        "sample_rate": sample_rate,
        "parameters": parameter_values,
        "files": [],
    }
    for index in range(count):
        item_seed = int(seed) + index
        filename = f"{kind}_{index + 1:03d}.wav"
        wav_bytes = render_wav_bytes(
            kind,
            seed=item_seed,
            sample_rate=sample_rate,
            parameters=parameter_values,
        )
        (destination_path / filename).write_bytes(wav_bytes)
        manifest["files"].append({"file": filename, "seed": item_seed})
    (destination_path / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return destination_path
