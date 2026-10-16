"""Parse Rockwell tester EOL logs into per-cycle / per-test timing records.

Usage: python3 parse_logs.py <ProcessAnalysis dir> <out.json>
"""
import json, os, re, sys
from datetime import datetime

STATIONS = ["EOL1L", "EOL1R", "EOL5L", "EOL5R", "EOL20", "EOL21"]
RX_TEST = re.compile(r"Id: (\d+) TotId: (\d+) Hash:\d+ Name:(.*)$")
RX_FIN = re.compile(r"Finish test \(result:(\w+), finishType:(\w+)(?:, resultValue:[^)]*)?\)")


def ts(s):
    return datetime.strptime(s[:23], "%Y-%m-%d %H:%M:%S.%f").timestamp()


def parse(path):
    cycles, cur, last_end = [], None, None
    barcode = {}
    with open(path, "rb") as fh:
        for raw in fh:
            line = raw.decode("utf-8", "replace").replace("\x00", "").rstrip("\r\n")
            p = line.split("\t")
            if len(p) < 5 or not p[0].startswith("20"):
                continue
            t = ts(p[0])
            src, msg = p[1], p[4]
            if src == "ParseBarCode" and " as Broadcast" in msg:
                barcode = {"broadcast": msg.split(":", 1)[1].split(" as ")[0].strip(), "t": t}
            elif src == "ParseBarCode" and " as CarNumber" in msg:
                barcode["carnumber"] = msg.split(":", 1)[1].split(" as ")[0].strip()
            elif "oRobotAut = " in msg and cur is not None:
                cur["robot"] = msg.endswith("True")
            m = RX_TEST.search(src)
            if m:
                tid, tot, name = m.group(1), m.group(2), m.group(3).strip()
                if msg == "Starting test":
                    if tid == "0":  # MainGroupOfTests
                        cur = {"main_start": t, "prev_end": last_end, "barcode": barcode,
                               "tests": {}, "robot": None}
                        barcode = {}
                    elif cur is not None:
                        cur["tests"].setdefault(tid, {"name": name, "runs": []})["runs"].append([t, None, None])
                    continue
                f = RX_FIN.match(msg)
                if f and cur is not None:
                    if tid == "0":
                        cur["main_end"] = t
                        cur["main_ok"] = f.group(1) == "True"
                    else:
                        e = cur["tests"].get(tid)
                        if e:
                            for r in reversed(e["runs"]):
                                if r[1] is None:
                                    r[1], r[2] = t, f.group(1) == "True"
                                    break
                continue
            if msg.startswith("onTestsFinished") or msg.startswith("Tests_TestsFinished :"):
                if cur is not None and "main_end" in cur and "cycle_end" not in cur:
                    cur["cycle_end"] = t
                    cycles.append(cur)
                    cur = None
                last_end = t
    return cycles


if __name__ == "__main__":
    base, out = sys.argv[1], sys.argv[2]
    res = {}
    for s in STATIONS:
        res[s] = parse(os.path.join(base, s, "Log20261014.txt"))
        print(s, len(res[s]), "cycles")
    json.dump(res, open(out, "w"))
