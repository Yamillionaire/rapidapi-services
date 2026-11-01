# RecipeBase - RapidAPI listing notes (launch, 2026-11-01)

Product: RecipeBase, competitor to Tasty (Api Dojo, registry #18).
Service: https://recipebase.onrender.com (Render, see registry entry
for the service id). Listing package: listings/recipebase-openapi.json.
Spotlight proof doc: docs/recipebase-reliability.md.
Publish runs under the user's 2026-10-29 FULL AUTOMATION authorization.

## Short description (use verbatim)

"Recipe API whose list and similarity endpoints actually work, with
case-insensitive partial-keyword search: CARB finds the carbonara.
501 curated world recipes, CC BY-SA data, servings scaler, honest
empty searches (200, count 0). The incumbent's $10 tier is free."

## Plans (hard limits, monthly)

- BASIC $0 / 250 requests
- PRO $0 / 10,000 requests (the incumbent's $10 Pro tier, free as the hook)
- ULTRA $20 / 100,000 requests (incumbent $30)
- MEGA $290 / 1,000,000 requests (incumbent $300; platform max at price if lower)

## Endpoints (8)

GET /recipes/list, GET /recipes/search, GET /recipes/auto-complete,
GET /recipes/get-more-info, GET /recipes/list-similarities,
GET /tags/list, GET /attribution, GET /health.

## Spotlight

Title: "The recipe endpoints that actually work, and a search that finds things"
Description (keep under 280 characters): "RecipeBase: the list and
similarity endpoints actually work, and search is case-insensitive
with partial keywords, so CARB finds the carbonara. Honest 501-recipe
world catalog, CC BY-SA data. The incumbent's $10 tier is free here."
URL: the GitHub blob URL of docs/recipebase-reliability.md in
Yamillionaire/rapidapi-services.

## Honesty notes baked into copy

- Catalog size (501 recipes, 127 countries) stated up front.
- Nutrition labeled computed planning reference, never lab-measured.
- Photos served only with per-photo author and license.
- No competitor other than the incumbent's public listing facts is
  named; the wider pain pool is described, not named.
