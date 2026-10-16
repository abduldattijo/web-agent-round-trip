# I Broke a Browser Agent on Purpose. Spotting the Fault Was Not the Same as Fixing It

*I replayed correct model decisions through four broken browser actions. A simple page check missed half of the wrong clicks, and raised a false alarm on every click that worked inside an embedded page.*

[WebFovea](https://arxiv.org/html/2610.03036v2), a paper by Jiangang Han, reports a disquieting browser agent failure. A mismatch between screenshot and browser coordinates placed clicks at three quarters of their intended position. A click meant for a point 400 pixels across landed 300 pixels across.

The mismatch came from the service that runs the model, which shrank each screenshot before the model looked at it. The paper estimates that a 1920 by 1080 screenshot reached the model as about 1440 by 810, which is three quarters of the size. Anthropic's [vision documentation](https://platform.claude.com/docs/en/build-with-claude/vision) describes the same behavior for its own models. It says large images are scaled down to cap their cost, and that the model answers in positions on the resized picture. The paper's software used those positions as if they were measured on the full size screen, so every click landed at three quarters of the intended spot.

The agent in the paper is a browser agent, a program that lets an artificial intelligence model inspect a web page and choose actions such as clicking a button. Coordinates, the numbers in the click example above, are positions on the screen, given in pixels.

Besides the click error, WebFovea reports two more failures in the software between the model and the page. Hidden end of message markers from the model were typed into search boxes. A click inside a page embedded in another page worked, but was reported as having no effect.

The paper fixed failures like these across four submissions to a 2026 contest on live websites. The agent's score rose from 31.0 to 57.0 out of 100 with the same model. Each submission bundled several changes, and the live websites could vary, so the score alone does not show which fix mattered most. That is the gap I tried to look at on a small scale.

To look at that gap, I tested what happens after the model makes a correct choice. I built a small browser site with four short tasks, such as searching for a record and clicking a button. I asked Claude Haiku 5.5, a small, low cost model from Anthropic, to complete them.

I saved 80 of its decisions that worked, then replayed each through browser code that I had deliberately broken. A check is a small piece of code that looks at the page after an action and decides whether the action worked. I measured whether checks spotted the fault and whether the agent, meaning the model plus the code that drives the browser, still finished the task.

Spotting a fault and getting past it turned out to be different problems. The faults matter to anyone who asks an AI tool to click through a website, including web developers and people who build sites by describing them to an AI tool. The [WebFovea paper and its code](https://github.com/jianganghan/WebFovea) motivated my setup. The results below come from my own browser pages and saved step by step logs.

The [code, step by step logs, figures, and recording](https://github.com/abduldattijo/web-agent-round-trip) are public. The [first test](https://github.com/abduldattijo/web-agent-round-trip/blob/main/results/phase_a.jsonl), where I ran the checks on 40 versions of each page, and the [final agent runs](https://github.com/abduldattijo/web-agent-round-trip/blob/main/results/phase_c.jsonl) support the counts below.

## One right decision, two different clicks

One of the 80 saved decisions shows the problem clearly. The test page shows a grid of numbered buttons, Item 0 to Item 24. The agent saw a 900 pixel wide screenshot of it and was asked to click Item 15. It answered with the image point `(150, 413)`, meaning 150 pixels across and 413 down from the top left corner. The browser's visible area, called the viewport, was 1200 pixels wide.

I made the screenshot smaller on purpose, to copy the problem in the paper. That means the executor, the code that sends an action to the browser, must scale each image coordinate up to browser size. Here the browser is 1200 pixels wide and the image is 900, so the scale is four thirds. The working executor multiplied 150 by four thirds to get 200, and 413 by four thirds to get 550.67. It clicked `(200, 550.67)` in browser pixels and selected Item 15.

The broken executor skipped that scaling and sent `(150, 413)` directly as browser pixels. That point fell on Item 10, one row above Item 15, so Item 10 was selected. I saved the model's answer and ran it twice, once through each executor. The screenshot, instruction, and saved answer were identical both times.

The following code shows the general conversion. In this experiment, both image dimensions were three quarters of the matching browser dimensions, so each coordinate was multiplied by four thirds.

```python
browser_x = image_x * viewport_width / image_width
browser_y = image_y * viewport_height / image_height
page.mouse.click(browser_x, browser_y)
```

The click itself comes from Playwright, a tool that lets code control a browser. [Its mouse documentation](https://playwright.dev/python/docs/api/class-mouse) specifies browser viewport pixels for a click. The conversion belongs in the executor, the step between the model's answer and the browser. My 900 by 600 image and 1200 by 800 viewport follow the proportions of the three quarter error in WebFovea. This is a constructed example on my site, not a second observation from live websites.

![Two screenshots of the same recorded click show Item 15 selected with correct conversion and Item 10 selected with faulty conversion.](figures/continuous_click_seed12_comparison.png)

*Figure 1. Image by author. Both frames come from the continuous recording of one version of the test page, using the same saved decision. The green circle marks the working click on Item 15. The red circle marks the faulty click on Item 10.*

Watch the [continuous browser recording](https://github.com/abduldattijo/web-agent-round-trip/blob/main/figures/continuous_model_click_seed12.webm) or the [short GIF](https://github.com/abduldattijo/web-agent-round-trip/blob/main/figures/continuous_model_click_seed12.gif).

## What did I break, and what could the checks see?

To choose what to break, I used the paper's way of describing a browser action. The [WebFovea paper](https://arxiv.org/html/2610.03036v2) treats each one as a round trip. The action travels from the model to the page, and the result travels back. The paper splits that trip into four steps.

A parser turns the model's reply into an action. An executor sends the action to the page. Feedback tells the model what happened. Observation is what the model is shown afterwards, usually a new screenshot.

Three terms in the table need a quick explanation. An embedded frame, or iframe, is a page inside another page. A tooltip is the small label that appears beside a chart mark when the pointer rests on it. The text `[im_end]` in the table below stands in for an end of message marker that some AI models use. I added one deliberate fault at each step.

| Step | Task | Deliberate fault |
| --- | --- | --- |
| Parsing | Search for an exact record | Append `[im_end]` to the text entered in the field |
| Execution | Click a named grid item | Treat image coordinates as browser coordinates |
| Feedback | Select a row inside an embedded frame | Say “No detectable change” after the click succeeds |
| Observation | Hover over a chart mark to read a value | Capture the image before the tooltip appears |

In the Feedback row, my embedded frame comes from the same site as its parent page, which is easier because the page can read its own frame directly. The paper's frame example involved a harder case across sites.

To see whether the checks caught these faults, I generated 40 layouts for each task, with different target positions or values. A layout is one arrangement of the same page. Every check was applied to 40 faulty actions and 40 working actions. The working actions matter because a check that always warns would catch every fault and also interrupt every correct action.

To know whether a check was right, the page kept its own record. It logged the text entered, the button clicked, the frame row selected, and the tooltip visible when the screenshot was taken. That record was the answer key for counting detected faults. The checks could not read it while deciding whether to warn.

I compared four policies, meaning four ways of checking an action. **Unverified** accepted the message the browser tool sent back to the model, such as “No detectable change”, as true. **Generic** looked for changes in the web address or the main page's state. **Pixel** compared screenshots. **Outcome check** compared the page with the specific outcome requested, such as the exact field text, the selected button, the row inside the frame, or whether the chart value appeared.

The first table counts faults caught out of 40 faulty actions. The second counts false alarms out of 40 working actions. A higher count is better in the first table and worse in the second.

| Faults caught out of 40 | Unverified | Generic | Pixel | Outcome check |
| --- | --- | --- | --- | --- |
| Corrupted search text | 0 | 0 | 3 | 40 |
| Wrong click position | 0 | 20 | 20 | 40 |
| False frame feedback | 0 | 40 | 0 | 40 |
| Missing tooltip in image | 0 | 40 | 40 | 40 |

*Table 1. Faults caught in the first test, which used 40 layouts. Higher counts mean more of the injected faults were detected. Counts came from the page's own record.*

| False alarms out of 40 | Unverified | Generic | Pixel | Outcome check |
| --- | --- | --- | --- | --- |
| Working exact search | 0 | 0 | 40 | 0 |
| Working target click | 0 | 0 | 0 | 0 |
| Working frame click | 0 | 40 | 0 | 0 |
| Working chart hover | 0 | 0 | 0 | 0 |

*Table 2. Warnings on 40 working actions per task. Lower counts mean fewer needless warnings.*

The simple checks failed in different ways. Generic missed 20 of 40 wrong clicks. In those, the click hit a different button, which turned green, so the page looked as if it had responded. The other 20 clicks hit empty space, and Generic caught those. It also warned on all 40 correct frame clicks because the main page did not change when the embedded page did.

Pixel had a different weakness. It found only three corrupted searches and warned on all 40 working searches, because the page looks different after every search. A change in pixels does not prove that an exact query survived parsing.

By contrast, Outcome check found all 40 faults in each task and made no false alarms on the matching working actions. I wrote both the checks and the page code used as the answer key. The checks were built for these faults, so perfect detection here proves little about a different website. A mistake in my thinking could therefore sit in both.

![Clean and corrupted text shown in a search field.](figures/search_token_evidence.png)

*Figure 2. Screenshot by author. The parser adds `[im_end]` to the search term `Record-10`. The field changes visibly, but an exact search needs the original name.*

## Did spotting a fault help the agent finish?

Spotting a fault was only half of the question. I used the first 20 of the 40 layouts for a second experiment, and fixed that choice before any model call. Haiku first made one decision on a working page for each of the 80 combinations of task and layout, four tasks times 20 layouts. Every one of those decisions worked, and I kept all 80.

I replayed each recorded decision with the fault enabled, then let the model see the result, as each policy would report it, and respond. An **episode** is one attempt to complete a task. The model could stop, retry, or wait, meaning pause so the page could finish changing. It had up to three browser actions.

This comparison used Unverified, Generic, and Outcome check. Pixel was evaluated for fault detection but not for task completion, so this experiment cannot say whether it would have helped the agent finish. Each policy ran three times on the same 20 layouts for each of four tasks, yielding `4 × 20 × 3 × 3 = 720` final episodes, from four tasks, 20 layouts, three policies, and three runs. I scored an episode as successful when the requested action reached its target, or when the chart answer came from a screenshot that actually showed the value.

One choice shapes the results below. I left the search parser and click executor broken on every retry, because fixing code is not something the model can do. This shows what better information alone can give it. A check could describe their errors, but another action through the same code would make the same mistake.

![Bar chart of successful episodes for four tasks under three checking policies.](figures/phase_c_success.png)

*Figure 3. Image by author. Each count is successful episodes out of 60 for one task and policy. Higher means more tasks completed. The click and search faults persisted under all policies; either check gained four chart completions over Unverified.*

| Task with fault enabled | Unverified | Generic | Outcome check |
| --- | --- | --- | --- |
| Exact search with extra marker | 0/60 | 0/60 | 0/60 |
| Click sent to wrong position | 0/60 | 0/60 | 0/60 |
| Correct frame click, false message | 60/60 | 60/60 | 60/60 |
| Chart tooltip captured too early | 56/60 | 60/60 | 60/60 |

*Table 3. Successful episodes from the final run. Each cell contains 20 layouts repeated three times. Higher counts mean more completed tasks.*

That persistence matters when reading the zeros. The zeros were expected, and they show what a diagnosis does and does not give the model. On one search, Outcome check read `Record-10[im_end]` back from the field and told the model it differed from `Record-10`. A retry still went through the same parser.

The click episodes show something less obvious. In all 60 Outcome check episodes, the check reported the item hit and supplied the target's correct browser position. The instructions still told the model to answer in image coordinates, and it repeated its original point all three times. The unchanged executor therefore sent three wrong clicks in every episode.

On the frame task the result was the opposite. The browser tool said “No detectable change,” yet the page selected the correct row. All three policies completed all 60 episodes.

Generic told the model nothing had changed, because it watched only the main page, and in 4 of 60 episodes the model clicked a second time for no reason. Outcome check read the frame and needed no extra click. The browser tool's message and the page disagreed, but the screenshot showed the row selected, so the model could finish.

![Record 4 selected in an embedded frame beside misleading tool feedback.](figures/iframe_feedback_evidence.png)

*Figure 4. Screenshot by author. The Outcome check reports the selected row while raw tool feedback says “No detectable change.” The embedded frame comes from the same site.*

The chart task, where the screenshot came before the tooltip appeared, was the only one with a completion difference. Unverified succeeded 56 times out of 60. In four episodes it stopped before a screenshot showed the value. Either check led the model to hover again or wait, then take a new screenshot, and it succeeded in all 60.

![Chart mark without a tooltip beside the same layout after a second hover reveals Value 89.](figures/hover_timing_evidence.png)

*Figure 5. Screenshot by author. These are separate policy episodes on the same layout. Unverified stopped before the value appeared in its screenshot; Generic repeated the hover and saw 89.*

The gain is four of 60 episodes, or 6.7 percentage points. To see how much the gain could vary, I redrew the 20 layouts many times, keeping each layout's three runs together. The middle 95 percent of the redrawn gains ran from 0 to 15 points. Zero gain is still possible, so this small result does not establish a reliable advantage. Generic matched Outcome check on completion, so the simpler check was enough on this task.

## Changes and limits that affect the comparison

These changes and limits matter when comparing the final counts with earlier runs or applying them to other browser agents.

A development run showed that some model replies were cut off before the action text was complete. I switched to a fixed reply format before the final results. I also stopped the first attempt, which ran one episode after another, after 13 episodes because completing all 720 that way would take too long. Those 13 search episodes had zero successes and are archived, then excluded from the final table.

I reran the full set in four separate groups of 180 episodes. The prompts, faults, checks, scoring rules, and 20 selected layouts stayed the same across that schedule change.

Beyond that schedule change, the study has limits. The 20 layouts in the full run were a subset of the 40 layouts in the first test. The study used one simple site, one model and prompt, deliberately injected faults, and a frame from the same site. Each final episode began with a decision already known to work on a clean page. These counts measure recovery on this setup, not the frequency of such failures on public websites or accuracy on harder browsing tasks.

The experiment was cheap to run. The final loop used about 24 US cents in logged model calls. All logged model work for this article, including development and the stopped first attempt, totaled about 27 US cents.

## What does this mean if you test or build websites with AI tools?

The test was small, but the WebFovea paper reports all four kinds of fault on live websites. That makes them worth knowing about if you ask an AI tool to click through a site. This applies to web developers who test pages this way, and to people who build sites by describing them to an AI tool, sometimes called vibe coding. The table below turns each result from the test into something you can do.

| What happened in the test | What it means for you | What to do |
| --- | --- | --- |
| I injected a conversion error. The model had chosen the right button in all 80 saved decisions, and only the broken conversion changed the click. | If an AI tool clicks the wrong thing, the model may not be the problem. | Check how screenshot positions are converted before you rewrite the prompt or switch models. Log the screenshot size and the browser window size. |
| The tool said “No detectable change” in all 180 frame episodes, though every click had worked. | A message that nothing happened is not proof that nothing happened. | If your page uses iframes, check the state inside the frame and not only the outer page. |
| I injected a fault that added a stray marker to the text typed into a search box. The paper found markers like this in real runs. | A tool can type something different from what you asked. | Read back what was typed into a field before you trust the result. |
| In 4 of 60 runs without a check, the screenshot came before the tooltip appeared, so the value was missed. | A value that shows only after a hover or a delay can be missed. | Wait, then take a new screenshot before the tool answers. |

*Table 4. What each result means for someone who tests or builds with AI tools. Each row comes from a result reported above.*

These are suggestions from one small test, so check them against your own site and tools. One idea goes beyond what I measured. If you build a site, showing an important value in the page text, and not only on hover, may make it easier for a screenshot based tool to read. I did not test that, so treat it as a guess.

A last suggestion is for anyone who builds or checks a site with an AI tool. If the tool says it clicked a button but the page looks the same, ask it to read the page back and say what changed. That is what the Outcome check did in this experiment.

## What would I check in a browser agent?

These faults all happened between the model's answer and the page. So I would save the model's request, the image and browser dimensions, and the action actually sent to the browser. I would also record the element or frame that received it and the observation shown to the model.

The click conversion above makes one step explicit, the move from image position to browser position. An exact search also needs the text read back from the search box. A frame click needs the state of that frame, and a chart answer needs a screenshot that contains its value.

Checks can reveal a mismatch and can help when another observation supplies missing evidence. They cannot correct a persistent parser or executor fault unless the agent or its surrounding code changes how the next action is sent. When an agent appears to reason badly, inspect the action's path through the browser before changing the prompt.

After a failed click, would your logs show the coordinates the model asked for, the point the browser actually received, or only the final screenshot?

## Selected sources

- [WebFovea paper](https://arxiv.org/html/2610.03036v2), for the reported live site failures and four step framing.
- [Anthropic vision documentation](https://platform.claude.com/docs/en/build-with-claude/vision), for how large images are resized before the model sees them, and how the model's coordinates relate to the resized image.
- [Playwright Mouse API](https://playwright.dev/python/docs/api/class-mouse), for the browser pixel convention.
- [Experiment code and raw results](https://github.com/abduldattijo/web-agent-round-trip), including the browser pages, step by step logs, figures, and recording.
