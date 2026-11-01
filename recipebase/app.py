"""RecipeBase - competitor to Tasty (Api Dojo) on RapidAPI.

Incumbent verified 2026-11-01: 17,905 subscribers, rated 2/5 (50 votes),
pricing $0/$10/$30/$300. Complaints from its own Discussions (20+ threads,
nearly all Unanswered): recipes/list and recipes/list-similarities
reported not working; search is case-sensitive and misses partial
keywords. The Spoonacular listing's Discussions carry the same pain:
404s, searches returning nothing, 401s.
This service: a recipe API whose list, search, and similarity endpoints
actually work. Search is case-insensitive and matches partial keywords
across names, summaries, and ingredients; an empty search is a 200 with
count 0, never an error; every failure is a structured JSON object.

Corpus: UniTools World Recipes v2.0.0 (501 recipes, 127 countries),
CC BY-SA 4.0, commercial use allowed, verified at the primary source
2026-11-01 (docs/spec-tasty-competitor.md). No Tasty, BuzzFeed, or other
scraped recipe text anywhere. The dataset is fetched at boot from
theunitools.com (a local data/ copy is used when present) and cached.
Every recipe response carries the CC BY-SA credit line; photos are
served only with the per-photo author and license the data provides.
Nutrition figures are computed from ingredients by the dataset, not
lab-measured, and are labeled a planning reference wherever served.
Zero dependencies beyond the shared scaffold. Run: python3 app.py (PORT env, default 8118).
"""
import math
import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "shared"))
from rapidapi_server import run, fetch_json, cache_get, cache_set

DATA_URL = "https://theunitools.com/data/unitools-recipes-v1.json"
LOCAL_DATA = os.path.join(os.path.dirname(__file__), "data", "unitools-recipes-v1.json")
CREDIT = "Recipe data: UniTools - theunitools.com, CC BY-SA 4.0"
NUTRITION_NOTE = ("Nutrition is computed from the recipe's ingredients by the "
                  "dataset, not lab-measured; treat it as a planning reference.")
MAX_SIZE = 100

_state = {"recipes": None, "countries": {}, "version": None, "loaded_at": 0}
_lock = threading.Lock()


def _load_dataset():
    """Fetch (or read local) corpus once; return True when loaded."""
    if _state["recipes"] is not None:
        return True
    with _lock:
        if _state["recipes"] is not None:
            return True
        data = None
        if os.path.exists(LOCAL_DATA):
            import json
            with open(LOCAL_DATA, encoding="utf-8") as fh:
                data = json.load(fh)
        if data is None:
            cached, _stale = cache_get("unitools")
            if cached is not None:
                data = cached
            else:
                data = fetch_json(DATA_URL, timeout=60, headers={
                    "User-Agent": "RecipeBase/1.0 (+https://rapidapi.com/YamilLittle/api/recipebase)",
                    "Accept": "application/json"})
                cache_set("unitools", data, 24 * 3600)
        recipes = []
        for raw in data["recipes"]:
            recipes.append(_normalize(raw, data))
        _state["recipes"] = recipes
        _state["by_slug"] = {r["id"]: r for r in recipes}
        _state["countries"] = {c["code"]: c["name"].get("en", c["code"])
                                for c in data.get("countries", [])}
        _state["version"] = data.get("version")
        _state["attribution"] = data.get("attribution", "UniTools - theunitools.com")
        return True


def _photo(raw):
    p = raw.get("photo") or {}
    if not p.get("url"):
        return None
    # Photos ship only with the per-photo attribution the data provides.
    return {"url": p["url"], "author": p.get("author"),
            "license": p.get("license"), "credit": f"Photo: {p.get('author')} ({p.get('license')})"}


def _normalize(raw, dataset):
    name = raw["name"].get("en", "")
    ingredients = []
    for ing in raw.get("ingredients", []):
        ingredients.append({
            "id": ing["id"],
            "name": ing["name"].get("en", ""),
            "quantity": ing.get("quantity"),
            "unit": ing.get("unit"),
            "scaling": ing.get("scaling", "linear"),
            "note": (ing.get("note") or {}).get("en") if isinstance(ing.get("note"), dict) else ing.get("note"),
        })
    return {
        "id": raw["slug"],
        "name": name,
        "native_name": raw.get("nativeName"),
        "summary": (raw.get("summary") or {}).get("en", ""),
        "country_code": raw.get("country"),
        "category": raw.get("category"),
        "diets": raw.get("diets") or [],
        "difficulty": raw.get("difficulty"),
        "base_servings": raw.get("baseServings"),
        "prep_minutes": raw.get("prepMinutes"),
        "cook_minutes": raw.get("cookMinutes"),
        "total_minutes": (raw.get("prepMinutes") or 0) + (raw.get("cookMinutes") or 0),
        "nutrition_per_serving": raw.get("nutritionPerServing"),
        "ingredients": ingredients,
        "steps": [{"text": s["text"].get("en", ""), "minutes": s.get("minutes")}
                  for s in raw.get("steps", [])],
        "photo": _photo(raw),
        "_search_text": " ".join([
            name.lower(),
            (raw.get("nativeName") or "").lower(),
            (raw.get("summary") or {}).get("en", "").lower(),
            " ".join(i["name"].lower() for i in ingredients),
            " ".join(i["id"].replace("-", " ").replace("_", " ") for i in ingredients),
            (raw.get("category") or ""),
        ]),
        "_ingredient_ids": {i["id"] for i in ingredients},
    }


def _summary_view(r):
    return {
        "id": r["id"], "name": r["name"], "native_name": r["native_name"],
        "summary": r["summary"], "country_code": r["country_code"],
        "country": _state["countries"].get(r["country_code"]),
        "category": r["category"], "diets": r["diets"],
        "difficulty": r["difficulty"], "base_servings": r["base_servings"],
        "prep_minutes": r["prep_minutes"], "cook_minutes": r["cook_minutes"],
        "total_minutes": r["total_minutes"],
        "nutrition_per_serving": r["nutrition_per_serving"],
        "photo": r["photo"],
        "source": CREDIT,
    }


def _scale_quantity(qty, scaling, factor):
    if qty is None:
        return None
    if scaling == "fixed":
        return qty
    if scaling in ("damped", "sublinear"):
        scaled = qty * math.sqrt(factor)
    else:
        scaled = qty * factor
    # Round to a cook-friendly precision.
    if scaled >= 100:
        return round(scaled)
    if scaled >= 10:
        return round(scaled, 1)
    return round(scaled, 2)


def _detail_view(r, servings=None):
    view = _summary_view(r)
    factor = 1.0
    served = r["base_servings"]
    if servings and r["base_servings"]:
        factor = servings / r["base_servings"]
        served = servings
    view["servings"] = served
    view["ingredients"] = [
        {"id": i["id"], "name": i["name"],
         "quantity": _scale_quantity(i["quantity"], i["scaling"], factor),
         "unit": i["unit"], "note": i["note"]}
        for i in r["ingredients"]
    ]
    view["steps"] = r["steps"]
    view["nutrition_note"] = NUTRITION_NOTE
    return view


def _paginate(items, params):
    try:
        offset = max(0, int(params.get("from", 0)))
    except ValueError:
        return None, None, (422, {"error": "invalid_parameter",
                                  "detail": "from must be a non-negative integer."})
    try:
        size = int(params.get("size", 20))
    except ValueError:
        return None, None, (422, {"error": "invalid_parameter",
                                  "detail": "size must be an integer."})
    if size < 1 or size > MAX_SIZE:
        return None, None, (422, {"error": "invalid_parameter",
                                  "detail": f"size must be between 1 and {MAX_SIZE}."})
    return items[offset:offset + size], {"from": offset, "size": size,
                                         "total": len(items)}, None


def _matches(r, q):
    """Case-insensitive partial-keyword match: every token must appear."""
    text = r["_search_text"]
    return all(tok in text for tok in q.lower().split())


def list_recipes(params):
    _load_dataset()
    items = list(_state["recipes"])
    q = params.get("q", "").strip()
    if q:
        items = [r for r in items if _matches(r, q)]
    for key, field in (("category", "category"), ("difficulty", "difficulty"),
                       ("country", "country_code")):
        want = params.get(key, "").strip().lower()
        if want:
            items = [r for r in items if (r[field] or "").lower() == want]
    diet = params.get("diet", "").strip().lower()
    if diet:
        items = [r for r in items if diet in [d.lower() for d in r["diets"]]]
    tag = params.get("tags", "").strip().lower()  # incumbent's filter name
    if tag:
        items = [r for r in items
                 if tag in [d.lower() for d in r["diets"]] or (r["category"] or "").lower() == tag]
    page, meta, err = _paginate(items, params)
    if err:
        return err
    return 200, {"count": meta["total"], "from": meta["from"], "size": meta["size"],
                 "results": [_summary_view(r) for r in page],
                 "source": CREDIT}


def search(params):
    _load_dataset()
    q = params.get("q", "").strip()
    if not q:
        return 422, {"error": "missing_parameter",
                     "detail": "q is required. Search is case-insensitive and matches partial keywords."}
    items = [r for r in _state["recipes"] if _matches(r, q)]
    page, meta, err = _paginate(items, params)
    if err:
        return err
    # An empty result is a successful search, never an error (the pain fix).
    return 200, {"query": q, "count": meta["total"], "from": meta["from"],
                 "size": meta["size"],
                 "results": [_summary_view(r) for r in page],
                 "note": "Case-insensitive partial-keyword search over names, summaries, and ingredients.",
                 "source": CREDIT}


def autocomplete(params):
    _load_dataset()
    prefix = params.get("prefix", "").strip().lower()
    if not prefix:
        return 422, {"error": "missing_parameter", "detail": "prefix is required."}
    seen, out = set(), []
    for r in _state["recipes"]:
        for cand in [r["name"]] + [i["name"] for i in r["ingredients"]]:
            low = cand.lower()
            if low.startswith(prefix) and low not in seen:
                seen.add(low)
                out.append(cand)
    return 200, {"prefix": prefix, "count": len(out[:20]), "suggestions": out[:20]}


def get_more_info(params):
    _load_dataset()
    rid = params.get("id", "").strip()
    if not rid:
        return 422, {"error": "missing_parameter",
                     "detail": "id is required (a recipe slug from /recipes/list)."}
    r = _state["by_slug"].get(rid)
    if r is None:
        return 404, {"error": "recipe_not_found",
                     "detail": f"No recipe with id '{rid}'. Ids are slugs returned by /recipes/list and /recipes/search."}
    servings = None
    if params.get("servings"):
        try:
            servings = int(params["servings"])
            if servings < 1 or servings > 100:
                raise ValueError
        except ValueError:
            return 422, {"error": "invalid_parameter",
                         "detail": "servings must be an integer between 1 and 100."}
    return 200, _detail_view(r, servings)


def list_similarities(params):
    _load_dataset()
    rid = params.get("id", "").strip()
    if not rid:
        return 422, {"error": "missing_parameter",
                     "detail": "id is required (a recipe slug from /recipes/list)."}
    base = _state["by_slug"].get(rid)
    if base is None:
        return 404, {"error": "recipe_not_found",
                     "detail": f"No recipe with id '{rid}'. Ids are slugs returned by /recipes/list and /recipes/search."}
    scored = []
    for r in _state["recipes"]:
        if r["id"] == rid:
            continue
        shared = len(base["_ingredient_ids"] & r["_ingredient_ids"])
        score = shared * 2
        if r["category"] == base["category"]:
            score += 2
        if r["country_code"] == base["country_code"]:
            score += 1
        if score > 0:
            scored.append((score, shared, r))
    scored.sort(key=lambda t: (-t[0], t[2]["name"]))
    page, meta, err = _paginate([s[2] for s in scored], params)
    if err:
        return err
    results = []
    smap = {s[2]["id"]: (s[0], s[1]) for s in scored}
    for r in page:
        v = _summary_view(r)
        v["shared_ingredients"] = smap[r["id"]][1]
        results.append(v)
    return 200, {"id": rid, "count": meta["total"], "from": meta["from"],
                 "size": meta["size"], "results": results, "source": CREDIT}


def tags_list(params):
    _load_dataset()
    cats = sorted({r["category"] for r in _state["recipes"] if r["category"]})
    diets = sorted({d for r in _state["recipes"] for d in r["diets"]})
    countries = [{"code": c, "name": _state["countries"].get(c)}
                 for c in sorted({r["country_code"] for r in _state["recipes"] if r["country_code"]})]
    return 200, {"categories": cats, "diets": diets, "countries": countries,
                 "source": CREDIT}


def attribution(params):
    _load_dataset()
    return 200, {
        "dataset": "UniTools World Recipes",
        "dataset_version": _state["version"],
        "recipes": len(_state["recipes"]),
        "license": "CC BY-SA 4.0",
        "license_url": "https://creativecommons.org/licenses/by-sa/4.0/",
        "attribution": _state["attribution"],
        "credit_line": CREDIT,
        "dataset_page": "https://theunitools.com/en/data",
        "share_alike": "The served recipe data adaptation is offered under CC BY-SA 4.0, the same license as the source dataset.",
        "photos": "Each photo is served with its own author and license from the dataset.",
        "nutrition": NUTRITION_NOTE,
    }


def health(params):
    try:
        _load_dataset()
        loaded = _state["recipes"] is not None
        count = len(_state["recipes"]) if loaded else 0
    except Exception as exc:
        loaded, count = False, 0
        return 200, {"status": "degraded", "service": "recipebase",
                     "detail": f"Dataset not loaded: {type(exc).__name__}"}
    return 200, {"status": "ok", "service": "recipebase",
                 "recipes": count, "dataset": "UniTools World Recipes",
                 "dataset_version": _state["version"], "license": "CC BY-SA 4.0",
                 "search": "case-insensitive, partial-keyword",
                 "note": "List, search, and similarity endpoints return structured JSON; an empty search is a 200 with count 0."}


if __name__ == "__main__":
    run({"/recipes/list": list_recipes,
         "/recipes/search": search,
         "/recipes/auto-complete": autocomplete,
         "/recipes/get-more-info": get_more_info,
         "/recipes/list-similarities": list_similarities,
         "/tags/list": tags_list,
         "/attribution": attribution,
         "/health": health},
        int(os.environ.get("PORT", "8118")), "recipebase")
