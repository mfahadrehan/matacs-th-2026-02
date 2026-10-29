# MATACS-TH-2026-02: AI Proposal Triage Design

- **Name:** Fahad Rehan
- **Reference:** MATACS-TH-2026-02
- **Time actually spent:** 30 min

## Files
- [WRITEUP.md](WRITEUP.md): answers to the five questions
- [diagram/flow.png](diagram/flow.png): process flow from upload to ranked output (AI, rule and human steps colour-coded)
- [PROMPTS.md](PROMPTS.md): extraction and explanation prompts
- [ranking.json](ranking.json): expected ranking of proposals A to E
- [prototype/](prototype/): optional basic Python script. `python triage.py` scores structured facts with the gate, formulas and ranking (no API key needed). `python test_triage.py` checks the five sample outcomes. `--extract` runs the extraction prompt on local text files in `prototype/samples/` (git-ignored). Copy `.env.example` to `.env`; no keys are committed.

## How I used AI tools
I used Claude (Anthropic) to help with this whole submission. It drafted the design, the write-up, the prompts, the flow diagram, the basic Python prototype and this README, and I read every file, checked the five proposal scores by hand, and edited the wording of the write-up to match how I would explain it.

One place I corrected the AI: I did not accept its first draft as final. I asked it to review the submission strictly against the brief. That review found that a mandatory pass/fail item could be marked "false" without any supporting quote, and that the diagram's flag boxes did not lead to the reviewer. I had both fixed: a "false" now needs a quote or the proposal is flagged instead of rejected, and the diagram now shows every flag and ineligible result going to the reviewer, plus an admin criteria screen and a re-score loop.

The code is simple on purpose and is marked as AI-assisted in its header comment.
