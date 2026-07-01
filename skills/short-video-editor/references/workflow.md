# Short Video Editing Workflow

Use this reference when executing a complete short-video project, not for small one-off questions.

## Project Structure

Prefer this folder layout inside the user's project:

```text
project/
├── 文案.txt
├── oral.mp4 or ai底稿.mp4
├── bgm/                         # optional
├── assets/
│   ├── raw/
│   │   ├── video/
│   │   ├── image/
│   │   ├── screenshot/
│   │   ├── screen_recording/
│   │   └── logo/
│   ├── processed/               # cropped or normalized assets
│   ├── selected/
│   │   ├── by_shot/
│   │   └── by_theme/
│   ├── metadata/
│   │   └── asset_manifest.json
│   ├── sources.csv
│   └── 素材来源.md
├── work/
│   ├── plan/
│   │   ├── visual_strategy.csv
│   │   ├── news_source_plan.json
│   │   ├── asset_search_plan.json
│   │   ├── style_contract.json
│   │   ├── video_topic.json
│   │   ├── style_intake_report.json
│   │   ├── subtitle_cues.json
│   │   ├── subtitle_timing_audit.json
│   │   ├── shot_plan.json
│   │   ├── hyperframe_polish_guard.json
│   │   ├── visual_ratio_audit.json
│   │   ├── layout_qc_report.json
│   │   ├── topic_banner_audit.json
│   │   ├── subtitle_style_audit.json
│   │   ├── source_uniqueness_audit.json
│   │   ├── source_playback_audit.json
│   │   ├── remediation_log.json
│   │   ├── shotlist_render.csv
│   │   └── edit_manifest.csv
│   └── render_*.py
├── assets_library/
│   └── asset_index.json
└── output/
    ├── qc/
    │   ├── style_preview_contact_sheet.png
    │   ├── probe_render.mp4
    │   ├── probe_frames/
    │   └── final_qc_frames/
    ├── final.mp4
    ├── subtitles.ass
    ├── subtitles.srt
    └── edit_package/
```

## Input Discovery Checklist

Inspect and report:

- Script path and word count.
- Oral video path, duration, resolution, frame rate, and audio presence.
- Existing B-roll, cards, screenshots, style references, and BGM.
- Existing asset library, source metadata, and previous reusable assets.
- Target platform: Douyin, WeChat Channels, Bilibili, YouTube Shorts.
- Requested output: plan only, final MP4, editable layers, or all.

Use ffmpeg for media inspection. If `ffprobe` is unavailable, use `ffmpeg -hide_banner -i`.

## Style Intake And Topic Banner Generation

Run this stage before script-to-visual planning and before any render script is written.

Execution order:

1. Check whether the user prompt explicitly specifies subtitle/title/layout style.
2. Check whether reference screenshots are present.
3. Read the script and existing素材 plan to identify the core topic.
4. When reference images exist, Codex must visually inspect them and record subtitle size, title/banner position, dominant colors, outline/shadow, and style tendency such as news, suspense, finance, technology, casual, or documentary. Save this in `work/plan/style_intake_report.json`; do not pretend the Python helper performed visual judgment.
5. When there is no reference image and no style prompt, use the default `large_short_video_caption` style without asking.
6. Generate `work/plan/video_topic.json` automatically from the script, oral topic, asset plan, and shot plan. The banner must answer what the video is about, what the conflict is, and why it is worth watching.
7. Generate or update `work/plan/style_contract.json` using `scripts/create_style_contract.py`.
8. Ask the user only when the reference styles conflict, the project use case clearly conflicts with default short-video style, multiple main script lines conflict, or the generated banner could mislead.

Default command:

```bash
python skills/short-video-editor/scripts/create_style_contract.py <project_dir> --script <script_path> --style auto --topic auto
```

Required outputs:

- `work/plan/style_contract.json`
- `work/plan/video_topic.json`
- `work/plan/style_intake_report.json`

Top topic banner rules:

- The banner is a topic anchor / visual thesis, not a second subtitle layer.
- It must not copy the current bottom subtitle.
- It should normally stay visible for the full video.
- Talking-head shots may use compact mode so the banner does not cover the face core.
- If the user explicitly disables the banner, set `persistent_topic_banner.enabled = false`; later audit records `user_disabled` and does not fail for missing banner.

## Script Analysis

Segment the script into thought units. For each unit:

- Identify the information type.
- Identify logical relation: comparison, time change, process, cause-effect, condition, metaphor, conclusion.
- Decide if the unit should be full-screen digital human, full-screen B-roll, B-roll with light overlay, light data card, screen recording, or HyperFrame.
- Mark the screen role explicitly as one of: `数字人全屏`, `纯素材`, `轻标注`, `轻量数据卡`, `录屏`, or `HyperFrame重点帧`.
- Decide whether the unit needs an AE/PPT-style overlay on top of B-roll. Candidate units include process flow, comparison, timeline, cause-effect chain, KPI/data card, system structure, decision logic, or a key thesis that benefits from staged visual emphasis.
- Before the final shot plan is accepted, every semantic unit must be evaluated for PPT/AE/HyperFrame usefulness. Fill `ae_overlay_candidate`, `ae_overlay_type`, `visual_pattern`, `hyperframe_score`, `hyperframe_allowed`, `why_simple_broll_is_not_enough`, `broll_base_asset`, `overlay_layer_plan`, `design_plan`, and `animation_plan`.
- If an overlay decision is uncertain, produce a short storyboard option for user confirmation before rendering: time range, spoken phrase, B-roll base, proposed AE/HyperFrame overlay, reason, and concern.
- Mark keyword subtitles: numbers, named entities, turning words, risk words, and final claims.
- Extract shot-specific video search keywords at the same time as script segmentation. The search terms must visibly match that script unit, not only the video's broad topic.
- Missing B-roll must trigger sourcing, not HyperFrame substitution. If a candidate overlay needs B-roll behind it, mark `broll_base_asset` as needed and keep the shot blocked until a selected asset exists or the sourcing shortage is documented.

For a 1-2 minute video, aim for roughly 18-25 visual units. For a 2-3 minute video, 25-35 units is acceptable.

## Audio-Aligned Subtitle-Driven Timeline

For oral/talking-head projects, final rendering must be driven by audio-aligned semantic subtitle cues, not by coarse 6-8s script segments and not by fixed character-count slicing.

Create `work/plan/subtitle_cues.json` before final rendering:

```json
{
  "alignment_method": "asr_word_timestamps | forced_alignment | phrase_timestamps | script_length_proportional_draft_only",
  "rules": {
    "final_render_requires_audio_alignment": true,
    "semantic_complete_cue_required": true,
    "character_count_is_soft_limit": true,
    "target_readability": "short spoken fragment, target 6-14 Chinese characters, hard max 18 except named entities",
    "max_same_subtitle_reuse": 1,
    "sync_tolerance_sec": 0.25
  },
  "cues": [
    {
      "cue_id": "C001",
      "start_sec": 0,
      "end_sec": 1.2,
      "audio_start_sec": 0,
      "audio_end_sec": 1.2,
      "text": "",
      "keywords": [],
      "semantic_unit": "",
      "split_reason": "sentence_end | clause_end | breath_pause | contrast_turn | emphasis | entity_preserved",
      "alignment_source": "asr_word | forced_alignment | manual_timestamp",
      "sync_confidence": "high | medium | low",
      "parent_shot_id": "001",
      "visual_intent": "talking_head | broll | motion_card | data_card",
      "asset_keywords": [],
      "preferred_asset_id": "",
      "subtitle_line_count": 1,
      "punctuation_semantic_required": false,
      "allow_long_named_entity": false
    }
  ]
}
```

Rules:

- Final MP4 subtitle timing must come from the audio: ASR word timestamps, phrase timestamps, or forced alignment between the supplied script and oral audio. If no reliable audio alignment is available, stop before final render and report the missing transcription/alignment dependency. A script-length proportional timeline may be saved only as a rough planning preview and must be marked `script_length_proportional_draft_only`.
- If `alignment_method = script_length_proportional_draft_only`, do not render `output/final.mp4`. First run subtitle alignment remediation: extract oral audio with ffmpeg, look for available local ASR/Whisper/faster-whisper/whisper.cpp/mlx-whisper or existing transcript tooling, align transcript phrase timings back to the supplied script, or consume manual phrase timestamps if present. Only when those paths fail should you render `output/draft_preview.mp4`, mark final delivery blocked, and explain the missing audio-derived cue timing.
- Every final cue must have audio-derived `start_sec` and `end_sec` from ASR, forced alignment, phrase timestamps, or manual phrase timestamps. Low-confidence/proportional/missing cue timing fails final render.
- Segment subtitles by meaning first. Start with sentence and clause boundaries, then refine by ASR pauses/breaths, contrast pivots, emphasis, and natural spoken phrase boundaries. Each cue must be a complete spoken phrase or meaningful clause; do not cut midway through a subject-predicate-object phrase, number, named entity, technical term, comparison, or cause-effect unit.
- Burned subtitles must be short spoken fragments, not full written sentences. For Chinese captions, target `6-14` Chinese characters per cue and hard-stop above `18` characters except named entities.
- Remove visible punctuation such as `，。；：` from burned captions unless it is semantically required.
- Character count is a readability check, not the first segmentation algorithm. First split on semantic/audio boundaries, then revise any cue that exceeds the short-cue target.
- Cue start/end must track the spoken words: start at the first word in that cue and end after the final word, with only small readability padding. Keep a sync tolerance target around `0.15-0.25s`; flag any cue whose text begins or ends noticeably before/after the audio.
- The same subtitle text must not remain visible across multiple B-roll or motion-card cuts. If a sentence spans several visual beats, split it at natural semantic/audio boundaries, not at arbitrary character counts.
- Use cue boundaries as edit boundaries. Cut B-roll on every semantic cue or every two very short adjacent cues.
- Do not create a top/middle title card that repeats the exact bottom subtitle. Top/middle text should be a section title, data value, source label, or visual thesis.
- Save a cue audit in `work/plan/subtitle_timing_audit.json` with alignment method, sync tolerance, sync failures, semantic completeness failures, repeated cue text count, readability length warnings, and any cues that violate the rules. Treat `script_length_proportional_draft_only` as failing for final renders unless the user explicitly approved a draft.

After keyword extraction, run the asset gate before rendering or generating motion substitutes:

1. Check local project assets for every B-roll/screen-recording/image-motion shot.
2. If local assets are missing or insufficient, search online and attempt lawful download or authorized recording using the source order in `asset-sourcing.md`.
3. Record every query, provider, result, blocked reason, selected asset, and local path.
4. If an API provider needs a key that is not in the environment or project `.env`, create/update `.env.example`, ask the user to create `.env`, and pause only that API provider. Continue with other lawful non-API/direct/official/recording sources unless that provider is the only remaining lawful path. If the user says they have no key or asks to continue, mark that provider as `needs_api_key` and keep sourcing elsewhere.
5. If enough relevant assets cannot be acquired, stop at the sourcing stage. Do not generate HyperFrames, generated bitmap assets, generated diagrams, placeholder cards, or text-only motion as replacements for missing B-roll.

For every shot marked `broll_needed: true`, local checks must include:

- `assets/raw/video`
- `assets/selected/by_shot`
- `assets/selected/by_theme`
- `assets/raw/screen_recording`
- `assets/metadata/asset_manifest.json`
- `assets_library/asset_index.json`

If no suitable local asset exists, Codex must generate shot-level search keywords from the script fragment, search related-news and official/event sources first, search official media kits/IR/product/public-data/public-domain sources second, search downloadable video/open-video providers third, try lawful download or authorized screen recording, and record every query/result/blocked reason/selected asset/source URL/license note. Use still images only after the required video search fails and a lawful relevant image exists. Stop if the asset shortage remains.

Do not continue to final render by substituting HyperFrame, generated diagrams, generated bitmap assets, text-only cards, placeholder motion, repeated old B-roll, looped short clips, or still-image stacks.

## Style Positioning And Ratio Plan

Use this default unless the user gives a different style:

```text
B-roll 主视觉 + 短时全屏数字人口播 + 少量专业 HyperFrame 动效
```

The edit is not a pure digital-human oral video, not a pure B-roll splice, and not a pure HyperFrame / motion-graphics video.

Target ratios:

- Full-screen digital human: `15%-28%`.
- B-roll / related footage / screen recording / image motion: `50%-70%`.
- HyperFrame motion graphics: `8%-18%`.
- For a 2-minute video, target roughly `18-34s` digital human, `60-85s` B-roll, and `10-22s` HyperFrames.

Compute final ratios only after assets are selected and exist on disk. Preliminary ratio planning is allowed, but rendering must wait until the selected B-roll/screen-recording/image assets can carry the planned B-roll runtime.

Digital-human rules:

- Digital human is a short full-screen brand/trust anchor, not the default main picture.
- Each appearance is normally `1.5-4s`.
- Except opening/ending, avoid more than `5s` continuously.
- Never exceed `15s` continuous full-screen digital-human narration.
- If the digital human appears visually, it must be full screen. Do not use picture-in-picture, split screen, half-screen, corner windows, transparent overlays on B-roll, or long-term persistent host views.
- During B-roll, the oral audio can continue, but the digital human should not appear on screen.

B-roll rules:

- B-roll is the default main visual carrier for ordinary explanation, industry background, examples, products, tools, companies, technology, and market context.
- Use `broll_fullscreen`, `broll_with_overlay`, `screen_recording`, screenshot with subtle motion, or image with Ken Burns effect.
- B-roll shots are normally `2-5s`; long B-roll sections need multiple distinct sources.
- If footage is missing, search fallback B-roll terms and then use lawful image motion, official screenshots, or public authorized screen recordings only when the search actually finds those assets. If the required assets cannot be found, stop. Do not use HyperFrames, generated bitmap assets, generated diagrams, light graphic cards, or placeholder cards as substitutes for failed sourcing.
- Do not layer still images over video footage or stack multiple still images as fake depth. Use stills only as single full-screen image shots, restrained photo motion, or short image sequences when they are more relevant than available video.
- When the edit is subtitle-driven, each selected B-roll asset should normally cover one cue or two short adjacent cues. Avoid one B-roll clip carrying a whole paragraph unless it has several distinct source shots inside it.

HyperFrame rules:

- HyperFrames are allowed only for key comparison, key process, time change, cause-effect chain, core data, system structure, professional architecture, or a key business/technical mechanism.
- HyperFrame or AE overlay is required by default for any shot expressing 2+ KPI changes, cost/efficiency/risk pressure, process migration, before/after comparison, or `not X but Y` decision logic.
- Downgrade a required-trigger shot only after writing `downgrade_reason`, `why_simple_broll_is_enough`, and a user-visible warning in the plan.
- Do not upgrade ordinary background, generic concepts, emotional transitions, or general opinions into HyperFrames.
- Do not let any continuous HyperFrame block exceed `15s`.
- HyperFrames should follow a refined tech/business news style when the user provides similar references: dark relevant footage or video-derived background, cinematic blur/vignette, deep navy glass panels, mint/cyan and magenta accents, large metrics, neon node/line systems, and complete reveal-build-hold-settle animation. Avoid rough grid diagrams, flat boxes, cluttered labels, and image-collage placeholders.
- Use selected B-roll or a video-derived frame as the background for HyperFrame/motion-card shots whenever possible. Darken/blur/vignette the background and layer a restrained graphic system over it. Empty grid backgrounds are a fallback only when the concept has no relevant footage and the asset gate has already passed.
- Treat HyperFrame/AE effects in oral-video edits as overlay design first: transparent graphics or pre-composited graphic layers above selected B-roll. They may be full-screen standalone cards only for explicitly justified key logic/data shots; otherwise they must enhance the B-roll, not replace it.
- Before generating any HyperFrame HTML, run the polish guard described in `hyperframe-polish-guard.md`. Produce `design_plan`, downgrade weak candidates, lint/render/preview, capture `0%/25%/50%/75%/100%` snapshots, auto-fix visual QA failures, and only mark the shot complete after QA passes.

Save `work/plan/visual_ratio_audit.json` before rendering:

```json
{
  "total_duration_sec": 120,
  "digital_human_fullscreen_sec": 0,
  "digital_human_ratio": "0%",
  "broll_or_screen_recording_sec": 0,
  "broll_ratio": "0%",
  "hyperframe_sec": 0,
  "hyperframe_ratio": "0%",
  "continuous_digital_human_max_sec": 0,
  "continuous_hyperframe_max_sec": 0,
  "rule_check": []
}
```

If the ratio audit fails, revise the shot plan before rendering: add or source more B-roll, shorten digital-human spans, and downgrade unnecessary HyperFrames. If more B-roll cannot be sourced after the required search/download and remediation process, stop instead of rendering.

## Related-News Scan

Before generic stock sourcing, search the script's named event, company, product, policy, report, people, date, and place. This is mandatory for news commentary, current affairs, business, technology, policy, finance, sports, and public-event scripts.

Create `work/plan/news_source_plan.json` with:

```json
{
  "script_event_summary": "",
  "queries": [],
  "sources": [
    {
      "title": "",
      "publisher": "",
      "url": "",
      "published_at": "",
      "source_type": "official | news | social | video_platform | report | reference_only",
      "video_available": true,
      "download_status": "downloaded | direct_download_available | needs_api_key | screen_record_possible | reference_only | cannot_download",
      "license_or_terms_note": "",
      "matched_shots": []
    }
  ]
}
```

Rules:

- Prefer official event videos, press conference pages, company/government/organization media pages, and public-domain or Creative Commons video sources.
- Try lawful direct downloads, official media-kit downloads, provider APIs, or user-authorized screen recordings before using generic stock footage.
- Do not bypass paywalls, login gates, DRM, download restrictions, robots policies, or platform terms. If a news clip cannot be downloaded lawfully, keep it as `reference_only` and source a permissible replacement.
- Record failed attempts and why they failed. Do not silently replace related news footage with unrelated stock footage.

## Visual Strategy CSV

Create `work/plan/visual_strategy.csv` with:

```csv
shot,script_fragment,narrative_role,logic_type,scene_type,renderer,digital_human_presence,digital_human_reason,broll_keywords,overlay_text,data_visual_type,hyperframe_score,hyperframe_allowed,hyperframe_reason,why_simple_broll_is_not_enough,downgrade_reason,why_simple_broll_is_enough,visual_pattern,ae_overlay_candidate,ae_overlay_type,broll_base_asset,overlay_layer_plan,design_plan,animation_plan,hyperframe_polish_guard,hyperframe_completeness_check,editing_rhythm,screen_text,user_review_needed
```

Rules:

- `scene_type`, `renderer`, and `visual_pattern` must be executable, not abstract.
- `broll_keywords` should include Chinese and English terms when web search may be needed.
- `data_visual_type` should be `none`, a light data pattern, or a justified HyperFrame data pattern.
- `screen_text` should be short enough for vertical video.
- Avoid card overload. A strong video can have many visualizations, but only key claims need large cards.
- For opinion-spreading short videos, prefer B-roll plus subtitles for setup and explanation. Reserve AE-style cards or diagrams for one or two key moments per visual mode.
- Every semantic unit must explicitly fill `ae_overlay_candidate`, `ae_overlay_type`, `visual_pattern`, `hyperframe_score`, `hyperframe_allowed`, `broll_base_asset`, `overlay_layer_plan`, `design_plan`, and `animation_plan`.
- HyperFrame is allowed only when `hyperframe_score >= 3` and `why_simple_broll_is_not_enough` is defensible.
- AE/HyperFrame should normally be an overlay above selected B-roll or a video-derived background. Standalone full-screen cards are allowed only for justified key logic/data moments.
- Required-trigger AE/HyperFrame shots may be downgraded only with `downgrade_reason`, `why_simple_broll_is_enough`, and a user-visible warning.
- If a candidate overlay is uncertain or may feel like PPT filler, set `user_review_needed: yes`.
- Default visual priority is `broll_fullscreen` -> `broll_with_overlay` -> `talking_head_fullscreen` -> `data_card_light` -> `hyperframe_logic` / `hyperframe_data`.
- Use full-screen digital human for opening brand, core question, chapter switch, strong judgment, pre-complex-content trust beat, or conclusion. Ordinary narration should use B-roll or B-roll with light overlay.
- Use light overlays for keywords, simple data, labels, names, products, companies, short conclusions, callouts, arrows, local zoom, darkened background, or spotlight effects. Do not duplicate the bottom subtitle text in a title box.
- Keyword highlights should be implemented in the bottom `.ass` subtitle layer when useful. Highlight only important numbers, names, logical pivots, risk words, and conclusions; keep `.srt` plain for editor compatibility.
- For every `renderer: hyperframe` shot, `design_plan` must be created before HTML, `animation_plan` must name the animation stages, `hyperframe_polish_guard` must record lint/render/snapshot/visual-QA status, and `hyperframe_completeness_check` must describe final verification. Leave these empty for non-HyperFrame shots.
- For every process/comparison/timeline/cause-effect/data/system-structure unit, explicitly set `ae_overlay_candidate` to `yes` or `no`. If `yes`, `ae_overlay_type` must be one of `process_flow`, `comparison_matrix`, `timeline`, `cause_effect_chain`, `kpi_card`, `system_diagram`, `decision_tree`, or `callout_overlay`.
- `broll_base_asset` is required for any AE/HyperFrame overlay unless the shot is explicitly approved as a standalone key logic/data card.
- Set `user_review_needed: yes` when the overlay may feel like a PPT page, when it could distract from B-roll, or when the logic is not clearly improved by motion; provide a simple storyboard before rendering.
- When the user requests 20-25素材, count only distinct underlying footage/images. Reusing the same footage with different overlays or movement is still one asset.
- Keep talking head and B-roll interleaved. The base rhythm is fast cuts between host and distinct source footage; motion graphics are emphasis, not filler.
- In render-ready plans, add or create `subtitle_cues.csv/json` so each visual segment can be traced to one or two subtitle cue ids. Large shot ids may group cues for planning, but final timing should be cue-level.

## Shot Plan JSON

Before rendering, create `work/plan/shot_plan.json`. Each shot must include:

```json
{
  "project_type": "knowledge_short_video",
  "style_positioning": "broll_main_visual_with_short_fullscreen_digital_human_and_selective_hyperframe",
  "global_rules": {
    "digital_human_role": "short fullscreen brand anchor",
    "broll_role": "main visual carrier",
    "hyperframe_role": "only key logic, data, comparison, flow, timeline, causality, system structure, and professional emphasis",
    "digital_human_ratio_target": "15%-28%",
    "broll_ratio_target": "50%-70%",
    "hyperframe_total_ratio_target": "8%-18%"
  },
  "shots": [
    {
      "shot_id": "001",
      "script_excerpt": "",
      "duration_sec": 4,
      "narrative_role": "intro | concept | background | example | comparison | data | flow | causality | system_structure | transition | conclusion",
      "logic_type": "none | comparison | timeline | process | causality | data_point | system_structure",
      "scene_type": "talking_head_fullscreen | broll_fullscreen | broll_with_overlay | data_card_light | hyperframe_logic | hyperframe_data | screen_recording | conclusion_card",
      "renderer": "editing_timeline | remotion | hyperframe | screen_recording",
      "digital_human_presence": "fullscreen | voice_only | absent",
      "digital_human_reason": "",
      "broll_needed": true,
      "broll_keywords": [],
      "broll_usage": "fullscreen | background | cutaway",
      "overlay_text": "",
      "data_visual_needed": false,
      "data_visual_type": "none | KPI card | delta card | line chart | timeline | comparison matrix | flowchart | metric dashboard | bar ranking",
      "hyperframe_score": 0,
      "hyperframe_allowed": false,
      "hyperframe_reason": "",
      "why_simple_broll_is_not_enough": "",
      "visual_pattern": "none | side-by-side comparison | before-after | comparison matrix | process flow | timeline | cause-effect chain | KPI card | system diagram | dashboard card",
      "ae_overlay_candidate": false,
      "ae_overlay_type": "none | process_flow | comparison_matrix | timeline | cause_effect_chain | kpi_card | system_diagram | decision_tree | callout_overlay",
      "broll_base_asset": "",
      "overlay_layer_plan": {
        "layer_type": "transparent_overlay | precomposited_over_broll | standalone_key_card",
        "must_sit_above_broll": true,
        "screen_elements": [],
        "timing_sync": "",
        "user_review_needed": false,
        "uncertainty_reason": ""
      },
      "design_plan": {
        "shot_purpose": "",
        "key_message": "",
        "exact_screen_text": [],
        "visual_pattern": "",
        "layout_type": "hero_number | two_column_comparison | three_step_process | timeline | cause_effect_chain | dashboard_card | system_diagram",
        "typography_scale": {},
        "color_tokens": {},
        "animation_sequence": [],
        "duration_sec": 0,
        "why_hyperframe_is_needed": ""
      },
      "animation_plan": {
        "stages": "none | setup -> enter -> build -> emphasis -> hold -> exit_or_settle",
        "timing_notes": "",
        "sync_to_narration": "",
        "readability_hold_sec": 0
      },
      "hyperframe_polish_guard": {
        "triggered": false,
        "lint_status": "",
        "preview_or_render_status": "",
        "snapshot_paths": {},
        "visual_qa_status": "",
        "fixes_applied": [],
        "final_status": ""
      },
      "hyperframe_completeness_check": {
        "standalone_clip_path": "",
        "frame_checks": [],
        "decode_check": "",
        "all_elements_animated": false,
        "no_partial_or_placeholder_animation": false
      },
      "assets": [],
      "edit_notes": "",
      "asset_notes": ""
    }
  ],
  "hyperframe_summary": {
    "total_hyperframe_shots": 0,
    "estimated_total_hyperframe_duration_sec": 0,
    "estimated_hyperframe_ratio": "0%",
    "reasonableness_check": ""
  },
  "digital_human_summary": {
    "estimated_total_digital_human_duration_sec": 0,
    "estimated_digital_human_ratio": "0%",
    "rule_check": ""
  },
  "broll_summary": {
    "estimated_total_broll_duration_sec": 0,
    "estimated_broll_ratio": "0%",
    "rule_check": ""
  }
}
```

Use these scene-type definitions:

- `talking_head_fullscreen`: digital human full screen; only for opening, chapter switch, judgment, conclusion, or trust beat.
- `broll_fullscreen`: default main picture for most explanation.
- `broll_with_overlay`: B-roll plus keywords, light callouts, simple labels, small data, arrows, zoom, or spotlight.
- `data_card_light`: one key number, short conclusion, or one core metric; may be over B-roll or briefly full screen; not HyperFrame.
- `hyperframe_logic`: full HyperFrame for key comparison, process, timeline, causality, or system structure.
- `hyperframe_data`: full HyperFrame for core data, trend, ranking, or complex metrics dashboard.
- `screen_recording`: public or authorized webpage, product, tool, report, dashboard, or search process.
- `conclusion_card`: simple conclusion card or short justified HyperFrame; avoid excessive motion.

Use this renderer split:

- `renderer: editing_timeline` for `talking_head_fullscreen`, `broll_fullscreen`, most `broll_with_overlay`, subtitles, audio, lower thirds, and direct cuts.
- `renderer: remotion` for template-like text animation, light overlays, and `data_card_light` when normal editing tools are not enough.
- `renderer: hyperframe` only for `hyperframe_logic` and `hyperframe_data`.
- `renderer: screen_recording` only for `screen_recording`.

HyperFrame scoring:

```text
key comparison +2
process / steps +2
time change +2
cause-effect chain +2
core data +2
needs professional structure diagram +2
ordinary explanation -2
background introduction -2
transition sentence -3
can be expressed clearly by B-roll -2
digital human is better for trust -1
```

Only use HyperFrames when `hyperframe_score >= 3`. If `hyperframe_score < 3`, choose `talking_head_fullscreen`, `broll_fullscreen`, `broll_with_overlay`, `data_card_light`, or `screen_recording`. If several consecutive shots are HyperFrames, keep only the most important one and downgrade the others.

HyperFrame polish guard trigger:

- `scene_type = hyperframe_logic`
- `scene_type = hyperframe_data`
- `scene_type = data_card_light` and `renderer = hyperframe`
- `visual_pattern` in `comparison`, `side-by-side comparison`, `timeline`, `process flow`, `KPI card`, `dashboard`, `dashboard card`, `system diagram`, or `cause-effect chain`

When triggered, read `hyperframe-polish-guard.md` and create a design plan before writing HTML. If the design plan shows the shot does not need HyperFrame, downgrade automatically to `broll_with_overlay`, `data_card_light`, `screen_recording`, or `remotion simple overlay`.

HyperFrame completeness gate:

- A HyperFrame shot must have a complete animation lifecycle: setup, enter, build, emphasis, readable hold, and exit or settled final state.
- Every promised visual element must be initialized, animated, and visible long enough to understand.
- Counters, lines, nodes, charts, arrows, and labels must reach their final values/positions before the clip ends.
- Generated HTML must use `1080x1920`, safe area, max content width, at most one main idea, at most `3-5` items, no long paragraphs, no random colors, no crowded dashboard, and no over-animation.
- Run `npx hyperframes lint`.
- Run `npx hyperframes preview` or `npx hyperframes render`.
- The clip must render as a standalone file before insertion into the main timeline.
- Inspect frames near `0%`, `25%`, `50%`, `75%`, and `100%` progress for blank frames, missing elements, unfinished transitions, text overlap, subtitle clearance, safe-area violations, color inconsistency, wrong end state, messy PPT look, and random webpage look.
- Auto-fix overflow, tiny text, crowding, overlap, safe-area violations, wrong animation end state, and color inconsistency before accepting the shot.
- Decode-check the standalone clip with `ffmpeg -v error -i <clip> -f null -`.
- If the animation cannot be completed and verified within the task, downgrade to `broll_with_overlay`, `data_card_light`, or `screen_recording`.

Allowed downgrades:

```text
hyperframe_logic -> broll_with_overlay
hyperframe_data -> data_card_light
data_card_light -> subtitle highlight / overlay
animated background -> B-roll
pure animation explanation -> B-roll + oral audio
non-critical flowchart -> B-roll + simple arrow / callout
```

Ordinary B-roll rules:

- Use direct cuts or short hard-cut montages.
- Do not add masks when the sample style is direct footage.
- Do not add left-right shake or rotation-based motion.
- Use 2-4 distinct source shots for long B-roll sections instead of stretching one source.
- Mark any missing unique source as `needs_sourcing: true`.
- Do not use title-box text that repeats the subtitle. Use only necessary labels, callouts, source marks, or small data overlays.

## Asset Sourcing

Read `asset-sourcing.md` before searching or selecting assets.

Use this priority:

1. User-provided screenshots, product images, charts, B-roll, BGM.
2. Related-news and official event videos found from `news_source_plan.json`.
3. Official company/media kits, IR materials, public event pages, government/public datasets, public-domain archives.
4. Downloadable video sources from Pexels, Pixabay, Coverr, Mixkit, Videvo, Wikimedia Commons, Openverse, or other permissible providers.
5. Still images only when no good video is available and the sourcing workflow finds a lawful, relevant image.
6. Authorized screen recordings when a public/authorized playable video, product UI, report, or dashboard cannot be downloaded through a lawful direct/API/media-kit route.

Generated bitmap assets are not part of the acquisition ladder for missing B-roll. Use generated assets only with explicit user approval for covers, optional backgrounds, or non-B-roll design elements; never count them toward the B-roll/source target.

For API-backed providers in this priority list, missing keys require a pause for that provider on first encounter: generate `.env.example`, ask the user to create `.env`, and proceed without that API only after the user confirms they have no key or asks to continue. Do not stop the whole sourcing stage while non-API, direct, official, open-license, or authorized recording paths remain.

Video-first rules:

- Search for video by each shot's `primary_terms`, `video_terms`, and `news_terms` before image search.
- Candidate clips must be screened against the exact script line. Reject cinematic but off-topic clips.
- If many good clips are found, select only what the timeline needs and discard weaker surplus clips.
- Long ordinary B-roll sections can use 2-4 distinct clips; short shots usually need only the best one.
- Still images are fallback assets. Do not use a stack of images or image-over-video layers to imitate motion.
- If a still is more accurate than all available video, use it as a full-screen image shot with restrained motion and mark it as `fallback_image` or `image_preferred_for_accuracy`.
- If no lawful, relevant downloadable/recordable asset is found after provider and fallback searches, mark `needs_sourcing: true`, write the blocked reasons, and stop. Do not continue by creating HyperFrames, generated visuals, or text-only filler.

For every shot, create or update `work/plan/asset_search_plan.json` with:

```json
{
  "shot_id": "V03",
  "info_type": "concept_explanation",
  "visualizable_keywords": {
    "direct_visual": ["server rack"],
    "action_scene": ["engineer typing"],
    "visual_proxy": ["data center"],
    "brand_entities": [],
    "data_visual_needed": false,
    "data_visual_pattern": ""
  },
  "search_terms": {
    "primary_terms": ["AI data center", "server rack"],
    "fallback_terms": ["cloud computing", "computer chip"],
    "video_terms": ["AI data center video", "server rack footage"],
    "news_terms": ["related event official video"],
    "screen_recording_targets": []
  },
  "min_distinct_assets": 1,
  "selected_assets": [],
  "download_candidates": [],
  "video_source_audit": [],
  "needs_sourcing": true
}
```

Record at least:

```csv
asset_key,path,source_url,license_or_note,usage
```

For each candidate, score `relevance_score`, `visual_clarity_score`, `editability_score`, `copyright_risk`, `usage_type`, `aspect_fit`, and `minimum_duration`.

Do not silently use irrelevant filler assets. If a B-roll asset is weak, state that it is a placeholder. If the user asked for video素材, do not render a final video from still images or generated cards unless the source shortage is clearly documented and the user approves the fallback. Without that approval, stop at sourcing.

Before final rendering, count unique underlying video sources separately from images/cards. If the video count is below the target for a video-led edit, stop at the planning/sourcing stage and gather more footage instead of reusing one asset with different animation. Only after this count passes should `visual_ratio_audit.json` be treated as final and rendering proceed.

Final timeline source audits:

- Treat two B-roll uses as duplicates when they share the same `source_url`, `direct_download_url`, provider asset id, original file page, or cached source file.
- Different crops, encodes, trims, speeds, text overlays, or exported local filenames do not make a repeated source unique.
- Before rendering, write `work/plan/source_uniqueness_audit.json` with `used_source_keys`, `duplicates`, and `status`.
- If `duplicates` is not empty, revise the cue-to-asset assignment or source more assets. Do not render a video-led edit that repeats B-roll sources unless the user explicitly approves reuse.

Source playback audit:

- Before final delivery, write `work/plan/source_playback_audit.json` from the edit manifest and render commands.
- Require every B-roll event to record `asset_key`, `source_in`, `source_out`, timeline `start`, timeline `end`, and `playback_policy`.
- A source clip may be shortened by selecting one continuous trim range. It must not be looped, restarted from `0s`, replayed from an earlier timestamp, or used in multiple timeline ranges.
- Reject `ffmpeg -stream_loop`, repeated `asset_key` ranges, overlapping source ranges, `source_in` values that move backward after the source has played, and any output duration longer than `source_out - source_in` for a video source.
- Expensive per-frame similarity checks are optional. The primary requirement is edit-level playback bookkeeping that prevents replay before rendering.
- Approved still-image fallback shots must be listed separately with `approved_still_fallback: true`, source URL, reason, and duration. They must not be counted as video B-roll.
- If playback replay/loop/rewind is found outside approved still fallback, revise the timeline, source more unique footage, or shorten the B-roll section before rendering the final MP4.

Screen recordings are allowed only for public pages or pages the user has permission to access. In this workflow, screen recording means recording a relevant playable public/authorized video or product/report/dashboard interface when direct download/API/media-kit access is unavailable. It does not mean scrolling a webpage to create motion. Do not bypass login, paywalls, DRM, or download restrictions. Provide a recording script before recording.

## Layout Preflight Before Final Render

Run this stage after `subtitle_cues.json`, `shot_plan.json`, and `edit_manifest.csv` exist, and before rendering `final.mp4`.

Inputs:

- `work/plan/style_contract.json`
- `work/plan/video_topic.json`
- `work/plan/subtitle_cues.json`
- `work/plan/shot_plan.json`
- `work/plan/edit_manifest.csv`

Required checks:

1. `subtitle.font_size_px >= subtitle.font_size_min_px`.
2. Subtitle line count is at most two.
3. Subtitle box stays inside the configured safe layout.
4. `subtitle_cues.alignment_method` is audio-derived; `script_length_proportional_draft_only` blocks final render.
5. Every final cue has audio-derived start/end and no low-confidence timing.
6. Burned subtitle cues target `6-14` Chinese characters and hard-stop above `18` except named entities.
7. Visible punctuation is removed unless semantically required.
8. When `persistent_topic_banner.enabled = true`, the banner covers `0` to full duration unless the user disabled it.
9. Banner does not copy the current subtitle.
10. Banner box and subtitle box do not overlap.
11. Banner box stays in the upper safe layout; compact mode is allowed for talking-head face clearance.
12. HyperFrame/design cards do not occupy the subtitle area.
13. Long subtitles are semantically split; shrinking below the minimum font size is forbidden.
14. If the user explicitly disables the banner, record `user_disabled` and do not fail for missing banner.

Process:

1. Run `scripts/audit_layout_plan.py <project_dir>`.
2. Generate `6-12` representative preview frames/contact sheet, including opening talking-head, B-roll + subtitle, B-roll + top banner, data card/HyperFrame, long subtitle, and ending where those exist.
3. Save the preview as `output/qc/style_preview_contact_sheet.png`.
4. Save audit outputs:
   - `work/plan/layout_qc_report.json`
   - `work/plan/topic_banner_audit.json`
   - `work/plan/subtitle_style_audit.json`
5. If any audit fails, revise subtitle cue splitting, audio alignment, banner compact mode, banner size, allowed font size, or safe-area layout, then regenerate preview and audit.
6. Only `layout_qc_report.json.status == "passed"` permits full render.

Probe render gate:

- Before full render, generate `8-15s` of `output/qc/probe_render.mp4`.
- The probe must cover at least one talking-head shot, one B-roll shot, one topic-banner frame, and one long-subtitle frame when those exist in the manifest.
- Extract probe frames to `output/qc/probe_frames/`.
- If probe decoding fails, subtitles are too small, subtitles are clipped/cropped by player controls, text is too long horizontally, captions occupy more than two balanced lines, the banner is missing, text overflows, elements overlap, or representative frames show unsafe layout, stop before full render.

## Gate Remediation Loop

Run this loop whenever a gate fails. The goal is to fix the plan and rerun the failed audit, not to write `FINAL_BLOCKED.md` immediately.

Create or update `work/plan/remediation_log.json`:

```json
{
  "status": "not_run | in_progress | exhausted | resolved",
  "attempts": [
    {
      "gate": "subtitle_alignment | asset_sourcing | visual_ratio | source_uniqueness | source_playback | hyperframe | layout_qc | probe_render",
      "failure_code": "",
      "action": "",
      "result": "resolved | still_failing | needs_user_permission | needs_user_credential | not_available",
      "files_changed": [],
      "next_action": ""
    }
  ],
  "unresolved_blockers": [],
  "final_block_allowed": false
}
```

Remediation paths:

1. **Subtitle alignment failure**
   - Extract audio from the oral video with ffmpeg.
   - Check for usable local ASR or alignment tools already installed: Whisper CLI, faster-whisper, whisper.cpp, mlx-whisper, existing transcript files, SRT/VTT, or a project-specific transcript helper.
   - If ASR transcript exists, align spoken phrases back to the supplied script and rebuild `subtitle_cues.json` with audio-derived start/end, semantic splits, and sync confidence.
   - If ASR is unavailable but manual phrase timestamps/SRT exist, convert them into `subtitle_cues.json`.
   - If no timing path exists, keep only `draft_preview.mp4`, write an alignment dependency report, and set `final_block_allowed = true`.

2. **Asset sourcing failure**
   - Recheck local asset folders and `assets_library/asset_index.json`.
   - Expand shot-level keywords from direct visual terms to fallback visual proxies while staying related to the spoken line.
   - Continue the source order: related news/official event pages, official media kits, public-domain archives, downloadable/open video providers, lawful image sources, then authorized screen-recording plans.
   - Missing Pexels/Pixabay or other API keys block only those API providers. Record `needs_api_key`, keep searching non-API/direct/official/open/recording paths, and ask the user only when that provider or a permissioned recording is the only remaining lawful route.
   - If enough unique assets still cannot be acquired, write the shortage report and set `final_block_allowed = true`.

3. **Visual ratio failure**
   - Source more unique B-roll first.
   - Shorten overlong full-screen digital-human spans and redistribute coverage to selected B-roll.
   - Downgrade weak HyperFrame candidates to B-roll with light overlays only when they do not meet required-trigger logic.
   - If the B-roll target still cannot be met without repeats or generated substitutes, block final with the sourcing shortage.

4. **Source uniqueness/playback failure**
   - Replace repeated source keys with unused assets.
   - If a source was replayed or restarted, choose one continuous non-looped trim or replace the later occurrence.
   - Shorten the visual coverage instead of looping footage.
   - Source more material if the cue-level timeline needs more events than available unique sources.

5. **HyperFrame/AE failure**
   - If a required-trigger shot lacks a B-roll base, source/select the base asset first.
   - If lint/render/snapshot QA fails, fix the HyperFrame and rerun snapshots.
   - Downgrade only after writing `downgrade_reason`, `why_simple_broll_is_enough`, and a user-visible warning.

6. **Layout/subtitle/topic/probe failure**
   - Split overlong captions on semantic/audio boundaries, remove non-semantic punctuation, and keep font size at or above the minimum.
   - Adjust topic banner compact mode, banner height, or safe-area position; do not remove the banner unless the user explicitly disables it.
   - Regenerate contact sheet/probe frames and rerun `audit_layout_plan.py`.
   - If probe decode fails, fix the render script or codec settings and rerun the probe before final.

Only write `output/FINAL_BLOCKED.md` after this loop is exhausted. The blocked report must include `remediation_log.json`, the audits that still fail, and the exact user action needed, such as providing an API key, authorizing a screen recording, uploading B-roll, or supplying phrase timestamps.

## Workflow Integration Gate

Before final render, confirm all old and new gates passed:

1. `style_contract.json` exists.
2. `video_topic.json` exists.
3. `subtitle_cues.json` is audio-aligned and not `script_length_proportional_draft_only`.
4. `visual_strategy.csv` exists and includes AE/PPT/HyperFrame candidate decisions.
5. `shot_plan.json` exists and all B-roll shots have `broll_keywords`.
6. `asset_search_plan.json` exists and all needed B-roll shots have selected assets or documented shortage.
7. `video_source_audit.csv` exists when sourcing was needed.
8. `asset_manifest.json` exists.
9. `visual_ratio_audit.json` passes.
10. `source_uniqueness_audit.json` passes.
11. `source_playback_audit.json` passes.
12. `hyperframe_polish_guard.json` passes for accepted HyperFrame shots.
13. `layout_qc_report.json` passes.
14. `topic_banner_audit.json` passes or records explicit `user_disabled`.
15. `subtitle_style_audit.json` passes.
16. Probe render exists and decodes.

If any item fails, run the Gate Remediation Loop and rerun the failed audit. Do not render final MP4 until the failed item is resolved. Style contracts, topic banners, layout preflight, and probe render are additive quality gates; they cannot replace asset sourcing, visual strategy planning, visual ratio audit, source uniqueness audit, source playback audit, or HyperFrame polish guard.

## Rendering Guidance

Prefer reproducible render scripts over manual ffmpeg command chains for complex edits.

Do not start rendering until the asset gate passes: selected B-roll/screen-recording/image assets exist locally, source metadata is saved, and `visual_ratio_audit.json` confirms the B-roll, digital-human, and animation/HyperFrame mix using those selected assets. If the gate fails, output the sourcing plan and shortage report instead of a final MP4.

Do not start final rendering until the style/layout gate passes: `style_contract.json`, `video_topic.json`, `layout_qc_report.json`, `topic_banner_audit.json`, `subtitle_style_audit.json`, `output/qc/style_preview_contact_sheet.png`, `output/qc/probe_render.mp4`, and `output/qc/probe_frames/` must exist. Topic banner audit may be `user_disabled` only when the user explicitly disabled the banner.

Also do not start final rendering until the Workflow Integration Gate passes. The style/layout gate is a later quality layer, not a replacement for asset sourcing, visual ratio audit, source uniqueness audit, source playback audit, or HyperFrame polish guard.

Render from audio-aligned semantic cue-level timing:

1. Load `subtitle_cues.json`.
2. If `alignment_method` is proportional/draft-only and the requested output is a final MP4, run subtitle alignment remediation before failing.
3. Validate that every cue has an audio-derived start/end, a semantic split reason, and no sync/meaning failures.
4. Assign each semantic cue or cue pair to one visual event.
5. Choose a unique selected B-roll source for every B-roll visual event.
6. Insert full-screen digital-human only at cue ranges marked for trust, pivot, opening, or conclusion.
7. Insert AE/HyperFrame effects as overlay layers above selected B-roll or video-derived backgrounds; use standalone full-screen cards only for explicitly justified key logic/data moments.
8. Generate `.srt` and `.ass` from the same cue list used by the visual timeline.
9. Run `source_uniqueness_audit.json` and `source_playback_audit.json`.
10. Generate `style_preview_contact_sheet.png`, run `audit_layout_plan.py`, render `probe_render.mp4`, and extract probe frames.
11. Fail the final render only after remediation is exhausted if cues are not audio-aligned, if the cue plan remains `script_length_proportional_draft_only`, if any cue has low-confidence/proportional timing, if a cue breaks semantic phrasing unnaturally, if subtitle text repeats across multiple visual cuts, if burned subtitle cues exceed the short-cue target, if subtitles are below the hard minimum `72px`, if any subtitle has more than two lines, if the required topic banner is missing/duplicative/overlapping, if any B-roll source is reused, or if any source playback loop/restart/rewind is found outside approved still fallback.

Common render outputs:

- `visual_track.mp4`: cards/B-roll with no audio.
- `final.mp4`: visual track + oral audio + subtitle burn-in.
- `cover_frame.jpg`: first frame or selected cover frame.
- `subtitles.ass`: keyword-highlight subtitles.
- `subtitles.srt`: generic editor-compatible subtitles.
- `work/plan/hyperframe_polish_guard.json`: per-HyperFrame lint/render/snapshot/visual-QA records.

Use `1080x1920`, `30fps`, H.264, AAC for Douyin/WeChat compatibility unless the user specifies otherwise.

Ordinary B-roll rendering rules:

- Let downloaded footage carry motion. Use direct cuts, short fades, speed-normalized trims, or simple crop/scale only.
- Do not place subtitle-like title cards over ordinary B-roll. Screen text outside the subtitle layer should be limited to necessary labels, source marks, chart values, or brief non-duplicative visual annotations.
- Do not composite unrelated still images onto video or build multi-layer still-image collages. If using stills, cut them as full-screen photo shots or short photo sequences.
- Final preview may burn subtitles; base/editable exports should keep subtitles separate.
- If a motion-enhanced card is needed, insert it only where the shot plan marks `renderer: hyperframe`, `hyperframe_allowed: true`, and `hyperframe_score >= 3`.
- Do not insert a HyperFrame clip unless `hyperframe_polish_guard.final_status = complete` and `hyperframe_completeness_check` confirms a standalone render, representative frame checks, decode check, and no partial/placeholder animation.

## Codex Default Execution Order

When the user says `帮我剪这个视频`, `用这个 skill 做成短视频`, or `生成成片` and does not specify subtitle style, execute this order:

1. Read `SKILL.md`, `workflow.md`, `visual-language.md`, `asset-sourcing.md`, `hyperframes.md`, `hyperframe-polish-guard.md`, and `style-contract.md`.
2. Inspect project media, script, oral video, local assets, existing B-roll, BGM, screenshots, and reference images.
3. Run style intake only to create/update `style_contract.json`, `video_topic.json`, and `style_intake_report.json`.
4. Read the full script.
5. Create semantic script analysis:
   - information type
   - logic type
   - narrative role
   - B-roll need
   - B-roll keywords
   - AE/PPT/HyperFrame candidate
   - data visual candidate
   - talking-head pivot reason
6. Create `subtitle_cues.json` from audio-aligned semantic cues.
7. Create initial `visual_strategy.csv` and `shot_plan.json`.
8. Run related-news/event source scan before generic stock search.
9. Check local assets for every B-roll/screen-recording/image-motion shot.
10. If local B-roll is missing or insufficient, search online using `asset-sourcing.md`.
11. Write/update:
    - `work/plan/news_source_plan.json`
    - `work/plan/asset_search_plan.json`
    - `work/plan/video_source_audit.csv`
    - `assets/sources.csv`
    - `assets/metadata/asset_manifest.json`
12. If enough lawful relevant B-roll/video/image/screen-recording assets cannot be found, stop at the sourcing stage and report the shortage. Do not render final MP4 from HyperFrame, generated diagrams, text cards, or placeholder motion.
13. After selected assets exist on disk, finalize `shot_plan.json` and `edit_manifest.csv`.
14. Compute `work/plan/visual_ratio_audit.json` using selected assets:
    - full-screen digital human target: `15%-28%`
    - B-roll / related footage / screen recording / image motion target: `50%-70%`
    - HyperFrame / AE motion graphics target: `8%-18%`
15. If visual ratio audit fails, revise the shot plan, source more B-roll, shorten digital-human spans, or downgrade unnecessary HyperFrames.
16. For accepted HyperFrame/AE shots, create `design_plan`, `animation_plan`, `hyperframe_polish_guard`, render standalone clips, capture `0/25/50/75/100` snapshots, and verify decode.
17. Run source uniqueness audit.
18. Run source playback audit.
19. Run layout preflight:
    - `audit_layout_plan.py`
    - style preview contact sheet
    - topic banner audit
    - subtitle style audit
20. Render `probe_render.mp4`.
21. Extract probe frames and inspect layout.
22. If any gate fails, run the Gate Remediation Loop, update `remediation_log.json`, and rerun the failed audit.
23. Only if all gates pass after remediation, render `final.mp4`.
24. If remediation is exhausted, write `output/FINAL_BLOCKED.md` with attempted fixes and the exact missing user credential/permission/asset/timestamp.
25. Extract final QC frames.
26. Export editable package.

## Editable Package

When the user may manually revise:

```text
edit_package/
├── 00_edit_manifest.csv
├── 01_base_with_oral_no_cards_no_subtitles.mp4
├── 02_clean_broll_no_cards_no_oral.mp4
├── 03_overlay_cards_png/
├── 04_subtitles.srt
├── 04_subtitles.ass
├── 05_original_oral_video.mp4
├── 06_visual_strategy.csv
├── 07_shotlist_render.csv
├── 08_script.txt
├── 09_downloaded_video_sources/
├── 10_hyperframe_clips/
└── 11_image_sources_used/
```

`01_base...` is the main manual editing base. `02_clean...` is useful when the user wants to redesign oral-video exposure or overlay new B-roll from scratch.

## QC Checklist

Run:

- Decode check: `ffmpeg -v error -i final.mp4 -f null -`
- Media info: `ffmpeg -hide_banner -i final.mp4`
- Extract representative frames at key times.
- Confirm `output/qc/style_preview_contact_sheet.png`, `output/qc/probe_render.mp4`, `output/qc/probe_frames/`, and `output/qc/final_qc_frames/` exist.
- Confirm `work/plan/layout_qc_report.json.status = passed`.
- Confirm `work/plan/topic_banner_audit.json.status = passed` or `user_disabled`.
- Confirm `work/plan/subtitle_style_audit.json.status = passed`.

Inspect:

- Asset gate passed before render; no missing B-roll was replaced by HyperFrame, generated bitmap assets, generated diagrams, placeholder cards, or text-only filler.
- Default Chinese short-video subtitles are large and readable; ordinary subtitles default to `78-82px` and are never smaller than `72px`, emphasis subtitles are in the `86-96px` range when used, and no cue is three lines.
- Top topic banner is present through the video unless the user explicitly disabled it; it summarizes the video thesis and does not逐句复制 bottom subtitles.
- Talking-head shots use compact banner mode when the normal banner would cover the face core.
- Layout preflight and probe render passed before final render.
- No blank or unrelated frames.
- No B-roll clip is looped, restarted, replayed from an earlier timestamp, or used in multiple ranges according to `source_playback_audit.json`. Optional sampled-frame QC may be used only as an extra check.
- No subtitle/card overlap.
- No duplicate subtitle text in upper/middle title boxes.
- Subtitle cues are audio-aligned: the visible cue matches the phrase currently being spoken, does not appear early, and does not linger after the phrase ends.
- Subtitle cues are semantic: no cue is a fixed-character fragment that cuts a phrase, number, named entity, technical term, comparison, or cause-effect unit in half.
- Bottom source text is not clipped.
- Chinese text fits within cards.
- Digital human appears only full-screen in intended intervals; no PIP, split screen, half-screen, transparent overlay, corner window, or persistent host view.
- Digital human and HyperFrame continuous durations stay within the limits.
- B-roll is the main visual carrier and meets the target ratio.
- HyperFrames only appear at scored key logic/data/comparison/process/timeline/causality/system-structure moments.
- AE/HyperFrame motion sits above B-roll or a video-derived background unless the plan explicitly marks it as a standalone key logic/data card.
- Uncertain AE/HyperFrame choices were shown as a simple storyboard and confirmed before rendering.
- HyperFrame animation is complete: start/build/peak/settle/end frames were inspected, all elements animate to final state, no placeholder layers remain, and standalone clips decode before timeline insertion.
- HyperFrame polish guard passed: design plan exists, `npx hyperframes lint` ran, preview/render ran, `0%/25%/50%/75%/100%` snapshots were inspected, any visual QA failures were fixed, and the shot is marked complete only after passing.
- Ordinary narration has not been misclassified as HyperFrame.
- Final video has audio.
- Extra B-roll/source count meets the target.
- Ordinary B-roll shots are direct cuts or short montages, not masked/rotated filler.
- `assets/metadata/asset_manifest.json` and `assets_library/asset_index.json` are updated when assets are selected or reused.
- `work/plan/visual_ratio_audit.json` passes or records exact revisions made to pass.

## Acceptance Cases

Case A: project has no B-roll.

Expected:

- Codex does not render `final.mp4` directly.
- Codex first generates `asset_search_plan.json`.
- Codex performs online asset sourcing.
- Codex writes `video_source_audit.csv`.
- If enough lawful relevant assets cannot be found, Codex stops and outputs a shortage report.

Case B: script includes process, comparison, timeline, or cause-effect logic.

Expected:

- Related rows in `visual_strategy.csv` set `ae_overlay_candidate = yes`.
- `ae_overlay_type` is filled correctly.
- HyperFrame candidates have `hyperframe_score` and a reason.
- Segments that do not justify HyperFrame are downgraded to B-roll + light overlay.

Case C: project has B-roll, but not enough to support the `50%-70%` B-roll target.

Expected:

- `visual_ratio_audit.json` fails.
- Codex continues sourcing or shortens non-essential durations, records attempts in `remediation_log.json`, and reruns the audit.
- Codex does not use repeated assets, looped assets, generated cards, or placeholder motion to pad runtime.

Case D: added style features are enabled.

Expected:

- Large subtitles, persistent topic banner, layout preflight, and probe render run normally.
- These steps happen after the asset gate, visual ratio gate, source uniqueness audit, and source playback audit; they do not replace those gates.

Case E: final render.

Expected:

- Final render starts only after all pass: asset gate, visual strategy / AE candidate gate, visual ratio audit, source uniqueness audit, source playback audit, HyperFrame polish guard, layout QC, and probe render.

Case F: a gate fails during production.

Expected:

- Codex runs the Gate Remediation Loop before blocking.
- Missing ASR/timing triggers audio extraction and local ASR/alignment checks before draft-only blocking.
- Missing B-roll triggers more sourcing and non-API/official/authorized recording paths before shortage blocking.
- `output/FINAL_BLOCKED.md`, when present, cites `remediation_log.json` and the remaining user action needed.

## User-Facing Closeout

Keep the final answer short. Include:

- Final MP4 path.
- Editable package path.
- Important files for manual editing.
- Verification summary.
- Any limitation, such as missing BGM or placeholder B-roll.
