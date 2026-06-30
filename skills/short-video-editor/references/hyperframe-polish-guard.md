# HyperFrame Polish Guard

Use this reference whenever generating or revising HyperFrames motion graphics inside `short-video-editor`.

## Trigger Conditions

Apply this guard before generating any HyperFrame when a shot has any of these conditions:

- `scene_type = hyperframe_logic`
- `scene_type = hyperframe_data`
- `scene_type = data_card_light` and `renderer = hyperframe`
- `visual_pattern` is one of `comparison`, `side-by-side comparison`, `timeline`, `process flow`, `KPI card`, `dashboard`, `dashboard card`, `system diagram`, or `cause-effect chain`

The guard is a quality gate, not a style lock. The visual style can vary by project, but the composition must be readable, restrained, and QA-verified before it can be marked complete.

## Pre-Build Design Plan

Before writing HyperFrames HTML, output and save a compact `design_plan` for every triggered shot:

```json
{
  "shot_id": "",
  "shot_purpose": "",
  "key_message": "",
  "exact_screen_text": [],
  "visual_pattern": "",
  "layout_type": "hero_number | two_column_comparison | three_step_process | timeline | cause_effect_chain | dashboard_card | system_diagram",
  "typography_scale": {
    "hero_number": "120-180px",
    "main_title": "64-92px",
    "section_title": "48-64px",
    "body": "34-44px",
    "small_label": "24-30px",
    "source_note": "20-24px"
  },
  "color_tokens": {
    "background": "",
    "primary_text": "",
    "secondary_text": "",
    "card_background": "",
    "border": "",
    "accent": "",
    "warning": ""
  },
  "animation_sequence": ["setup", "enter", "build", "emphasis", "readable_hold", "exit_or_settle"],
  "duration_sec": 0,
  "why_hyperframe_is_needed": ""
}
```

If the design plan cannot justify HyperFrame, downgrade before coding:

```text
hyperframe_logic -> broll_with_overlay
hyperframe_data -> data_card_light
data_card_light + renderer hyperframe -> remotion simple overlay
complex visual but available footage explains it -> screen_recording or broll_with_overlay
```

## Format And Layout Rules

Use vertical short-video format:

- Canvas: `1080x1920`, `9:16`
- Safe area top: `160px`
- Safe area bottom: `180px`
- Safe area left/right: `72px`
- Main content max width: `936px`
- Important text must stay inside the safe area.
- Main content should be vertically centered unless the shot needs a clear top title.

Maximum content per shot:

- One main idea.
- One main title.
- One main visual structure.
- `3-5` supporting items maximum.
- One primary accent color, plus optional warning color.
- One dominant motion pattern.
- No long paragraphs.

If a shot needs more than five items, split the shot or downgrade part of it to B-roll with overlay.

## Allowed Layout Patterns

- `hero_number`: one large number, one short label, one implication sentence, optional small source line.
- `two_column_comparison`: balanced left/right cards, clear labels, maximum three points per side, one highlighted key difference.
- `three_step_process`: three steps with one icon/number, one label, and one short explanation per step.
- `timeline`: three to five nodes, one highlighted turning point, short labels only.
- `cause_effect_chain`: cause nodes, restrained arrows, emphasized final result.
- `dashboard_card`: maximum three metrics, one primary metric, two secondary metrics, clean grid, no fake complex UI.
- `system_diagram`: maximum five nodes, grouped relationships, clear directional arrows, no spiderweb.

## Typography Rules

- Use at most two font families, preferably Inter, Geist, Manrope, SF Pro-style sans-serif, or `system-ui`.
- Use no more than three text sizes in one composition.
- Chinese main title should usually be under 14 characters.
- Chinese body line should usually be under 18 characters.
- Rewrite long explanations into two or three short labels.

Recommended type scale:

```text
hero number: 120-180px, weight 700-800
main title: 64-92px, weight 650-750
section title: 48-64px
body: 34-44px, weight 400-500
small label: 24-30px, weight 500-600
source note: 20-24px
```

## Color Rules

Use a restricted palette:

- One background color.
- One primary text color.
- One muted text color.
- One accent color.
- Optional one warning color.

Default professional palette:

```text
background: #0B0F17 or #F7F8FA
primary text: #FFFFFF or #111827
secondary text: #AAB2C0 or #4B5563
card background: rgba(255,255,255,0.08) or #FFFFFF
border: rgba(255,255,255,0.14) or #E5E7EB
accent: #4F8CFF / #7C5CFF / #00C2A8
```

If the project has `DESIGN.md`, use those tokens instead of inventing new colors.

Avoid random rainbow colors, unmotivated neon palettes, and inconsistent accent colors.

## Card And Motion Rules

Cards must be intentional:

- Border radius: `28-40px`
- Padding: `36-56px`
- Gap: `20-36px`
- Use subtle border, subtle shadow, or subtle glass effect.
- Prefer fewer larger cards over many small cards.
- Avoid nested cards, thick borders, random rotations, and text touching borders.

Allowed motion vocabulary:

- fade + slide up
- scale `0.96 -> 1`
- number count-up
- line draw
- arrow reveal
- card stagger
- spotlight highlight
- background slow drift
- chart grow
- node connect

Default timing:

```text
micro motion: 0.25-0.45s
card entrance: 0.45-0.7s
title entrance: 0.5-0.8s
chart reveal: 0.8-1.2s
full beat: 3-7s
```

Use at most two animation styles in one shot. Do not animate every element at once, bounce everything, use long rotations, or use random 3D flips unless explicitly requested.

## HyperFrames Technical Rules

- Use a valid root composition element.
- Use the correct `data-composition-id`.
- Use `class="clip"` for timed elements.
- Register GSAP timelines with `window.__timelines` using the composition id.
- GSAP timelines must be paused.
- Use absolute timing positions in GSAP.
- Do not call `video.play()`, `video.pause()`, `audio.play()`, or set `currentTime` in scripts.
- Do not animate `width`, `height`, `top`, or `left` directly on video elements.
- If a video needs to move or resize, wrap it in a div and animate the wrapper.
- Extend timeline duration explicitly if needed.
- Run lint before final render.

## Required Validation

After generating or editing a HyperFrame composition:

1. Run `npx hyperframes lint`.
2. Run `npx hyperframes preview` or `npx hyperframes render`.
3. Capture snapshots at `0%`, `25%`, `50%`, `75%`, and `100%`.
4. Visually inspect snapshots.
5. Fix layout and animation issues before final output.

If the exact HyperFrames CLI is unavailable, record the missing tool as a blocker for `renderer: hyperframe` and either install/configure it if allowed, or downgrade the shot. Do not mark the shot complete without equivalent lint/render/snapshot validation.

Snapshot QA must check:

- Text overflow.
- Unreadable small text.
- Elements outside safe area.
- Elements overlapping.
- Inconsistent spacing.
- Crowded layout.
- Animation ending in wrong state.
- Card or chart clipped by screen boundary.
- Wrong aspect ratio.
- Too many visual elements.
- Color mismatch with `DESIGN.md` or design tokens.
- Looks like messy PPT.
- Looks like random webpage.

## Auto-Fix Loop

If a snapshot shows a problem, revise and re-render automatically when feasible:

- Overflow: reduce content, shorten text, increase card size, or split the shot.
- Tiny text: increase type scale, remove minor labels, or change layout.
- Crowding: reduce items to `3-5`, increase gaps, or downgrade.
- Overlap: change grid, safe-area bounds, or animation final states.
- Outside safe area: move or scale the whole composition inside `72/160/180px` safe margins.
- Wrong end state: extend or correct GSAP timeline positions and final values.
- Color mismatch: normalize tokens to `DESIGN.md` or the shot's color plan.
- Messy PPT/random webpage look: simplify to one main idea, one main visual structure, and restrained motion.

Only mark a HyperFrame shot as `complete` when lint/render/snapshots pass visual QA.

## Completion Record

Save a per-shot polish record in `work/plan/hyperframe_polish_guard.json`:

```json
{
  "shot_id": "",
  "triggered": true,
  "design_plan_path": "",
  "lint_command": "npx hyperframes lint",
  "lint_status": "passed | failed | unavailable",
  "preview_or_render_command": "npx hyperframes preview",
  "render_status": "passed | failed | unavailable",
  "snapshot_paths": {
    "0": "",
    "25": "",
    "50": "",
    "75": "",
    "100": ""
  },
  "visual_qa_status": "passed | failed | downgraded",
  "fixes_applied": [],
  "final_status": "complete | downgraded | blocked"
}
```
