---
name: short-video-editor
description: Create reproducible workflows and editable assets for 1-2 minute vertical knowledge, explainer, or news commentary videos from an oral/talking-head video plus script, including news/event verification, downloadable video B-roll sourcing, data cards, subtitles, final renders, and recut packages. Use when the user asks to analyze a Chinese script, create a shotlist, collect/download video素材 or B-roll, plan related-news footage, design cards/charts/logical visualizations, render a Douyin/WeChat Channels style video, or export separated layers for Jianying/Premiere/DaVinci.
---

# Short Video Editor

## Overview

Build logic-led short videos from a script and oral video. The default style is **B-roll 主视觉 + 短时全屏数字人口播 + 少量专业 HyperFrame 动效**: B-roll carries most explanations, the digital human appears only as a short full-screen brand/trust anchor, and HyperFrames are reserved for key logic or data. Prefer a reproducible project workflow over one-off manual edits: analyze the full script, create a visual strategy, gather/record assets, render or plan the edit, then export both the final MP4 and editable layers.

Critical gate: after extracting script keywords, if matching local assets do not exist, online asset search/download is mandatory. Follow the source-acquisition order in `references/asset-sourcing.md`; do not replace missing B-roll with HyperFrames, generated bitmap assets, generated diagrams, text cards, or placeholder motion. If lawful downloadable or recordable assets cannot be found, stop at the sourcing stage and report the shortage instead of rendering.

Timing gate: final edits should be audio-aligned and subtitle-driven, not large-shot driven. Build a cue timeline from the oral audio plus script before rendering; use those cue boundaries to cut B-roll, motion cards, and digital-human appearances. Subtitle splitting must preserve spoken meaning and phrase boundaries: do not hard-split by a fixed character count such as every 12 Chinese characters. Avoid long subtitles, repeated subtitles across multiple visual frames, and B-roll sections whose visual changes do not follow the spoken cue rhythm.

Uniqueness gate: final edits must not reuse B-roll sources and must not replay a source after it has already been used. A source clip may be trimmed shorter once, but it must not be looped, restarted from the beginning, replayed from an earlier timestamp, or used as multiple source ranges. Audit the edit manifest and render commands for source playback ranges; expensive per-frame similarity checks are optional, not required. If replay/loop/rewind is detected outside an explicitly approved still-image fallback, revise the timeline, source more footage, or shorten coverage before rendering.

AE/HyperFrame overlay gate: during script and storyboard generation, actively identify where a PPT/process-style AE effect or HyperFrame overlay would improve the argument: process flow, comparison, timeline, cause-effect chain, KPI/data card, system structure, or decision logic. These dynamic effects are overlay layers on top of selected B-roll/video-derived backgrounds, not replacements for B-roll and not filler for missing footage. If unsure whether a segment deserves an AE/HyperFrame overlay, show a simple timecoded storyboard option to the user and ask for confirmation before rendering that section.

## Start Here

1. Inspect the project folder for script, oral video, BGM, existing assets, example screenshots, previous outputs, and user constraints.
2. If the project lacks structure, run `scripts/init_short_video_project.py <project_dir>` from this skill to create standard folders and CSV templates.
3. Read `references/workflow.md` before implementing a full video or workflow.
4. Read `references/visual-language.md` when assigning visual expressions to script logic, scene types, digital-human exposure, B-roll usage, data cards, and HyperFrame eligibility.
5. Read `references/hyperframes.md` when the user requests HyperFrames, GSAP, richer motion graphics, or a renderer split between ordinary edits and enhanced motion clips.
6. Read `references/asset-sourcing.md` before collecting, searching, downloading, screen-recording, or validating B-roll and reusable assets.
7. After reading the full script, run a related-news/event source scan before generic stock search. Save URLs, dates, and download feasibility in `work/plan/news_source_plan.json`.
8. When the user provides style screenshots, summarize the visual style first, then encode the style into the shot plan and HyperFrame direction before rendering.
9. Read `references/hyperframe-polish-guard.md` before generating any shot whose `scene_type` is `hyperframe_logic` or `hyperframe_data`, whose `scene_type` is `data_card_light` with `renderer: hyperframe`, or whose `visual_pattern` is comparison, timeline, process flow, KPI card, dashboard, system diagram, or cause-effect chain.

## Core Rules

- Treat the script as the source of truth. Read the full script before writing a shotlist.
- For an oral-video edit, create a subtitle cue timeline before the final edit timeline. Final renders require audio-derived timing: ASR word timestamps, phrase timestamps, or forced alignment between the supplied script and oral audio. Script-length proportional timing is allowed only for rough planning previews and must not be used for a final MP4 unless the user explicitly accepts a non-synced draft. Save the result as `work/plan/subtitle_cues.json`.
- Subtitle segmentation must be meaning-aware. Split on sentence, clause, breath, pause, contrast, and spoken phrase boundaries; each cue should read as a complete spoken phrase or meaningful clause. Do not break a fixed number of characters in the middle of a phrase, named entity, number, technical term, or cause-effect relation just to satisfy a length target.
- Keep subtitles readable without making character count a hard cutter. Prefer one line when a complete phrase is short; allow two balanced lines when a complete spoken phrase would be damaged by over-splitting. Use length targets as soft readability checks, not as the segmentation algorithm.
- Keep most cue durations around the actual spoken phrase timing. A cue starts at the first spoken word and ends after the last spoken word, with small padding only when needed for readability. Avoid any subtitle cue staying on screen for several visual cuts.
- Use subtitle cues as edit points. B-roll and motion cards should change on cue boundaries or every `1-2` cues. Do not build a final timeline from coarse 6-8s script segments and then stretch one subtitle across that whole segment.
- Do not repeat the same subtitle text over consecutive visual frames. If a sentence needs multiple visual beats, split it into multiple cue texts or keep only a short keyword highlight on later beats.
- Default to B-roll as the main picture, not the digital human and not HyperFrames. The normal priority is: `broll_fullscreen` -> `broll_with_overlay` -> `talking_head_fullscreen` -> `data_card_light` -> `hyperframe_logic` / `hyperframe_data`.
- Keep the total visual mix near these targets: full-screen digital human `15%-28%`, B-roll/related footage/screen recording/image motion `50%-70%`, HyperFrames `8%-18%`. For a 2-minute video, that roughly means digital human `18-34s`, B-roll `60-85s`, and HyperFrames `10-22s`.
- Treat the visual mix as a render gate, not an early excuse to synthesize visuals. First acquire selected B-roll/screen-recording/image assets, then compute the video B-roll, digital-human, and animation/HyperFrame ratios from those selected assets before rendering.
- When the digital human appears, it must be full screen. Do not use picture-in-picture, split screen, half-screen, corner windows, transparent overlays on B-roll, or persistent small host views.
- Digital-human appearances should be short and intentional: usually `1.5-4s` each; except opening/ending, avoid more than `5s` continuously, and never let continuous full-screen digital-human narration exceed `15s`.
- Use full-screen digital human for opening brand presence, core question, section switch, strong judgment, trust/credibility beat, and conclusion. Use voice-only narration over B-roll for ordinary explanation.
- Strengthen only key data, judgments, turning points, comparisons, causal explanations, processes, timelines, system structures, and conclusions. Do not make every sentence a card.
- Do not convert ordinary narration into a PPT-style page. A short video should be B-roll-led, with light labels and only a few justified HyperFrame cards or diagrams.
- For B-roll, use many distinct assets in a 1-2 minute video; avoid repeating the same footage unless repetition is intentional.
- Count B-roll distinctness by the underlying visual source/shot, not by a different overlay, crop, animation, or rotation applied to the same source.
- In the final timeline, do not reuse the same `source_url`, `direct_download_url`, provider asset id, or local source clip as B-roll. Different trims, crops, speeds, overlays, or encodes of the same URL count as the same asset. If the timeline needs more visual time, source more unique footage or shorten B-roll coverage; do not pad with repeats.
- Do not loop a short clip, freeze a video frame, restart a source from `0s`, or replay an earlier part of a source to fill time. Before final render, write `work/plan/source_playback_audit.json` from the edit manifest/render commands; if any source is looped, restarted, used in multiple ranges, or assigned output duration longer than its available non-looped trim, fail the render unless it is an explicitly approved still-image fallback.
- Split production into four renderer classes:
  - `editing_timeline` for full-screen digital human, direct B-roll cuts, subtitles, audio, lower thirds, and simple overlays.
  - `remotion` for template-like light overlays and light data cards when normal editing tools are not enough.
  - `hyperframe` only for scored/justified key logic, key data, strong comparison, process explanation, time change, cause-effect chain, or system-structure breakdown.
  - `screen_recording` for public/authorized websites, products, dashboards, reports, or search processes.
- When a shot has no motion-enhanced logic, do not add decorative masks, left-right shaking, or artificial panning just to create movement. Cut distinct footage directly and let the source motion carry the shot.
- Before rendering, create `work/plan/shot_plan.json` and make every shot declare `narrative_role`, `logic_type`, `scene_type`, `renderer`, `digital_human_presence`, `broll_needed`, `broll_keywords`, `overlay_text`, `data_visual_type`, `hyperframe_score`, `hyperframe_allowed`, `visual_pattern`, `ae_overlay_candidate`, `ae_overlay_type`, `broll_base_asset`, `duration_sec`, `assets`, and `edit_notes`.
- Allowed `scene_type` values are `talking_head_fullscreen`, `broll_fullscreen`, `broll_with_overlay`, `data_card_light`, `hyperframe_logic`, `hyperframe_data`, `screen_recording`, and `conclusion_card`.
- HyperFrames require a written `hyperframe_reason`, `why_simple_broll_is_not_enough`, `visual_pattern`, and `hyperframe_score >= 3`. If the reason is weak, downgrade to B-roll, light overlay, light data card, screen recording, or full-screen digital-human pivot.
- If a HyperFrame is used for animation, the effect must be complete: define the animation lifecycle, render a standalone clip, inspect start/build/peak/settle/end frames, verify the clip decodes, and confirm every promised element enters, animates, holds long enough to read, and exits or settles cleanly. If this cannot be completed, downgrade the shot instead of shipping a partial animation.
- HyperFrame generation must pass the polish guard before coding and before completion. Produce `design_plan` first, then generate HTML, run `npx hyperframes lint`, run `npx hyperframes preview` or `npx hyperframes render`, capture `0%/25%/50%/75%/100%` snapshots, fix visual QA issues, and only then mark the shot complete. If the guard decides the shot does not need HyperFrame, downgrade automatically.
- HyperFrames should look like polished tech/business news motion graphics, not rough grid diagrams. Prefer real or video-derived dark cinematic backgrounds, deep navy translucent HUD panels, neon mint/pink accent colors, large high-contrast metrics, refined icon/line systems, glow/blur/parallax/scan-light effects, and well-timed reveals. Avoid crude flat boxes, crowded labels, generic grids, and unfinished-looking cards.
- For any motion card or HyperFrame inside an oral-video edit, use relevant selected B-roll or video-derived stills as the visual base whenever possible; darken, blur, crop, or vignette that base instead of using an empty grid/background. Motion graphics enhance key logic after the asset gate; they must not be the filler visual system.
- Treat AE/HyperFrame work as an overlay track: it should sit above B-roll or a video-derived background as transparent graphics, labels, arrows, data widgets, process nodes, animated masks, or pre-composited graphic layers. Do not replace a required B-roll segment with a full-screen generated card unless the shot is explicitly classified as a key standalone logic/data card.
- Require enough unique footage before final rendering. A 1-2 minute video should normally have at least 20-25 distinct underlying footage/image sources, and the plan must mark shortages with `needs_sourcing`.
- Asset search is a required production stage, not a cosmetic afterthought. For each shot, extract visualizable keywords, generate primary/fallback/search-recording terms, screen candidates, and record metadata before rendering.
- After keyword extraction, check local assets first. If no suitable local asset exists for a B-roll shot, search online and attempt lawful download or authorized screen recording before any rendering work. This search is mandatory; do not skip it because a generated card or HyperFrame would be faster.
- Video sourcing is first-class. Check every configured/known source for downloadable video before using lawful still images or authorized screen recordings. Generated graphics and placeholder cards are not sourcing fallbacks.
- If a provider search/download needs an API key and neither the environment nor project `.env` provides it, create or update a project-root `.env.example` with placeholder variable names, tell the user to create `.env`, and pause before running that API source. If the user says they do not have the key or explicitly asks to continue, record that provider as `needs_api_key` and continue with non-API public/direct-download/official/authorized-recording sources.
- Search and download video素材 by shot-level related keywords, not only broad topic terms. During script-to-visual planning, map each script fragment to the closest visible footage keywords and select the most relevant clips for the edit; when there are more good clips than runtime, discard weaker surplus rather than forcing every downloaded asset into the video.
- Do not treat still images, generated diagrams, crops, masks, HyperFrames, generated bitmap assets, or text cards as substitutes for missing video B-roll. Still images may be used only when the sourcing workflow found no suitable video but did find a lawful, relevant image; generated assets require explicit user approval and must not satisfy the B-roll count.
- If the sourcing workflow cannot find enough lawful, relevant video/image/screen-recording assets for the planned B-roll coverage, stop. Produce `asset_search_plan.json`, `video_source_audit.csv`, and a concise shortage report; do not render a final video from generated substitutes.
- If subtitle timing cannot be derived from audio timestamps or reliable forced alignment, stop before final rendering. Produce the draft cue plan and a concise alignment dependency report; do not render a final MP4 from script-length proportional timing unless the user explicitly requests a non-synced draft.
- Do not layer multiple unrelated still images in stacked depth layers, and do not place still images on top of video footage as faux B-roll. If a still image is the most relevant asset, use it as a single full-screen shot with restrained editing treatment such as a slow push, pan, crop, blur-to-focus, match cut, or brief photo montage; record the image fallback reason.
- Search related news and official event materials early. Download only lawful, permitted, non-DRM video assets; otherwise mark the source as `reference_only` or `cannot_download` and use a permissible replacement.
- Screen recording means recording a playable public/authorized video or product/report interface when no direct download/API/media-kit route is available. It does not mean scrolling a webpage just to create motion. Do not use website-scroll screen recordings as a replacement for missing B-roll unless the page interaction itself is the story.
- For ordinary edit shots, maintain a fast base rhythm: short full-screen digital-human pivots and distinct B-roll should be interleaved, and motion graphics should only reinforce important ideas.
- Do not add subtitle-like title boxes over B-roll when bottom subtitles already say the same thing. Non-subtitle screen text should be limited to concise labels, source marks, chart values, or non-duplicative callouts.
- Bottom subtitles may use keyword highlights in `.ass`: mark only key numbers, entities, logic pivots, risk words, and conclusions with one or two accent colors. Do not create a second subtitle layer or duplicate the same sentence in a title box.
- Subtitle styling should favor short, high-impact cue text with selective keyword highlight. Do not burn three-line paragraph subtitles. Split long technical phrases across several cue timings instead of shrinking text or holding a long cue.
- Keep every output reproducible: save scripts, source lists, shotlists, subtitles, manifests, and generated assets.
- When using web assets, prefer official, permissive, or clearly attributable sources. Record URLs and licenses/notes in a source file.
- Always produce an editable package when the user may manually refine the result.

## Required Shotlist Columns

Every script-to-visual plan must include these fields, in Chinese unless the project is English:

```csv
shot,script_fragment,narrative_role,logic_type,scene_type,renderer,digital_human_presence,digital_human_reason,broll_keywords,overlay_text,data_visual_type,hyperframe_score,hyperframe_allowed,visual_pattern,ae_overlay_candidate,ae_overlay_type,broll_base_asset,overlay_layer_plan,design_plan,animation_plan,hyperframe_polish_guard,hyperframe_completeness_check,editing_rhythm,screen_text,user_review_needed
```

For render-ready edits, also create a timecoded manifest:

```csv
shot_id,source_segments,start,end,duration,visual_mode,asset_key,source_in,source_out,playback_policy,overlay_png,script
```

## Workflow

1. **Context discovery**
   - Identify oral video, script file, target platform, aspect ratio, expected duration, BGM, sample visual style, and output preference.
   - For Chinese vertical short video default to `1080x1920`, `30fps`, strong subtitles, and short visual units.

2. **Script analysis**
   - Segment the script by meaning, not just punctuation.
   - Label each segment as data, comparison, time change, process, cause-effect, risk, turning point, metaphor, or conclusion.
   - While segmenting, decide whether the segment should get B-roll only, a light label, or an AE/HyperFrame overlay on top of B-roll. Mark process/comparison/timeline/cause-effect/data/system-structure segments as overlay candidates when a motion layer would clarify the logic.
   - Extract shot-level visible keywords and related-news terms while segmenting, so asset search stays tied to the script instead of becoming generic stock search.
   - Group adjacent sentences into 20-30 visual units for a 2-3 minute video when the user wants a dense edit.
   - For oral-video projects, also create audio-aligned subtitle cues from the script/audio and record cue id, start, end, text, keywords, related shot, visual intent, alignment source, and split reason. These cues drive the render timeline.
   - If an AE/HyperFrame overlay decision is uncertain, create a simple storyboard row showing time, spoken phrase, proposed B-roll base, proposed overlay, and why it may be useful; ask the user before rendering that overlay.

3. **Visual strategy**
   - Use `references/visual-language.md` to choose the visual expression.
   - Keep full-screen digital-human intervals short and intentional.
   - Explicitly mark each segment as `talking_head_fullscreen`, `broll_fullscreen`, `broll_with_overlay`, `data_card_light`, `screen_recording`, `hyperframe_logic`, `hyperframe_data`, or `conclusion_card` before rendering.
   - Choose `renderer: editing_timeline` for ordinary cuts, `renderer: remotion` for light template overlays/cards, `renderer: screen_recording` for authorized recordings, and `renderer: hyperframe` only for scored motion-enhanced clips.
   - Include B-roll keywords, digital-human reason, data-card need, HyperFrame score/reason, and whether simple B-roll is enough.
   - For every HyperFrame-triggered shot, write `design_plan` and `hyperframe_polish_guard` records before generating HTML. Downgrade weak HyperFrame candidates before coding.
   - For every AE/HyperFrame overlay candidate, specify the B-roll base asset, overlay layer content, animation stages, and whether the output should be a transparent overlay or pre-composited over B-roll.
   - Do not generate HyperFrame/video-card substitutes for shots marked `broll_needed: true` until the asset gate has passed. HyperFrames can enhance selected moments only after real selected assets exist and the ratio audit is based on those assets.

4. **Asset plan**
   - Read `references/asset-sourcing.md`.
   - Use local assets first. If local assets are missing or insufficient, search online in the required acquisition order: related news/official event sources, official media kits/public datasets, downloadable stock/open video sources, permissible image sources, then authorized screen recordings.
   - When a required provider API key is missing, create/update `.env.example`, ask the user to add `.env`, and stop before using that API provider unless the user already said they have no key or asked to continue. After that explicit user direction, skip only the missing-key API attempt and keep searching other lawful sources.
   - Search video first for every B-roll shot. Prefer clips whose visible content directly matches the script fragment; when enough better clips exist, drop loosely related clips from the edit even if downloaded.
   - For every listed provider/source, check whether a downloadable video source is available and record the result before using image fallback. If no lawful downloadable or recordable asset is found for required B-roll coverage, stop at this stage.
   - For every shot, output `primary_terms`, `fallback_terms`, `screen_recording_targets`, `data_visual_needed`, and selected/needed assets.
   - Save source metadata in `assets/metadata/asset_manifest.json`, `assets/素材来源.md`, or `assets/sources.csv`.
   - Enforce the distinct-source target before rendering.
   - Do not use unrelated images just because they look cinematic. Do not use HyperFrame, generated bitmap assets, generated diagrams, or placeholder cards to satisfy missing B-roll.

5. **Rendering or handoff**
   - Before rendering, verify that selected assets exist on disk and `visual_ratio_audit.json` computes B-roll, digital-human, and animation/HyperFrame ratios from the selected assets. If the B-roll target cannot be met, stop and report sourcing gaps.
   - If generating a video, create a local render script under `work/` that can be rerun.
   - Generate the edit timeline from `subtitle_cues.json`: choose one visual event per semantic cue or per two very short adjacent cues, bind each event to one unique source asset, and cut on cue boundaries.
   - Run a duplicate-source audit before rendering. If any B-roll source URL or direct-download URL appears twice in the final timeline, revise the timeline or source more assets before rendering.
   - Run a source playback audit before final delivery. If the edit manifest or render commands show looped footage, restarted source playback, repeated source ranges, or output duration longer than the selected trim, revise the timeline or source more footage before rendering.
   - Burn subtitles only for final preview. Keep separate `.srt` and, when keyword highlights are used, `.ass`.
   - Export a final MP4 and an editable package.

6. **Editable package**
   - Export `01_base_with_oral_no_cards_no_subtitles.mp4`.
   - Export `02_clean_broll_no_cards_no_oral.mp4` when possible.
   - Export `03_overlay_cards_png/` with transparent card/chart PNGs or PNG sequences.
   - Export `04_subtitles.srt` and optional `04_subtitles.ass`.
   - Export `00_edit_manifest.csv`.
   - Include the original oral video and script for manual recutting.

7. **Verification**
   - Run ffmpeg decode checks on final and base videos.
   - Extract representative frames covering data card, oral pivot, process diagram, timeline, decision tree, and conclusion.
   - Inspect frames for blank output, clipped text, subtitle/card overlap, wrong aspect ratio, and missing audio.
   - For HyperFrame shots, verify `npx hyperframes lint`, preview/render, `0%/25%/50%/75%/100%` snapshots, visual QA, and auto-fix records in `work/plan/hyperframe_polish_guard.json`.
   - Check `work/plan/visual_ratio_audit.json` for digital-human, B-roll, and HyperFrame ratios and continuous-duration violations.

## Manual Recut Guidance

Tell the user to edit with this track structure:

```text
V4 subtitles: SRT/ASS or manual subtitle layer
V3 overlay cards/charts: transparent PNG or PNG sequence
V2 replacement B-roll: user-added footage
V1 base video: base_with_oral_no_cards_no_subtitles.mp4
A1 narration/audio: base audio or original oral video audio
```

When the user dislikes a card, replace only that PNG using `00_edit_manifest.csv`. When the user dislikes footage, cover the time range with new B-roll on V2.

## Completion Checklist

- Final MP4 exists and decodes.
- Base editable MP4 exists and decodes.
- Subtitle files exist separately from final MP4.
- Shotlist and manifest exist.
- Visual ratio audit exists and passes or records the required revisions.
- HyperFrame polish guard records exist and pass for every HyperFrame-triggered shot, or those shots were downgraded before render.
- Subtitle cues exist, are audio-aligned, meaning-aware, and used as edit timing boundaries.
- Subtitle audit confirms final subtitles are not fixed-character splits, each cue preserves a complete spoken phrase or meaningful clause, and cue timing follows the spoken audio.
- The final timeline has no repeated B-roll `source_url`, `direct_download_url`, provider id, or local source clip.
- Source playback audit exists and confirms no B-roll source is looped, restarted, replayed from an earlier timestamp, or used in multiple timeline ranges. Per-frame duplicate checks are optional for extra QC, not the primary requirement.
- AE/HyperFrame overlay candidates were evaluated during script planning, and accepted overlays are layered over B-roll/video-derived backgrounds unless explicitly marked as key standalone logic/data cards.
- Related-news plan and provider video-source audit exist when assets were sourced.
- Assets and sources are traceable.
- API keys are not hardcoded or copied into manifests/edit packages.
- A few QC frames were inspected.
- Explain which files to open for manual editing.
