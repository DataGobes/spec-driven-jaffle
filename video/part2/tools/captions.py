"""Build compositions/captions.html from words.json: 3-5 word groups, one on screen at a time."""
import json, html
words = json.load(open("words.json"))
# on-screen type already says these lines: no captions there
# on-screen type already says these: "Order 65 disagreed" on the hook, the whole closing card
skip = lambda w: (w["line"] == "vo1" and 3.3 <= w["start"] < 5.2) or w["line"] == "vo7"
import math
phrases, cur = [], []
for w in words:
    if skip(w):
        if cur: phrases.append(cur); cur = []
        continue
    if cur and (cur[-1]["line"] != w["line"] or w["start"] - cur[-1]["end"] > 0.1):
        phrases.append(cur); cur = []
    cur.append(w)
    if w["text"][-1] in ".?:":
        phrases.append(cur); cur = []
if cur: phrases.append(cur)
def chunks(ph):
    """At most 5 words per caption; split long phrases at a comma, else in the middle."""
    if len(ph) <= 5:
        return [ph]
    commas = [i + 1 for i, w in enumerate(ph[:-1]) if w["text"].endswith(",")]
    mid = len(ph) / 2
    cut = min(commas, key=lambda i: abs(i - mid)) if commas else math.ceil(mid)
    return chunks(ph[:cut]) + chunks(ph[cut:])
merged = [c for ph in phrases for c in chunks(ph)]
rows, js = [], []
for i, g in enumerate(merged):
    start = g[0]["start"] - 0.05
    nxt = merged[i + 1][0]["start"] - 0.05 if i + 1 < len(merged) else 99
    end = min(g[-1]["end"] + 0.6, nxt)
    text = html.escape(" ".join(w["text"] for w in g))
    rows.append(f'      <div class="cp-g" id="cp-{i}">{text}</div>')
    js.append(f"[{start:.2f},{end:.2f}]")
out = f'''<template>
  <style>
    #root {{ position: absolute; inset: 0; }}
    .cp-g {{
      position: absolute; left: 0; right: 0; top: 948px; text-align: center; overflow: visible;
      font: 600 36px/1.2 var(--font-display); color: var(--color-ink); opacity: 0;
    }}
  </style>
  <div id="root" data-composition-id="captions" data-width="1080" data-height="1080">
    <div id="cp-stage" class="clip" data-start="0" data-duration="62.6" data-layout-allow-caption-zone>
{chr(10).join(rows)}
    </div>
  </div>
  <script>
    const tl = gsap.timeline({{ paused: true }});
    const T = [{",".join(js)}];
    T.forEach(([a, b], i) => {{
      const g = "#cp-" + i;
      tl.fromTo(g, {{ opacity: 0 }}, {{ opacity: 1, duration: 0.08, ease: "none" }}, a);
      tl.to(g, {{ opacity: 0, duration: 0.08, ease: "power2.in" }}, b - 0.08);
      tl.set(g, {{ opacity: 0, visibility: "hidden" }}, b);
    }});
    window.__timelines["captions"] = tl;
  </script>
</template>
'''
open("compositions/captions.html", "w").write(out)
for i, g in enumerate(merged): print(i, " ".join(w["text"] for w in g))
