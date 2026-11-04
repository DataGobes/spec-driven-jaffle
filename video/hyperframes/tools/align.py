"""Word timings from measured pauses: words are spread inside each spoken phrase by length."""
import json, re
VO = {  # line: (global start, [(phrase_start, phrase_end, text), ...]) phrase times measured with silencedetect
 "vo1": (0.4, [(0.0, 2.68, "Your coding agent just wrote a new dbt model."), (3.08, 3.77, "It runs."),
               (4.26, 4.42, "But"), (4.65, 7.08, "does it do what the business actually asked for?")]),
 "vo2": (8.7, [(0.0, 1.58, "Start with a spec instead."), (2.12, 2.73, "Grain,"), (2.96, 3.53, "types,"),
               (3.73, 5.54, "allowed values and business rules,"), (6.04, 7.42, "reviewed by a human"),
               (7.55, 8.75, "before any code exists.")]),
 "vo3": (18.3, [(0.0, 4.43, "A small generator turns that spec into an enforced dbt contract,"),
                (4.63, 5.92, "plus seven tests."), (6.53, 8.36, "Platform conventions come along for free.")]),
 "vo4": (27.7, [(0.0, 2.20, "Then the agent writes the SQL."), (2.82, 4.11, "Every rule from the spec,"),
                (4.46, 5.79, "implemented literally."), (6.30, 8.20, "And it is not allowed to change the spec.")]),
 "vo5": (37.1, [(0.0, 2.75, "dbt build checks it against real data."), (3.25, 3.80, "Grain,"),
                (3.97, 5.50, "references, ranges"), (5.62, 6.52, "and row counts."),
                (6.95, 7.76, "Twenty tests."), (8.13, 8.76, "All green.")]),
 "vo6": (47.3, [(0.0, 1.01, "One spec in."), (1.58, 2.95, "One tested table out:"),
                (3.38, 4.12, "every customer,"), (4.46, 5.32, "with a value tier.")]),
 "vo7": (54.4, [(0.0, 1.97, "The spec is the source of truth."), (2.48, 5.33, "The SQL is just its latest implementation.")]),
}
def weight(w):
    w2 = re.sub(r"\W", "", w)
    if w2 == "dbt": return 5.0
    if w2 == "SQL": return 4.0
    return 1.2 + len(w2)
out = []
for line, (g0, phrases) in VO.items():
    for (a, b, text) in phrases:
        ws = text.split(); tot = sum(weight(w) for w in ws); t = a
        for w in ws:
            d = (b - a) * weight(w) / tot
            out.append({"line": line, "text": w, "start": round(g0 + t, 2), "end": round(g0 + t + d, 2)})
            t += d
json.dump(out, open("words.json", "w"), indent=1)
for o in out: print(o["line"], f'{o["start"]:6.2f}', o["text"])
