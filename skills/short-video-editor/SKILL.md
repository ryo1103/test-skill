---
name: short-video-editor
description: Contract-driven command router for producing or validating short oral videos through the bundled deterministic short_video_engine. Use the engine for execution; never hand-write PASS reports or bypass validators.
---

# Short Video Editor

This skill is not the editing executor. It is a contract and command router.

The execution owner is:

```bash
python skills/short-video-editor/engine/short_video_engine/cli.py
```

Preferred wrapper commands:

```bash
python skills/short-video-editor/scripts/init_short_video_project.py <project>
python skills/short-video-editor/scripts/run_pipeline.py --project-dir <project> --strict
python skills/short-video-editor/scripts/run_pipeline.py --project-dir <project> --strict --enable-asr
python skills/short-video-editor/scripts/validate_stage.py --project-dir <project> --stage S0_intake
python skills/short-video-editor/scripts/validate_final.py --project-dir <project>
python skills/short-video-editor/scripts/validate_production_acceptance.py --project-dir <project>
```

Draft preview is allowed only as draft:

```bash
python skills/short-video-editor/scripts/run_pipeline.py --project-dir <project> --no-strict --draft-ok
```

Rules:

- Codex must call the engine for production work.
- Pipeline order includes `S1_5_subtitle_layout_planning` between S1 and S2; S1 owns exact source/timing cues, S1.5 owns readable subtitle beats, and S2 must plan shots from those beats.
- Pipeline order includes `S4_5_motion_icon_preparation` between S4 and S5; it may materialize only sanitized local SVG semantic icons and must never derive motion assets from B-roll.
- Strict S5 motion must use localized readability backdrops and semantic node-to-node animation. Global decorative outer frames, unmotivated full-width connector lines, text-glyph arrows, and generic English template chrome cannot receive professional PASS.
- S5 must preserve one editorial-tech visual grammar without forcing one diagram onto every sentence: relation/causal claims use progressive node topology, time/change claims use narrative curves, bottleneck claims use anchored evidence, comparisons use split fields, and processes use milestone paths. Template choice follows `semantic_action`; color and layout alone never justify a template.
- Remotion motion timing must scale from `durationInFrames` and subtitle cue anchors so every required semantic stage materializes before the clip ends. A source-only project, an incomplete short-clip animation, or a generic fallback surface cannot receive professional PASS.
- `--enable-asr` may run local faster-whisper to produce `asr_word_timestamps.json`; guessed/proportional timing remains draft-only.
- Codex must not manually create or edit PASS reports.
- Codex must not treat request files, queued rows, dummy metadata, static images, generated placeholders, or metadata-only files as production evidence.
- Completion can be claimed only when `work/plan/production_acceptance_report.json` is engine-generated, has `status=PASS`, has `can_claim_complete=true`, and passes provenance/hash validation.
- `output/FINAL_REPORT.md` is valid only when produced after production acceptance PASS.
- `DRAFT_ONLY_REPORT.md` is not a final deliverable.
- `FINAL_BLOCKED.md` means real artifacts or trusted evidence are still missing.
