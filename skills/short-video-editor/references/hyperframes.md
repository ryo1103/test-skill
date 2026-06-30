# HyperFrames Motion Clips

Use this reference when the edit is split into ordinary Remotion timeline shots and enhanced HyperFrames motion graphic clips.

## Role In The Video

HyperFrames are not the main style of the whole video. The default video positioning is:

```text
B-roll 主视觉 + 短时全屏数字人口播 + 少量专业 HyperFrame 动效
```

Target HyperFrame share: `8%-18%` of the final runtime. For a 2-minute video, that is roughly `10-22s`. Do not let one continuous HyperFrame block exceed `15s`.

## Renderer Split

Use `editing_timeline` or `remotion` for:

- Full-screen digital-human cuts.
- Direct B-roll cutting.
- Audio, subtitles, lower thirds, and simple static cards.
- B-roll montages where the source footage itself carries the motion.
- Light overlays and `data_card_light` when a normal edit is enough.

Use `hyperframe` only for:

- Key data and KPI dashboards.
- Strong comparisons.
- Process explanations.
- Time changes and inflection points.
- Cause-effect chains.
- System or structure breakdowns.
- Final high-importance takeaways.

Do not use HyperFrames just to decorate ordinary B-roll, compensate for missing素材, or turn ordinary narration into a PPT-style page.

## Premium Tech-News Style

When the user asks for refined HyperFrame animation or provides screenshots like cinematic business/tech explainers, use this style target:

- **Base footage first**: use a relevant video frame or video clip as the background whenever possible, usually darkened, desaturated, blurred, or blue-toned. Avoid empty grid-only backgrounds unless the subject is an abstract system diagram.
- **Cinematic contrast**: black/charcoal top area, deep navy lower panels, soft vignette, local spotlights, subtle grain, and depth blur. The frame should feel like a premium finance/technology news package, not a PPT slide.
- **Accent palette**: mint/cyan for headline/trust/logic, hot pink/magenta for key emphasis, white for primary metrics, and deep translucent navy for glass panels. Use 1-2 accent colors per clip; avoid rainbow diagrams.
- **Typography**: large bold Chinese headline or label when needed, strong metric numerals, compact supporting labels. Use high contrast, subtle glow or shadow, and enough tracking/line height for vertical mobile viewing.
- **Composition**: a large visual anchor plus one clear data or logic layer. Good patterns include top hook plate + lower metric dashboard, translucent horizontal HUD band over B-roll, network nodes on a dark product/technology background, or side-by-side KPI fields.
- **Motion feel**: masked panel reveal, counter rise, line draw, node pulse, icon scale-in, soft glow bloom, scan light sweep, parallax background drift, and short hold. Motion should be smooth and intentional, not shaky or random.
- **Layering discipline**: use one B-roll/background layer plus one coherent graphic system. Do not stack multiple unrelated screenshots/photos at different depths, and do not paste still images over video as decoration.
- **Subtitle clearance**: keep bottom subtitle safe space clear. If there is a top headline, it must be a hook/section label or visual thesis, not a duplicate of the bottom subtitle sentence.

Preferred refined patterns:

```text
cinematic_kpi_dashboard
top_hook_plus_metric_band
neon_network_map
split_panel_comparison
dark_glass_timeline
spotlighted_product_logic
```

Avoid low-fidelity patterns:

```text
blank_grid_card
flat_boxes_with_arrows
crowded_node_graph
generic_icon_cloud
full_sentence_title_box
unrelated_image_collage
```

## Eligibility Gate

Compute `hyperframe_score` for every candidate shot:

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

Only assign `scene_type: hyperframe_logic` or `scene_type: hyperframe_data` when:

- `hyperframe_score >= 3`.
- The shot includes `hyperframe_reason`.
- The shot includes `why_simple_broll_is_not_enough`.
- The shot declares a concrete `visual_pattern`.

If any of these are missing, downgrade the shot.

Allowed HyperFrame visual patterns:

- `side-by-side comparison`
- `before-after`
- `comparison matrix`
- `process flow`
- `timeline`
- `cause-effect chain`
- `KPI card`
- `system diagram`
- `dashboard card`

Do not use HyperFrame for:

- Ordinary background introduction.
- Generic topic setup.
- Lines whose main job is emotional connection, such as "但问题也来了".
- Generic opinions without data/process/comparison/causality, such as "这会提高效率".
- Transition lines, such as "接下来我们看第二点".
- B-roll-friendly statements such as "B-roll 可以让画面更丰富".
- Non-critical flowcharts.

Downgrade map:

```text
hyperframe_logic -> broll_with_overlay
hyperframe_data -> data_card_light
data_card_light -> subtitle highlight / overlay
animated background -> B-roll
pure animation explanation -> B-roll + oral audio
non-critical flowchart -> B-roll + simple arrow / callout
```

If several consecutive shots are HyperFrames, keep only the most important one and downgrade the others.

## Polish Guard Gate

Before generating HyperFrames HTML, read and apply [hyperframe-polish-guard.md](hyperframe-polish-guard.md) when any shot has:

- `scene_type = hyperframe_logic`
- `scene_type = hyperframe_data`
- `scene_type = data_card_light` and `renderer = hyperframe`
- `visual_pattern` in `comparison`, `side-by-side comparison`, `timeline`, `process flow`, `KPI card`, `dashboard`, `dashboard card`, `system diagram`, or `cause-effect chain`

For every triggered shot, produce `design_plan` before coding. The plan must include:

- shot purpose
- key message
- exact screen text
- visual pattern
- layout type
- typography scale
- color tokens
- animation sequence
- duration
- why HyperFrame is needed

If the design plan shows that B-roll, screen recording, a light data card, or a Remotion simple overlay can communicate the point clearly, downgrade before coding.

Use this downgrade map:

```text
hyperframe_logic -> broll_with_overlay
hyperframe_data -> data_card_light
data_card_light + renderer hyperframe -> remotion simple overlay
available footage explains the point -> broll_with_overlay
public/product/report UI explains the point -> screen_recording
```

## Completeness Gate

If HyperFrames are used to make an animation effect, the effect must be complete. Do not ship a static placeholder, a half-animated diagram, an unfinished counter, or a clip where elements appear/disappear without a clear lifecycle.

Each HyperFrame clip must define these stages:

```text
setup -> enter -> build -> emphasis -> readable hold -> exit_or_settle
```

Requirements:

- `setup`: all layers, data, labels, positions, and safe areas are initialized before animation begins.
- `enter`: the viewer can understand what object or concept is entering the frame.
- `build`: lines, nodes, cards, charts, counters, arrows, and relationships animate according to the narration beat.
- `emphasis`: the key conclusion, metric, comparison, or causal link is visually emphasized.
- `readable hold`: important text/data stays readable long enough, normally at least `0.8-1.5s` depending on density.
- `exit_or_settle`: the animation either exits cleanly into the next edit or settles into a complete final frame. It must not end mid-transition.

Every promised element in `visual_pattern`, `screen_text`, and `animation_notes` must appear in the rendered clip. If a planned element cannot be animated fully, remove it from the plan or downgrade the shot.

## Clip Contract

Each HyperFrames clip should be a standalone video asset:

```text
work/hyperframes/clips/<shot_id>_<slug>.mp4
```

Then insert it into the Remotion main timeline as a full-screen source clip.

The source plan should include:

```json
{
  "shot_id": "V01",
  "renderer": "hyperframe",
  "scene_type": "hyperframe_data",
  "visual_pattern": "kpi_dashboard_side_by_side",
  "duration": 5.2,
  "assets": [],
  "screen_text": "",
  "design_plan": {
    "shot_purpose": "",
    "key_message": "",
    "exact_screen_text": [],
    "layout_type": "",
    "typography_scale": {},
    "color_tokens": {},
    "animation_sequence": [],
    "why_hyperframe_is_needed": ""
  },
  "animation_plan": {
    "stages": "setup -> enter -> build -> emphasis -> readable hold -> exit_or_settle",
    "timing_notes": "Counter builds from 0.8s to 2.2s; comparison line settles by 3.5s.",
    "sync_to_narration": "Main metric lands on the spoken conclusion.",
    "readability_hold_sec": 1.2
  },
  "hyperframe_completeness_check": {
    "standalone_clip_path": "work/hyperframes/clips/V01_kpi_dashboard.mp4",
    "frame_checks": ["0%", "25%", "50%", "75%", "100%"],
    "decode_check": "pending",
    "all_elements_animated": false,
    "no_partial_or_placeholder_animation": false
  },
  "hyperframe_polish_guard": {
    "lint_status": "pending",
    "preview_or_render_status": "pending",
    "snapshots": ["0%", "25%", "50%", "75%", "100%"],
    "visual_qa_status": "pending",
    "final_status": "pending"
  },
  "hyperframe_score": 4,
  "hyperframe_reason": "The core data comparison drives the argument.",
  "why_simple_broll_is_not_enough": "B-roll cannot show the metric relationship clearly."
}
```

## Animation Direction

Prefer realistic motion:

- Use GSAP timelines with stagger, easing, anticipation, overshoot, and settle.
- Animate values with counters and momentum, not linear text swaps.
- Use line drawing, glow pulses, depth blur, scan light, masked glass-panel reveals, and parallax only when they clarify the logic.
- When using real footage under graphics, treat it like a cinematic plate: darken or blur enough for readability, but keep the subject recognizable and relevant to the script.
- Use refined micro-interactions: numbers count up with easing, nodes breathe once then settle, lines draw along the reading order, panels reveal on beat, and the final state holds.
- Keep motion tied to the narration beat.
- Leave safe space for subtitles.
- Make the whole timeline deterministic and complete: no orphan tweens, no uninitialized states, no animation that begins after the clip ends, and no final frame that contradicts the intended conclusion.

Avoid:

- Generic rotation templates.
- Random lateral shaking.
- Continuous zoom/pan on every shot.
- Decorative masks on normal B-roll.
- Overlapping labels, lines, and subtitles.
- Repeating the bottom subtitle as a second title box.
- Rough diagrams that look like debug output: plain grids, unstyled rectangles, thin unreadable lines, labels pasted without visual hierarchy, or charts with elements colliding.
- Image-collage fake depth: multiple stills stacked in layers, still images pasted over video, or unrelated screenshots used as background filler.
- Full-screen animation for ordinary narration.
- Ending a chart, line, counter, or node-link animation before it reaches its final value or state.
- Placeholder text, placeholder icons, missing logos, missing data labels, or invisible layers in the rendered clip.

## Ordinary B-Roll

When a shot is ordinary B-roll:

- Cut distinct footage directly.
- Use hard cuts or very short dissolves.
- Do not use masks unless the user explicitly asks.
- Do not count a different crop, scale, or overlay as a new asset.
- If the section is longer than 5 seconds, use multiple distinct source shots.
- Use light labels, callouts, arrows, or small data cards when necessary, but do not upgrade to HyperFrame unless the eligibility gate passes.

## QC

For each HyperFrames clip:

- Run `npx hyperframes lint` before final render. If the CLI is unavailable, record it and downgrade or block the HyperFrame; do not mark it complete.
- Run `npx hyperframes preview` or `npx hyperframes render`.
- Capture and inspect stills at `0%`, `25%`, `50%`, `75%`, and `100%` progress.
- Inspect text overlap, subtitle clearance, and edge clipping.
- Decode-check the exported clip with `ffmpeg -v error`.
- Confirm `hyperframe_score >= 3` and the reason fields are present.
- Confirm `design_plan` exists and justifies HyperFrame over B-roll, screen recording, light card, or simple overlay.
- Confirm the HTML uses `1080x1920`, safe area, max content width, one main idea, `3-5` items maximum, no long paragraphs, no random colors, no crowded dashboard, and no over-animation.
- Confirm `animation_plan` has setup, enter, build, emphasis, readable hold, and exit/settle stages.
- Confirm all promised elements appear, animate, and reach the final intended state.
- Confirm no placeholder, half-rendered, blank, or mid-transition ending frame remains.
- Auto-fix and re-render when snapshots show overflow, tiny text, crowded layout, overlap, unsafe placement, wrong end state, inconsistent colors, a messy PPT look, or random webpage look.
- Mark the shot `complete` only after visual QA passes. Otherwise downgrade, block, or keep it out of the final timeline.

For the final Remotion timeline:

- Confirm ordinary B-roll sections do not receive HyperFrames motion treatment.
- Confirm HyperFrames clips are inserted only at planned key moments.
- Confirm total HyperFrame duration is within `8%-18%` unless the user explicitly approves a different mix.
- Confirm no continuous HyperFrame block exceeds `15s`.
