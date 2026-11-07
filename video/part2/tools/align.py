"""Word timings from measured pauses: words are spread inside each spoken phrase by length."""
import json, re
VO = {  # line: (global start, [(phrase_start, phrase_end, text), ...]) phrase times measured with silencedetect
 "vo1": (0.35, [(0.05, 0.96, "My spec said"), (1.10, 2.50, "every order costs money."),
                (3.08, 4.72, "Order 65 disagreed:"), (5.19, 5.73, "completed,"), (6.05, 7.25, "paid zero dollars.")]),
 "vo2": (8.45, [(0.05, 1.94, "Specs now start from the data."), (2.62, 5.59, "One command profiles the table and drafts the spec:"),
                (6.15, 7.45, "columns, types, grain"), (7.58, 9.35, "and allowed values.")]),
 "vo3": (18.55, [(0.05, 1.99, "A draft spec only warns."), (2.41, 4.36, "The model meets real data first,"),
                 (4.54, 5.94, "and the build stays green.")]),
 "vo4": (25.35, [(0.05, 1.49, "When the data disagrees,"), (1.70, 2.90, "the agent documents it."),
                 (3.42, 5.20, "A human decides,"), (5.20, 7.40, "and only a clean run makes the spec strict.")]),
 "vo5": (33.7, [(0.05, 2.61, "Contracts and data tests check structure."), (3.23, 4.85, "The next layer checks behaviour."),
                (5.57, 7.61, "Delete a business rule from the SQL,"), (7.80, 9.38, "and the structure still looks fine.")]),
 "vo6": (44.1, [(0.05, 2.70, "So every rule in the spec carries examples:"), (3.07, 3.80, "rows in,"), (3.95, 4.62, "rows out,"),
                (5.01, 6.84, "run as dbt unit tests."), (7.37, 9.31, "Delete the rule, and the build fails,"),
                (9.44, 10.94, "showing the exact rows.")]),
 "vo7": (55.95, [(0.05, 1.02, "Start from the data."), (1.56, 2.82, "Verify the behaviour."), (3.29, 4.56, "Part two is in the repo.")]),
}
def weight(w):
    w2 = re.sub(r"\W", "", w)
    if w2 == "dbt": return 5.0
    if w2 == "65": return 7.0
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
