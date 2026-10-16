# Your Web Agent Chose the Right Button and Still Clicked the Wrong One

Status: Phase A, the Haiku pilot, Phase B, and Phase C completed (2026-10-16). The local fixture, frozen 40-layout manifest and free audit are in this folder. Results and trace review are in `PHASE_A_NOTES.md`; the model pilot is in `PILOT_NOTES.md`; final-layout decisions and video are in `PHASE_B_NOTES.md`; full-loop outcomes are in `PHASE_C_NOTES.md`. The revised article draft is in `draft.md`, its previous version is in `draft.before_editorial_revision_2026-10-16.md`, and visuals are indexed in `VISUAL_EVIDENCE.md`. Your original plan is kept in `v1_original/`.

## Reader question

When a browser agent fails, how can we tell whether its decision was wrong or whether the software carrying that decision to and from the page failed?

The article's contribution is a repeatable way to record the full round trip and check the page's real state, plus honest numbers on what each kind of check can and cannot see. It is not a reproduction of WebFovea's challenge score.

## What I checked against the paper (arXiv 2610.03036v2, read 2026-10-16)

| Claim in plan v1 | What the paper says | Verdict |
|---|---|---|
| Four stages: parsing, execution, feedback, observation | Same four stages (the abstract words them as parse, take effect, report, show) | Correct |
| One model across four submissions, 31 to 57 | Same model (claude-opus-4-6 per the html) in all four submissions, 31.0 to 57.0, hidden set | Correct |
| Gains cannot be assigned to one fix | Section 5.2 explicitly says each submission bundled several changes, so gains cannot be attributed to single components. Component evidence is from small targeted sets. It estimates about 7 of the first 10 points came from finishing more tasks | Correct. Attribute the score trajectory to bundled harness revisions, not one fix |
| Clicks landed at three quarters of intended coordinates | "Every click at 3/4 of its intended coordinates", from API downscaling plus the reference code's mapping | Correct. My 900 x 600 over 1200 x 800 mirrors it by construction, so say so |
| Iframe feedback fault | Paper: a successful iframe click was reported as "no detectable change". Its click probe was on a **cross-origin** iframe, and clicks had no effect | Our same origin frame is a different, easier case. State this |
| Template tokens | 15 of 305 episodes (4.9%), 12 of 13 scorable ones failed. Success 7.7% against 41.7%, called observational | Do not quote these as our result |
| Playwright source | Mouse coordinates are CSS pixels relative to the main frame's viewport | Cite the core API page (`playwright.dev/python/docs/api/class-mouse`). The CLI page cited in v1 is the command line tool, not the library |
| Code at github.com/jianganghan/WebFovea | Paper v2 adds a code link | Inspected source at commit `4b75e10722e2f9c1c662f16dbb8319fe2a33188f`. Treat as a reference, not our result |

The paper's HTML tables and the relevant released source paths have now been inspected. The article still needs to cite the paper for reported outcomes and distinguish our local fixtures from its live-site runs.

## Problems I found in plan v1, and the fixes

1. **Replay of injected bugs proves very little.** With one layout per task, a deliberately broken executor fails and a fixed one passes. That is built in. Four tasks give four data points.
   **Fix:** many layouts per task (see Phase A) and clean cases where nothing is broken.
2. **No measure of false alarms.** A check that always alerts "catches" every fault.
   **Fix:** every task also runs with the defect off. Report detection rate and false alarm rate for each check, with ranges.
3. **The checks could be written to fit the bugs.** Then catching them proves nothing.
   **Fix:** an independent oracle (below) decides what really happened. Checks are written as general rules and frozen. A "surprise" set of four failures the checks were not written for shows what slips through.
4. **The "decisions" in the tape were hand written.**
   **Fix:** record real model decisions on a clean harness, keep the ones that succeeded, and replay those through the broken harnesses. Then "the model was right" is literally true.
5. **Phases that cost money were mixed with free ones.**
   **Fix:** Phase A is free and deterministic. Model phases have a pilot, a cost cap and a stop rule.
6. **The model call limits were not set.**
   **Fix:** budget cap and pilot stop rules below.
7. **Title.** The working title sits very close to the paper's title ("When the Model Is Right but the Click Is Wrong").
   **Fix:** keep it as a working title, choose the final one after results, and make sure it states our finding.

## Design

One local website served by Python's HTTP server and controlled by Playwright. No logins or third-party data; the browser visits only localhost. Four tasks, one for each stage, each with a known target and an observable end state. Layouts come from a seed (positions, sizes, labels, viewport pairs), so there are many.

| Stage | Task | Injected defect | What the page ledger records |
|---|---|---|---|
| Parsing | Type a query into a search box | A chat template token is appended to the typed text | Exact text in the box and the submitted text |
| Execution | Click one button in a grid | Image coordinates used as viewport coordinates (900 x 600 image of a 1200 x 800 viewport) | Which element received the real click |
| Feedback | Select a row inside an embedded same origin frame | Feedback inspects only the top page | Selected row inside the frame |
| Observation | Read a chart value that shows on hover only | Next view captured before the tooltip appears | Tooltip text visible at capture time |

**Independent oracle.** Each page keeps its own event ledger in JavaScript (real click target, input value, frame state, tooltip text). Policies cannot read it. The audit also checks whether the harness's feedback matches the actual page state. Thus a successful iframe click with false feedback is a failed round trip even though the action itself succeeded. For delayed rendering, score the evidence at capture time and separately record whether the state appeared later.

**Four policies (Phase A), three in Phase C:**
- **Unverified:** dispatch, then continue.
- **Generic check:** compare URL, top page text length and main frame state before and after.
- **Pixel change:** compare screenshots before and after. (Phase A only.)
- **Round trip check:** verify the specific outcome, namely input read back, element at the executed point against the intended target, state of the frame that received the action, and evidence visible in the observation.

Checks are written as general rules and frozen before the main run. The surprise set below is then added.

**Additional fault set (not tuned on):** delayed render (state changes 800 ms late), target below the fold, an overlay covering the target, and a disabled button. These faults are named in advance, so do not describe them as blind surprises. Run each across the 40 final layouts once and report what each policy sees. Freeze the checks before running these layouts.

### Phase A: harness audit (free)
- Seeds 0 to 9: development only. Seeds 10 to 49: final, frozen before any run.
- Per task and policy, 40 defect cases and 40 clean cases. Each policy reads the same action trace. Timing based tasks are repeated three times, and disagreement is reported.
- Output: for each policy and task, detection rate when the required round trip failed and false alarm rate when it worked, with Wilson 95 percent ranges over the 40 layouts. No model calls.

### Phase B: real decisions (cheap)
- One vision model, one prompt, one viewport. Claude Haiku 5.5 with thinking disabled, as in the RAG test, unless the pilot shows it cannot aim clicks.
- On a clean harness, 20 final layouts per task. Report how often the model's click is right. Keep the right ones as the decision tape.
- Replay the tape through each defect, so every failure is a case where the model was correct.

### Phase C: does checking change the outcome? (cheap)
- The model runs the full loop with the defect on and feedback supplied by each of three policies. A retry is allowed up to three actions.
- 20 final layouts x 4 tasks x 3 policies x 3 runs = 720 episodes. Report task success, extra actions, elapsed time, tokens and cost, per task before any total.
- If checks only expose failures and do not change success, say so.

## Cost and stop rules

Estimates, to be replaced by pilot measurements. A 900 x 600 screenshot is about 720 image tokens, so a step is about 1,500 input and 120 output tokens. On Haiku 5.5 ($0.10 and $0.50 per million), Phase C is about 2,200 calls, roughly $0.50. Sonnet 5.5 would be about $9, over the cap. Hard stop at $2 total (same guard as the RAG harness).

**Pilot (about $0.05 budget, $0.000792 actual):** Development seeds 0 and 1 for each task, clean and defect, one run. Check that the model can click a target on a 900 x 600 image, that logs and the oracle agree, and that the screenshots are readable. The same model action is replayed through the defect, so 16 episodes used eight model decisions.

**Stop rules, decided now:**
- If the model's clean success on a task is under 70 percent, enlarge targets or move that task to Sonnet, report the change, and never change layouts after seeing final results.
- If the oracle and a check disagree for a reason I did not expect, stop and read the traces before continuing.
- Never drop failed cases. Report every one.

## Logging

One JSONL record per action: task, seed, run, policy, model reply, parsed action, intended and executed coordinates, image and viewport size, element at the executed point, before and after URL, frame states, ledger entries, feedback text, screenshot path, verdict, oracle truth, tokens, cost, time. Keep every screenshot used in the article.

## Figures

1. Opening overlay: intended point, faulty point, corrected point, and button bounds on one screenshot.
2. Four stage diagram with one logged field at each boundary.
3. Detection and false alarm table per task and policy, with ranges.
4. An additional fault strip: which checks saw which of the four extra failures.
5. One trace card: model decision, browser event, ledger entry, feedback, next observation.
6. Phase C success by policy, per task, with run spread.

## Interpretation limits

- Injected defects show what each check can see. They do not estimate how often these faults occur on real sites. Say so every time.
- The oracle and checks are written by one person, so a shared blind spot is possible. The surprise set is partly meant to expose that.
- Same origin frames and local pages are a controlled demonstration. Cross origin frames, native dropdowns, canvases and live site drift are not tested, and the paper reports them as real problems.
- One model, one prompt, one size, 40 final layouts. Rates are for this setup.
- The article's conclusion follows the measured results. It need not claim that every extra check helps every task.

## Order of work

1. Install Python Playwright in a new venv (a Chromium build is already cached, so no big download is expected). Authorized by the user's go-ahead on 2026-10-16.
2. Build pages, ledger, executors and policies. Freeze `manifest.json` (hash recorded in `FROZEN.txt`).
3. Phase A. Read the traces, including a sample of every failure and every false alarm.
4. Pilot, then Phase B, then Phase C.
5. Audit logs and screenshots, then write the article from observed cases using `guidelines/`.
