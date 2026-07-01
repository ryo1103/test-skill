# Asset Sourcing Workflow

Use this reference when a short video needs enough B-roll, screenshots, screen recordings, logos, or reusable visual assets. The goal is to keep the edit moving quickly between talking head and distinct footage while reserving motion graphics for emphasis.

## Core Principle

For a 1-2 minute knowledge, explainer, or news commentary video:

- Target at least 20 extra distinct visual sources beyond the oral/talking-head video.
- When the user asks for video素材, target downloadable video sources first. Count video footage separately from still images, screenshots, generated graphics, and card renders.
- B-roll / related footage / screen recordings / image motion should normally carry `50%-70%` of the final runtime. Full-screen digital human is short, and HyperFrames are only highlights.
- Use B-roll as the default visual carrier for ordinary explanation, industry background, examples, products, tools, company context, technology context, and market context.
- Count only different underlying footage, screenshots, lawful images, or authorized screen recordings. A different crop, overlay, mask, pan, rotation, generated variant, or animation on the same source is not a new asset.
- For final timeline use, `source_url`, `direct_download_url`, provider asset id, original file page, and cached source file are uniqueness keys. If two timeline entries share any of these keys, they are duplicate B-roll even when exported to different local files.
- Source uniqueness is mandatory but not sufficient. The final edit must also avoid source playback replay: do not loop short clips, restart a clip from `0s`, jump back to an earlier timestamp, or play the same source in multiple timeline ranges to pad runtime.
- Treat talking head and B-roll as the base rhythm of the video. Motion graphics, cards, and HyperFrames are highlights used when the script needs emphasis.
- If there are not enough distinct video assets, stop before final rendering and source more material instead of filling the edit with still images, generated diagrams, or subtitle-like text cards.
- If a subtitle-driven timeline requires more B-roll cuts than there are unique source keys, source more video or shorten B-roll coverage. Do not pad a cue-level edit by reusing the same clip with a different trim/crop.
- Do not use HyperFrames as a fallback for missing B-roll. First try fallback B-roll keywords, official screenshots, lawful image motion, and public/authorized screen recording through the required source order. If those searches do not yield usable assets, stop instead of generating filler.
- Search and select video素材 at the shot level. Each B-roll shot should have keywords derived from its exact script fragment, not only the whole-video topic. The selected clip must visibly relate to the spoken line.
- If source search returns more good clips than the runtime needs, choose the most relevant, clearest, and easiest-to-cut clips; discard surplus weaker clips instead of forcing them into the edit.
- Still images are fallback visuals, not fake video layers. Do not stack multiple still images into foreground/background layers, and do not paste still images on top of video footage. If a still is the most relevant source, use it as one full-screen image shot with restrained editorial motion and record why video was not used.

## Mandatory Asset Gate

After reading the full script and extracting shot-level keywords:

1. Check local project assets for each B-roll, image-motion, screen-recording, logo, and data/source shot.
2. If a required local asset is missing, search online in the source priority order below and attempt lawful direct download, provider/API download, official media-kit download, permissible image download, or authorized screen recording.
3. Save search terms, provider attempts, blocked reasons, source URLs, licenses/terms notes, local paths, and selected assets in `asset_search_plan.json`, `video_source_audit.csv`, and `asset_manifest.json`.
4. If enough lawful, relevant assets cannot be acquired, stop at the sourcing stage and return the shortage report. Do not render a final video.
5. Before rendering, run a source uniqueness audit over the planned timeline. Reject repeated `source_url`, `direct_download_url`, provider id, original file page, or cached source file unless the user explicitly approves reuse.
6. Before final delivery, run a source playback audit from the edit manifest and render commands. Reject looped clips, source restarts, backward seeks, repeated source ranges, or any output duration that exceeds the selected non-looped source trim unless they are approved still-image fallback shots with documented source and reason.
7. Never satisfy missing B-roll with HyperFrames, generated bitmap assets, generated diagrams, placeholder cards, text-only motion, reused crops of the same source, looped clips, source replays, or playback filler. Generated assets may be used only with explicit user approval for non-B-roll design elements and must not count toward the B-roll/source target.

Only after this gate passes should the edit compute the B-roll/digital-human/animation ratio and proceed to rendering.

For any shot marked `broll_needed: true`, the local check must explicitly inspect:

- `assets/raw/video`
- `assets/selected/by_shot`
- `assets/selected/by_theme`
- `assets/raw/screen_recording`
- `assets/metadata/asset_manifest.json`
- `assets_library/asset_index.json`

If no suitable local asset exists, Codex must:

1. Generate shot-level search keywords from the exact script fragment.
2. Search related-news and official/event sources first.
3. Search official media kits, IR pages, product pages, public datasets, and public-domain archives.
4. Search downloadable video providers and open video sources.
5. Try lawful download or authorized screen recording.
6. Record every query, result, blocked reason, selected asset, source URL, and license note.
7. Use still images only if the required video search failed but a lawful relevant image exists.
8. Stop if the asset shortage remains.

Do not continue to final render by substituting HyperFrame, generated diagrams, generated bitmap assets, text-only cards, placeholder motion, repeated old B-roll, looped short clips, or still-image stacks.

## API Key Configuration

Provider API keys must be configured outside source code.

Preferred locations, in order:

1. Environment variables in the shell/session that runs the downloader, such as `PEXELS_API_KEY` or `PIXABAY_API_KEY`.
2. A project-root `.env` file beside the script/oral video, such as:

   ```text
   PEXELS_API_KEY=your_pexels_key_here
   PIXABAY_API_KEY=your_pixabay_key_here
   ```

3. A project-root `.env.example` with placeholder names only, for handoff.

Downloader scripts should load process environment first, then project `.env`. Never hardcode keys in scripts, manifests, source files, edit packages, or final user-facing reports.

When an API source is useful or required but its key is missing:

1. Create or update a project-root `.env.example` with the needed placeholder names, such as:

   ```text
   PEXELS_API_KEY=
   PIXABAY_API_KEY=
   ```

2. Tell the user which provider key is missing and ask them to create `.env` from `.env.example`.
3. Stop before running that API provider only. Do not silently skip it on the first pass, but do not stop the entire sourcing stage while non-API public pages, visible direct downloads, official/media-kit sources, Wikimedia/Openverse-style sources, or authorized screen recordings remain available.
4. If the user says they do not have the key or explicitly asks to continue without it, mark that provider attempt as `needs_api_key` in `video_source_audit.csv` or `asset_search_plan.json`, then continue searching the remaining lawful paths.
5. Ask the user again only when the missing-key API provider is the only remaining lawful route for enough relevant素材, or when a screen recording requires explicit user authorization.
6. Do not claim API search/download was completed when the key was missing. If non-API continuation still cannot acquire enough assets, stop at the sourcing gate with a shortage report and include the attempted fallback paths.

## Script-To-Asset Analysis

Read the full script before searching. Segment by meaning, then label each segment with one primary information type:

- `concept_explanation`
- `case_example`
- `industry_context`
- `data_change`
- `comparison`
- `process`
- `cause_effect`
- `trend`
- `conclusion`

Do not mechanically search every noun. Extract only keywords that can become visible footage, screenshots, or data visuals.

## News-First Sourcing

After reading the script, search for related news and official event materials before generic stock search.

Use script facts to build searches:

- Named entities: companies, products, systems, people, institutions, reports.
- Dates and places: publication date, launch event, conference, country/city.
- Claims and numbers: rankings, benchmarks, funding, policy changes, accidents, releases.
- Chinese and English terms when the event is international.

Create `work/plan/news_source_plan.json` before downloading generic assets. Record:

```json
{
  "title": "",
  "publisher": "",
  "url": "",
  "published_at": "",
  "relevance_note": "",
  "video_available": true,
  "download_status": "downloaded | direct_download_available | api_available | needs_permission | screen_record_possible | reference_only | cannot_download",
  "license_or_terms_note": "",
  "local_path": "",
  "matched_shots": []
}
```

Download strategy:

1. Prefer official downloadable clips: government/organization event video, company media kit, press-room B-roll, conference recordings, public-domain archives.
2. Use provider APIs or visible download buttons when terms allow reuse/download.
3. Use screen recording only when a relevant public/authorized playable video, product UI, data dashboard, or report interface cannot be downloaded through a lawful direct/API/media-kit route. Document the exact page, crop, playback/cursor behavior, and duration.
4. Do not bypass login, paywalls, DRM, robots policy, download restrictions, or platform terms. Do not rip news-site or video-platform clips when downloading is prohibited. Mark those as `reference_only` or `cannot_download`.
5. If related-news video cannot be downloaded lawfully, use it for factual reference and replace visuals with official/permissive stock footage that matches the script.

Do not silently replace related-news footage with unrelated cinematic stock. State the gap in the plan and sources file.

## Keyword Types

For each shot, extract these keyword categories.

### A. Direct Visual Keywords

Use concrete visible objects or places:

```text
chip, data center, server rack, AI model, Nvidia GPU, factory, office worker, stock market, mobile app, dashboard
```

### B. Action / Scene Keywords

Use filmable actions or scenes:

```text
engineer typing, team meeting, trading screen, AI computing, robot automation, warehouse logistics
```

### C. Visual Proxy Terms For Abstract Concepts

When the script contains abstract concepts, convert them into filmable proxies:

| Abstract idea | Searchable visual proxy |
|---|---|
| 算力增长 | data center, GPU server, server racks, cloud computing |
| 竞争加剧 | business competition, racing, crowded market, multiple companies |
| 成本下降 | falling chart, price decrease, discount tag, production line |
| 效率提升 | automation workflow, robot arm, fast production line, dashboard improvement |
| 风险累积 | warning sign, red alert, system error, risk dashboard |
| 市场分化 | split market, diverging chart, two groups, comparison dashboard |
| 流程变化 | workflow, process diagram, automation pipeline |

### D. Brand / Entity Assets

When the script mentions a company, product, website, app, paper, report, or news page, prioritize:

- Official website screenshots.
- Official press kit / media kit.
- Public product UI recordings.
- Logo assets from official media resources.
- Public launch event or official video clips where use is allowed.

Record `source_url`, `provider`, and `license_note`. Do not download or use assets with obvious infringement risk, strong watermarks, paid-stock restrictions, DRM protection, login bypass, or paywall bypass.

### E. Data Display Assets

When the script contains key numbers, growth rates, rankings, time changes, or comparisons, do not only search for B-roll. Mark:

```json
"data_visual_needed": true
```

Recommend one of:

- `KPI card`
- `delta card`
- `line chart`
- `bar ranking`
- `timeline`
- `comparison matrix`
- `dashboard card`

These can later be generated by Remotion, HyperFrames, or a PPT-style module only after the asset gate passes. They must not replace missing B-roll or count as sourced footage.

## Search Terms Per Shot

For every shot, output:

```json
{
  "primary_terms": ["AI data center", "server rack", "GPU chip"],
  "fallback_terms": ["computer chip", "semiconductor", "circuit board"],
  "video_terms": ["server rack video", "data center footage"],
  "news_terms": ["TOP500 June 2026 supercomputer video"],
  "screen_recording_targets": [
    {
      "target": "official playable video or product/data interface",
      "url": "https://example.com",
      "recording_plan": "Record the relevant playable clip or interface area for 6-8 seconds after direct download/API/media-kit attempts fail."
    }
  ]
}
```

Rules:

- `primary_terms`: 1-3 English phrases, each 1-4 words, tightly matched to the script. English works better for Pexels, Pixabay, Coverr, and similar stock sources.
- `fallback_terms`: broader industry scenes or visual proxies when primary terms fail.
- `video_terms`: search/download terms for provider video APIs and stock video sites.
- `news_terms`: event-specific terms for related news, official releases, conference clips, and public-domain/current-affairs video.
- `screen_recording_targets`: public/authorized playable videos, product UIs, official dashboards, reports, tools, or pages the user has permission to access. Do not use generic webpage scrolling as B-roll filler.

Screen recording must not bypass login, paywalls, DRM, paid-download restrictions, or other access controls. Close or crop out unrelated personal information before recording. Record page scrolling only when the page interaction itself is the story or the user explicitly requests a page walkthrough.

## Source Priority

Search in this order.

1. **Local Project Assets**
   - Check `assets/raw`, `assets/processed`, `assets/selected`, and previous project outputs.
   - Reuse downloaded assets that are relevant and high quality.
   - Avoid duplicate downloads of the same source.

2. **Related News / Event Sources**
   - Search official event pages, press rooms, public conference pages, government/organization releases, public-domain archives, and news articles with video.
   - Download only when there is a lawful direct download, permissive API/source, official B-roll/media kit, or user-authorized screen recording path.
   - Save related-news candidates, successful downloads, and failed/blocked attempts in `work/plan/news_source_plan.json`.

3. **Free / Commercial-Usable Stock Video Sources**
   - Pexels
   - Pixabay
   - Coverr
   - Mixkit
   - Videvo
   - Wikimedia Commons
   - Openverse/Flickr/other Creative Commons providers
   - Official press kits / media kits

   Record `source_url`, `provider`, and `license_note`.

4. **Provider Video Source Audit**
   Check every listed provider/source for downloadable video before image fallback. Save the audit in `work/plan/video_source_audit.csv` or inside each shot in `asset_search_plan.json`.

   Required audit fields:

   ```csv
   provider,query,video_found,downloadable,api_or_method,selected_asset_key,source_url,license_or_terms_note,blocked_reason
   ```

   Provider notes:

   - **Pexels**: Use the official Videos API when `PEXELS_API_KEY` is available. Read from environment variable `PEXELS_API_KEY` or the project-root `.env`; send it in the `Authorization` header. Use `/v1/videos/search`; record the video page URL, selected file URL, and Pexels license note. Do not hardcode API keys in scripts. If the key is missing, create/update `.env.example`, pause only the Pexels API attempt, record `download_status: needs_api_key`, and keep searching other lawful providers/sources unless Pexels is the only remaining lawful path.
   - **Pixabay**: Use the Pixabay Videos API when `PIXABAY_API_KEY` is available from environment or project `.env`; otherwise pause only the Pixabay API attempt, record `download_status: needs_api_key`, and keep searching manual/public/direct/official/open-license sources. Record `pageURL`, user, tags, duration, and Pixabay license note when the API is used.
   - **Coverr**: Check for directly downloadable stock videos and current license/terms on the clip page. Record the clip page URL. If the site blocks automated download or requires interaction, mark the attempt and use another source.
   - **Mixkit**: Check Mixkit stock video pages for downloadable clips and license terms. Record the clip page URL and Mixkit license note.
   - **Videvo**: Check the exact clip license. Use only clips with free/permissive terms suitable for the project; some clips require attribution or have restrictions. Record the clip page URL and license name.
   - **Wikimedia Commons**: Use a descriptive User-Agent, respect robot policy, prefer file pages and available transcodes for video (`webm`, `ogv`, `mp4` when present), and record the Commons file page and license. Do not hammer original downloads; use appropriate transcodes/thumbnails where possible.
   - **Openverse/Flickr/Creative Commons**: Filter out NC/ND when commercial/editable reuse is needed. Use only assets with clear source pages and license URLs.
   - **Official media kits / press rooms**: Prefer official B-roll, launch footage, product videos, conference clips, and downloadable media assets. Record terms and download method.

5. **Images**
   - Use images only after video and official/source searches have been attempted and recorded.
   - Suitable for single full-screen image motion, sourced data-card backgrounds, PPT-style explanation frames, and sourced visual pages.
   - Do not create a fake-depth collage from multiple stills, and do not overlay still images on top of unrelated video.
   - If using several images in one section, cut them as a sequence or montage with clear transitions rather than stacking them into one composite.

6. **Screen Recording**
   - Use when the script involves a playable public/authorized video, product UI, data page, dashboard, report, company page, news page, or tool interface and a lawful direct download/API/media-kit route is unavailable.
   - Prefer recording the actual video player or relevant UI state. Avoid webpage-scroll recordings as substitute B-roll.
   - Provide a recording script: page URL, exact playable clip or interface section, cursor behavior, playback behavior, crop area, and duration.

7. **Generated Assets**
   - Generated assets are outside the required B-roll sourcing ladder and require explicit user approval.
   - Use generated bitmap assets only for abstract covers, optional design backgrounds, or non-B-roll data-card styling after the asset gate passes.
   - Do not use generated stills, generated diagrams, text cards, or HyperFrames to satisfy a requested video素材 count or to continue when online sourcing failed.

## Screening Before Download / Save

Score every candidate before saving:

```json
{
  "relevance_score": 0,
  "visual_clarity_score": 0,
  "editability_score": 0,
  "copyright_risk": "low | medium | high",
  "usage_type": "broll | background | data_card_bg | screenshot | screen_recording | logo | reference_only",
  "aspect_fit": "portrait_9_16 | landscape_16_9 | square | needs_crop",
  "minimum_duration": 4
}
```

Reject or avoid:

- Low resolution.
- Strong watermark.
- Overly decorative or distracting footage.
- Off-topic footage.
- Footage that is too dark for subtitles/cards.
- Severe built-in captions that will conflict with the edit.
- High copyright risk.
- Still-image composites that fake motion by stacking unrelated images.
- Video clips whose visible subject does not match the shot's script keywords, even if they look cinematic.

Video assets should usually be at least 4 seconds unless used as a fast cutaway.

## Selecting Final Assets For The Edit

After downloading, do not automatically use every asset. For each shot:

1. Match candidates against the exact script fragment and `broll_keywords`.
2. Prefer real video over stills, official/event footage over generic stock, and clear subject matter over atmosphere.
3. Select the best 1 clip for a `2-4s` shot, or 2-4 clips for a longer ordinary B-roll section.
4. Discard surplus clips when the section is already visually covered.
5. Mark weak but necessary replacements as `placeholder` or `fallback_image`.
6. Keep `source_segments` in the edit manifest tied to the selected shot, so manual recutting can replace only the weak ranges.
7. If a required shot has no selected lawful asset after all source-priority searches, keep it marked `needs_sourcing: true` and stop before rendering. Do not select a generated substitute.

For subtitle-driven edits:

1. Assign assets at cue or cue-pair granularity, not only at broad shot granularity.
2. Use each underlying B-roll source key once in the main timeline.
3. If a long script section needs several cuts, choose several distinct source keys; do not loop a single clip or replay it from the beginning.
4. Write `work/plan/source_uniqueness_audit.json` before rendering:

   ```json
   {
     "status": "passed | failed",
     "used_source_keys": [],
     "duplicates": [],
     "rule": "No repeated source_url, direct_download_url, provider id, file page, or cached source file in final B-roll timeline."
   }
   ```
5. Write `work/plan/source_playback_audit.json` before final delivery:

   ```json
   {
     "status": "passed | failed",
     "source_playback_ranges": [],
     "restarted_sources": [],
     "backward_seek_sources": [],
     "looped_sources": [],
     "multi_range_sources": [],
     "duration_exceeds_trim": [],
     "ffmpeg_stream_loop_uses": [],
     "approved_still_fallbacks": [],
     "rule": "A video source may be trimmed shorter once, but must not be looped, restarted, replayed from an earlier timestamp, or used in multiple timeline ranges."
   }
   ```

## Video Download Manifest

For downloaded footage, include these fields in `assets/metadata/asset_manifest.json`:

```json
{
  "asset_id": "",
  "file_path": "assets/raw/video/provider/file.mp4",
  "shot_id": "",
  "theme": "",
  "source_url": "",
  "direct_download_url": "",
  "provider": "pexels | pixabay | coverr | mixkit | videvo | wikimedia | official | screen_recording",
  "license_note": "",
  "download_method": "api | direct_download | official_media_kit | screen_recording | manual",
  "original_keyword": "",
  "matched_script_line": "",
  "usage_type": "broll",
  "duration": 0,
  "resolution": "",
  "fps": "",
  "has_audio": false,
  "aspect_fit": "portrait_9_16 | landscape_16_9 | square | needs_crop",
  "relevance_score": 0,
  "visual_clarity_score": 0,
  "editability_score": 0,
  "copyright_risk": "low | medium | high",
  "download_status": "downloaded",
  "created_at": ""
}
```

Run `ffmpeg -v error -i <asset> -f null -` on downloaded video assets before selecting them.

## File Naming

Save assets with this structure:

```text
assets/
  raw/
    video/
    image/
    screenshot/
    screen_recording/
    logo/
  selected/
    by_shot/
    by_theme/
  metadata/
    asset_manifest.json
```

Filename format:

```text
shot_{shot_id}__{theme}__{provider}__{keyword}__{hash}.mp4
shot_{shot_id}__{theme}__{provider}__{keyword}__{hash}.jpg
shot_{shot_id}__{theme}__screen_recording__{target}.mp4
```

Examples:

```text
shot_03__ai_compute__pexels__server_rack__a82f1.mp4
shot_05__nvidia__official_site__screenshot__gpu_page.png
shot_07__market_growth__screen_recording__statista_chart.mp4
```

## Asset Manifest

Maintain `assets/metadata/asset_manifest.json`:

```json
{
  "assets": [
    {
      "asset_id": "shot_03__ai_compute__pexels__server_rack__a82f1",
      "file_path": "assets/raw/video/shot_03__ai_compute__pexels__server_rack__a82f1.mp4",
      "shot_id": "03",
      "theme": "ai_compute",
      "source_url": "https://...",
      "provider": "pexels",
      "license_note": "Pexels license; verify current terms at source URL",
      "original_keyword": "server rack",
      "matched_script_line": "算力增长...",
      "usage_type": "broll",
      "aspect_fit": "landscape_16_9",
      "duration": 6.4,
      "relevance_score": 88,
      "visual_clarity_score": 92,
      "editability_score": 86,
      "copyright_risk": "low",
      "reuse_tags": ["AI", "data_center", "server"],
      "created_at": "2026-06-29T18:00:00+08:00"
    }
  ]
}
```

## Project-End Classification

After the project, classify reusable assets into:

```text
assets_library/
  AI/
    chips/
    data_centers/
    robots/
    dashboards/
  Finance/
    stock_market/
    charts/
    trading_screens/
  Business/
    meetings/
    office/
    factories/
    logistics/
  Technology/
    cloud/
    software_ui/
    cybersecurity/
  Brands/
    nvidia/
    openai/
    google/
    microsoft/
  Generic/
    abstract_background/
    city/
    people/
    warning/
    success/
  ScreenRecordings/
    websites/
    tools/
    dashboards/
  DataVisuals/
    kpi_cards/
    timelines/
    comparison/
    flowcharts/
```

Maintain global `assets_library/asset_index.json`:

```json
{
  "assets": [
    {
      "asset_id": "",
      "file_path": "",
      "theme": "",
      "sub_theme": "",
      "source_url": "",
      "provider": "",
      "license_note": "",
      "original_keyword": "",
      "matched_script_line": "",
      "used_in_project": "",
      "shot_id": "",
      "relevance_score": 0,
      "copyright_risk": "low",
      "reuse_tags": [],
      "created_at": ""
    }
  ]
}
```

## Gate Before Rendering

Before final video rendering, verify:

- Every B-roll shot has at least one selected asset.
- Every selected asset exists on disk and is traceable to local user-provided media, lawful download, or authorized screen recording.
- Every configured/listed source has been checked for downloadable video or has an explicit `blocked_reason`.
- Related-news/event searches have been completed and saved to `news_source_plan.json`.
- Long ordinary B-roll shots have 2-4 distinct source shots.
- The total distinct extra visual sources meets the project target, normally 20-25 for a 1-2 minute video.
- When the user asked for video素材, the distinct extra video-footage count meets the target or the shortage is explicitly approved before rendering; without approval, stop.
- B-roll / related footage / screen recordings / image motion can carry the planned `50%-70%` runtime in `visual_ratio_audit.json`, computed after selected assets are acquired.
- Talking head and B-roll are interleaved in the timeline.
- Motion graphics are only used to clarify key ideas, not as filler for missing footage.
- Missing footage has not been silently replaced by HyperFrames, generated bitmap assets, generated diagrams, placeholder cards, text-only motion, or repeated crops of the same source.
- `source_uniqueness_audit.json` passes with no repeated B-roll source keys.
- `source_playback_audit.json` passes with no looped clip, source restart, backward seek, repeated source range, or output duration longer than the selected trim outside approved still fallbacks.
