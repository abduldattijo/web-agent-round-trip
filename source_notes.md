# Source notes

## Primary paper

- Jiangang Han, [WebFovea: When the Model Is Right but the Click Is Wrong](https://arxiv.org/html/2610.03036v2), submitted 2 October 2026, revised 7 October 2026 (v2 added the code link). Single author. Agent used claude-opus-4-6 on the WebRetriever Protocol III challenge. The paper defines parsing, execution, feedback, and observation as stages of each browser action round trip.
- The paper reports a coordinate mismatch: model-visible coordinates were about three quarters of viewport coordinates until screenshot dimensions were aligned. It reports silent input and embedded-frame issues and template-token contamination. These are the paper's observations, not ours.
- Its 31.0-to-57.0 hidden-set score trajectory combines several changes across successive submissions on live sites. Section 5.2 explicitly states that each submission bundled changes and gains cannot be attributed to single components. The paper estimates about 7 of the first 10 points came from finishing more tasks. Section 5.3 calls its small targeted component comparisons directional rather than statistically significant.
- The [released WebFovea code](https://github.com/jianganghan/WebFovea), inspected at commit `4b75e10722e2f9c1c662f16dbb8319fe2a33188f`, is a reference for the author's implementation. `src/agent/agent.py` maps model image coordinates to viewport pixels using `round(x / sent_width * screen_width)` and the analogous y calculation. It truncates model text at the first unrecognized chat-template token while preserving coordinate box tokens. `src/agent/web_controller.py` fingerprints the page and the child frame that received an action. These are implementation details of WebFovea, not code or results from our experiment. Our project should remain independently runnable and identify any code reused from it.

## Browser mechanics

- [Playwright frames documentation](https://playwright.dev/docs/frames): a page has a main frame and may contain child frames. The experiment's frame-aware check must inspect the frame where the action occurred.
- [Playwright Mouse API](https://playwright.dev/python/docs/api/class-mouse): coordinates are CSS pixels relative to the main frame's viewport (verified 2026-10-16). Store image and viewport dimensions with each decision so conversion is auditable. The earlier cited agent-cli page documents the command line tool, not the library.

## Editorial differentiation

The author's earlier article, `articles/tool-calling-agent/draft-redesign.md`, shows validation and trace evidence for Python API tools. This piece's original evidence must come from browser execution and observation. A summary of WebFovea alone would overlap both the paper and the earlier article.

## Claims reserved for our data

Do not write success percentages, latency gains, model cost, or "the checks fixed the agent" until the local run is complete and the corresponding raw traces and screenshots are saved. Label injected failures as injected. Label decision-tape replay separately from model-run results.

## Exact figures from the paper that may be quoted with attribution (read 2026-10-16)

- Clicks landed at 3/4 of intended coordinates (API downscaling plus the reference code's mapping). On 24 paired dev tasks success rose from 8/24 to 20/24, and the paper notes that version had other changes.
- Template tokens appeared in 15 of 305 local episodes (4.9%). Success was 7.7% for contaminated and 41.7% for clean episodes, which the paper calls observational.
- 79 of 356 type calls (22%) ended in a newline without the Enter key being pressed.
- A successful iframe click was reported as "no detectable change". The click probe was on a cross origin iframe.
- Limitations: one model, small component sets, live sites that vary, each official score from a single run.

## Our local setup differs from the paper

- Our frame test is same origin, the paper's click problem was cross origin.
- Our 3/4 image to viewport ratio is built to mirror the paper, it is not an API effect.

## Cost references checked 2026-10-16

- [Claude Haiku 5.5 pricing](https://www.anthropic.com/claude/haiku) lists $0.10 per million input tokens and $0.50 per million output tokens for prompts up to 100,000 tokens. The plan's full-run estimate still needs replacement with measured pilot usage.
- [Claude vision coordinate guidance](https://platform.claude.com/docs/en/build-with-claude/vision-coordinates) counts one visual token per 28 by 28 pixel patch. An unresized 900 by 600 image is 33 by 22 patches, or 726 visual tokens, before text and any other request overhead.
