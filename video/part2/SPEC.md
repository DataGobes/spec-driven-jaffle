GOAL:    Part 2 of the series. A data engineer sees two extensions in one minute: specs that start from
         the data (draft → enforced), and business rules verified by behaviour (examples → dbt unit tests).
         Ends wanting to clone the repo.
OUTPUT:  HyperFrames, 1080 x 1080 (LinkedIn feed, square), 30 fps
TIME:    ~60 s. Narrated: the voice is the clock. Same music bed as part 1 at 0.14.
LOOK:    Same as part 1: real terminal and editor windows on a warm concrete ground.
         ground #DCD8CF; ink #1A1C1F; windows #15181C, bar #23272D, 14 px radius.
         Semantic colour only: amber #E8A33D = from the spec; steel #5FA8C8 = generated / profiled;
         green #3FB46A = passed; red #D9624B = data disagrees / failed (new in part 2).
         Readability fix vs part 1: code 30 px / 44 px line, at most 8 lines per window, labels 26 px.
OBJECTS: rows window (fct_orders, real rows 62–68); terminal; draft spec window; findings window;
         SQL window; examples window. Chapter chip at top: "Extension 1 · Start from the data",
         "Extension 2 · Verify behaviour".
SHOTS:   S1 hook: real rows, order 65 ($0.00) lights red against the spec line amount > 0.
         S2 draft: terminal runs specgen draft; draft spec with profiled values in steel.
         S3 warn: dbt build, WARN 1, "PASS=7 WARN=1 ERROR=0", build stays green.
         S4 decide: finding → human decision → amount >= 0 → promote refused, then enforced.
         S5 structure: SQL line with the returned-orders rule is struck out; data tests still 7/7 green.
         S6 behaviour: rule example (given / expect) → unit test FAIL with the real diff 10.00 → 159.00.
         S7 close: two lines of type; repo; hold.
BANNED:  as part 1.
