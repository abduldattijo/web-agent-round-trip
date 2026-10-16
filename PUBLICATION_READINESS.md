# Publication readiness

The revised article is `draft.md`. The earlier draft is preserved as `draft.before_editorial_revision_2026-10-16.md`. The figures, video, and GIF are indexed in `VISUAL_EVIDENCE.md`.

## Done

- The opening centers the measured detection failures and avoids presenting the deliberately persistent click fault as a surprising recovery test.
- The full experiment disclosures, 20 of 40 layout choice, 13 excluded serial episodes, fixed model reply format, four group schedule, shared check and answer key authorship, and about $0.27 logged project spend are in the article.
- The article includes the coordinate conversion, the four by four detection and false alarm table, consistent policy names, definitions on first use, source labels for every figure, and an engagement question.
- The article style linter reports zero hyphens, dashes, prose colons, banned phrases, sentences over 30 words, and paragraphs over five sentences.
- The detection and completion counts, paired interval, and spend were checked against `results/phase_a.summary.json` and `results/phase_c.summary.json`.
- The second editorial pass moved the page event record before the detection results, split faults caught from false alarms, stated the persistent fault before the completion chart, and updated both chart and hover figure labels. All 60 Round trip click episodes were checked against their action traces; each repeated the original image point for all three actions.

## Before public submission

1. Publish a companion repository or other stable public download, then add its real URL near the opening and under the sources. Do not invent a link. The image paths in `draft.md` are relative to this folder and need to be uploaded into the publication editor or changed to public URLs. The video link should be added only after it has a public destination.
2. The staged public copy is in the sibling `web-agent-round-trip-public` folder. It reads `ANTHROPIC_API_KEY` from the environment and contains no local key file fallback. The fallback existed in `pilot.py`; `phase_b.py` and `phase_c.py` imported its key loading function. The original frozen scripts and hashes remain in this folder as the experiment record. The staged copy preserves the original Phase B freeze record under `provenance/`, records the credential only change, and passes the local freeze checks. Review the staged files and decide where to publish them; no remote repository exists yet.
3. In the publication editor, put each `Image by author` or `Screenshot by author` attribution in the actual image caption field. Inspect how the table, code block, GIF, and figures render at article width.

The companion repository has not been published, and no article has been submitted.
