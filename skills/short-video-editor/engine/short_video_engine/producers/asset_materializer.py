from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from ..contracts import read_json, write_json
from ..paths import assets_dir, plan_dir
from ..stage_result import failure
from .asset_downloaders.asset_library_adapter import AssetLibraryProvider
from .asset_downloaders.base import ALLOWED_EXTERNAL_PROVENANCE, PROVIDER_LADDER, ProviderAttempt, probe_and_decode, sha256_file
from .asset_downloaders.coverr_adapter import CoverrProvider
from .asset_downloaders.mixkit_adapter import MixkitProvider
from .asset_downloaders.openverse_adapter import OpenverseProvider
from .asset_downloaders.pexels_adapter import PexelsProvider
from .asset_downloaders.pixabay_adapter import PixabayProvider
from .asset_downloaders.videvo_adapter import VidevoProvider
from .asset_downloaders.wikimedia_commons_adapter import WikimediaCommonsProvider


STRICT_MIN_ASSETS = 20
MAX_DOWNLOAD_CANDIDATES_PER_PROVIDER = 3
MAX_STAGE_SECONDS = 180
MAX_PROVIDER_SECONDS = 35
MAX_SHOTS_PER_RUN = 16
PROVIDER_CLASSES = {
    "asset_library": AssetLibraryProvider,
    "mixkit": MixkitProvider,
    "pexels": PexelsProvider,
    "pixabay": PixabayProvider,
    "coverr": CoverrProvider,
    "videvo": VidevoProvider,
    "wikimedia_commons": WikimediaCommonsProvider,
    "openverse": OpenverseProvider,
}
DISALLOWED_MEDIA_MARKERS = {"screen_recording", "browser_recording", "html_recording", "generated", "hyperframe", "drawtext", "ken_burns", "static_image", "image"}
GENERIC_BROLL = {"business meeting", "city skyline", "abstract tech", "stock trading"}


def manifest_path(project_dir: Path) -> Path:
    return assets_dir(project_dir) / "metadata" / "asset_manifest.json"


def load_manifest(project_dir: Path) -> list[dict[str, Any]]:
    payload = read_json(manifest_path(project_dir), [])
    if isinstance(payload, dict):
        items = payload.get("assets") or payload.get("records") or []
    else:
        items = payload
    return [item for item in items if isinstance(item, dict)]


def write_manifest(project_dir: Path, records: list[dict[str, Any]]) -> None:
    write_json(manifest_path(project_dir), {"generated_by": "short_video_engine", "assets": records})


def load_shots(project_dir: Path) -> list[dict[str, Any]]:
    payload = read_json(plan_dir(project_dir) / "shot_plan.json", {})
    shots = payload.get("shots") if isinstance(payload, dict) else []
    if not isinstance(shots, list):
        return []
    return [shot for shot in shots if isinstance(shot, dict)]


def materialize_assets(project_dir: Path, target_count: int = STRICT_MIN_ASSETS, no_network: bool = False) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    deadline = time.monotonic() + MAX_STAGE_SECONDS
    records = load_manifest(project_dir)
    attempts: list[dict[str, Any]] = []
    shots = load_shots(project_dir)
    target_dir = assets_dir(project_dir) / "raw" / "video"
    passed_count = len(distinct_passed_records(project_dir, records)[0])
    for shot in shots[:MAX_SHOTS_PER_RUN]:
        if passed_count >= target_count:
            break
        if time.monotonic() > deadline:
            attempts.append(ProviderAttempt("s3_asset_sourcing", "skipped_budget_exhausted", "stage", f"Reached {MAX_STAGE_SECONDS}s stage budget").to_dict())
            break
        wanted = as_list(shot.get("wanted_visuals"))
        avoid = as_list(shot.get("avoid_visuals"))
        entities = as_list(shot.get("required_entities"))
        query = " ".join([str(shot.get("script_fragment") or ""), *wanted, *entities]).strip()
        for provider_name in PROVIDER_LADDER:
            if time.monotonic() > deadline:
                attempts.append(ProviderAttempt(provider_name, "skipped_budget_exhausted", query, f"Reached {MAX_STAGE_SECONDS}s stage budget").to_dict())
                break
            provider = PROVIDER_CLASSES[provider_name](project_dir)
            if provider.requires_api_key and not provider.configured():
                attempts.append(ProviderAttempt(provider_name, "skipped_missing_api_key", query, f"Missing {provider.api_key_env}").to_dict())
                continue
            if no_network and provider_name != "asset_library":
                attempts.append(ProviderAttempt(provider_name, "skipped_no_network", query).to_dict())
                continue
            provider_deadline = time.monotonic() + MAX_PROVIDER_SECONDS
            try:
                remaining = max(1, target_count - passed_count)
                search_limit = max(remaining, target_count * 3)
                candidates = provider.search(query, wanted, avoid, entities, limit=search_limit)
            except Exception as exc:
                attempts.append(ProviderAttempt(provider_name, "search_failed", query, str(exc)).to_dict())
                continue
            attempts.append(ProviderAttempt(provider_name, "searched", query, f"candidates={len(candidates)}").to_dict())
            download_attempts = 0
            for candidate in candidates:
                if time.monotonic() > deadline or time.monotonic() > provider_deadline:
                    attempts.append(ProviderAttempt(provider_name, "skipped_budget_exhausted", query, f"Reached {MAX_PROVIDER_SECONDS}s provider budget").to_dict())
                    break
                candidate = {**candidate, "shot_id": shot.get("shot_id"), "wanted_visuals": wanted, "avoid_visuals": avoid, "required_entities": entities}
                if candidate_already_recorded(candidate, records):
                    attempts.append(ProviderAttempt(provider_name, "skipped_duplicate_candidate", query, str(candidate.get("provider_asset_id") or candidate.get("source_key") or candidate.get("source_url"))).to_dict())
                    continue
                if download_attempts >= MAX_DOWNLOAD_CANDIDATES_PER_PROVIDER:
                    break
                candidate["relevance_status"] = "passed" if relevance_passed(candidate, wanted, avoid, entities) else "failed"
                if candidate["relevance_status"] != "passed":
                    continue
                download_attempts += 1
                try:
                    local_path = provider.download(candidate, target_dir)
                except Exception as exc:
                    attempts.append(ProviderAttempt(provider_name, "download_failed", query, str(exc)).to_dict())
                    continue
                if not local_path:
                    attempts.append(ProviderAttempt(provider_name, "download_failed", query, "no local video produced").to_dict())
                    continue
                try:
                    record = provider.normalize_metadata(candidate, local_path)
                except ValueError as exc:
                    attempts.append(ProviderAttempt(provider_name, "decode_failed", query, str(exc)).to_dict())
                    continue
                records.append(record)
                attempts.append(ProviderAttempt(provider_name, "materialized", query, record["asset_key"]).to_dict())
                write_manifest(project_dir, records)
                write_json(plan_dir(project_dir) / "asset_provider_attempts.json", {"generated_by": "short_video_engine", "attempts": attempts})
                passed_count = len(distinct_passed_records(project_dir, records)[0])
                if passed_count >= target_count:
                    break
            if passed_count >= target_count:
                break
    write_manifest(project_dir, records)
    write_json(plan_dir(project_dir) / "asset_provider_attempts.json", {"generated_by": "short_video_engine", "attempts": attempts})
    return records, attempts


def candidate_already_recorded(candidate: dict[str, Any], records: list[dict[str, Any]]) -> bool:
    keys = {
        str(candidate.get("provider_asset_id") or "").strip(),
        str(candidate.get("source_key") or "").strip(),
        str(candidate.get("source_url") or "").strip(),
        str(candidate.get("direct_download_url") or "").strip(),
    }
    keys.discard("")
    if not keys:
        return False
    for record in records:
        existing = {
            str(record.get("provider_asset_id") or "").strip(),
            str(record.get("source_key") or "").strip(),
            str(record.get("source_url") or "").strip(),
            str(record.get("direct_download_url") or "").strip(),
        }
        existing.discard("")
        if keys & existing:
            return True
    return False


def as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value:
        return [str(value)]
    return []


def resolve_local(project_dir: Path, record: dict[str, Any]) -> Path:
    path = Path(str(record.get("local_path") or record.get("path") or "")).expanduser()
    return path if path.is_absolute() else project_dir / path


def relevance_passed(record: dict[str, Any], wanted_visuals: list[str], avoid_visuals: list[str], required_entities: list[str]) -> bool:
    text = " ".join(str(record.get(key, "") or "") for key in ("title", "description", "tags", "source_url", "local_path", "path", "source_key")).lower()
    semantic_text = " ".join(str(record.get(key, "") or "") for key in ("semantic_query", "match_reason")).lower()
    if any(marker in text for marker in DISALLOWED_MEDIA_MARKERS):
        return False
    for avoid in avoid_visuals:
        avoid_text = str(avoid).lower()
        if avoid_text and avoid_text in text:
            return False
    for entity in required_entities:
        entity_text = str(entity).lower()
        if entity_text and entity_text not in text and not (record.get("provider") == "asset_library" and entity_text in semantic_text):
            return False
    if any(generic in text for generic in GENERIC_BROLL):
        wanted = " ".join(wanted_visuals).lower()
        return any(generic in wanted for generic in GENERIC_BROLL)
    return True


def validate_record(project_dir: Path, record: dict[str, Any]) -> tuple[bool, list[dict[str, str]], dict[str, Any]]:
    failures = []
    normalized = dict(record)
    text = " ".join(str(record.get(key, "") or "") for key in ("media_class", "usage", "usage_type", "provenance_type", "source_url", "local_path", "asset_key")).lower()
    if any(marker in text for marker in DISALLOWED_MEDIA_MARKERS):
        failures.append(failure("disallowed_media_class", "Generated, screen-recorded, HTML, static image, or request-only media cannot count."))
    if record.get("media_class") != "video_broll":
        failures.append(failure("not_video_broll", "Asset media_class must be video_broll."))
    if record.get("provider") not in PROVIDER_LADDER:
        failures.append(failure("unknown_provider", "Asset provider is not in the fixed provider ladder."))
    if record.get("external_source") is not True:
        failures.append(failure("missing_external_source", "Asset must have external_source=true."))
    if record.get("provenance_type") not in ALLOWED_EXTERNAL_PROVENANCE:
        failures.append(failure("invalid_provenance_type", "Asset provenance_type is not allowed external provenance."))
    if not (record.get("source_url") or record.get("direct_download_url")):
        failures.append(failure("missing_source_url", "Asset must include source_url or direct_download_url."))
    if not record.get("license_or_note"):
        failures.append(failure("missing_license", "Asset must include license_or_note."))
    if record.get("materialized_status") != "passed":
        failures.append(failure("materialization_not_passed", "Asset materialized_status must be passed."))
    if record.get("ffprobe_decode_status") != "passed":
        failures.append(failure("decode_not_passed", "Asset ffprobe_decode_status must be passed."))
    if record.get("relevance_status") != "passed":
        failures.append(failure("relevance_not_passed", "Asset relevance_status must be passed."))
    local = resolve_local(project_dir, record)
    metadata, error = probe_and_decode(local)
    if metadata is None:
        failures.append(failure("local_video_decode_failed", f"Local video failed probe/decode: {error}"))
    else:
        normalized["sha256"] = sha256_file(local)
        normalized["duration_sec"] = metadata["container_duration"] or metadata["video_stream_duration"] or metadata["audio_stream_duration"]
        normalized["width"] = metadata["resolution"]["width"]
        normalized["height"] = metadata["resolution"]["height"]
        normalized["fps"] = metadata["fps"]
        normalized["local_path"] = str(local)
    if not normalized.get("sha256"):
        failures.append(failure("missing_sha256", "Asset must include sha256."))
    if float(normalized.get("duration_sec") or 0) <= 0:
        failures.append(failure("missing_duration", "Asset must include positive duration."))
    return not failures, failures, normalized


def distinct_passed_records(project_dir: Path, records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    passed: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for record in records:
        ok, record_failures, normalized = validate_record(project_dir, record)
        if not ok:
            failures.append({"asset_key": record.get("asset_key"), "failures": record_failures})
            continue
        duplicate_key = first_duplicate_key(normalized, seen)
        if duplicate_key:
            duplicates.append({"asset_key": normalized.get("asset_key"), "duplicate_key": duplicate_key})
            continue
        register_keys(normalized, seen)
        passed.append(normalized)
    return passed, failures, duplicates


def first_duplicate_key(record: dict[str, Any], seen: set[tuple[str, str]]) -> str | None:
    for key in ("source_url", "direct_download_url", "provider_asset_id", "source_key", "sha256"):
        value = str(record.get(key) or "").strip()
        if value and (key, value) in seen:
            return f"{key}:{value}"
    return None


def register_keys(record: dict[str, Any], seen: set[tuple[str, str]]) -> None:
    for key in ("source_url", "direct_download_url", "provider_asset_id", "source_key", "sha256"):
        value = str(record.get(key) or "").strip()
        if value:
            seen.add((key, value))
