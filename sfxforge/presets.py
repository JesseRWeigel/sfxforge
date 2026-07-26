"""Preset metadata shared by the synthesizer, CLI, and browser editor."""

PRESETS = {
    "impact": {
        "label": "Impact",
        "description": "A sharp noise transient driving several damped resonant modes.",
        "duration": 0.62,
        "brightness": 0.48,
        "resonance": 0.72,
        "variation": 0.35,
    },
    "pickup": {
        "label": "Pickup",
        "description": "A rising tonal sweep with scattered bell-like grains.",
        "duration": 0.48,
        "brightness": 0.78,
        "resonance": 0.61,
        "variation": 0.28,
    },
    "ui_click": {
        "label": "UI click",
        "description": "A compact oscillator tick layered with a shaped noise snap.",
        "duration": 0.11,
        "brightness": 0.72,
        "resonance": 0.38,
        "variation": 0.18,
    },
    "footstep": {
        "label": "Footstep",
        "description": "Surface-shaped noise, body resonance, and scattered contact grains.",
        "duration": 0.34,
        "brightness": 0.42,
        "resonance": 0.52,
        "variation": 0.62,
    },
}

SURFACES = {
    "dirt": {
        "label": "Dirt",
        "noise_color": 0.13,
        "body_frequency": 92.0,
        "grain_frequency": 580.0,
        "grain_count": 13,
        "decay": 0.13,
    },
    "grass": {
        "label": "Grass",
        "noise_color": 0.2,
        "body_frequency": 78.0,
        "grain_frequency": 880.0,
        "grain_count": 18,
        "decay": 0.1,
    },
    "wood": {
        "label": "Wood",
        "noise_color": 0.34,
        "body_frequency": 168.0,
        "grain_frequency": 1350.0,
        "grain_count": 7,
        "decay": 0.2,
    },
    "metal": {
        "label": "Metal",
        "noise_color": 0.58,
        "body_frequency": 310.0,
        "grain_frequency": 2700.0,
        "grain_count": 5,
        "decay": 0.31,
    },
    "stone": {
        "label": "Stone",
        "noise_color": 0.41,
        "body_frequency": 128.0,
        "grain_frequency": 1900.0,
        "grain_count": 8,
        "decay": 0.17,
    },
}
