# Phase A: frozen local harness audit

Run date: 2026-10-16. Final layouts: 40 per task (seeds 10–49). The manifest and audit/site SHA-256 hashes are in [FROZEN.txt](FROZEN.txt). Playwright 1.64.0 and Pillow 12.3.0 ran in the project venv using cached Chromium. No model calls or API charges. Full traces: [results/phase_a.jsonl](results/phase_a.jsonl). Machine-readable intervals: [results/phase_a.summary.json](results/phase_a.summary.json).

The 720 browser cases represent 40 clean and 40 defective cases for each of the four main tasks, with three timing repeats for hover, plus 40 cases for each extra fault, with three repeats for delay. All four policies read each case's captured evidence. The unit for the Wilson intervals is the layout (40), not each timing repeat. No timing outcome disagreed across repeats.

| Main task | Unverified | Generic | Pixel change | Round trip |
|---|---:|---:|---:|---:|
| Wrong query token: detected / false alarms | 0/40 / 0/40 | 0/40 / 0/40 | 3/40 / 40/40 | 40/40 / 0/40 |
| Scaled click: detected / false alarms | 0/40 / 0/40 | 20/40 / 0/40 | 20/40 / 0/40 | 40/40 / 0/40 |
| False iframe feedback: detected / false alarms | 0/40 / 0/40 | 40/40 / 40/40 | 0/40 / 0/40 | 40/40 / 0/40 |
| Missing hover tooltip: detected / false alarms | 0/40 / 0/40 | 40/40 / 0/40 | 40/40 / 0/40 | 40/40 / 0/40 |

Each entry is **detected failures / false alarms on successful round trips**. The 95% Wilson interval is [0, 0.088] for 0/40, [0.352, 0.648] for 20/40, and [0.912, 1] for 40/40. The 3/40 detection interval is in the JSON summary.

The four extra faults (delayed render, below-fold target, overlay, disabled button) each failed at the first observation in all 40 layouts. Generic, pixel, and round-trip checks alerted on all 40 for each fault; unverified alerted on none. No clean comparison was run for these extra faults, so their false alarm rates are undefined. For delayed render, the click did fire and the state appeared later in all 40 layouts. That is an early-observation failure, not a lost action.

## Trace inspection

- **Wrong query, seed 10:** the ledger records `Record-10[im_end]` submitted; the field contains the same text and the page reports no exact result. Generic sees a changed status and does not alert. The pixel change (0.002017) narrowly passes its frozen 0.002 threshold. With the clean query, the page finds `Record-10`, yet pixel change is 0.001833 and triggers a false alarm. This check is threshold-sensitive here, not a reliable parsing detector. Defective seeds 11, 41, and 49 did trigger it; all 40 clean cases were false alarms.
- **Scaled click, seed 10:** the correct center is `(740, 446)` CSS pixels. The faulty executor dispatches at `(555, 335)`. The ledger records `button-7`, rather than the intended button. Generic and pixel checks see a changed page and miss the wrong target. Across 40 layouts, 20 wrong clicks landed on another button and 20 landed on empty stage; the two coarse checks caught only the empty-stage cases.
- **Iframe, seed 10:** the ledger confirms `row-4` was selected. Clean feedback says `Selected row-4`; faulty feedback says `No detectable change`. Generic flags both because the top page does not change, giving 40 false alarms. Pixel sees the successful visual change in both and misses the false report. Round-trip comparison reads the child frame and catches the mismatch.
- **Hover, seed 10:** the ledger records the hover, but the early capture has no visible tooltip. At the later clean capture the tooltip appears. The generic and pixel checks work for this specific visible tooltip; this does not show they would work for every observation defect.
- **Delay, seed 10:** at 100 ms the page says `Ready` and the button is not selected, so all three checking policies alert. The ledger later confirms `activated`. A retry at the first capture could therefore be unnecessary; Phase C must measure whether checking improves end-to-end behavior.

These injected faults and the exact-outcome round-trip checks are closely matched by construction. A 40/40 detection result validates this fixture's instrumentation; it does **not** estimate performance on real websites. The most useful article cases are the wrong-button click that coarse checks miss, and the iframe feedback fault where the action succeeds but the report lies. No model decision has been recorded yet, so the article cannot yet claim that a model chose the right button.
