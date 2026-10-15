"""Build the HTML overview from summary.json.  Usage: python3 build_report.py <summary.json> <out.html>"""
import html, json, sys

d = json.load(open(sys.argv[1]))
ST = list(d)
HW = {"EOL1L": "PLC (gP)", "EOL1R": "PLC (gP)", "EOL5L": "PLC (gP)", "EOL5R": "PLC (gP)",
      "EOL20": "IO1978 (g7)", "EOL21": "IO1978 (g7)"}
SIDE = {"EOL1L": "left", "EOL1R": "right", "EOL5L": "left", "EOL5R": "right", "EOL20": "left", "EOL21": "right"}
f1 = lambda x: f"{x:.1f}"
med = lambda s, k: d[s]["phases"][k]["med"]

GROUPS = [
    ("Handling & waiting", "s1", lambda s: d[s]["load_time"]["med"]),
    ("Setup: assembly check, grounding", "s2", lambda s: sum(med(s, k) for k in ["Init & parameter calc", "Check assembly position", "Grounding & isolation check", "Grounding release"])),
    ("PSM power-up & diagnostics", "s3", lambda s: sum(med(s, k) for k in ["Start parallel tests + PSM power-up", "PSM reset & diag start"])),
    ("Component tests (in line)", "s4", lambda s: sum(med(s, k) for k in ["Short to ground", "Ventilation, SBR unload, Lumbar", "Massage (option) + wait for parallel tests"])),
    ("Movements", "s5", lambda s: med(s, "Movements")),
    ("Expedition, final CAN, unplug", "s6", lambda s: med(s, "Expedition position & final CAN") + d[s]["finish_time"]["med"]),
]

# ---------- stacked bar: median cycle composition ----------
W, LW, RH, GAP = 760, 70, 30, 14
mx = max(sum(g[2](s) for g in GROUPS) for s in ST)
scale = (W - LW - 60) / 150
rows = []
for i, s in enumerate(ST):
    y, x = 10 + i * (RH + GAP), LW
    segs = []
    for name, cls, fn in GROUPS:
        v = fn(s); w = v * scale
        segs.append(f'<rect class="{cls}" x="{x:.1f}" y="{y}" width="{max(w-2,0):.1f}" height="{RH}" rx="2"><title>{s} · {name}: {v:.1f} s</title></rect>')
        if w > 26:
            segs.append(f'<text class="seglbl" x="{x + w/2 - 1:.1f}" y="{y + RH/2 + 4}" text-anchor="middle">{v:.0f}</text>')
        x += w
    tot = sum(g[2](s) for g in GROUPS)
    rows.append(f'<text class="axl" x="{LW-8}" y="{y + RH/2 + 4}" text-anchor="end">{s}</text>' + "".join(segs) +
                f'<text class="axv" x="{x + 6:.1f}" y="{y + RH/2 + 4}">{tot:.0f} s</text>')
H = 10 + len(ST) * (RH + GAP) + 20
ticks = "".join(f'<line class="grid" x1="{LW + t*scale}" x2="{LW + t*scale}" y1="4" y2="{H-22}"/><text class="axt" x="{LW + t*scale}" y="{H-6}" text-anchor="middle">{t}</text>' for t in range(0, 151, 30))
bar_svg = f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Median cycle composition per station">{ticks}{"".join(rows)}</svg>'
legend = "".join(f'<span class="lg"><i class="{c}"></i>{html.escape(n)}</span>' for n, c, _ in GROUPS)

# ---------- Gantt per station ----------
SEQ = ["Init & parameter calc", "Check assembly position", "Grounding & isolation check", "Short to ground", "Grounding release",
       "Start parallel tests + PSM power-up", "PSM reset & diag start", "Ventilation, SBR unload, Lumbar",
       "Massage (option) + wait for parallel tests", "Movements", "Expedition position & final CAN"]
COMPONENT_SEQ = {"Short to ground", "Ventilation, SBR unload, Lumbar", "Massage (option) + wait for parallel tests", "Movements"}
PAR = ["Airbags (SAB/FSAB)", "Belt buckle", "STPS", "SBR (occupant sensor)", "Mood light", "Heating"]


def gantt(s):
    gw, glw, rh = 760, 250, 19
    sc = (gw - glw - 20) / 100
    out, y, t = [], 8, 0.0
    for k in SEQ:
        v = med(s, k)
        cls = "gc" if k in COMPONENT_SEQ else "gs"
        out.append(f'<text class="gl" x="{glw-8}" y="{y+13}" text-anchor="end">{html.escape(k)}</text>'
                   f'<rect class="{cls}" x="{glw + t*sc:.1f}" y="{y+2}" width="{max(v*sc,1.5):.1f}" height="{rh-5}" rx="2"><title>{k}: starts {t:.1f} s, lasts {v:.1f} s (median)</title></rect>'
                   f'<text class="gv" x="{glw + (t+v)*sc + 4:.1f}" y="{y+13}">{v:.1f}</text>')
        t += v; y += rh
    y += 8
    out.append(f'<text class="gh" x="{glw-8}" y="{y+10}" text-anchor="end">Running in background</text>'); y += rh
    for k in PAR:
        c = d[s]["components"][k]
        if not c["dur"]:
            continue
        o, v = c["start_offset"]["med"], c["dur"]["med"]
        out.append(f'<text class="gl" x="{glw-8}" y="{y+13}" text-anchor="end">{html.escape(k)}</text>'
                   f'<rect class="gp" x="{glw + o*sc:.1f}" y="{y+2}" width="{max(v*sc,1.5):.1f}" height="{rh-5}" rx="2"><title>{k}: starts {o:.1f} s, lasts {v:.1f} s (median)</title></rect>'
                   f'<text class="gv" x="{glw + (o+v)*sc + 4:.1f}" y="{y+13}">{v:.1f}</text>')
        y += rh
    gh = y + 24
    tk = "".join(f'<line class="grid" x1="{glw + x*sc}" x2="{glw + x*sc}" y1="4" y2="{gh-20}"/><text class="axt" x="{glw + x*sc}" y="{gh-6}" text-anchor="middle">{x} s</text>' for x in range(0, 101, 10))
    return f'<svg viewBox="0 0 {gw} {gh}" role="img" aria-label="Test timeline {s}">{tk}{"".join(out)}</svg>'


gantts = "".join(f'<figure class="gantt" id="g-{s}" {"" if i == 0 else "hidden"}>{gantt(s)}</figure>' for i, s in enumerate(ST))
tabs = "".join(f'<button type="button" class="tab" id="tab-{s}" data-s="{s}" aria-pressed="{str(i == 0).lower()}">{s}</button>' for i, s in enumerate(ST))

# ---------- tables ----------
def hdr():
    return "<tr><th></th>" + "".join(f'<th>{s}<small>{HW[s]}</small></th>' for s in ST) + "</tr>"

kpi = [("Seats tested", lambda s: str(d[s]["cycles"])),
       ("of which SPA-3", lambda s: str(d[s]["spa3"])),
       ("NOK seats", lambda s: str(d[s]["nok"])),
       ("Main test time, median", lambda s: f1(d[s]["main_time"]["med"]) + " s"),
       ("Main test time, p10–p90", lambda s: f'{d[s]["main_time"]["p10"]:.0f}–{d[s]["main_time"]["p90"]:.0f} s'),
       ("Handling & waiting, median", lambda s: f1(d[s]["load_time"]["med"]) + " s"),
       ("Finish / unplug, median", lambda s: f1(d[s]["finish_time"]["med"]) + " s"),
       ("Seat-to-seat tact, median", lambda s: f1(d[s]["tact"]["med"]) + " s"),
       ("Stops ≥ 5 min (count / min)", lambda s: f'{d[s]["stoppages"]["count"]} / {d[s]["stoppages"]["minutes"]:.0f}')]
kpi_rows = "".join(f"<tr><th>{n}</th>" + "".join(f"<td>{fn(s)}</td>" for s in ST) + "</tr>" for n, fn in kpi)

comp_rows = ""
for k in d[ST[0]]["components"]:
    vals = [d[s]["components"][k] for s in ST]
    meds = [v["dur"]["med"] for v in vals if v["dur"]]
    lo, hi = min(meds), max(meds)
    cells = ""
    for v in vals:
        m = v["dur"]["med"]
        flag = ' class="hi"' if hi - lo > 1.5 and m == hi else ""
        cells += f'<td{flag}>{m:.1f}<small>{v["share"]}% · start {v["start_offset"]["med"]:.0f} s{" · " + str(v["fail"]) + " fail" if v["fail"] else ""}</small></td>'
    mode = '<span class="pill par">background</span>' if vals[0]["parallel"] else '<span class="pill seq">in line</span>'
    comp_rows += f"<tr><th>{k} {mode}</th>{cells}</tr>"

axis_rows = ""
for k in d[ST[0]]["axes"]:
    meds = [d[s]["axes"][k]["med"] for s in ST]
    lo = min(meds)
    axis_rows += f"<tr><th>{k}</th>" + "".join(
        f'<td{" class=hi" if m - lo > 2 else ""}>{m:.1f}<small>{d[s]["axes"][k]["share"]}%</small></td>' for m, s in zip(meds, ST)) + "</tr>"

phase_rows = "".join(f"<tr><th>{k}</th>" + "".join(f'<td>{med(s,k):.1f}<small>p90 {d[s]["phases"][k]["p90"]:.1f}</small></td>' for s in ST) + "</tr>" for k in SEQ)

spa3 = "".join(f'<tr><th>{s}</th><td>{len(d[s]["spa3_detail"])}</td><td>{", ".join(f1(x["main"]) for x in d[s]["spa3_detail"])}</td><td>{", ".join(f1(x["calibration"]) for x in d[s]["spa3_detail"])}</td></tr>' for s in ST)
nok = "".join(f'<tr><th>{s}</th><td>{d[s]["nok"]}</td><td>{", ".join(f"{k} ×{v}" for k, v in d[s]["nok_by_component"].items()) or "–"}</td></tr>' for s in ST)

tpl = open(__file__.replace("build_report.py", "report_template.html")).read()
for k, v in {"BAR": bar_svg, "LEGEND": legend, "TABS": tabs, "GANTTS": gantts, "HDR": hdr(), "KPI": kpi_rows,
             "COMP": comp_rows, "AXES": axis_rows, "PHASES": phase_rows, "SPA3": spa3, "NOK": nok}.items():
    tpl = tpl.replace("{{" + k + "}}", v)
open(sys.argv[2], "w").write(tpl)
print("written", sys.argv[2])
