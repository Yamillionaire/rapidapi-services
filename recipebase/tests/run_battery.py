"""Local battery for RecipeBase: complaint cases first.
Run: python3 tests/run_battery.py [base_url]  (default http://localhost:8119)
Writes tests/battery-local-2026-11-01.json next to this file.
"""
import json
import os
import sys
import urllib.request
import urllib.parse

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8119"
results = []


def get(path, **params):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=60) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def check(name, cond, detail=""):
    results.append({"test": name, "pass": bool(cond), "detail": str(detail)[:300]})
    print(("PASS" if cond else "FAIL"), name, detail if not cond else "")


# health
s, b = get("/health")
check("health ok with corpus loaded", s == 200 and b.get("recipes") == 501, b.get("recipes"))

# COMPLAINT CASE 1: recipes/list works and paginates
s, b = get("/recipes/list", size=5)
check("list returns 5 of 501", s == 200 and b["count"] == 501 and len(b["results"]) == 5, (s, b.get("count")))
s, b2 = get("/recipes/list", **{"from": 5, "size": 5})
check("list page 2 differs", s == 200 and b2["results"][0]["id"] != b["results"][0]["id"])
check("list carries CC BY-SA credit", "CC BY-SA 4.0" in b.get("source", ""))

# COMPLAINT CASE 2: list-similarities works
s, b = get("/recipes/list-similarities", id="spaghetti-carbonara")
check("similarities returns results", s == 200 and b["count"] > 0 and len(b["results"]) > 0, (s, b.get("count")))
check("similarities excludes self", all(r["id"] != "spaghetti-carbonara" for r in b["results"]))
s, b = get("/recipes/list-similarities", id="no-such-recipe")
check("similarities unknown id is structured 404", s == 404 and b.get("error") == "recipe_not_found", s)

# COMPLAINT CASE 3: search is case-insensitive and partial-keyword
for q in ("CARBONARA", "carbonara", "Carbon", "carb", "SPAGHETTI CARB"):
    s, b = get("/recipes/search", q=q)
    check(f"search {q!r} finds carbonara", s == 200 and any(r["id"] == "spaghetti-carbonara" for r in b["results"]), (s, b.get("count")))
# ingredient search
s, b = get("/recipes/search", q="guanciale")
check("search by ingredient works", s == 200 and b["count"] >= 1, b.get("count"))
# empty search is a 200 with count 0, never an error (Spoonacular pain)
s, b = get("/recipes/search", q="zzzznothingmatchesthis")
check("empty search is 200 count 0", s == 200 and b["count"] == 0 and b["results"] == [], (s, b.get("count")))
s, b = get("/recipes/search")
check("search without q is structured 422", s == 422 and b.get("error") == "missing_parameter", s)

# get-more-info: full detail, servings scaling, nutrition labeled
s, b = get("/recipes/get-more-info", id="spaghetti-carbonara")
check("detail has ingredients+steps", s == 200 and len(b["ingredients"]) == 7 and len(b["steps"]) >= 5, (s, len(b.get("ingredients", []))))
check("photo served with author+license", b["photo"] and b["photo"].get("author") and b["photo"].get("license"), b.get("photo"))
check("nutrition labeled planning reference", "planning reference" in b.get("nutrition_note", ""))
base_spaghetti = [i for i in b["ingredients"] if i["id"] == "spaghetti"][0]["quantity"]
s, b4 = get("/recipes/get-more-info", id="spaghetti-carbonara", servings=4)
scaled = [i for i in b4["ingredients"] if i["id"] == "spaghetti"][0]["quantity"]
check("servings scaling doubles linear qty", scaled == base_spaghetti * 2, (base_spaghetti, scaled))
s, b = get("/recipes/get-more-info", id="nope")
check("detail unknown id is structured 404", s == 404 and b.get("error") == "recipe_not_found", s)

# filters + autocomplete + tags + attribution
s, b = get("/recipes/list", diet="vegan", size=100)
check("diet filter vegan all vegan", s == 200 and b["count"] > 0 and all("vegan" in r["diets"] for r in b["results"]), b.get("count"))
s, b = get("/recipes/auto-complete", prefix="spa")
check("autocomplete finds Spaghetti", s == 200 and any(x == "Spaghetti" for x in b["suggestions"]), b.get("suggestions"))
s, b = get("/tags/list")
check("tags lists categories+diets+countries", s == 200 and "main" in b["categories"] and len(b["countries"]) > 50)
s, b = get("/attribution")
check("attribution endpoint carries license", s == 200 and b.get("license") == "CC BY-SA 4.0" and "UniTools" in b.get("attribution", ""))

out = {"base": BASE, "passed": sum(1 for r in results if r["pass"]), "total": len(results), "results": results}
path = os.path.join(os.path.dirname(__file__), "battery-local-2026-11-01.json")
with open(path, "w") as fh:
    json.dump(out, fh, indent=1)
print(f"{out['passed']}/{out['total']} passed -> {path}")
sys.exit(0 if out["passed"] == out["total"] else 1)
