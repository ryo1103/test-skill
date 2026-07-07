from __future__ import annotations

from pathlib import Path

from .. import ENGINE_VERSION
from ..contracts import write_json
from ..paths import plan_dir
from ..producers.asset_downloaders.base import PROVIDER_LADDER
from ..producers.asset_materializer import STRICT_MIN_ASSETS, distinct_passed_records, materialize_assets
from ..stage_result import FINAL_BLOCKED, PASS, StageResult, current_command, failure


def run(project_dir: Path, no_network: bool = False, **_: object) -> StageResult:
    records, attempts = materialize_assets(project_dir, target_count=STRICT_MIN_ASSETS, no_network=no_network)
    passed, record_failures, duplicates = distinct_passed_records(project_dir, records)
    report_path = plan_dir(project_dir) / "materialized_assets_report.json"
    request_only = (plan_dir(project_dir) / "asset_search_remediation_request.json").exists()
    failures = []
    if len(passed) < STRICT_MIN_ASSETS:
        failures.append(
            failure(
                "insufficient_distinct_materialized_video_broll",
                f"S3 strict PASS requires at least {STRICT_MIN_ASSETS} relevant distinct materialized video_broll assets; found {len(passed)}.",
                "Run real provider downloaders or provide licensed external local video assets.",
            )
        )
    payload = {
        "generated_by": "short_video_engine",
        "engine_version": ENGINE_VERSION,
        "validator": "s3_asset_sourcing",
        "stage": "S3_asset_sourcing",
        "command": " ".join(current_command()),
        "provider_ladder": PROVIDER_LADDER,
        "strict_min_assets": STRICT_MIN_ASSETS,
        "usable_video_broll_count": len(passed),
        "records_checked": len(records),
        "duplicate_records": duplicates,
        "record_failures": record_failures,
        "provider_attempts": attempts,
        "request_only_files_present": request_only,
        "status": FINAL_BLOCKED if failures else PASS,
        "failure_codes": [item["code"] for item in failures],
        "input_artifact_hashes": {},
        "output_artifact_hashes": {},
    }
    write_json(report_path, payload)
    return StageResult("S3_asset_sourcing", FINAL_BLOCKED if failures else PASS, "s3_asset_sourcing", current_command(), failures=failures, outputs=[report_path])
