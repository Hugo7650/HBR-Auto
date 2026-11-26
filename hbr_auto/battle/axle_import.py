from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .models import (
    BattleAction,
    BattlePlan,
    BattleTurn,
    OverdriveInstruction,
    PartyMemberSpec,
    PartyProfile,
    ProgressionSnapshot,
    ResonanceSupportSpec,
    TurnKind,
)


class AxleImportError(ValueError):
    """Base exception for invalid AxleTool files or payloads."""


class UnsupportedAxleVersionError(AxleImportError):
    pass


@dataclass(frozen=True, slots=True)
class AxleImportLimits:
    max_file_bytes: int = 20 * 1024 * 1024
    max_payload_chars: int = 4 * 1024 * 1024
    max_rows: int = 100
    max_string_length: int = 512


class AxlePlanImporter:
    """Import the HBR-AxleTool-vue JPEG export format (lz-string 1.5.0 Base64)."""

    SUPPORTED_VERSIONS = {"1.0.0", "1.0.1"}
    _OD_PATTERN = re.compile(r"^OD([1-5])(?:/Bonus([1-3]))?$")
    _TURN_PATTERN = re.compile(r"^T([1-9][0-9]?)$")

    def __init__(
        self,
        *,
        limits: AxleImportLimits | None = None,
        exif_reader: Callable[[bytes], bytes | str | None] | None = None,
        decompressor: Callable[[str], str | None] | None = None,
    ) -> None:
        self.limits = limits or AxleImportLimits()
        self._exif_reader = exif_reader or self._read_exif_user_comment
        self._decompressor = decompressor or self._decompress_lzstring

    def import_file(self, path: str | Path) -> BattlePlan:
        file_path = Path(path)
        try:
            data = file_path.read_bytes()
        except OSError as exc:
            raise AxleImportError(f"Unable to read AxleTool JPEG {file_path}: {exc}") from exc
        return self.import_bytes(data, source_path=str(file_path))

    def import_bytes(self, data: bytes, *, source_path: str | None = None) -> BattlePlan:
        if len(data) > self.limits.max_file_bytes:
            raise AxleImportError(
                f"JPEG exceeds the configured size limit ({len(data)} > {self.limits.max_file_bytes})"
            )
        if not data.startswith(b"\xff\xd8"):
            raise AxleImportError("AxleTool input must be a JPEG/JPG file")
        comment = self._exif_reader(data)
        if comment is None:
            raise AxleImportError("JPEG EXIF does not contain ExifIFD.UserComment")
        compressed = self._decode_user_comment(comment)
        decoded = self._decompressor(compressed)
        if decoded is None:
            raise AxleImportError("LZ-String Base64 decompression failed")
        if len(decoded) > self.limits.max_payload_chars:
            raise AxleImportError(
                f"Decompressed AxleTool payload exceeds {self.limits.max_payload_chars} characters"
            )
        try:
            payload = json.loads(decoded)
        except json.JSONDecodeError as exc:
            raise AxleImportError(f"Decompressed AxleTool data is not valid JSON: {exc}") from exc
        return self.normalize(payload, source_path=source_path, payload_sha256=hashlib.sha256(decoded.encode()).hexdigest())

    def normalize(
        self,
        payload: Any,
        *,
        source_path: str | None = None,
        payload_sha256: str | None = None,
    ) -> BattlePlan:
        if not isinstance(payload, dict):
            raise AxleImportError("AxleTool JSON root must be an object")
        version = payload.get("version")
        if not isinstance(version, str):
            raise AxleImportError("AxleTool payload has no valid string version")
        if version not in self.SUPPORTED_VERSIONS:
            raise UnsupportedAxleVersionError(
                f"AxleTool data version {version!r} is not supported; supported: "
                f"{', '.join(sorted(self.SUPPORTED_VERSIONS))}"
            )

        raw_char = payload.get("char")
        raw_skills = payload.get("skills")
        raw_turns = payload.get("turns")
        if not isinstance(raw_char, dict) or not isinstance(raw_skills, list) or not isinstance(raw_turns, list):
            raise AxleImportError("AxleTool payload must contain object char and array skills/turns")
        if len(raw_skills) > self.limits.max_rows or len(raw_turns) > self.limits.max_rows:
            raise AxleImportError(f"AxleTool plan exceeds maximum row count {self.limits.max_rows}")
        if len(raw_skills) != len(raw_turns):
            raise AxleImportError(
                f"skills/turns row count mismatch: {len(raw_skills)} != {len(raw_turns)}"
            )
        declared_rows = payload.get("rows")
        if declared_rows is not None and (
            isinstance(declared_rows, bool)
            or not isinstance(declared_rows, int)
            or declared_rows != len(raw_skills)
        ):
            raise AxleImportError("AxleTool rows field does not match skills/turns row count")

        warnings: list[str] = []
        parties = self._parse_parties(raw_char, warnings)
        party_by_tab = {party.tab_id: party for party in parties}
        if len(party_by_tab) != len(parties):
            raise AxleImportError("char contains duplicate team tab identifiers after normalization")
        turns = self._parse_turns(raw_skills, raw_turns, party_by_tab, version, warnings)
        referenced_tabs = {
            action.team_tab
            for turn in turns
            for action in turn.actions
            if action is not None
        }
        missing_tabs = referenced_tabs - set(party_by_tab)
        if missing_tabs:
            raise AxleImportError(f"Action rows reference missing team tabs: {', '.join(sorted(missing_tabs))}")

        # Upstream getUsedTeams() exports only tabs referenced by an action row.
        used_parties = tuple(party for party in parties if party.tab_id in referenced_tabs)
        if not used_parties and turns:
            raise AxleImportError("No team profile is referenced by any action row")

        name = payload.get("axleName", "")
        language = payload.get("language")
        if not isinstance(name, str):
            raise AxleImportError("axleName must be a string")
        if language is not None and not isinstance(language, str):
            raise AxleImportError("language must be a string when present")
        if language is not None and len(language) > self.limits.max_string_length:
            raise AxleImportError("language exceeds the string length limit")
        return BattlePlan(
            name=name[: self.limits.max_string_length],
            source_version=version,
            language=language,
            parties=used_parties,
            turns=tuple(turns),
            warnings=tuple(warnings),
            source_path=source_path,
            payload_sha256=payload_sha256,
        )

    @staticmethod
    def _read_exif_user_comment(data: bytes) -> bytes | str | None:
        try:
            import piexif
        except ImportError as exc:
            raise AxleImportError("piexif is required to read JPEG EXIF metadata") from exc
        try:
            exif = piexif.load(data)
        except Exception as exc:  # piexif surfaces several parse exceptions
            raise AxleImportError(f"Unable to parse JPEG EXIF metadata: {exc}") from exc
        return exif.get("Exif", {}).get(37510)

    @staticmethod
    def _decompress_lzstring(value: str) -> str | None:
        try:
            import lzstring
        except ImportError as exc:
            raise AxleImportError("py-lzstring is required to decode AxleTool export data") from exc
        return lzstring.decompress_from_base64(value)

    def _decode_user_comment(self, value: bytes | str) -> str:
        if isinstance(value, str):
            result = value
        elif isinstance(value, bytes):
            if value.startswith(b"ASCII\x00\x00\x00"):
                value = value[8:]
                result = value.decode("ascii", errors="strict")
            elif value.startswith(b"UNICODE\x00"):
                result = value[8:].decode("utf-16-be", errors="strict").rstrip("\x00")
            else:
                result = value.decode("utf-8", errors="strict")
        else:
            raise AxleImportError(f"Unsupported EXIF UserComment type: {type(value).__name__}")
        result = result.strip("\x00\ufeff\r\n \t")
        if not result:
            raise AxleImportError("EXIF UserComment is empty")
        return result

    def _parse_parties(self, raw_char: dict[str, Any], warnings: list[str]) -> tuple[PartyProfile, ...]:
        parties: list[PartyProfile] = []
        seen_tabs: set[str] = set()
        if len(raw_char) > 6:
            raise AxleImportError("AxleTool payload contains more than six team tabs")
        for tab_key, raw_slots in raw_char.items():
            tab_id = str(tab_key)
            if tab_id in seen_tabs:
                raise AxleImportError(f"Duplicate team tab identifier after normalization: {tab_id!r}")
            seen_tabs.add(tab_id)
            if not isinstance(raw_slots, dict):
                raise AxleImportError(f"char[{tab_id!r}] must be an object of six slots")
            members: list[PartyMemberSpec | None] = [None] * 6
            seen_slots: set[int] = set()
            if len(raw_slots) > 6:
                raise AxleImportError(f"Team tab {tab_id} contains more than six slots")
            for slot_key, raw_member in raw_slots.items():
                try:
                    slot = int(slot_key)
                except (TypeError, ValueError) as exc:
                    raise AxleImportError(f"Invalid slot key {slot_key!r} in char[{tab_id!r}]") from exc
                if not 1 <= slot <= 6:
                    raise AxleImportError(f"Slot index must be 1..6, got {slot} in tab {tab_id}")
                if slot in seen_slots:
                    raise AxleImportError(f"Duplicate slot {slot} after normalization in team tab {tab_id}")
                seen_slots.add(slot)
                if not isinstance(raw_member, dict):
                    raise AxleImportError(f"char[{tab_id!r}][{slot}] must be an object")
                character = self._optional_string(raw_member.get("character"), "character")
                style = self._optional_string(raw_member.get("style"), "style")
                if character is None:
                    if style is not None:
                        warnings.append(f"Tab {tab_id} slot {slot} has a style but no character identity")
                    continue

                passive = raw_member.get("passiveSkill", [])
                passive_skills = self._skill_values(passive, f"char[{tab_id}][{slot}].passiveSkill")
                support = self._parse_support(raw_member.get("support"), tab_id, slot, warnings)
                progression = ProgressionSnapshot(
                    rank=self._optional_string(raw_member.get("rank"), "rank"),
                    flower=self._optional_bool(raw_member.get("flower"), "flower"),
                    earring=self._optional_string(raw_member.get("earring"), "earring"),
                    spiritual=self._optional_string(raw_member.get("spiritual"), "spiritual"),
                    reincarnation=self._optional_string(raw_member.get("reincarnation"), "reincarnation"),
                )
                members[slot - 1] = PartyMemberSpec(
                    slot=slot,
                    character_id=character,
                    team=self._optional_string(raw_member.get("team"), "team"),
                    style=style,
                    style_id=self._optional_string(raw_member.get("style_id"), "style_id"),
                    passive_skills=passive_skills,
                    support=support,
                    progression=progression,
                )
            parties.append(PartyProfile(tab_id, tuple(members)))
        return tuple(parties)

    def _parse_support(
        self,
        value: Any,
        tab_id: str,
        slot: int,
        warnings: list[str],
    ) -> ResonanceSupportSpec:
        if value is None:
            # AxleTool adds createEmptySupport() while importing old share data.
            return ResonanceSupportSpec()
        if not isinstance(value, dict):
            warnings.append(f"Tab {tab_id} slot {slot} has unrecognized support data")
            return ResonanceSupportSpec()
        return ResonanceSupportSpec(
            team=self._optional_string(value.get("team"), "support.team"),
            character_id=self._optional_string(value.get("character"), "support.character"),
            style=self._optional_string(value.get("style"), "support.style"),
            style_id=self._optional_string(value.get("style_id"), "support.style_id"),
            rank=self._optional_string(value.get("rank"), "support.rank"),
            image=self._optional_string(value.get("img"), "support.img"),
            crucial=self._optional_bool(value.get("crucial", False), "support.crucial") or False,
        )

    def _parse_turns(
        self,
        raw_skills: list[Any],
        raw_turns: list[Any],
        parties: dict[str, PartyProfile],
        version: str,
        warnings: list[str],
    ) -> list[BattleTurn]:
        result: list[BattleTurn] = []
        for row_index, (raw_actions, raw_turn) in enumerate(zip(raw_skills, raw_turns, strict=True), start=1):
            if not isinstance(raw_actions, list) or not isinstance(raw_turn, dict):
                raise AxleImportError(f"skills/turns row {row_index} has an invalid type")
            if len(raw_actions) > 3:
                raise AxleImportError(f"skills row {row_index} contains more than three action slots")
            actions: list[BattleAction | None] = []
            for action_slot, raw_action in enumerate(raw_actions, start=1):
                if not isinstance(raw_action, dict):
                    raise AxleImportError(f"skills[{row_index - 1}][{action_slot - 1}] must be an object")
                actions.append(
                    self._parse_action(
                        raw_action,
                        action_slot,
                        parties,
                        version,
                        row_index,
                        warnings,
                    )
                )
            actions.extend([None] * (3 - len(actions)))

            raw_label = raw_turn.get("turn")
            if raw_label is not None and not isinstance(raw_label, str):
                raise AxleImportError(f"turns[{row_index - 1}].turn must be a string or null")
            label = "" if raw_label is None else raw_label
            kind = self._turn_kind(label)
            overdrive = self._parse_overdrive(raw_turn.get("od"), row_index, warnings)
            if kind is TurnKind.SWITCH and any(action is not None for action in actions):
                warnings.append(f"Switch row {row_index} contains action data; the row is preserved but not executable")
            if kind is TurnKind.UNKNOWN:
                warnings.append(f"Turn row {row_index} has an unknown label {label!r}; manual handling is required")
            result.append(BattleTurn(row_index, label, kind, overdrive, tuple(actions)))
        return result

    def _parse_action(
        self,
        raw: dict[str, Any],
        action_slot: int,
        parties: dict[str, PartyProfile],
        version: str,
        row_index: int,
        warnings: list[str],
    ) -> BattleAction | None:
        selected_tab = raw.get("selectedTab")
        style = self._optional_string(raw.get("style"), "style")
        skill = self._optional_string(raw.get("skill"), "skill")
        target = self._optional_string(raw.get("target"), "target")
        if selected_tab is None and style is None and skill is None and target is None:
            return None
        if selected_tab is None:
            raise AxleImportError(f"Action row {row_index}, slot {action_slot} has data but no selectedTab")
        tab_id = str(selected_tab)
        if tab_id not in parties:
            raise AxleImportError(f"Action row {row_index} references missing team tab {tab_id!r}")

        style_id = self._optional_string(raw.get("style_id"), "style_id")
        active_form_id = self._optional_string(raw.get("activeFormId"), "activeFormId")
        if version == "1.0.0":
            profile = parties[tab_id]
            matching = [m for m in profile.members if m is not None and m.style == style]
            if style_id is None and len(matching) == 1:
                style_id = matching[0].style_id
            if active_form_id is None:
                style_image = raw.get("style_img")
                if isinstance(style_image, str) and style_image:
                    active_form_id = Path(style_image).stem
        profile = parties[tab_id]
        matching_members = [
            member
            for member in profile.members
            if member is not None
            and (style is None or member.style == style)
            and (style_id is None or member.style_id is None or member.style_id == style_id)
        ]
        character_id: str | None = None
        if len(matching_members) == 1:
            character_id = matching_members[0].character_id
        elif style is not None:
            warnings.append(
                f"Action row {row_index}, slot {action_slot} maps style {style!r} to "
                f"{len(matching_members)} members in team tab {tab_id}; actor is unresolved"
            )
        if skill is None:
            warnings.append(f"Action row {row_index}, slot {action_slot} has no active skill value")
        is_1_damage = raw.get("is1Damage", False)
        if not isinstance(is_1_damage, bool):
            raise AxleImportError(f"Action row {row_index}, slot {action_slot} is1Damage must be boolean")
        return BattleAction(
            slot=action_slot,
            team_tab=tab_id,
            character_id=character_id,
            style=style,
            style_id=style_id,
            active_form_id=active_form_id,
            skill_value=skill,
            target_value=target,
            is_1_damage=is_1_damage,
        )

    def _parse_overdrive(self, value: Any, row_index: int, warnings: list[str]) -> OverdriveInstruction | None:
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            raise AxleImportError(f"turns[{row_index - 1}].od must be a string")
        match = self._OD_PATTERN.fullmatch(value)
        if match is None:
            warnings.append(f"Turn row {row_index} has unrecognized OD command {value!r}")
            return OverdriveInstruction(value)
        return OverdriveInstruction(value, int(match.group(1)), int(match.group(2)) if match.group(2) else None)

    def _turn_kind(self, label: str) -> TurnKind:
        if label == "Switch":
            return TurnKind.SWITCH
        if label in ("追加回合", "Extra Turn", "Extra"):
            return TurnKind.EXTRA
        if label == "":
            return TurnKind.EMPTY
        if self._TURN_PATTERN.fullmatch(label):
            return TurnKind.NORMAL
        return TurnKind.UNKNOWN

    def _optional_string(self, value: Any, field_name: str) -> str | None:
        if value is None or value == "":
            return None
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            result = str(value)
            if len(result) > self.limits.max_string_length:
                raise AxleImportError(f"Field {field_name} exceeds the string length limit")
            return result
        raise AxleImportError(f"Field {field_name} must be a string, integer or null")

    def _optional_bool(self, value: Any, field_name: str) -> bool | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        raise AxleImportError(f"Field {field_name} must be boolean or null")

    def _skill_values(self, value: Any, field_name: str) -> tuple[str, ...]:
        if value is None:
            return ()
        if not isinstance(value, list):
            raise AxleImportError(f"Field {field_name} must be a list")
        values: list[str] = []
        for index, item in enumerate(value):
            if isinstance(item, str):
                candidate = item
            elif isinstance(item, dict):
                candidate = item.get("value")
                if candidate is None:
                    raise AxleImportError(f"Field {field_name}[{index}] has no value")
                candidate = str(candidate)
            else:
                raise AxleImportError(f"Field {field_name}[{index}] has an invalid type")
            if len(candidate) > self.limits.max_string_length:
                raise AxleImportError(f"Field {field_name}[{index}] exceeds the string length limit")
            if candidate not in values:
                values.append(candidate)
        return tuple(values)
