from pathlib import Path

from ..contracts import read_json
from ..paths import plan_dir
from ..producers.motion_icon_resolver import resolve_motion_icons
from ..stage_result import FINAL_BLOCKED, PASS, StageResult, current_command, failure


def run(project_dir: Path, **options: object) -> StageResult:
    assertions_path = plan_dir(project_dir) / "motion_assertions.json"
    requests_path = plan_dir(project_dir) / "motion_icon_requests.json"
    assertions = read_json(assertions_path, {})
    if not assertions_path.exists() or not requests_path.exists():
        return StageResult("S4_5_motion_icon_preparation", FINAL_BLOCKED, "s4_5_motion_icon_preparation", current_command(), failures=[failure("motion_icon_inputs_missing", "S4.5 requires S2 motion_assertions.json and motion_icon_requests.json.")])
    manifest_path, _manifest, failures = resolve_motion_icons(project_dir, assertions, no_network=bool(options.get("no_network")))
    report_path = plan_dir(project_dir) / "motion_icon_preparation_report.json"
    return StageResult("S4_5_motion_icon_preparation", PASS if not failures else FINAL_BLOCKED, "s4_5_motion_icon_preparation", current_command(), failures=failures, inputs=[assertions_path, requests_path], outputs=[manifest_path, report_path])
