# What Browser Agent Checks Can See, and What They Cannot Fix

*I replayed correct model decisions through four broken browser actions. A generic page check missed half the wrong clicks and flagged every correct frame click.*

[WebFovea](https://arxiv.org/html/2610.03036v2) describes a browser agent whose clicks landed at three quarters of the intended coordinates. A browser agent is a program that lets an artificial intelligence model inspect a web page and choose actions such as clicking a button. WebFovea reports other failures in the software between the model and the page. Its challenge score rose from 31.0 to 57.0 across four submissions using the same model. Each submission bundled several changes, and the live websites could vary.

I wanted to test what happens after the model makes a correct choice. I built a small browser site, recorded 80 successful decisions from Claude Haiku 5.5, and replayed those decisions with deliberate faults. I measured whether checks spotted the fault and whether the agent still finished the task. The answers were often different. The [WebFovea paper and its code](https://github.com/jianganghan/WebFovea) motivated my setup; the results below come from my own browser pages and saved traces.

## One right decision, two different clicks

The agent saw a 900 pixel wide screenshot and was asked to click Item 15. It returned image point `(150, 413)`. The browser's visible area, called the viewport, was 1200 pixels wide.

The executor, the code that sends an action to the browser, must multiply each image coordinate by the ratio of browser size to image size. Here that ratio is four thirds. The working executor clicked `(200, 550.67)` in browser pixels and selected Item 15.

The broken executor sent `(150, 413)` directly as browser pixels. It selected Item 10. The screenshot, instruction, and recorded model decision were identical in both replays.

The following code shows the general conversion. In this experiment, both image dimensions were three quarters of the matching browser dimensions, so each coordinate was multiplied by four thirds.

```python
browser_x = image_x * viewport_width / image_width
browser_y = image_y * viewport_height / image_height
page.mouse.click(browser_x, browser_y)
```

[Playwright's mouse documentation](https://playwright.dev/python/docs/api/class-mouse) specifies browser viewport pixels for the click. The conversion belongs at this boundary. My 900 by 600 image and 1200 by 800 viewport deliberately reproduce the three quarter error described in WebFovea. This is a constructed example on my site, not a second observation from live websites.

![Two screenshots of the same recorded click show Item 15 selected with correct conversion and Item 10 selected with faulty conversion.](figures/continuous_click_seed12_comparison.png)

*Figure 1. Image by author. Both stills come from the continuous seed 12 recording of the same saved decision. The green circle marks the working click on Item 15. The red circle marks the faulty click on Item 10.*

## What did I break, and what could the checks see?

The [WebFovea paper](https://arxiv.org/html/2610.03036v2) separates a browser action into four steps. A parser turns the model's reply into an action. An executor sends the action to the page. Feedback tells the model what happened.

The next observation, often a screenshot, shows what the model can use next. An embedded frame, or iframe, is a page inside another page. A tooltip is the small label that appears beside a chart mark when the pointer rests on it. I injected one fault at each step.

| Step | Task | Deliberate fault |
| --- | --- | --- |
| Parsing | Search for an exact record | Append `[im_end]` to the text entered in the field |
| Execution | Click a named grid item | Treat image coordinates as browser coordinates |
| Feedback | Select a row inside an embedded frame | Say “No detectable change” after the click succeeds |
| Observation | Hover over a chart mark to read a value | Capture the image before the tooltip appears |

My embedded frame comes from the same site as its parent page. The paper's frame example involved a harder case across sites.

For each task, I generated 40 layouts with different target positions or values. A layout is one arrangement of the same page. Every check saw 40 faulty actions and 40 working actions. The working actions matter because a check that always warns would catch every fault and also interrupt every correct action.

The page kept its own record of the text entered, the button clicked, the frame row selected, and the tooltip visible when the screenshot was taken. That record was the answer key for counting detected faults. The checks could not read it while deciding whether to warn.

I compared four policies. **Unverified** accepted the tool's response. **Generic** looked for changes in the address or main page state. **Pixel** compared screenshots. **Round trip** checked the specific outcome requested, such as the exact field text, the selected button, the row inside the frame, or whether the chart value appeared.

The first table counts faults caught out of 40 faulty actions. The second counts false alarms out of 40 working actions. A higher count is better in the first table and worse in the second.

| Faults caught out of 40 | Unverified | Generic | Pixel | Round trip |
| --- | --- | --- | --- | --- |
| Corrupted search text | 0 | 0 | 3 | 40 |
| Wrong click position | 0 | 20 | 20 | 40 |
| False frame feedback | 0 | 40 | 0 | 40 |
| Missing tooltip in image | 0 | 40 | 40 | 40 |

*Table 1. Faults caught in the 40 layout browser audit. Higher counts mean more of the injected faults were detected. Counts came from the saved page event log.*

| False alarms out of 40 | Unverified | Generic | Pixel | Round trip |
| --- | --- | --- | --- | --- |
| Working exact search | 0 | 0 | 40 | 0 |
| Working target click | 0 | 0 | 0 | 0 |
| Working frame click | 0 | 40 | 0 | 0 |
| Working chart hover | 0 | 0 | 0 | 0 |

*Table 2. Warnings on 40 working actions per task. Lower counts mean fewer needless warnings.*

Generic missed 20 of 40 wrong clicks because another button changed state. It also warned on all 40 correct frame clicks because the main page did not change when the embedded page did. Pixel found only three corrupted searches and warned on all 40 working searches. A change in pixels does not prove that an exact query survived parsing.

Round trip found all 40 faults in each task and made no false alarms on the matching working actions. I wrote both the checks and the page code used as the answer key. The checks were built for these faults, so perfect detection here proves little about a different website. Both still reflected my design choices.

![Clean and corrupted text shown in a search field.](figures/search_token_evidence.png)

*Figure 2. Screenshot by author. The parser adds `[im_end]` to `Record-10`. The field changes visibly, but an exact search needs the original name.*

## Did spotting a fault help the agent finish?

Spotting a fault is different from getting past it. I used 20 of the 40 layouts for a second experiment. I chose those 20 before this full run. Haiku first made one correct decision on a working page for each of the 80 task and layout combinations. I kept every one of those 80 decisions.

I replayed each recorded decision with the fault enabled, then let the model see the result and respond. An **episode** is one attempt to complete a task. The model could stop, retry, or wait, up to three browser actions.

This comparison used Unverified, Generic, and Round trip. Pixel was measured only in the earlier audit. Each policy ran three times on the same 20 layouts for each of four tasks, yielding `4 × 20 × 3 × 3 = 720` final episodes. I scored an episode as successful when the requested action reached its target, or when the chart answer came from a screenshot that actually showed the value.

The search parser and click executor were deliberately left broken on every retry. A check could describe their errors, but another action through the same code would make the same mistake.

![Bar chart of successful episodes for four tasks under three checking policies.](figures/phase_c_success.png)

*Figure 3. Image by author. Each count is successful episodes out of 60 for one task and policy. Higher means more tasks completed. The click and search faults persisted under all policies; either check gained four chart completions over Unverified.*

| Task with fault enabled | Unverified | Generic | Round trip |
| --- | --- | --- | --- |
| Exact search with extra token | 0/60 | 0/60 | 0/60 |
| Click sent to wrong position | 0/60 | 0/60 | 0/60 |
| Correct frame click, false message | 60/60 | 60/60 | 60/60 |
| Chart tooltip captured too early | 56/60 | 60/60 | 60/60 |

*Table 3. Successful episodes from the final run. Each cell contains 20 layouts repeated three times. Higher counts mean more completed tasks.*

That persistence matters when reading the zeros. This result shows that diagnosis alone cannot repair code that repeats the same mistake. On one search, Round trip read `Record-10[im_end]` back from the field and told the model it differed from `Record-10`. A retry still went through the same parser.

The click traces were more revealing. In all 60 Round trip episodes, the check reported the item hit and supplied the target's correct browser position. The prompt still required image coordinates, and the model repeated its original point all three times. The unchanged executor therefore sent three wrong clicks in every episode.

The frame task went the other way. The tool said “No detectable change,” yet the page selected the correct row. All three policies completed all 60 episodes.

Generic prompted four unnecessary second clicks because it watched the main page. Round trip read the frame and required no extra click. The tool's message and the page disagreed, yet the model could still see enough to finish.

![Record 4 selected in an embedded frame beside misleading tool feedback.](figures/iframe_feedback_evidence.png)

*Figure 4. Screenshot by author. The frame aware check reports the selected row while raw tool feedback says “No detectable change.” The embedded frame comes from the same site.*

The early tooltip was the only task with a completion difference. Unverified succeeded 56 times out of 60. In four episodes it stopped before a screenshot showed the value. Either check prompted another observation and succeeded in all 60.

The gain is four of 60 episodes, or 6.7 percentage points. When I resampled by layout and kept its three repeats together, the 95 percent interval for the gain ran from 0 to 15 points. Zero gain is still possible, so this small result does not establish a reliable advantage. Generic matched Round trip on completion.

![Chart mark without a tooltip beside the same layout after a second hover reveals Value 89.](figures/hover_timing_evidence.png)

*Figure 5. Screenshot by author. These are separate policy episodes on the same layout. Unverified stopped before the value appeared in its screenshot; Generic repeated the hover and saw 89.*

## Changes and limits that affect the comparison

These changes and limits matter when comparing the final counts with earlier runs or applying them to other browser agents.

A development run showed that free form model replies could end before the action text was complete. I switched to a fixed reply format before the final results. I also stopped the first serial attempt after 13 episodes because completing all 720 in that schedule would take too long. Those 13 search episodes had zero successes and are archived, then excluded from the final table.

I reran the full set in four separate groups of 180 episodes. The prompts, faults, checks, scoring rules, and 20 selected layouts stayed the same across that schedule change.

The 20 layouts in the full run were a subset of the 40 layouts in the browser audit. The study used one simple site, one model and prompt, deliberately injected faults, and a frame from the same site. Each final episode began with a decision already known to work on a clean page. These counts measure recovery on this setup, not the frequency of such failures on public websites or accuracy on harder browsing tasks.

The final loop used about $0.24 in logged model calls. All logged model work for this article, including development and the stopped serial attempt, totaled about $0.27. The small timing differences between policies are not a speed ranking because the runs used a parallel schedule and browser timing can vary.

## What would I check in a browser agent?

I would save the model's request, the image and browser dimensions, and the action actually sent to the browser. I would also record the element or frame that received it and the observation shown to the model. The click conversion above makes one boundary explicit. An exact search also needs a text read back, a frame click needs the state of that frame, and a chart answer needs a screenshot that contains its value.

Checks can reveal a mismatch and can help when another observation supplies missing evidence. They cannot correct a persistent parser or executor fault unless the agent or its surrounding code changes how the next action is sent. When an agent appears to reason badly, inspect the action's path through the browser before changing the prompt.

Which would your current browser logs tell you after a failed click, the coordinates the model requested, the point the browser received, or only the final screenshot?

## Selected sources

- [WebFovea paper](https://arxiv.org/html/2610.03036v2), for the reported live site failures and four step framing.
- [Playwright Mouse API](https://playwright.dev/python/docs/api/class-mouse), for the browser pixel convention.
