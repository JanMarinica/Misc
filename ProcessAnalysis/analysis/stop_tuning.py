"""Recommend per-station movement stop offsets that minimise Check & Fix corrections.

Usage: python3 stop_tuning.py <stops.json> <cycles.json> <out.json>

Length:   stop = target + offL  (seat moves backward, laser value falls)
Backrest: stop = target - offB  (backrest moves forward, value rises)
The motor is stopped when the laser passes `stop`; the seat then coasts.
Verify passes when the final value is inside [min, max] (target +-4 length, +-5 backrest).
"""
import json, statistics as st, sys
from datetime import datetime

CUR_OFF = {"L": {s: 8 for s in ["EOL1L", "EOL1R", "EOL5L", "EOL5R", "EOL20", "EOL21"]},
           "B": {"EOL1L": 15, "EOL1R": 15, "EOL5L": 15, "EOL5R": 15, "EOL20": 10, "EOL21": 15}}
SIGN = {"L": 1, "B": -1}


def main(stops_p, cycles_p, out_p):
    stops, cycles = json.load(open(stops_p)), json.load(open(cycles_p))
    res = {}
    for s, cs in stops.items():
        # Check & Fix durations (1st run = length, 2nd = backrest) keyed by main start hh:mm:ss
        cf = {}
        for c in cycles[s]:
            key = datetime.fromtimestamp(c["main_start"]).strftime("%H:%M:%S")
            runs = c["tests"].get("22857", {"runs": []})["runs"]
            cf[key] = [r[1] - r[0] for r in runs if r[1]]
        res[s] = {}
        for ax in "LB":
            v = [c["v"] for c in cs if c["bc"] and c["bc"][0] == "V"
                 and c["v"].get(ax + "_ver") is not None and c["v"].get(ax + "_trig") is not None]
            sg, off0 = SIGN[ax], CUR_OFF[ax][s]
            # travel past the stop value, and window half-width, per cycle
            rows = [(x[ax + "_ver"] - x[ax + "_stop"], (x[ax + "_max"] - x[ax + "_min"]) / 2,
                     x[ax + "_ver_ok"], x[ax + "_min"] <= x[ax + "_ver"] <= x[ax + "_max"]) for x in v]

            def outside(off):
                # final - target = sg*off + travel
                return sum(abs(sg * off + t) > hw for t, hw, _, _ in rows) / len(rows)

            best = min(range(0, 40), key=lambda o: (round(outside(o), 4), abs(o - off0)))
            durs = {"ok": [], "nok": []}
            for c in cs:
                if c["bc"] and c["bc"][0] == "V" and c["v"].get(ax + "_ver") is not None:
                    d = cf.get(c["t"])
                    i = 0 if ax == "L" else 1
                    if d and len(d) > i:
                        durs["ok" if c["v"][ax + "_ver_ok"] else "nok"].append(d[i])
            ok_t = st.median(durs["ok"]) if durs["ok"] else 0.6
            nok_t = st.median(durs["nok"]) if durs["nok"] else 7.0
            unstable = sum(inw and not ok for _, _, ok, inw in rows) / len(rows)
            cur_rate = sum(not ok for _, _, ok, _ in rows) / len(rows)
            new_rate = outside(best) + unstable
            res[s][ax] = {
                "n": len(rows), "current_offset": off0, "recommended_offset": best,
                "final_minus_target_med": round(st.median(sg * off0 + t for t, *_ in rows), 1),
                "travel_after_stop_med": round(st.median(t for t, *_ in rows), 1),
                "travel_p10_p90": [round(sorted(t for t, *_ in rows)[int(.1 * len(rows))], 1),
                                   round(sorted(t for t, *_ in rows)[int(.9 * len(rows))], 1)],
                "check_fix_now_pct": round(100 * cur_rate, 1),
                "out_of_window_now_pct": round(100 * outside(off0), 1),
                "out_of_window_new_pct": round(100 * outside(best), 1),
                "unstable_verify_pct": round(100 * unstable, 1),
                "check_fix_new_pct": round(100 * new_rate, 1),
                "cf_time_ok_s": round(ok_t, 1), "cf_time_nok_s": round(nok_t, 1),
                "saving_s_per_seat": round((cur_rate - new_rate) * (nok_t - ok_t), 1),
            }
    json.dump(res, open(out_p, "w"), indent=1)
    for s, a in res.items():
        for ax, r in a.items():
            print(s, ax, {k: r[k] for k in ["current_offset", "recommended_offset", "final_minus_target_med",
                                            "check_fix_now_pct", "out_of_window_now_pct", "out_of_window_new_pct",
                                            "unstable_verify_pct", "check_fix_new_pct", "cf_time_ok_s", "cf_time_nok_s",
                                            "saving_s_per_seat"]})


if __name__ == "__main__":
    main(*sys.argv[1:4])
