from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .battle.axle_import import AxleImportError, AxlePlanImporter
from .battle.catalog import EmptyAxleCatalog
from .battle.preparation import PreparationPlanner
from .core.device import AdbDiscovery, DeviceError


def _json_default(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, (set, frozenset, tuple)):
        return list(value)
    raise TypeError(f"Value of type {type(value).__name__} is not JSON serializable")


def _plan_summary(path: Path) -> dict[str, Any]:
    plan = AxlePlanImporter().import_file(path)
    preparation = PreparationPlanner(EmptyAxleCatalog()).compile(plan)
    return {
        "name": plan.name,
        "source_version": plan.source_version,
        "source_path": plan.source_path,
        "language": plan.language,
        "party_profiles": [
            {
                "team_tab": profile.tab_id,
                "members": [
                    None
                    if member is None
                    else {
                        "slot": member.slot,
                        "character_id": member.character_id,
                        "team": member.team,
                        "style": member.style,
                        "style_id": member.style_id,
                        "passive_skills": list(member.passive_skills),
                        "support": _json_default(member.support),
                    }
                    for member in profile.members
                ],
            }
            for profile in plan.parties
        ],
        "turns": [
            {
                "index": turn.index,
                "label": turn.label,
                "kind": turn.kind.value,
                "overdrive": None if turn.overdrive is None else _json_default(turn.overdrive),
                "actions": [
                    None
                    if action is None
                    else {
                        "slot": action.slot,
                        "team_tab": action.team_tab,
                        "character_id": action.character_id,
                        "style": action.style,
                        "style_id": action.style_id,
                        "skill_value": action.skill_value,
                        "target_value": action.target_value,
                    }
                    for action in turn.actions
                ],
            }
            for turn in plan.turns
        ],
        "action_count": plan.action_count,
        "required_skill_count": len(preparation.required_skills),
        "required_passive_skill_count": len(preparation.required_passive_skills),
        "unresolved_skill_values": preparation.unresolved_skill_values,
        "unresolved_passive_values": preparation.unresolved_passive_values,
        "warnings": plan.warnings,
        "note": "A catalog must be supplied to validate learned/equipped skills; this command does not connect to the game.",
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="hbr-auto", description="Python-first HBR automation foundations")
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser("inspect-plan", help="Import and print an AxleTool JPEG plan")
    import_parser.add_argument("image", type=Path, help="AxleTool-exported JPG/JPEG")
    import_parser.add_argument("--output", type=Path, help="Write JSON summary to this file")

    adb_parser = subparsers.add_parser("adb-devices", help="List ADB devices visible to this host")
    adb_parser.add_argument("--adb-path", type=Path, help="Path to adb executable")

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "inspect-plan":
            summary = _plan_summary(args.image)
            output = json.dumps(summary, ensure_ascii=False, indent=2, default=_json_default)
            if args.output:
                args.output.write_text(output + "\n", encoding="utf-8")
            else:
                print(output)
            return 0
        if args.command == "adb-devices":
            devices = AdbDiscovery(args.adb_path).discover()
            print(json.dumps([_json_default(device) for device in devices], ensure_ascii=False, indent=2))
            return 0
    except (AxleImportError, DeviceError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2
