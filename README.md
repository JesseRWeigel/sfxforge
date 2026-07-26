# SFX Forge

SFX Forge is a dependency-free procedural sound-effects synthesizer for game audio.
It creates impacts, pickups, UI clicks, and footsteps using shaped noise, damped modal
resonators, tonal sweeps, and granular scattering. An integer seed makes every take
repeatable while sequential seeds produce distinct variations for sound banks.

Catalog task: `ART-036`. Part of [thousand](https://github.com/JesseRWeigel/722-things-to-build).

**[Read this on the web](https://jesserweigel.github.io/sfxforge/)**

The browser editor is a front end for the local Python server and cannot run on a static
host, because synthesis happens in Python. Run `python3 -m sfxforge serve` and open
`http://localhost:8000`. An earlier version of the Pages site advertised a hosted editor
that could not work; the link is gone rather than left to disappoint.

## What this is

The project includes:

- A Python synthesis engine that runs on CPU with no model weights
- Four effect families and dirt, grass, wood, metal, and stone footstep surfaces
- Controls for duration, brightness, resonance, variation, seed, and sample rate
- A command-line tool for individual WAV files and bank directories
- A responsive browser editor with waveform preview, playback, WAV download, and ZIP bank export
- JSON manifests that record each bank's parameters and per-file seed
- Mono 16-bit PCM WAV output at sample rates from 8 kHz through 96 kHz

The browser editor and CLI use the same synthesis engine. The careful-engineering
assumption for the task is that a browser editor may call a local Python service.
This keeps audio generation consistent across batch and interactive workflows.

## Running it

Python 3.10 or newer is required. No package installation is needed.

Start the browser editor:

```bash
python3 -m sfxforge serve
```

Then open `http://127.0.0.1:8765`.

Render one effect:

```bash
python3 -m sfxforge render \
  --kind impact \
  --seed 36 \
  --brightness 0.65 \
  --resonance 0.8 \
  --output impact.wav
```

Export a bank of varied footsteps:

```bash
python3 -m sfxforge bank \
  --kind footstep \
  --surface wood \
  --seed 720 \
  --count 100 \
  --output wood-footsteps
```

List effect and surface names:

```bash
python3 -m sfxforge list
```

## Verification

Run from the project root:

```bash
python3 -m unittest discover -s tests -v && python3 scripts/smoke_test.py
```

The tests exercise the DSP primitives, all effect families, every footstep surface,
seed determinism, variation uniqueness, WAV encoding, bank manifests, validation,
static editor assets, and the HTTP routes. The smoke test drives the CLI and parses
its generated WAV files and ZIP bank.

## Defects found by independent review and fixed

A reviewer that did not build this audited it and found two ordering bugs where a rejected call
did damage before it failed. Both now have regression tests, including one asserting the normal
path still works, so the guards cannot be "fixed" by disabling the behaviour they protect.

**An invalid sample rate destroyed an existing bank.** `export_bank` created the destination and
deleted every WAV named in the old manifest, and only validated the sample rate once rendering
began. `--sample-rate 100` against a three-file bank deleted all three files and then reported an
error, leaving a manifest still claiming three files existed. All input validation now happens
before anything touches the filesystem.

**A corrupt manifest was silently treated as absent.** A manifest that existed but could not be
parsed fell into the same branch as no manifest at all, so a re-export left the old WAV files
orphaned on disk while writing a new manifest that claimed to describe the whole directory. That
now fails loudly and touches nothing, because a directory holding files this function cannot
account for is not a directory it should be cleaning up.

**The hosted editor claim was withdrawn.** The Pages site briefly advertised a browser editor.
The editor is a front end for the local Python server, synthesis happens in Python, and the
copied assets used root-relative paths that resolved outside the published subdirectory. Rather
than ship a link to a page that could not work, the link is gone and the README says the editor
is local. Run `python3 -m sfxforge serve` and open `http://localhost:8000`.

**The local server refused cross-origin requests.** Binding 127.0.0.1 stops other machines but
not the browser already running on this one. Any page could POST to localhost, and choosing
`Content-Type: text/plain` keeps the request "simple" so no CORS preflight is sent and the
browser never asks permission, while `/api/bank` performs synchronous synthesis. Three checks
now apply: a JSON Content-Type is required, which is the load-bearing one because it forces a
preflight the server never answers; a cross-origin `Origin` header is refused; and the `Host`
header must be a loopback name, which blocks DNS rebinding. Five tests cover the refusals and,
importantly, that a same-origin request and an Origin-less CLI request both still work.

**A bank download could be misnamed.** The request body was snapshotted but the filename read
the current selection at completion time, so starting an impact export and choosing footstep
before it finished downloaded impact audio named `footstep_bank.zip`. The effect name is now
snapshotted with the payload. The single-render path was already correct, because changing any
setting bumps a revision counter and clears the held blob.

## Status

Verified with exit code 0 on 2026-07-25. Exact output:

```text
test_archive_contains_wavs_and_seed_manifest (test_engine.BankTests.test_archive_contains_wavs_and_seed_manifest) ... ok
test_bank_size_has_a_safe_limit (test_engine.BankTests.test_bank_size_has_a_safe_limit) ... ok
test_directory_reexport_removes_files_from_previous_manifest (test_engine.BankTests.test_directory_reexport_removes_files_from_previous_manifest) ... ok
test_manifest_records_effective_clamped_parameters (test_engine.BankTests.test_manifest_records_effective_clamped_parameters) ... ok
test_all_effects_produce_finite_non_silent_audio (test_engine.SynthesisTests.test_all_effects_produce_finite_non_silent_audio) ... ok
test_different_seeds_produce_distinct_variations (test_engine.SynthesisTests.test_different_seeds_produce_distinct_variations) ... ok
test_every_surface_changes_footstep_audio (test_engine.SynthesisTests.test_every_surface_changes_footstep_audio) ... ok
test_granular_scatter_is_seeded_and_populated (test_engine.SynthesisTests.test_granular_scatter_is_seeded_and_populated) ... ok
test_invalid_effect_surface_and_sample_rate_are_rejected (test_engine.SynthesisTests.test_invalid_effect_surface_and_sample_rate_are_rejected) ... ok
test_noise_shaping_and_resonator_are_active (test_engine.SynthesisTests.test_noise_shaping_and_resonator_are_active) ... ok
test_one_hundred_footsteps_are_distinct (test_engine.SynthesisTests.test_one_hundred_footsteps_are_distinct) ... ok
test_same_seed_produces_identical_wav (test_engine.SynthesisTests.test_same_seed_produces_identical_wav) ... ok
test_wav_is_mono_16_bit_pcm_at_requested_rate (test_engine.SynthesisTests.test_wav_is_mono_16_bit_pcm_at_requested_rate) ... ok
test_bad_request_returns_json_error (test_server.ServerTests.test_bad_request_returns_json_error) ... ok
test_editor_assets_and_preset_api_are_served (test_server.ServerTests.test_editor_assets_and_preset_api_are_served) ... ok
test_render_api_returns_wav_audio (test_server.ServerTests.test_render_api_returns_wav_audio) ... ok

----------------------------------------------------------------------
Ran 16 tests in 0.279s

OK
SMOKE: CLI rendered valid 44.1 kHz mono PCM WAV
SMOKE: seed 3600 reproduced byte-identical audio
SMOKE: WAV bank exported 6 distinct seeded wood footsteps
SMOKE: browser assets, WAV route, and ZIP bank route responded correctly
SMOKE: PASS
```

## Unfinished

- Live TCP binding is outside the verification command because the builder sandbox
  denies socket creation. The real HTTP request handler is exercised with complete
  HTTP request and response bytes through an in-memory connection.
- Stereo, 24-bit PCM, and compressed audio exports are not implemented.
- The editor has fixed synthesis families. It does not yet expose custom modal
  frequency lists or a visual grain sequencer.

## License

MIT
