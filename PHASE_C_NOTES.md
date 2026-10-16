# Phase C: did checking improve task completion?

Run date: 2026-10-16. The complete [merged action log](results/phase_c.jsonl), [machine-readable summary](results/phase_c.summary.json), [frozen implementation record](PHASE_C_FROZEN.txt), and [result figure](figures/phase_c_success.png) are available here. All 720 expected task × layout × policy × run combinations are present once. All 1,486 model replies parsed, all 1,486 action screenshots exist, and no episode exceeded three browser actions.

Each episode began with the **same correct Haiku 5.5 decision** recorded for that task and layout in Phase B. The faulty executor or feedback was then used. The model saw the next 900 × 600 screenshot and feedback from one of three policies: unverified, generic top-page change, or task-specific round-trip checking. It could stop, retry, or wait, up to three browser actions. Each policy ran three times on the same 20 layouts. Follow-up responses used a fixed JSON schema after a development run found that free-form replies could be truncated before their JSON action. The earlier development traces are archived; the schema and policy code were frozen before final results.

The first final attempt was stopped after a small partial serial log because 720 serial episodes would take too long. That log and its freeze record are archived and **excluded** from the final denominator. The execution schedule changed to four disjoint seed shards; the prompts, faults, policies, scoring rules, and layouts did not change. The final shards have 180 episodes each and were merged only after all completed.

## Results

Each cell below is successful episodes out of 60 (20 layouts × 3 runs). A successful chart task requires the correct numeric value **from a captured observation**, not a tooltip that appeared later while the model was responding.

| Task | Unverified | Generic check | Round-trip check |
|---|---:|---:|---:|
| Exact search with appended token | 0/60 | 0/60 | 0/60 |
| Click with wrong coordinate mapping | 0/60 | 0/60 | 0/60 |
| Iframe click with false feedback | 60/60 | 60/60 | 60/60 |
| Chart tooltip captured too early | 56/60 | 60/60 | 60/60 |

The only observed success difference was on the chart task: either check gained **4/60 episodes** (+6.7 percentage points) over unverified. The paired 95% bootstrap interval, resampling the 20 layouts with all three runs kept together, is **[0, +15] points**. It includes zero. There was no observed success difference on the other three tasks. The chart runs were 18/20, 19/20, 19/20 for unverified and 20/20 in every run for each check.

| Policy | Successes across all tasks | Mean browser actions | Median episode time | Follow-up model cost / episode |
|---|---:|---:|---:|---:|
| Unverified | 116/240 | 2.046 | 3.028 s | $0.000316 |
| Generic | 120/240 | 2.046 | 2.859 s | $0.000324 |
| Round trip | 120/240 | 2.100 | 3.239 s | $0.000358 |

These cost figures include Phase C follow-up calls only. The shared initial decisions were billed in Phase B at about **$0.000099 each** and replayed across policies and runs. Phase C used **$0.239535** in logged API calls. All logged API work for this article, including both development versions, the interrupted serial portion, the pilot, Phase B, and Phase C, totals about **$0.267166**, well below the $2 cap. An interrupted in-flight request might add a small unlogged charge, so the exact provider bill should be checked separately if needed. Timing is wall-clock time in this local, four-shard run; the small median differences should not be treated as a speed ranking.

## What the traces explain

- **Persistent parser fault:** on `search_token` seed 10, the round-trip check read back `Record-10[im_end]` and correctly reported that it differed from `Record-10`. A retry still passed through the same parser, leaving the corrupted query and no exact result. The check diagnosed the failure but could not remove the appended token.
- **Persistent coordinate fault:** on `scaled_click` seed 12, Haiku's recorded image coordinate `(150, 413)` correctly selected Item 15 on the clean page. The faulty executor used it as CSS coordinates and selected Item 10. Even after the round-trip report identified Item 10 and supplied the target's CSS center, the model repeated `(150, 413)` under the fixed image-coordinate instruction. Three wrong clicks did not become a correct one. The [continuous video](figures/continuous_model_click_seed12.webm) shows the clean and faulty replay of this same decision.
- **False iframe feedback:** every episode selected the intended row; the faulty text still said “No detectable change.” The model could see the selected row and stopped successfully with all three policies. The generic check caused four needless second clicks across 60 iframe episodes; the round-trip check correctly read the frame and needed no second click.
- **Early tooltip:** on `hover_value` seed 21, run 1, the unverified model stopped after a screenshot with no tooltip or value and was scored wrong. Generic feedback led it to hover again; round-trip feedback led it to wait 500 ms. Both then captured `Value: 89` and answered correctly. The four unverified misses occurred on three layouts; the seed-grouped uncertainty interval includes zero.

The observed answer to the article's question is that **better checking exposed the faults, but did not reliably repair persistent parser or coordinate bugs**. On this fixture it offered a small, uncertain gain for a delayed observation, and the simple generic check matched the task-specific check on completion. A page action can succeed while tool feedback lies, as the iframe case shows. The chart and video are controlled demonstrations, not estimates of how often these faults occur on live websites.

## Limits for the article

- One local site, simple instructions, same-origin iframe, one model and prompt, 20 selected final layouts, three runs. The 20 layouts were selected before Phase C from the frozen 40-layout set.
- Every Phase C episode was conditioned on an initially correct Phase B decision. This isolates the harness problem but does not measure end-to-end accuracy from a new model decision on every episode.
- Faults were deliberately persistent on retries. Detection could not fix an executor or parser that kept making the same error. A system that changes its executor after diagnosis might behave differently and was not tested.
- The page ledger and checking code were built for the same fixture. Round-trip checks are matched to the injected faults by design; Phase A's detection rates should not be generalized.
- The three runs measure variability within this setup. The bootstrap interval groups repeated runs by layout; it does not cover different sites, prompts, models or browser engines.
