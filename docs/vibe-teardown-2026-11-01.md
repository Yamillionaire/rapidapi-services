# Vibe.co teardown (2026-11-01)

Reverse engineering of Vibe.co's prompt-to-streaming-TV ad product,
triggered by their Facebook ad ("Your ad from Claude to streaming
TV", "Higgsfield to streaming TV, one prompt") and the user's
direction the same day: reverse engineer it and build an API of the
buildable part. Sources: vibe.co and help.vibe.co pages, Vibe's own
blog guides, a third-party review (dupple.com), and industry CTV
spec guides (Simulmedia, Google Display and Video 360 help). Every
number below is from one of those pages, read 2026-11-01.

## What Vibe sells

Vibe is a self-serve connected TV (CTV) advertising platform aimed
at small and mid-size businesses. The pitch: TV advertising that
works like paid social. You define an audience, supply or generate
a video ad, set a daily budget, and your ad runs full-screen and
non-skippable inside premium streaming apps: Hulu, Tubi, Peacock,
Disney+, Paramount+, Pluto TV, The Roku Channel, Samsung TV Plus
and 500+ channels in total, per their own pages.

The money model, from their help center: no platform fee, no
subscription, no seat fees. Advertisers pay media cost only,
priced per CPM (cost per 1,000 impressions). Typical CPMs are
$15-30 per the help center ($15-35 in their budgeting guide; live
sports and high-demand placements $40-60). Each campaign strategy
needs a minimum budget of $50/day to launch. Billing triggers at
$100 of accumulated spend, then every $500 or every 30 days. There
is no annual contract and no overall minimum commitment.

## The workflow, step by step

1. **Sign up and create a campaign.** No minimum spend, no
   contract; Vibe says an advertiser can be live in the same
   session.
2. **Define the audience.** Geography first: ZIP codes, radius,
   metro, county, state. Then household demographics, interests
   and purchase intent. Advertisers can also upload a CRM list
   (integrations named: Klaviyo, Shopify, HubSpot) and build
   lookalike audiences. Dayparting (time of day) is supported.
3. **Supply the creative, one of two ways.**
   - Upload a finished video ad that meets their specs (below).
     An outside ad server can also serve via a VAST tag.
   - Or generate one in **Vibe Studio** (their AI Creatives tool,
     free regardless of ad spend; see the next section).
4. **Compliance review.** Vibe scans uploads with ACR (automatic
   content recognition) technology; ads are typically reviewed and
   approved within 30 minutes, per their help center.
5. **Set budget and schedule.** $50/day minimum per strategy;
   budgets can be raised or lowered at any time. Vibe spreads
   delivery across the day and handles frequency capping and
   optimization across its supply network.
6. **Measure.** Dashboard reporting on impressions and completed
   views, QR code engagement (spots can carry a QR code viewers
   scan from the TV screen), and pixel-based website attribution.
   Results can be pushed into Google Analytics, Triple Whale or
   Northbeam. Vibe positions holdout-based incrementality as its
   measurement standard in its own guides.

## Vibe Studio and the Claude plus Higgsfield angle

Vibe Studio is the built-in AI ad generator, and it is the piece
their Facebook ad is really selling. Two creative routes converge
on the same campaign builder:

- **Vibe Studio route (inside Vibe).** The advertiser enters a
  website URL or a business name. The AI scans the site and pulls
  brand name, tagline, product images, key copy and color palette.
  In under two minutes (their claim) it assembles a 15 or 30
  second spot: visuals selected or generated, a written and
  recorded voiceover, and background music, formatted to streaming
  TV spec. The advertiser can then edit the headline text, swap
  images, change the voiceover style, and add a QR code. On
  approval the finished creative moves straight into the campaign
  builder with no file transfer or format conversion.
- **Prompt route (outside Vibe, the Facebook ad's framing).**
  "Your ad from Claude to streaming TV" describes the workflow
  creators already run: an LLM (Claude or ChatGPT) writes the ad
  script and breaks it into shots, then writes generation prompts
  for Higgsfield (Higgsfield ships an MCP connector for Claude,
  and public prompt skills teach Claude to write Higgsfield-ready
  prompts), Higgsfield models (Kling, Seedance) render the clips,
  the clips are assembled into a 15 or 30 second spot, and the
  finished file is uploaded to Vibe for placement. Vibe's
  contribution in this route is the last mile: compliant upload,
  targeting, delivery and measurement.

Either way, the product decomposes into four parts: (1) creative
strategy and script, (2) shot-level generation prompts and asset
production, (3) assembly to a delivery spec, and (4) media
placement and measurement. Parts 1 and 2 are pure information
work. Part 3 is file work. Part 4 is a licensed ad network.

## CTV delivery specs (what a finished file must be)

From Vibe's own help center (Video Creative Compliance and Upload
Your Video Ad):

- Aspect ratio 16:9
- Resolution: minimum 1280x720; 1920x1080 recommended
- Length: 5 to 90 seconds (15 and 30 are the standard spots;
  a file even 1 second over 90 is rejected at upload)
- Format: .mp4 only
- File size: 100 MB maximum
- Frame rate: constant; 23.976, 24, 25, 29.97 or 30 fps
- Bit rate: at least 2,500 kbps

Industry common denominator (Simulmedia's 2026 CTV specs guide,
Google DV360 creative guidelines, publisher spec sheets):

- 1920x1080 preferred, H.264 in .mp4 or .mov, 15-30 Mbps video
  bitrate for source files (some publishers accept up to 500 MB
  or 1 GB source files; Vibe's 100 MB cap is stricter)
- Audio: stereo, AAC or PCM, 48 kHz sample rate, at least
  192 kbps
- Loudness: -24 LKFS plus or minus 2, integrated (the CALM Act /
  ATSC A/85 standard for US TV), true peak at or below -2 dBTP
- No slates, countdowns, color bars or black leader; no
  letterboxing or pillarboxing used as decoration; audio and
  video durations must match (within about 500 ms)
- Key text, logos and calls to action kept inside title-safe
  margins (the center 90% rule of thumb), because TV screens
  overscan and platform UI can crowd edges
- Programmatic delivery beyond direct upload runs on VAST tags
  (VPAID is not supported on CTV devices)
- Some publishers require closed captions with the creative

## What is buildable by us, and what is not

**Buildable now, with our existing fleet:**

- The brief-to-creative step: brand brief in, a timed 15 or 30
  second script out, with word budgets computed in code (a 30
  second voiceover reads about 65-75 words; a 15 second spot
  about 32-38). This is exactly the LLM work in the Claude plus
  Higgsfield route.
- The shot breakdown: shot-by-shot list with timings and a
  ready-to-paste Higgsfield generation prompt per shot (16:9,
  camera language, no text in frame, text added in edit), which
  is the artifact the prompt route actually produces by hand.
- Voiceover production routing: the script's voiceover text is a
  direct input to our own SwiftRead API (POST /speak), so the
  package can carry a ready payload for it.
- End-card copy: headline, subline, call to action, logo and QR
  placement notes, hold duration.
- Spec enforcement: the delivery spec above as data, plus a
  checker that scores a finished file's measured specs (duration,
  resolution, loudness, peaks, bitrate, size) against it before
  anyone pays for placement. Our DriftCheck and SwiftRender
  services already do adjacent file QA.
- Assembly guidance and, where our fleet honestly supports it,
  assembly itself: SwiftRender already assembles gated clips
  against an audio track. A full automated render of a TV spot
  from generated clips is a bigger claim and is NOT made here.

**Not buildable by us, and never faked:**

- **Actual TV placement.** Delivery into Hulu, Tubi and the rest
  runs through Vibe's (or another DSP's) licensed supply
  agreements, advertiser account, payment method and compliance
  review. There is no API shortcut: someone has to open an
  advertiser account, accept the platform's terms and fund it.
  That is a user tap, full stop. Our API ends at a
  placement-ready package; the last mile belongs to the
  advertiser's own Vibe (or equivalent) account.
- Audience data and measurement: Vibe's household graph, CRM
  matching and incrementality measurement are theirs. Our package
  can recommend targeting in words; it cannot target.
- Vibe Studio's site-scrape brand extraction at their quality is
  their trained pipeline. Our brief is advertiser-supplied fields
  (plus an optional website URL recorded for the production
  notes), not a scraped brand kit, and the spec says so.

## The API we build from this: SpotBase

SpotBase replicates the buildable core as one API call: submit a
brief (brand name, product, audience, offer, call to action, tone,
15 or 30 seconds) and get back the complete streaming-TV ad
package: timed script, shot list with Higgsfield-ready prompts,
voiceover text with a SwiftRead-ready payload, end-card copy, the
CTV delivery spec, and a compliance checklist, plus a spec
checker endpoint for the finished file. Full design in
docs/spec-spotbase.md.
