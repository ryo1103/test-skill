# Visual Language Map

Use this reference when assigning a visual expression to each script segment.

## Default Visual Assignment

Default style positioning:

```text
B-roll 主视觉 + 短时全屏数字人口播 + 少量专业 HyperFrame 动效
```

For every script segment, choose visuals in this order:

```text
broll_fullscreen
-> broll_with_overlay
-> talking_head_fullscreen
-> data_card_light
-> hyperframe_logic / hyperframe_data
```

Do not jump straight to HyperFrame. First ask whether B-roll, B-roll plus a light overlay, a short full-screen digital-human beat, a light data card, or a screen recording can communicate the idea clearly.

Asset availability gates visual assignment: after keywords are extracted, local assets must be checked first; missing B-roll requires online sourcing through `asset-sourcing.md`. If no lawful, relevant asset can be acquired, stop instead of assigning a HyperFrame, generated visual, or text-card substitute.

Target mix for a 1-2 minute video:

- Full-screen digital human: `15%-28%`.
- B-roll / related footage / screen recording / image motion: `50%-70%`.
- HyperFrame: `8%-18%`.

Default subtitle/title style for Chinese vertical shorts:

```text
large_short_video_caption + persistent_topic_banner
```

If the user provides no style prompt, use this default without asking. If the user says `字幕太小`, `轻松好看`, `参考这个图`, or `任何帧都能知道视频讲什么`, keep or switch to this style and run layout preflight plus probe render before final.

## Scene Types

Use only these `scene_type` values in `shot_plan.json`:

| scene_type | Use for | Avoid |
|---|---|---|
| `talking_head_fullscreen` | Opening brand anchor, core question, section switch, strong judgment, trust beat, conclusion | Ordinary explanation, long narration, PIP, split screen, corner host |
| `broll_fullscreen` | Default main picture for background, examples, industries, products, tools, companies, scenes, abstract visual proxies | Repeating one weak asset for long spans |
| `broll_with_overlay` | Keywords, simple labels, names, products, short conclusions, callouts, small data, arrows, spotlight, local zoom | Repeating the subtitle in a large title box; placing still images over video as fake B-roll |
| `data_card_light` | One key number, one core metric, short conclusion, simple delta | Every number, full logic explanations |
| `hyperframe_logic` | Key comparison, process, timeline, cause-effect chain, system structure | Ordinary concepts, emotional transitions, generic background |
| `hyperframe_data` | Core data, trend, ranking, complex metric dashboard critical to the argument | Incidental numbers |
| `screen_recording` | Public/authorized website, product, report, dashboard, tool, search process | Login/paywall/DRM bypass |
| `conclusion_card` | Final thesis or concise takeaway | Decorative ending with too much motion |

## Mapping Table

| Information type | Preferred visual expression | Use when | Avoid |
|---|---|---|---|
| Key number | subtitle highlight, `data_card_light`; `hyperframe_data` only for argument-critical data | Revenue, margin, growth rate, count, percentage | HyperFrame for every number |
| Comparison | B-roll + labels; `hyperframe_logic` for key before/after, A/B, matrix | "before/now", company A vs B, old logic vs new logic | Single card with two unrelated bullets |
| Time change | B-roll + date labels; timeline/line chart only for key trend | Years, cycles, trend, "by 2027/2028", turning point | Static B-roll without date labels |
| Process | B-roll + arrows/callouts; HyperFrame process only for key mechanism | Procurement flow, production ramp, supply chain steps | Long paragraph card |
| Cause-effect | B-roll + simple chain; HyperFrame chain for the main causal argument | "because", "means", "leads to", risk transfer | Isolated decorative icons |
| Condition / decision | light decision label or decision tree if essential | "if... then...", "only when..." | Linear timeline |
| System structure | system diagram only when stock footage cannot explain the relationship | AI, memory, GPU, customers, capacity pool relationships | Decorative stock footage only |
| Resource pressure | B-roll + KPI/delta; pressure chart for core scarcity logic | scarce capacity, demand competing for supply | Generic warning icon |
| Risk / judgment | short full-screen digital human or key takeaway card | "real risk is...", "not X but Y" | Many small data labels |
| Metaphor | B-roll visual proxy or simple analogy diagram | engine/fuel, brain/memory, pipe/water | Literal unrelated stock footage |
| Conclusion | short full-screen digital human plus conclusion card if needed | Final claim or thesis restatement | Weak B-roll ending |

## Oral Video Use

Use full-screen digital-human/oral video for:

- Major turning point: "但这一次不一样"
- Question transition: "那问题来了..."
- A short credibility or emotional beat
- A pause before a new chapter
- Opening brand presence, core question, strong judgment, and conclusion

Avoid oral video for:

- Explaining a process that can be diagrammed.
- Showing comparisons or timelines.
- Delivering dense numbers without visual reinforcement.
- Ordinary explanation that can be carried by B-roll.
- Any picture-in-picture, split-screen, half-screen, corner-window, or transparent-overlay host layout.

When the digital human appears visually, it must be full screen. Each exposure should usually be `1.5-4s`; except opening/ending, avoid more than `5s` continuously, and never exceed `15s` continuous full-screen digital-human narration.

## B-Roll And Light Overlay

Use B-roll for most:

- Industry background.
- Case examples.
- Tools and product interfaces.
- Company or market context.
- Abstract concepts that can be converted into visual proxies.
- Scene-based explanation that keeps the video from feeling heavy.

Use light overlays for:

- Keywords.
- Simple data.
- Concept labels.
- Company/product/person names.
- Short conclusions.
- Simple arrows/callouts.
- Local zoom, darkened background, or spotlight.

Do not duplicate subtitles in a second title box. If the bottom subtitle already says the sentence, upper/middle screen text should add different visual information, such as a label, source, metric, or callout.

AE/PPT-style dynamic overlays:

- During script-to-visual planning, actively look for process, comparison, timeline, cause-effect, KPI/data, system-structure, and decision-logic segments that would benefit from staged AE/HyperFrame motion.
- Treat these effects as B-roll overlay layers by default: transparent graphics, process nodes, arrows, labels, chart widgets, highlight masks, or short animated callouts sit above selected B-roll or a video-derived background.
- Do not use AE/HyperFrame overlays to replace missing B-roll or to fill time. The B-roll base must be selected and sourced first.
- Use standalone full-screen motion cards only for key logic/data moments that cannot be clearly explained as an overlay; record the reason and keep the card count low.
- If the overlay choice is uncertain or may feel like a PPT page, produce a simple storyboard option for the user before rendering: spoken phrase, base B-roll, overlay idea, animation stages, and concern.

For still images:

- Use them only when they are more relevant than available video or when the required search process found no good video but did find a lawful, relevant image.
- Use a single full-screen image shot, restrained Ken Burns motion, blur-to-focus, crop reveal, or a short image sequence.
- Do not stack multiple still images as foreground/background layers.
- Do not overlay still images on top of video footage unless the image itself is a necessary chart/logo/document callout and not a B-roll substitute.

## HyperFrame Gate

Compute `hyperframe_score` before assigning `hyperframe_logic` or `hyperframe_data`:

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

Only use HyperFrame when `hyperframe_score >= 3`, and record `hyperframe_reason`, `visual_pattern`, and `why_simple_broll_is_not_enough`.

Use HyperFrame for:

- Key comparison: side-by-side, before/after, comparison matrix.
- Key process: process flow, pipeline, step-by-step structure.
- Time change: timeline, trend line, inflection point.
- Causality: cause-effect chain or risk transmission.
- Core data: KPI card, dashboard, ranking, trend.
- System/professional structure: architecture map, ecosystem map, business chain.

When HyperFrame is selected, aim for a refined tech/business news look: dark relevant footage or video-derived background, deep navy translucent panels, mint/cyan and magenta accents, large readable metrics, neon line/node systems, subtle glow/blur/parallax, and complete reveal-build-hold-settle motion. Avoid rough grid cards, flat rectangles, crowded debug-like diagrams, and unrelated image collage.

Do not use HyperFrame for:

- Replacing missing B-roll or continuing after asset sourcing failed.
- Ordinary background introduction.
- General concept explanation that B-roll can carry.
- Emotional connection lines like "但问题也来了".
- Generic opinions such as "这会提高效率" without data, process, comparison, or causal chain.
- Transition lines like "接下来我们看第二点".
- Making the whole video feel like a PPT animation collection.

If consecutive shots all become HyperFrames, keep only the most important one and downgrade the rest to `broll_fullscreen`, `broll_with_overlay`, `data_card_light`, `screen_recording`, or `talking_head_fullscreen`.

## Data Visual Rules

When a number appears, first judge its importance:

- Ordinary number: subtitle highlight, keyword overlay, or small data label.
- Important single metric: `data_card_light`.
- Core judgment data, trend, ranking, or complex indicator set: `hyperframe_data`.

Data visual patterns include KPI card, delta card, metric dashboard, line chart, bar ranking, comparison matrix, timeline, progress bar, and risk meter. Not every number needs a data card, and not every data card needs HyperFrame.

## Large Short-Video Caption Style

Use `large_short_video_caption` for ordinary Chinese Douyin/WeChat Channels/Shorts oral-video edits unless the user explicitly requests a different subtitle style.

Default visual rules for `1080x1920`:

- Normal bottom subtitle: `68-82px`, default `76px`.
- Emphasis subtitle: `86-96px`, default `88px`.
- Font weight: bold enough for mobile, usually `800`.
- Line count: maximum two lines.
- Soft line length: roughly `14` Chinese characters per line.
- Bottom margin: keep the subtitle above the platform/player danger zone, default around `240px`.
- Outline/shadow: strong enough to read over bright B-roll, default outline around `6px` plus subtle shadow.
- Keyword colors: one cyan and one mint/secondary accent are enough.

Long subtitle policy:

- Do not shrink below `font_size_min_px` to fit long text.
- Do not use three-line paragraph subtitles.
- Split long cues semantically by sentence, clause, breath, pause, contrast, named entity, number, technical term, or cause-effect boundary.
- Keep each cue as a complete spoken phrase or meaningful clause.
- Audio timing is mandatory for final render; a subtitle cannot start before the spoken phrase or linger after it.

## Persistent Topic Banner

Use a persistent topic banner when the user wants any frame to communicate what the video is about. It is recommended by default for Chinese news, finance, business, technology, and knowledge-explainer shorts.

Rules:

- The banner is a topic anchor / visual thesis, not a second subtitle layer.
- It must answer the video topic, conflict, and viewing hook.
- It should normally remain visible through the full video.
- It must not duplicate the current bottom subtitle or mirror subtitles sentence by sentence.
- Main title should usually be `8-16` Chinese characters; subtitle should usually be `10-22` Chinese characters.
- Place it in the upper safe area. For talking-head shots, use compact mode if the normal banner would cover the face core.
- Use strong contrast: dark translucent background, mint/cyan title, white subtitle, glow/outline if needed.
- Keep it visually stable. Do not change it every sentence; section banners are only for clear chapters.
- Include the banner in B-roll/overlay/HyperFrame collision checks. Cards, charts, labels, and HyperFrame panels must not collide with it or with bottom subtitles.

## Subtitle Keyword Highlighting

Highlight:

- Numbers and dates: `400亿`, `84.9%`, `2027`, `2028`
- Named entities: company names, product names, people, industries
- Logical pivots: `但`, `真正关键`, `不是...而是...`
- Risk and conclusion words: `没有`, `生存问题`, `基础设施`, `商业模式`

Do not highlight every noun. The highlighted text should guide attention, not decorate the subtitle.

Implementation rules:

- Use `.ass` for the final preview when keyword colors are needed; keep `.srt` as the plain editable subtitle handoff.
- Keep highlighting inside the bottom subtitle layer only.
- Generate audio-aligned subtitle cue timing before final rendering, and use the same cues to drive visual cut points.
- Segment by spoken meaning first, readability second. Each cue should be a complete spoken phrase or meaningful clause; do not split mechanically at a fixed character count such as 12 Chinese characters.
- Keep cues visually concise, but treat character count as a soft warning. If a complete spoken phrase is slightly longer, use two balanced lines or a slightly longer cue rather than cutting a phrase, number, named entity, technical term, comparison, or cause-effect unit in half.
- Cue timing must follow the audio. Start at the first spoken word and end after the last spoken word, with only small readability padding; do not allocate subtitle time from script length alone for a final render.
- Split technical clauses into multiple cue texts only at natural semantic/audio boundaries instead of shrinking the font or burning three-line paragraph subtitles.
- Do not show the same subtitle text on consecutive visual frames. If the spoken sentence spans several visuals, split it into several semantic cue-level subtitles and highlight the current keyword only.
- Use at most 1-2 accent colors, normally one cyan/mint and one warm/pink/yellow emphasis color.
- Highlight only the exact keyword span, not the whole subtitle line.
- Do not add an upper/middle title box that repeats the highlighted subtitle.
- Verify highlighted subtitles do not collide with cards, source marks, player-safe margins, or HyperFrame labels.
- Verify subtitle sync and phrasing in QC: representative frames should show the phrase currently being spoken, and cue text should not appear before the speaker says it or linger after the phrase has ended.

## Card Density

Use strong cards only for:

- The hook numbers.
- The main thesis.
- Critical mechanisms.
- Time inflection points.
- Final conclusion.

Use light labels or B-roll for:

- Transitional sentences.
- Repetition of already-explained concepts.
- Short setup phrases.
- Ordinary background, common examples, and statements without data/process/comparison/causality.

For a 1-2 minute opinion/explainer short, do not use every available visual mode. Pick the few that carry the argument, typically one or two KPI/data frames, one process/causal frame, one timeline or comparison frame, and one conclusion frame.

## B-Roll Distinctness

When planning dense edits, count a B-roll asset only when the underlying picture is different: a new source clip, shot, lawful image, or authorized screen recording. A generated scene, different crop, rotation, overlay, subtitle, or animation on the same source is not a distinct asset.

For subtitle-driven timelines, enforce source uniqueness at render time:

- one cue or cue-pair should map to one visual event;
- each B-roll visual event should use a different underlying source key;
- repeated `source_url`, `direct_download_url`, provider id, file page, or cached source file is a duplicate even when the local exported filename differs;
- a video source may be cut shorter once, but must not be looped, restarted from the beginning, replayed from an earlier timestamp, or used in multiple timeline ranges;
- if unique assets run out, stop and source more material instead of stretching one clip.

## Motion Card Refinement

When a key comparison/data/system cue requires a motion card:

- Use relevant selected B-roll or a video-derived still as the base layer whenever possible.
- Prefer an overlay on top of B-roll before choosing a full-screen standalone card.
- Darken, blur, vignette, or crop the base footage so graphic text is readable.
- Keep one main idea per card, with `3-5` visible items maximum.
- Animate in stages tied to subtitle cues: setup, enter, build, emphasis, readable hold, and settle.
- Keep card text shorter than the subtitle, and never duplicate the bottom subtitle sentence as a card title.
- Inspect representative frames for text fit, subtitle clearance, and whether the card feels like polished tech/business news rather than a static PPT page.

## Vertical Layout Rules

- Keep primary card content between roughly 450px and 1250px Y for 1080x1920.
- Reserve bottom space for large subtitles. Do not place cards, labels, source text, or HyperFrame panels in the subtitle box.
- Reserve upper safe space for the persistent topic banner when enabled. B-roll labels and HyperFrame titles must fit below or around it, not under it.
- During talking-head shots, use the compact topic-banner position when the normal banner would cover the face core.
- Run layout preflight before final render to verify banner/subtitle/card clearance.
- Keep source text small and short; split into two lines if needed.
- Avoid card nesting. Use one clear panel or unframed full-screen diagram.
- Use high contrast for Chinese text.
- Keep screen text concise enough to read in under 2 seconds.

## PPT Reuse

When possible, design visuals so they can become slides:

- One logic idea per card.
- Clear title, diagram, and conclusion line.
- Avoid motion-only meaning; the static frame must still make sense.
- Export transparent PNG cards for reuse in slides or manual editing.
