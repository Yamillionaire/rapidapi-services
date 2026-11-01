# Spec: Tasty competitor (registry candidate #18) - corpus proof stage

Status: SPEC STAGE ONLY. No build. Per PIPELINE.md, nothing builds without
the user's tap on the spec. Prepared 2026-11-01.

## The incumbent and the complaints being fixed

- Tasty by Api Dojo on RapidAPI: 17,905 subscribers, rated 2/5 on 50 votes,
  pricing $0/$10/$30/$300, service 100%, latency 1,154 ms (live-verified
  2026-11-01, candidate registry entry #18).
- Discussion pain (20+ threads, nearly all Unanswered): recipes/list and
  recipes/list-similarities endpoints reported not working; search is
  limited (case-insensitive q, partial keyword matching); feature gaps.
- The wedge: a smaller but dependable recipe API whose list and search
  endpoints actually work, with honest docs and answered support.

## Corpus licensing: the gating condition, now checked

Registry condition: the build must NOT scrape Tasty or BuzzFeed content; it
needs an original or openly licensed recipe corpus, and licensing must be
proven in the spec stage before any build.

### Proven lawful: UniTools World Recipes (launch corpus)

- Source verified at the primary repository on 2026-11-01:
  github.com/farcrak/unitools-recipes, LICENSE file present, dataset page
  theunitools.com/en/data, full JSON at
  theunitools.com/data/unitools-recipes-v1.json (about 2.6 MB).
- License: CC BY-SA 4.0. The README states it plainly: free to use,
  commercially included. Credit "UniTools - theunitools.com" and share
  derivatives under the same license.
- Contents: 501 home-cooking recipes from 127 countries, English and
  Russian written natively (serve the English text). About 1,500 unique
  ingredients with stable ids, 3,000+ steps with minutes on each step,
  per-serving nutrition on every dish, prep and cook minutes as separate
  fields, category, diets, difficulty, and ingredient scaling rules
  (linear, sublinear, fixed) that support a real servings scaler.
- Field fit: ingredients, steps, nutrition, timing, category and diet
  fields cover the incumbent's core list, detail, search and similar
  recipe shapes without inventing data.
- Caveats, stated honestly: 501 recipes is a small catalog next to the
  incumbent's; the dataset is maintained by one person (first release
  2026-08, current version 2.0.0); nutrition is computed from ingredients,
  not lab-measured, and must be labeled as a planning reference.
- Photos: each photo is a Wikimedia Commons image carrying its own
  license and author in the data. Serve photo URLs only with the
  per-photo attribution the data provides, or omit photos at launch.

### Proven lawful: USDA FoodData Central (nutrition enrichment)

- US government data, public domain. Use it for ingredient-level nutrition
  enrichment and cross-checks, as the registry entry already planned.
  Recipe-level nutrition stays the UniTools computed figures, labeled.

### Lawful growth lane (post-launch, not the launch corpus)

- Public domain cookbooks: works published in the US before 1923, via
  Project Gutenberg and Internet Archive, plus US government recipe
  collections. Copyright framing: ingredient lists are not copyrightable,
  but instructions are protectable expression, so only public domain or
  openly licensed sources may supply instruction text.

### Checked and excluded

- RecipeNLG (2.2 million recipes): restricted to non-commercial use only.
  Confirmed in a 2026 arXiv paper describing the dataset as "restricted
  to non-commercial usage only" and in dataset comparisons. EXCLUDED.
- Recipe1M+ (MIT): research-licensed. EXCLUDED.
- Food.com data on Kaggle: scraped provenance, raw text. EXCLUDED.
- CrawlFeeds 300K recipe dataset: a paid product built from scraped
  sites. Violates the fleet free-only rule. EXCLUDED unless API revenue
  later covers a license, with the breakeven written here first.
- TheMealDB: an existing free API with scraped provenance, not a corpus
  we can lawfully copy. EXCLUDED as a data source.

## Share-alike compliance design (CC BY-SA 4.0 obligations)

- Every recipe response carries the credit line: Recipe data: UniTools,
  CC BY-SA 4.0, with the dataset page address.
- An attribution endpoint and the listing page repeat the credit.
- The served dataset adaptation is itself offered under CC BY-SA 4.0. The
  license covers the data, not our code; the API service, search ranking
  and scaling logic remain ours.
- No Tasty, BuzzFeed or other scraped recipe text anywhere in the corpus.

## Positioning against the pain

- Sell reliability and search quality, not catalog size: working list and
  similarity endpoints, ingredient-based search, diet and category
  filters, servings scaling from the dataset's own scaling rules.
- The listing and docs state the catalog size (501 curated world recipes)
  up front. Honest scope is the brand difference against a 2/5 incumbent.

## Pricing grid (from registry entry #18, undercut by $10)

- BASIC $0 (the incumbent's $10 Pro tier is matched by making our Pro
  free as the hook, per the registry).
- PRO $0, ULTRA $20 (incumbent $30), MEGA $290 (incumbent $300).
- Net after RapidAPI's 25% fee: Ultra $15.00, Mega $217.50 per subscriber
  month. Exact quota numbers get set in the listing package at publish.

## Verdict

- The corpus condition is PROVEN for a lawful launch: UniTools CC BY-SA
  4.0 (verified at the primary source) plus public domain USDA data,
  with a public domain growth lane behind it.
- The tradeoff is catalog depth: 501 recipes at launch against an
  incumbent with thousands, answered by competing on the incumbent's
  documented pain (broken endpoints, weak search, unanswered support).
- Remaining step is the user's tap on this spec. On approval the pipeline
  runs unattended per standing authorization: build on the shared
  scaffold, deploy, proof battery, Studio listing, publish, Spotlight.
- Cost so far: $0. Corpus cost at build: $0 (open license plus public
  domain). One more Render service joins the fleet; the registry records
  17 services and about 91 hours of keep-warm headroom after #17, so one
  more always-on service needs the keep-warm window re-budgeted in the
  build step, the same adjustment made for services 16 and 17.
