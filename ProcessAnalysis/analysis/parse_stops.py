"""Extract length/backrest stop, coast and Check & Fix values per cycle.

Usage: python3 parse_stops.py <ProcessAnalysis dir> <out.json>
"""
import json, os, re, sys

STATIONS = ["EOL1L", "EOL1R", "EOL5L", "EOL5R", "EOL20", "EOL21"]
NAMES = {
    "Calculate Length Stop": "L_stop", "Calculate Length Max": "L_max", "Calculate Length Min": "L_min",
    "Calculate Backrest Stop": "B_stop", "Calculate Backrest Max": "B_max", "Calculate Backrest Min": "B_min",
    "Laser Slide Adjust gP": "L_trig", "Laser Slide Adjust g7": "L_trig",
    "Backrest adjust gP": "B_trig", "Laser Backrest Adjust g7": "B_trig",
    "Verify Length gP": "L_ver", "Verify Slide g7": "L_ver",
    "Verify Backrest gP": "B_ver", "Verify Backrest g7": "B_ver",
    "Correct Length gP": "L_cor", "Correct Slide g7": "L_cor",
    "Correct Backrest gP": "B_cor", "Correct Backrest g7": "B_cor",
}
RX = re.compile(r"Name:(.*)$")
RF = re.compile(r"Finish test \(result:(\w+), finishType:\w+(?:, resultValue:([-\d.,]+))?\)")


def parse(path):
    out, cur, bc = [], None, None
    with open(path, "rb") as fh:
        for raw in fh:
            p = raw.decode("utf-8", "replace").replace("\x00", "").rstrip("\r\n").split("\t")
            if len(p) < 5 or not p[0].startswith("20"):
                continue
            src, msg = p[1], p[4]
            if src == "ParseBarCode" and " as Broadcast" in msg:
                bc = msg.split(":", 1)[1].split(" as ")[0].strip()
            m = RX.search(src)
            if not m:
                continue
            name = m.group(1).strip()
            if name == "MainGroupOfTests" and msg == "Starting test":
                cur = {"t": p[0][11:19], "bc": bc, "v": {}}
                out.append(cur)
                continue
            key = NAMES.get(name)
            f = RF.match(msg)
            if cur is None or not key or not f:
                continue
            val = float(f.group(2).replace(",", ".")) if f.group(2) else None
            # first Calculate params block only (window used by Verify); keep first verify/correct per cycle
            if key in cur["v"]:
                continue
            cur["v"][key] = val
            cur["v"][key + "_ok"] = f.group(1) == "True"
    return out


if __name__ == "__main__":
    base, dst = sys.argv[1:3]
    res = {s: parse(os.path.join(base, s, "Log20261014.txt")) for s in STATIONS}
    json.dump(res, open(dst, "w"))
    for s, c in res.items():
        print(s, len(c), sum("B_ver" in x["v"] for x in c), sum("L_ver" in x["v"] for x in c))
