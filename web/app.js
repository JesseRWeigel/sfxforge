"use strict";

const state = {
  presets: {},
  surfaces: {},
  kind: "impact",
  seed: 36,
  wavBlob: null,
  wavUrl: null,
  audio: null,
};

const icons = {
  impact: "✦",
  pickup: "◇",
  ui_click: "⌁",
  footstep: "◒",
};

const techniqueLabels = {
  impact: "NOISE + MODES",
  pickup: "SWEEP + GRAINS",
  ui_click: "OSC + NOISE",
  footstep: "NOISE + GRAINS",
};

const elements = {
  voiceGrid: document.querySelector("#voice-grid"),
  surfaceField: document.querySelector("#surface-field"),
  surface: document.querySelector("#surface"),
  duration: document.querySelector("#duration"),
  brightness: document.querySelector("#brightness"),
  resonance: document.querySelector("#resonance"),
  variation: document.querySelector("#variation"),
  seedReadout: document.querySelector("#seed-readout"),
  randomize: document.querySelector("#randomize"),
  effectIndex: document.querySelector("#effect-index"),
  effectName: document.querySelector("#effect-name"),
  effectDescription: document.querySelector("#effect-description"),
  technique: document.querySelector("#technique"),
  waveform: document.querySelector("#waveform"),
  durationLabel: document.querySelector("#duration-label"),
  play: document.querySelector("#play"),
  render: document.querySelector("#render"),
  downloadOne: document.querySelector("#download-one"),
  exportBank: document.querySelector("#export-bank"),
  count: document.querySelector("#count"),
  status: document.querySelector("#status"),
};

function setStatus(message, isError = false) {
  elements.status.textContent = message;
  elements.status.classList.toggle("error", isError);
}

function parameterPayload() {
  return {
    kind: state.kind,
    seed: state.seed,
    sample_rate: 44100,
    surface: elements.surface.value,
    duration: Number(elements.duration.value),
    brightness: Number(elements.brightness.value),
    resonance: Number(elements.resonance.value),
    variation: Number(elements.variation.value),
  };
}

function updateRange(input) {
  const minimum = Number(input.min);
  const maximum = Number(input.max);
  const percent = ((Number(input.value) - minimum) / (maximum - minimum)) * 100;
  input.style.setProperty("--fill", `${percent}%`);
  const output = document.querySelector(`#${input.id}-value`);
  if (input.id === "duration") {
    output.value = `${Number(input.value).toFixed(2)} s`;
    elements.durationLabel.textContent = `0:${Number(input.value).toFixed(2).padStart(5, "0")}`;
  } else {
    output.value = `${Math.round(Number(input.value) * 100)}%`;
  }
}

function setPreset(kind) {
  state.kind = kind;
  const keys = Object.keys(state.presets);
  const preset = state.presets[kind];
  elements.duration.value = preset.duration;
  elements.brightness.value = preset.brightness;
  elements.resonance.value = preset.resonance;
  elements.variation.value = preset.variation;
  [elements.duration, elements.brightness, elements.resonance, elements.variation].forEach(updateRange);

  document.querySelectorAll(".voice-button").forEach((button) => {
    const active = button.dataset.kind === kind;
    button.classList.toggle("active", active);
    button.setAttribute("aria-checked", active ? "true" : "false");
  });
  elements.surfaceField.classList.toggle("hidden", kind !== "footstep");
  elements.effectIndex.textContent = `VOICE ${String(keys.indexOf(kind) + 1).padStart(2, "0")}`;
  elements.effectName.textContent = preset.label;
  elements.effectDescription.textContent = preset.description;
  elements.technique.textContent = techniqueLabels[kind];
  clearRenderedSound();
  drawPlaceholder();
}

function buildVoiceButtons() {
  elements.voiceGrid.replaceChildren();
  Object.entries(state.presets).forEach(([kind, preset]) => {
    const button = document.createElement("button");
    button.className = "voice-button";
    button.type = "button";
    button.dataset.kind = kind;
    button.setAttribute("role", "radio");
    button.innerHTML = `
      <span class="icon" aria-hidden="true">${icons[kind]}</span>
      <span><b>${preset.label}</b><small>${techniqueLabels[kind]}</small></span>
    `;
    button.addEventListener("click", () => setPreset(kind));
    elements.voiceGrid.append(button);
  });
}

function buildSurfaceOptions() {
  elements.surface.replaceChildren();
  Object.entries(state.surfaces).forEach(([key, surface]) => {
    const option = document.createElement("option");
    option.value = key;
    option.textContent = surface.label;
    elements.surface.append(option);
  });
}

function clearRenderedSound() {
  if (state.audio) {
    state.audio.pause();
  }
  if (state.wavUrl) {
    URL.revokeObjectURL(state.wavUrl);
  }
  state.wavBlob = null;
  state.wavUrl = null;
  state.audio = null;
  elements.downloadOne.disabled = true;
}

function canvasContext() {
  const canvas = elements.waveform;
  const scale = window.devicePixelRatio || 1;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  if (canvas.width !== Math.round(width * scale) || canvas.height !== Math.round(height * scale)) {
    canvas.width = Math.round(width * scale);
    canvas.height = Math.round(height * scale);
  }
  const context = canvas.getContext("2d");
  context.setTransform(scale, 0, 0, scale, 0, 0);
  return { context, width, height };
}

function drawPlaceholder() {
  const { context, width, height } = canvasContext();
  context.clearRect(0, 0, width, height);
  context.beginPath();
  context.moveTo(0, height / 2);
  for (let x = 0; x <= width; x += 3) {
    const decay = Math.exp(-x / Math.max(1, width * 0.23));
    const wave = Math.sin(x * 0.32) * decay * height * 0.22;
    context.lineTo(x, height / 2 + wave);
  }
  context.strokeStyle = "rgba(200, 247, 101, 0.25)";
  context.lineWidth = 1;
  context.stroke();
}

function drawWaveform(buffer) {
  const samples = buffer.getChannelData(0);
  const { context, width, height } = canvasContext();
  const center = height / 2;
  const bucket = Math.max(1, Math.floor(samples.length / width));
  context.clearRect(0, 0, width, height);
  context.beginPath();
  for (let x = 0; x < width; x += 1) {
    let minimum = 1;
    let maximum = -1;
    const start = x * bucket;
    const end = Math.min(samples.length, start + bucket);
    for (let index = start; index < end; index += 1) {
      minimum = Math.min(minimum, samples[index]);
      maximum = Math.max(maximum, samples[index]);
    }
    context.moveTo(x, center + minimum * center * 0.86);
    context.lineTo(x, center + maximum * center * 0.86);
  }
  context.strokeStyle = "#c8f765";
  context.lineWidth = 1;
  context.stroke();
}

async function renderSound(playAfter = false) {
  elements.play.classList.add("busy");
  setStatus("Synthesizing with the local CPU engine...");
  try {
    const response = await fetch("/api/render", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(parameterPayload()),
    });
    if (!response.ok) {
      const payload = await response.json();
      throw new Error(payload.error || `render failed with status ${response.status}`);
    }
    clearRenderedSound();
    state.wavBlob = await response.blob();
    state.wavUrl = URL.createObjectURL(state.wavBlob);
    state.audio = new Audio(state.wavUrl);
    const audioContext = new AudioContext();
    const audioData = await state.wavBlob.arrayBuffer();
    const decoded = await audioContext.decodeAudioData(audioData.slice(0));
    drawWaveform(decoded);
    await audioContext.close();
    elements.downloadOne.disabled = false;
    setStatus(`Rendered ${state.kind} seed ${state.seed} · ${(state.wavBlob.size / 1024).toFixed(1)} KB`);
    if (playAfter) {
      await state.audio.play();
    }
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    elements.play.classList.remove("busy");
  }
}

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

async function exportBank() {
  elements.exportBank.disabled = true;
  const count = Number(elements.count.value);
  setStatus(`Synthesizing ${count} variations...`);
  try {
    const response = await fetch("/api/bank", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...parameterPayload(), count }),
    });
    if (!response.ok) {
      const payload = await response.json();
      throw new Error(payload.error || `bank export failed with status ${response.status}`);
    }
    const archive = await response.blob();
    downloadBlob(archive, `${state.kind}_bank.zip`);
    setStatus(`Exported ${count} repeatable variations · ${(archive.size / 1024).toFixed(1)} KB`);
  } catch (error) {
    setStatus(error.message, true);
  } finally {
    elements.exportBank.disabled = false;
  }
}

function bindEvents() {
  [elements.duration, elements.brightness, elements.resonance, elements.variation].forEach((input) => {
    input.addEventListener("input", () => {
      updateRange(input);
      clearRenderedSound();
    });
  });
  elements.surface.addEventListener("change", clearRenderedSound);
  elements.randomize.addEventListener("click", () => {
    state.seed = Math.floor(Math.random() * 1_000_000);
    elements.seedReadout.value = `Seed ${state.seed}`;
    clearRenderedSound();
    drawPlaceholder();
    setStatus("New seed ready.");
  });
  elements.render.addEventListener("click", () => renderSound(false));
  elements.play.addEventListener("click", async () => {
    if (state.audio && state.wavUrl) {
      state.audio.currentTime = 0;
      await state.audio.play();
      return;
    }
    await renderSound(true);
  });
  elements.downloadOne.addEventListener("click", () => {
    if (state.wavBlob) {
      downloadBlob(state.wavBlob, `${state.kind}_${state.seed}.wav`);
    }
  });
  elements.exportBank.addEventListener("click", exportBank);
  window.addEventListener("resize", () => {
    if (!state.wavBlob) {
      drawPlaceholder();
    }
  });
}

async function initialize() {
  try {
    const response = await fetch("/api/presets");
    if (!response.ok) {
      throw new Error("Could not load synthesizer presets.");
    }
    const payload = await response.json();
    state.presets = payload.presets;
    state.surfaces = payload.surfaces;
    buildVoiceButtons();
    buildSurfaceOptions();
    bindEvents();
    setPreset("impact");
    elements.seedReadout.value = `Seed ${state.seed}`;
  } catch (error) {
    setStatus(error.message, true);
  }
}

initialize();
