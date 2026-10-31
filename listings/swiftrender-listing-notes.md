# SwiftRender - RapidAPI listing notes (prepared)

Status: package complete. Unlike FactBase/DesignBase/ActorBase,
SwiftRender needs NO engine key: the import adapter, the
DriftCheck gate and assembly all run on code + ffmpeg, so the
listing can proceed as soon as the Studio steps are run (create
listing, wire the proxy secret, publish, Spotlight) under the
lane's full-automation authorization. The Replicate adapter ships
parked on the owner's token (decision queue item 11); the listing
copy below describes it as an adapter that activates with the
user's own Replicate token, never as live generation.

## Basics

- API name: SwiftRender
- Base URL: https://swiftrender.onrender.com (confirm the exact
  subdomain in the reliability doc after deploy)
- Category: Artificial Intelligence/Machine Learning (same as
  DriftCheck, FactBase, DesignBase, ActorBase).
- Short description (neutral, no overclaim): "A video production
  pipeline API. It does not speed up any model's rendering; it
  removes the waiting around generation: right-sized generation
  durations computed from your timing map, automatic drift and
  freeze gating the moment a clip lands, corrected-prompt
  re-queueing for failed clips, and automatic assembly of passing
  clips against your audio track with a measured report."
- Overview copy rules: the honesty paragraph from
  docs/spec-swiftrender.md leads. Never "faster generation",
  never "speeds up Seedance" or any model. Speed claims are only
  the pipeline arithmetic, stated with its basis (right-sized
  durations vs a flat 10 s default; 66 s vs 160 s on the owner's
  real 16-line proof job).

## Endpoints (from listings/swiftrender-openapi.json)

- GET /health (no auth at the origin; engine + adapter states)
- POST /jobs (JSON with audio_url, or multipart with audio file)
- GET /jobs/{id} (status, gates, retry queue, assembly report)
- POST /jobs/{id}/clips/{line_id}/import (multipart video)
- POST /jobs/{id}/clips/{line_id}/generate (provider adapter)
- POST /jobs/{id}/assemble
- GET /jobs/{id}/output (the assembled MP4)

## Plans (monthly, PER REQUEST, hard limit)

- BASIC $0 / 100
- PRO $5 / 1,000
- ULTRA $20 / 10,000
- MEGA $60 / 50,000

## Spotlight draft (under 280 characters, no model-speed claim)

"SwiftRender: the pipeline around video generation, minus the
waiting. Right-sized clip durations from your timing map, instant
drift and freeze gating, corrected prompts for failed clips, and
automatic assembly against your track."

(238 characters. Post at launch per the lane rule: every new API
gets a Spotlight; keep it under 280 characters and let the
Spotlight URL carry the full spec doc on GitHub.)
