# The explainer videos

- `hyperframes/`: part 1, the spec → contract → SQL → verify loop.
- `part2/`: part 2, specs drafted from data (draft → enforced) and rule examples as dbt unit tests.

Each is a 60-second square video of the demo, made with [HyperFrames](https://hyperframes.heygen.com)
(HTML rendered to MP4). Voice, music and sound effects were generated with ElevenLabs.

```bash
cd video/hyperframes   # or video/part2
npx hyperframes preview          # edit and scrub in the browser
npx hyperframes render -o out.mp4
```

- `index.html` mounts one scene per file in `compositions/` and places the audio.
- `SPEC.md` is the director's brief: look, timing and every shot.
- `words.json` holds word timings measured from the voiceover; `tools/align.py` and
  `tools/captions.py` rebuild them and the captions.
- Repo link on the end card is a variable (`repo-url`) on `index.html`.
