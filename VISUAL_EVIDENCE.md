# Visual evidence for the article

Use these assets from the local browser fixture. They show deliberately injected faults, not failures observed on live websites. The captioned PNGs add labels and highlights to saved, otherwise unaltered browser screenshots. Their source screenshots remain under `results/`.

| Article use | Asset | What it shows |
| --- | --- | --- |
| One-figure explanation | [Failure and result story](figures/failure_and_result_story.png) | Clean versus faulty execution of the same recorded click, followed by the completion counts for all four faults. This combines saved video frames with results from the final experiment. |
| Article opening still | [Seed 12 click comparison](figures/continuous_click_seed12_comparison.png) | Two stills from the continuous recording of the exact decision described in the draft, with Item 15 and Item 10 outcomes side by side. |
| Opening demonstration | [Continuous WebM](figures/continuous_model_click_seed12.webm) | One uninterrupted recording: a recorded Haiku click succeeds on the clean page, the page resets, and the same click misses with faulty coordinate scaling. Labels and point markers are overlaid. |
| Animated version | [GIF from that WebM](figures/continuous_model_click_seed12.gif) | Short loop suitable for an article that accepts animated images. This is extracted from the continuous recording. |
| Static click figure | [Click comparison](figures/scaled_click_seed1_comparison.png) | Intended and executed click positions, with before and after page states from the pilot. |
| Search example | [Search token evidence](figures/search_token_evidence.png) | The exact input on clean and faulty Phase B replays of the same recorded decision, seed 10. The Phase C trace reports “No exact result” for the injected suffix. |
| Iframe example | [Iframe feedback evidence](figures/iframe_feedback_evidence.png) | In Phase C seed 10, run 1, Record 4 is visibly selected even though raw tool feedback says “No detectable change.” This fixture uses a same-origin frame. |
| Timing example | [Hover timing evidence](figures/hover_timing_evidence.png) | Phase C seed 21, run 1: the unverified policy captures no tooltip and stops; the generic policy repeats the hover and sees value 89. These are separate policy episodes on the same layout. |
| Results | [Phase C outcome chart](figures/phase_c_success.png) | Success counts for the four tasks and three feedback policies across 720 episodes. |

The video and GIF are the best lead visual. The PNGs explain distinct failure mechanisms at reading speed. The outcome chart belongs after the experiment and policy descriptions. Cite the screenshot provenance in captions so a reader can distinguish the browser image from our added labels and highlights.

Regenerate the three new captioned screenshot figures with `.venv/bin/python make_visual_evidence.py`. This command uses only saved screenshots and makes no browser or model calls.
