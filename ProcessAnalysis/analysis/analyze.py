"""Aggregate parsed cycles into phase / component timing per station.

Usage: python3 analyze.py <cycles.json> <summary.json>
"""
import collections, json, statistics as st, sys

# Seat-component (top-level, reported to SFCS) test groups -> test ids (PLC "gP" / IO1978 "g7" variants)
COMPONENTS = {
    "Short to ground": ["185"],
    "Airbags (SAB/FSAB)": ["14", "22521"],
    "Belt buckle": ["9"],
    "STPS": ["309"],
    "SBR (occupant sensor)": ["126"],
    "Mood light": ["1047", "327"],
    "Heating": ["403"],
    "Ventilation": ["22764", "22511"],
    "Lumbar": ["472"],
    "Massage": ["143"],
    "Movements": ["704"],
    "Expedition position": ["1233", "86", "22999"],
}
PARALLEL = {"Airbags (SAB/FSAB)", "Belt buckle", "STPS", "SBR (occupant sensor)", "Mood light", "Heating"}
MOVEMENT_AXES = {"Height up": "765", "Height down": "743", "Length forward": "772", "Length backward": "744",
                 "Cushion extension": "746", "Tilt": "747", "Backrest backward": "773", "Backrest forward": "745"}


def run(c, ids, which=0):
    for i in ids:
        e = c["tests"].get(i)
        if e and len(e["runs"]) > which and e["runs"][which][1] is not None:
            return e["runs"][which]
    return None


def first_start(c, ids):
    r = run(c, ids)
    return r[0] if r else None


def phases(c):
    """Sequential main-line segments (SPA-1 flow). Returns {phase: seconds}."""
    t0 = c["main_start"]
    g = lambda *ids: first_start(c, list(ids))
    marks = [
        ("Init & parameter calc", t0),
        ("Check assembly position", g("851")),
        ("Grounding & isolation check", g("753")),
        ("Short to ground", g("185")),
        ("Grounding release", g("972")),
        ("Start parallel tests + PSM power-up", g("605")),
        ("PSM reset & diag start", g("531")),
        ("Ventilation, SBR unload, Lumbar", g("22764", "472")),
        ("Massage (option) + wait for parallel tests", (run(c, ["472"]) or [None, None])[1]),
        ("Movements", g("704")),
        ("Expedition position & final CAN", (run(c, ["704"]) or [None, None])[1]),
        ("_main_end", c["main_end"]),
    ]
    if any(m[1] is None for m in marks):
        return None
    out = {}
    for (n, a), (_, b) in zip(marks, marks[1:]):
        out[n] = b - a
    return out


def stats(v):
    if not v:
        return None
    v = sorted(v)
    q = lambda p: v[min(len(v) - 1, int(round(p * (len(v) - 1))))]
    return {"n": len(v), "med": round(st.median(v), 2), "mean": round(st.mean(v), 2),
            "p10": round(q(.1), 2), "p90": round(q(.9), 2), "min": round(v[0], 2), "max": round(v[-1], 2)}


def main(src, dst):
    data = json.load(open(src))
    out = {}
    for s, cycles in data.items():
        spa1 = [c for c in cycles if c["barcode"].get("broadcast", "V")[0] == "V"]
        spa3 = [c for c in cycles if c["barcode"].get("broadcast", "V")[0] == "G"]
        S = {"cycles": len(cycles), "spa1": len(spa1), "spa3": len(spa3),
             "nok": sum(not c["main_ok"] for c in cycles)}
        # cycle-level times (SPA-1 only, OK cycles)
        ok1 = [c for c in spa1 if c["main_ok"]]
        S["main_time"] = stats([c["main_end"] - c["main_start"] for c in ok1])
        S["finish_time"] = stats([c["cycle_end"] - c["main_end"] for c in ok1])
        gaps = [c["main_start"] - c["prev_end"] for c in cycles if c["prev_end"]]
        S["load_time"] = stats([x for x in gaps if x < 300])
        S["stoppages"] = {"count": sum(x >= 300 for x in gaps), "minutes": round(sum(x for x in gaps if x >= 300) / 60, 1)}
        S["tact"] = stats([c["cycle_end"] - c["prev_end"] for c in ok1 if c["prev_end"] and c["cycle_end"] - c["prev_end"] < 400])
        first, last = cycles[0]["main_start"], cycles[-1]["cycle_end"]
        S["window_h"] = round((last - first) / 3600, 2)
        # phases
        ph = collections.defaultdict(list)
        for c in ok1:
            p = phases(c)
            if p:
                for k, v in p.items():
                    ph[k].append(v)
        S["phases"] = {k: stats(v) for k, v in ph.items()}
        # components
        comp = {}
        for name, ids in COMPONENTS.items():
            dur, off, n_run, n_fail = [], [], 0, 0
            for c in spa1:
                r = run(c, ids)
                if r:
                    n_run += 1
                    n_fail += r[2] is False
                    if c["main_ok"]:
                        dur.append(r[1] - r[0]); off.append(r[0] - c["main_start"])
            comp[name] = {"executed": n_run, "share": round(n_run / max(1, len(spa1)) * 100), "fail": n_fail,
                          "dur": stats(dur), "start_offset": stats(off), "parallel": name in PARALLEL}
        S["components"] = comp
        S["axes"] = {}
        for name, i in MOVEMENT_AXES.items():
            v = [r[1] - r[0] for c in ok1 for r in [run(c, [i])] if r]
            S["axes"][name] = dict(stats(v) or {}, share=round(len(v) / max(1, len(ok1)) * 100))
        # SPA-3
        S["spa3_detail"] = [{
            "main": round(c["main_end"] - c["main_start"], 1), "ok": c["main_ok"],
            "calibration": round((lambda r: r[1] - r[0] if r else 0)(run(c, ["22288"])), 1),
            "can_movements": round((lambda r: r[1] - r[0] if r else 0)(run(c, ["22295"])), 1)} for c in spa3]
        # failures: which component group failed in NOK cycles
        fails = collections.Counter()
        for c in cycles:
            if not c["main_ok"]:
                hit = [n for n, ids in COMPONENTS.items() for i in ids
                       if any(r[2] is False for r in c["tests"].get(i, {"runs": []})["runs"])]
                fails.update(hit or ["other / aborted"])
        S["nok_by_component"] = dict(fails)
        out[s] = S
    json.dump(out, open(dst, "w"), indent=1)


if __name__ == "__main__":
    main(*sys.argv[1:3])
