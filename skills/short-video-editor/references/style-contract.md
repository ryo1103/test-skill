# Style Contract

Use this reference whenever a short-video project needs subtitles, topic banners, ordinary overlays, Remotion overlays, HyperFrame overlays, preview frames, probe renders, or final renders.

`work/plan/style_contract.json` is the single visual input for render scripts. Render scripts, ASS subtitle generation, Remotion overlays, HyperFrame overlays, and ordinary edit-timeline overlays must read this file for subtitle size, title/banner placement, safe areas, colors, and QC policy. Do not hardcode subtitle font size, topic-title position, colors, or safe-area values inside one-off render scripts.

## Required Files

Create or update these files before shot planning and before final rendering:

```text
work/plan/style_contract.json
work/plan/video_topic.json
work/plan/style_intake_report.json
```

Final rendering also requires:

```text
work/plan/layout_qc_report.json
work/plan/topic_banner_audit.json
work/plan/subtitle_style_audit.json
work/plan/remediation_log.json              # required when any final gate failed before passing
output/qc/style_preview_contact_sheet.png
output/qc/probe_render.mp4
output/qc/probe_frames/
output/qc/final_qc_frames/
```

## Default `style_contract.json`

Default for 1080x1920, 30fps Chinese vertical short videos:

```json
{
  "canvas": {
    "width": 1080,
    "height": 1920,
    "fps": 30,
    "safe_area": {
      "top": 120,
      "bottom": 210,
      "left": 72,
      "right": 72
    }
  },
  "subtitle": {
    "mode": "large_short_video_caption",
    "font_family_preferred": ["Noto Sans CJK SC", "Source Han Sans SC", "PingFang SC", "Microsoft YaHei", "system-ui"],
    "font_size_px": 80,
    "font_size_min_px": 72,
    "font_size_emphasis_px": 92,
    "font_weight": 800,
    "line_count_max": 2,
    "chars_per_cue_target_min": 6,
    "chars_per_cue_target_max": 14,
    "chars_per_cue_hard_max": 18,
    "chars_per_line_soft_max": 14,
    "visible_punctuation_policy": "remove_unless_semantic_required",
    "bottom_margin_px": 240,
    "horizontal_margin_px": 72,
    "outline_px": 6,
    "shadow_px": 3,
    "primary_color": "#FFFFFF",
    "keyword_color": "#00E5FF",
    "secondary_keyword_color": "#7CFFB2",
    "forbid_three_line_subtitles": true,
    "forbid_shrinking_below_min": true,
    "require_audio_derived_timing_for_final": true,
    "fail_low_confidence_timing_for_final": true,
    "draft_alignment_output_policy": "draft_preview_only"
  },
  "persistent_topic_banner": {
    "enabled": true,
    "required_for_final_render": true,
    "visible_start_sec": 0,
    "visible_end_policy": "full_duration",
    "content_source": "work/plan/video_topic.json",
    "max_lines": 2,
    "main_font_size_px": 82,
    "sub_font_size_px": 74,
    "font_weight": 850,
    "position": {
      "x": 170,
      "y": 128,
      "width": 740,
      "height": 230
    },
    "compact_position_for_talking_head": {
      "x": 170,
      "y": 88,
      "width": 740,
      "height": 220
    },
    "background": "rgba(0,0,0,0.76)",
    "border_radius_px": 24,
    "padding_px": 28,
    "text_primary": "#8CFFD9",
    "text_secondary": "#FFFFFF",
    "outline_or_glow": true,
    "must_not_duplicate_current_subtitle": true
  },
  "style_prompt_policy": {
    "if_user_provides_style_reference": "extract_style_from_reference_and_apply",
    "if_user_specifies_style_in_prompt": "follow_user_style",
    "if_user_says_subtitles_too_small": "use_large_short_video_caption",
    "if_no_style_prompt": "use_default_large_short_video_caption",
    "ask_user_when": [
      "用户明确要求先选择风格",
      "参考图风格互相冲突",
      "项目用途和默认短视频风格明显不一致",
      "用户上传了多个强风格参考但没有说明想模仿哪一个",
      "文案主题高度不确定或多个主线冲突"
    ],
    "do_not_ask_when": [
      "只是普通中文口播短视频",
      "用户要求直接生成成片",
      "用户没有给样式要求但目标平台是抖音/视频号/Shorts",
      "用户已经说过要轻松好看的短视频风格"
    ]
  },
  "layout_qc": {
    "require_preflight_contact_sheet": true,
    "require_probe_render_before_final": true,
    "sample_every_sec": 5,
    "check_subtitle_safe_area": true,
    "check_banner_safe_area": true,
    "check_subtitle_banner_overlap": true,
    "check_text_min_size": true,
    "check_hyperframe_snapshots": true
  }
}
```

## `video_topic.json`

If the user does not provide a topic banner, generate it from the script, oral-video topic, asset plan, and shot plan.

```json
{
  "generation_mode": "auto_from_script | user_provided | reference_guided | manual_override",
  "source_files": [],
  "script_summary": "",
  "main_subject": "",
  "central_conflict": "",
  "viewer_hook": "",
  "one_sentence_promise": "",
  "candidate_banners": [
    {
      "main": "",
      "sub": "",
      "reason": "",
      "risk": "",
      "score": 0
    }
  ],
  "selected_banner": {
    "main": "",
    "sub": "",
    "reason": ""
  },
  "section_banners": [],
  "must_appear_full_video": true,
  "requires_user_confirmation": false,
  "uncertainty_reason": ""
}
```

Generation rules:

- The banner must answer what the video is about, what the conflict is, and why the viewer should keep watching.
- Main title should usually be `8-16` Chinese characters.
- Subtitle should usually be `10-22` Chinese characters.
- Use a question, conflict statement, or conclusion hook when it improves clarity.
- Finance, technology, and business videos default to `议题标题 + 逻辑钩子`.
- Knowledge explainers default to `核心问题 + 答案预告`.
- Opinion/person-view videos default to `观点冲突 + 结论钩子`.
- If several candidates exist, select the highest-scoring one without asking the user unless `requires_user_confirmation = true`.
- Use one full-video topic banner by default. Section banners are allowed only when the script has clear chapters; do not turn the edit into a PPT deck by changing banners too often.

Example finance/tech banner:

```json
{
  "selected_banner": {
    "main": "美光财报炸场真相",
    "sub": "存储周期逻辑失效？",
    "reason": "The script discusses a financial surprise and the market logic behind it."
  }
}
```

## `style_intake_report.json`

Record why the style was chosen:

```json
{
  "user_style_prompt_detected": false,
  "reference_images_detected": [],
  "style_decision": "default_large_short_video_caption | reference_guided | user_specified",
  "topic_decision": "auto_from_script | user_provided",
  "asked_user": false,
  "ask_reason": "",
  "final_decision_reason": ""
}
```

When reference images exist, Codex must visually inspect them and write the extracted style into the style contract or report: subtitle size, title position, dominant colors, outline/shadow treatment, and whether the look is news-like, suspense-like, finance-like, technology-like, casual, or documentary. The helper script can record reference paths, but it must not pretend that pure Python has performed OCR or visual style judgment.

## Default Behavior

- If the user gives no style prompt, use `large_short_video_caption` without asking.
- If the user says `字幕太小`, `轻松好看`, `参考这个图`, or `任何帧都能知道视频讲什么`, automatically enable large subtitles, persistent topic banner, layout preflight, and probe render.
- Ask the user only when the project has high uncertainty: conflicting reference styles, conflicting script themes, a style that would clearly mismatch the platform/use case, or a generated banner that may mislead.
- If the user explicitly disables the topic banner, set `persistent_topic_banner.enabled = false`; layout audit must record `user_disabled` rather than failing.

## Topic Banner Rules

The persistent topic banner is a topic anchor / visual thesis. It is not a second subtitle layer.

- It must summarize the full-video thesis or section, not copy the current bottom subtitle.
- It should visually match a large two-line short-video headline: main title `80-84px`, subtitle line `72-78px`, black rounded rectangle background at `0.72-0.78` opacity, and a centered title-card box around `720-760px` wide by `210-240px` high unless a reference style overrides it.
- It should stay in the upper safe area.
- It may use `compact_position_for_talking_head` during talking-head shots to avoid covering the speaker's face.
- It should remain visible for the full duration when `required_for_final_render = true`, unless the user explicitly disables it.
- It must not duplicate the active subtitle cue, including exact copies, near-identical rewrites, or per-sentence subtitle mirroring.

## Subtitle Rules

- Bottom subtitles default to large Chinese short-video captions.
- Normal subtitle size should default to `78-82px` for 1080x1920, with `72px` as the hard minimum.
- Emphasis size should be `86-96px`.
- Maximum subtitle line count is 2.
- Burned subtitle cues should be short spoken fragments, target `6-14` Chinese characters, hard max `18` except named entities.
- Remove visible punctuation such as `，。；：` unless semantically required.
- Long subtitles must be semantically split; do not shrink below `72px` or `font_size_min_px` to force long text into one cue.
- Each cue must remain a complete spoken phrase or meaningful clause and must use audio-derived timing for final renders.
- If `subtitle_cues.alignment_method = script_length_proportional_draft_only`, do not render `output/final.mp4`. First run subtitle alignment remediation: extract oral audio, check available ASR/Whisper/forced-alignment/manual timestamp inputs, rebuild cues, and rerun audits. Render only `output/draft_preview.mp4` and mark final blocked after those timing paths fail.
- Every final cue must have audio-derived timing from ASR, forced alignment, or manual phrase timestamps. Low-confidence/proportional cues fail final render.

## Required Gates Before Final

Final render must not start until all are true:

- `style_contract.json` exists and is used by render scripts.
- `video_topic.json` exists when the topic banner is enabled.
- `subtitle_style_audit.json.status = passed`.
- `topic_banner_audit.json.status = passed` or `user_disabled`.
- `layout_qc_report.json.status = passed`.
- `output/qc/style_preview_contact_sheet.png` exists.
- `output/qc/probe_render.mp4` exists, decodes, and representative probe frames exist.

Fail the final render if the required topic banner is missing, subtitles are below minimum size, subtitle timing is draft/proportional/low-confidence, subtitles exceed two lines or the hard cue length, visible punctuation remains without a semantic flag, title/subtitle text is clipped, banner and subtitle boxes overlap, HyperFrame/design cards occupy the subtitle zone, or preview/probe frames show unsafe layout.

Audit failures must trigger remediation before final blocking:

- Draft or missing timing: run audio extraction and ASR/forced/manual phrase timestamp alignment.
- Long or three-line subtitles: split on semantic/audio boundaries and rerun preview/audit.
- Banner missing/overlapping/duplicative: regenerate `video_topic.json` or adjust compact/safe-area layout.
- Probe/frame layout issues: revise style contract or render layout, regenerate contact sheet/probe, and audit again.

Write `output/FINAL_BLOCKED.md` only after these remediation attempts are exhausted, and cite `work/plan/remediation_log.json`.
