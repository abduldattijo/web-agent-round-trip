# Web agent round-trip audit

This folder contains a local, deterministic browser fixture for the WebFovea-inspired article. It never visits an external site or calls a model in Phase A.

## Reproduce Phase A

From this folder:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m playwright install chromium
.venv/bin/python audit.py freeze
.venv/bin/python audit.py run
```

The Chromium install line is only needed if the browser is not already cached. `freeze` refuses to overwrite a changed manifest or audit implementation. The final layouts are seeds 10–49. Seeds 0–9 are reserved for development.

`results/phase_a.jsonl` records each browser case. Every policy is evaluated on the same captured trace, with its alert stored in `alerts`. `results/phase_a.summary.json` gives detection and false alarm rates over layouts. Hover and delay cases have three repeats per layout; intervals count each layout once, and `timing_disagreements` records any different outcomes across repeats.

The page event ledger is the scoring oracle. Policy decisions use the page state and screenshots available to the harness and never read the ledger. The local fixture and scoring code were written together, which limits how independent the oracle really is. These rates measure only the injected faults on this site.

## Haiku pilot

The pilot uses development seeds 0 and 1 for each main task. It sends eight screenshots to `claude-haiku-5-5`, executes each model decision once on a clean page, then replays the same decision with the injected defect. It requires `ANTHROPIC_API_KEY`, enforces a $0.05 pilot guard, and writes `results/pilot.jsonl` plus screenshots. Run with `.venv/bin/python pilot.py`.

The visual in `figures/scaled_click_seed1.gif` is an **annotated three-frame screenshot sequence** from the actual pilot, not a continuous browser video. The companion PNG places the before and after states side by side. Green marks the model's intended point in the 900 × 600 image; red marks where the faulty executor clicked in that same image.

## Final decision tape and continuous video

`phase_b.py` uses 20 frozen final layouts per task (seeds 10–29). It calls Haiku once per layout on the clean page, then replays successful decisions with the defect. Its selection, prompt, and implementation hashes are recorded in `PHASE_B_FROZEN.txt`. It can resume from completed JSONL rows without repeating paid decisions. Run with `.venv/bin/python phase_b.py`.

`record_video.py` makes a continuous WebM recording of one recorded Phase B decision: clean execution, page reset, then faulty execution in the same browser tab. It makes no model call. `convert_video_to_gif.py` converts that actual recording into an animated GIF using the cached Playwright FFmpeg binary (or system FFmpeg). Labels and point markers are overlaid for clarity; the browser states and selected buttons are real local fixture outcomes.

`VISUAL_EVIDENCE.md` indexes the WebM, GIF, still click comparison, three captioned screenshot figures, and the results chart. The screenshot figures can be regenerated from saved traces with `.venv/bin/python make_visual_evidence.py`.

## Full-loop comparison

`phase_c.py dev` runs the development cases. The final prompt, policies, scoring, and shard schedule are recorded in `PHASE_C_FROZEN.txt`. The complete final experiment ran four disjoint seed shards (`phase_c.py run --shard 0` through `--shard 3`) with a $0.45 per-shard cap, leaving the total below the $2 project cap. Shards persist one JSONL record per episode. Run `.venv/bin/python analyze_phase_c.py` after all four shards finish to validate and merge exactly 720 episodes, then `.venv/bin/python make_phase_c_figure.py` for the article figure. See `PHASE_C_NOTES.md` for interpretation and caveats.
