# Phase B: final-layout decision tape and continuous video

Run date: 2026-10-16. Model: `claude-haiku-5-5`, thinking disabled. Selection: seeds 10–29 of the frozen 40-layout manifest for each of the four tasks, fixed in [PHASE_B_FROZEN.txt](PHASE_B_FROZEN.txt) before calls. The same prompt and 900 × 600 screenshot format as the pilot were used. [Raw decisions and ledgers](results/phase_b.jsonl) · [summary](results/phase_b.summary.json).

| Task | Clean decision succeeded | Successful decision replayed | Faulty round trip succeeded |
|---|---:|---:|---:|
| Exact search | 20/20 | 20 | 0/20 |
| Target click | 20/20 | 20 | 0/20 |
| Iframe selection | 20/20 | 20 | 0/20 |
| Chart hover | 20/20 | 20 | 0/20 |

The 80 model calls used 71,920 input tokens and 1,460 output tokens and cost **$0.007922**. Median API latency was 1.038 seconds (range 0.838–2.934). Every successful clean decision was replayed; none were discarded. Of the 20 faulty coordinate clicks, 11 selected another button and nine hit empty space. All 20 clean target clicks selected the requested button.

The defect failures were injected deliberately, so 0/80 is not an estimate of live-site error frequency. The 80/80 clean result shows Haiku can act on these simple local fixtures. It does not establish accuracy on real websites or harder tasks. Phase C must still test whether feedback checks and retries improve end-to-end outcomes; Phase A and B only show fault detection and decision replay.

## Continuous browser recording

[Watch the continuous WebM](figures/continuous_model_click_seed12.webm) · [GIF converted from that video](figures/continuous_model_click_seed12.gif) · [clean frame](figures/video_frame_clean.png) · [faulty frame](figures/video_frame_faulty.png)

The recording replays a **previously logged model decision** on seed 12 in one browser tab. Haiku replied `{"action":"click","x":150,"y":413}` for a 900 × 600 screenshot instructing it to click Item 15. Correct coordinate conversion dispatched at `(200, 550.67)` CSS pixels and the ledger recorded `button-15`. After a page reset, the injected executor dispatched the same image coordinates as CSS pixels, `(150, 413)`, and the ledger recorded `button-10`. The visible page selected Item 10. [Video provenance and both ledgers](figures/continuous_model_click_seed12.json).

The video is continuous local browser footage, approximately 11 seconds, at 900 × 600. The explanatory banner and colored point markers were overlaid during recording; the selected button states and event ledger were produced by the page. It is a replay of the recorded decision, not a live model call within the video, and it is not footage of an external website.
