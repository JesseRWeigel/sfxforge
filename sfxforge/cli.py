"""Command-line interface for SFX Forge."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .engine import export_bank, render_wav_bytes
from .presets import PRESETS, SURFACES
from .server import create_server


def _add_effect_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--kind", required=True, choices=sorted(PRESETS))
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--sample-rate", type=int, default=44_100)
    parser.add_argument("--surface", choices=sorted(SURFACES), default="dirt")
    parser.add_argument("--duration", type=float)
    parser.add_argument("--brightness", type=float)
    parser.add_argument("--resonance", type=float)
    parser.add_argument("--variation", type=float)


def _parameters(args: argparse.Namespace) -> dict[str, float | str]:
    values: dict[str, float | str] = {"surface": args.surface}
    for name in ("duration", "brightness", "resonance", "variation"):
        value = getattr(args, name)
        if value is not None:
            values[name] = value
    return values


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sfxforge",
        description="Synthesize deterministic game sound effects with standard Python.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="list available effects and footstep surfaces")

    render_parser = subparsers.add_parser("render", help="render one WAV file")
    _add_effect_arguments(render_parser)
    render_parser.add_argument("--output", required=True, type=Path)

    bank_parser = subparsers.add_parser("bank", help="export a directory of varied WAV files")
    _add_effect_arguments(bank_parser)
    bank_parser.add_argument("--count", type=int, default=16)
    bank_parser.add_argument("--output", required=True, type=Path)

    serve_parser = subparsers.add_parser("serve", help="start the browser editor")
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8765)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "list":
            payload = {
                "effects": {
                    key: {"label": value["label"], "description": value["description"]}
                    for key, value in PRESETS.items()
                },
                "footstep_surfaces": {
                    key: value["label"] for key, value in SURFACES.items()
                },
            }
            print(json.dumps(payload, indent=2, sort_keys=True))
            return 0

        if args.command == "render":
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_bytes(
                render_wav_bytes(
                    args.kind,
                    seed=args.seed,
                    sample_rate=args.sample_rate,
                    parameters=_parameters(args),
                )
            )
            print(f"rendered {args.output} with seed {args.seed}")
            return 0

        if args.command == "bank":
            destination = export_bank(
                args.kind,
                args.count,
                args.output,
                seed=args.seed,
                sample_rate=args.sample_rate,
                parameters=_parameters(args),
            )
            print(f"exported {args.count} {args.kind} sounds to {destination}")
            return 0

        server = create_server(args.host, args.port)
        host, port = server.server_address[:2]
        print(f"SFX Forge editor: http://{host}:{port}", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
        finally:
            server.server_close()
        return 0
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
