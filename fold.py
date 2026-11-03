#!/usr/bin/env python3
"""Fold `achievement` issues (harvested snapshot) into api/v1/runs.json and api/v1/leaderboard.json. Ids, dates, numbers; never names.
Stable-write: if only generated_at would change the files are left as they were."""
import json, re, sys, datetime, pathlib
src = json.load(open(sys.argv[1])); out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
issues = src.get("items", src) if isinstance(src, dict) else src   # harvested snapshot ({items:[...]}) or a raw gh list
for it in issues: it.setdefault("createdAt", it.get("created_at"))
VALID = {f"badge-{i}" for i in range(1, 9)} | {"elite-four", "hall-of-fame"}
HEX = re.compile(r"^[0-9a-f]{6,64}$")
runs = {}
for it in sorted(issues, key=lambda i: i.get("createdAt") or ""):
    m = re.search(r"```json\s*(\{.*?\})\s*```", it.get("body") or "", re.S)
    if not m: continue
    try: v = json.loads(m.group(1))
    except Exception: continue
    if v.get("arena") != "pokemon-gen1" or not isinstance(v.get("run_id"), str) or not HEX.match(v["run_id"]): continue
    claims = {}
    for c in v.get("claims") or []:
        if not isinstance(c, dict) or c.get("id") not in VALID or not isinstance(c.get("at"), str): continue
        d = c.get("decisions"); claims[c["id"]] = {"at": c["at"][:20], "decisions": int(d) if isinstance(d, (int, float)) and d >= 0 else None,
                                                  "evidence": str(c.get("evidence", ""))[:160]}
    if not claims: continue
    runs[v["run_id"]] = {  # latest issue for a run id wins (a run keeps filing as it earns more)
        "run_id": v["run_id"], "model": str(v.get("model", "unknown"))[:40], "game": str(v.get("game", "?"))[:16],
        "rom_sha256": str(v.get("rom_sha256", ""))[:16], "agent_sha256": str(v.get("agent_sha256", ""))[:16],
        "category": "autonomous" if v.get("category") == "autonomous" else "assisted",
        "started_at": str(v.get("started_at", ""))[:20], "claims": claims, "issue": it.get("number"),
        "badges": max([int(k.split("-")[1]) for k in claims if k.startswith("badge-")] or [0]), "hall_of_fame": "hall-of-fame" in claims}
board = {}
for r in runs.values():
    key = (r["model"], r["game"], r["category"]); b = board.setdefault(key, {"model": r["model"], "game": r["game"], "category": r["category"], "runs": 0, "best_badges": 0, "best_decisions_per_badge": None, "hall_of_fame": 0})
    b["runs"] += 1; b["best_badges"] = max(b["best_badges"], r["badges"]); b["hall_of_fame"] += int(r["hall_of_fame"])
    counted = [c for k, c in r["claims"].items() if k.startswith("badge-") and c["decisions"]]   # badges the log actually saw
    if counted:
        dpb = round(max(c["decisions"] for c in counted) / len(counted))
        if b["best_decisions_per_badge"] is None or dpb < b["best_decisions_per_badge"]: b["best_decisions_per_badge"] = dpb
rows = sorted(board.values(), key=lambda b: (-b["hall_of_fame"], -b["best_badges"], b["best_decisions_per_badge"] or 1e12))
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
def stable(path, obj):
    try:
        old = json.load(open(path))
        if {k: v for k, v in old.items() if k != "generated_at"} == {k: v for k, v in json.loads(json.dumps(obj)).items() if k != "generated_at"}: return
    except Exception: pass
    json.dump(obj, open(path, "w"), indent=1); open(path, "a").write("\n")
stable(out / "runs.json", {"schema": "gameboi-arena/1", "generated_at": now, "runs": sorted(runs.values(), key=lambda r: (-r["badges"], r["started_at"]))})
stable(out / "leaderboard.json", {"schema": "gameboi-arena/1", "generated_at": now, "submissions": len(issues), "runs": len(runs), "rows": rows})
print(f"{len(runs)} runs, {len(rows)} board rows")
