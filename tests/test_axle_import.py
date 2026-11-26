from __future__ import annotations

import json
from pathlib import Path

import pytest

from hbr_auto.battle.axle_import import AxleImportError, AxlePlanImporter, UnsupportedAxleVersionError
from hbr_auto.battle.models import TurnKind

FIXTURE = Path(__file__).parent / "fixtures" / "sample_axle_payload.json"


def payload() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_importer_decodes_exif_comment_and_lzstring_payload() -> None:
    raw = json.dumps(payload(), ensure_ascii=False)
    seen: list[str] = []

    def exif_reader(data: bytes) -> bytes:
        assert data.startswith(b"\xff\xd8")
        return b"ASCII\x00\x00\x00compressed-b64"

    def decompressor(value: str) -> str:
        seen.append(value)
        return raw

    importer = AxlePlanImporter(exif_reader=exif_reader, decompressor=decompressor)
    plan = importer.import_bytes(b"\xff\xd8synthetic-jpeg", source_path="fixture.jpg")

    assert seen == ["compressed-b64"]
    assert plan.name == "Offline fixture"
    assert plan.source_path == "fixture.jpg"
    assert plan.parties[0].tab_id == "1"
    assert len(plan.parties[0].members) == 6
    assert plan.parties[0].member(1).passive_skills == ("passive-001",)
    assert plan.turns[0].actions[0].skill_value == "skill-001"
    assert plan.turns[0].actions[0].target_value == "char-001"
    assert plan.turns[0].overdrive.level == 1
    assert plan.turns[0].overdrive.bonus == 1
    assert plan.turns[1].kind is TurnKind.SWITCH
    assert plan.turns[2].kind is TurnKind.EXTRA


def test_importer_rejects_non_jpeg_and_unknown_future_version() -> None:
    importer = AxlePlanImporter(exif_reader=lambda _: "compressed", decompressor=lambda _: "{}")
    with pytest.raises(AxleImportError, match="JPEG"):
        importer.import_bytes(b"not a jpeg")

    data = payload()
    data["version"] = "1.1.0"
    with pytest.raises(UnsupportedAxleVersionError):
        importer.normalize(data)


def test_importer_rejects_reference_to_missing_profile() -> None:
    data = payload()
    data["skills"][0][0]["selectedTab"] = 9
    with pytest.raises(AxleImportError, match="missing team tab"):
        AxlePlanImporter().normalize(data)


def test_version_100_migration_restores_active_form_id() -> None:
    data = payload()
    data["version"] = "1.0.0"
    data["skills"][0][0].pop("style_id")
    data["skills"][0][0].pop("activeFormId")
    data["skills"][0][0]["style_img"] = "/assets/styles/form-old.png"
    plan = AxlePlanImporter().normalize(data)
    action = plan.turns[0].actions[0]
    assert action.style_id == "style-id-001"
    assert action.active_form_id == "form-old"


def test_passive_skills_are_separate_from_action_skills() -> None:
    plan = AxlePlanImporter().normalize(payload())
    member = plan.parties[0].member(1)
    action = plan.turns[0].actions[0]
    assert member.passive_skills == ("passive-001",)
    assert action.skill_value == "skill-001"
    assert "skill-001" not in member.passive_skills


def test_exif_ascii_prefix_is_only_removed_when_present() -> None:
    importer = AxlePlanImporter(decompressor=lambda _: "{}")
    assert importer._decode_user_comment(b"ASCII\x00\x00\x00abc") == "abc"
    assert importer._decode_user_comment(b"plain-text") == "plain-text"
