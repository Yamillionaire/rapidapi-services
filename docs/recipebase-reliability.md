# The recipe endpoints that actually work, and a search that finds things

Tasty by Api Dojo (17,905 subscribers, rated 2/5 on 50 votes) carries
a Discussions board where the same complaints repeat across 20+
threads, nearly all of them Unanswered: recipes/list and
recipes/list-similarities reported not working, and a search that
misses what callers type. RecipeBase was built so each failure mode
has nowhere to live. The list endpoint paginates a real catalog with
filters that filter; the similarities endpoint ranks by shared
ingredients, category, and cuisine; and search is case-insensitive
with partial-keyword matching across names, summaries, and
ingredients, so "CARB", "carb", and "Carbon" all find the carbonara.
An empty search is a successful 200 with count 0, never an error, and
every failure anywhere is a structured JSON object that names the
problem.

Spotlight description (under 280 characters): RecipeBase: the list
and similarity endpoints actually work, and search is case-insensitive
with partial keywords, so CARB finds the carbonara. Honest 501-recipe
world catalog, CC BY-SA data. The incumbent's $10 tier is free here.

The catalog is stated honestly up front: 501 curated world recipes
from 127 countries (UniTools World Recipes, CC BY-SA 4.0, credited in
every response), with ingredients, timed steps, diet and category
filters, a servings scaler driven by the dataset's own scaling rules,
and photos served only with the per-photo author and license the
data provides. Nutrition is computed from ingredients and labeled a
planning reference, not lab-measured.

Verified against the local RecipeBase build on 2026-11-01 (battery
24/24, recipebase/tests/battery-local-2026-11-01.json):

| Test | Result |
| --- | --- |
| recipes/list | 200, count 501, paginates, carries the CC BY-SA credit line |
| recipes/list-similarities for spaghetti-carbonara | 200 with ranked results, excludes the recipe itself |
| Search: CARBONARA / carbonara / Carbon / carb / SPAGHETTI CARB | All find spaghetti-carbonara |
| Search by ingredient (guanciale) | 200, matches |
| Search with no matches | 200 with count 0 and an empty results array, not an error |
| get-more-info | Full ingredients and timed steps; photo carries its author and license; servings=4 doubles linear quantities exactly |
| Unknown id on detail and similarities | Structured 404 recipe_not_found |
| Missing or invalid parameters | Named 422 JSON errors |
| Diet filter (vegan) | Every returned recipe carries the vegan tag |
| /attribution | Dataset, license, credit line, and share-alike terms in one call |

And the pricing answers too: the incumbent charges $10 a month for
its entry tier. RecipeBase Pro is free as the hook, Ultra is $20
against their $30, and Mega is $290 against their $300, all hard
limits.
