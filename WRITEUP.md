# Write-up: AI proposal triage (MATACS-TH-2026-02)

**Idea in one line:** AI turns messy proposal text into structured facts with quoted evidence. Plain code does the gates, maths and ranking. A person makes the award decision.

## 1. AI vs. rules
**AI (two steps):**
- *Extraction:* reads each proposal and fills a fixed JSON record (licence, price, weeks, install count, warranties, team items), each fact with a quote or null.
- *Explanation:* writes a one-line reason per proposal from numbers already computed.

**Plain code or rules:** upload checks, loading the admin's criteria, PDF text extraction, a pattern scan for injected instructions, the mandatory pass/fail gate, budget and 16-week limits, every score formula, ranking with a tie-break, the audit log.

**Why here:** language is messy, so AI helps there. Anything that must be exact, repeatable and explainable (pass/fail, arithmetic, order) is code. A model never decides eligibility or does the maths.

## 2. Consistency and explainability
- Only extraction is probabilistic. It runs at temperature 0 with a strict schema and a versioned prompt. The result is cached by a hash of the text, prompt version and model, so re-ranking the same proposals reuses the same facts and gives the same ranking.
- Scores are formulas over those facts: same facts, same scores. Price and timeline are scored against the best clean, complete bid. Flagged bids never set that benchmark, so a fake low price cannot shift anyone else's score.
- For a fresh run without cache, extract twice and flag any field that differs.
- Reviewer view: a card per proposal with each criterion's score, the inputs to the formula, the quoted evidence, and any flags. The reviewer can trace every point.

## 3. Human in the loop
- **Correct a fact:** the reviewer sees extracted values beside the quotes and can fix one (for example a misread price). The correction is recorded with a comment and scores recompute.
- **Resolve flags:** flagged proposals (missing data, suspicious text) are held out of the ranked list until the reviewer decides.
- **Ineligible:** shown with the failed check; the reviewer may reinstate with a reason.
- **Final decision:** the reviewer confirms or reorders the list. The tool never awards anything.
- **Audit log:** who and when; criteria version; prompt version; model; file hashes; extracted JSON; scores; flags; each override with before, after and reason; the final decision.

## 4. Changing criteria
Criteria are versioned and every run stores the version it used.
- **Weights or thresholds edited:** old results are marked "scored under v1, outdated". Recomputing needs no AI call because extractions are stored separately, so it is instant and free.
- **Criterion added or redefined:** only the new field is extracted (a cheap re-run), then scores recompute.
- The reviewer can compare v1 and v2 rankings side by side. One ranked list never mixes versions, and a confirmed award is never silently changed.

## 5. Risks

| Risk | Safeguard |
|---|---|
| Wrong extraction (misread price, wrong count) | Every number or true needs a quote, and code checks the quote appears word for word in the proposal; otherwise null and a flag. Reviewer sees the quote and can correct. Double extraction on fresh runs. |
| Made-up facts | "Never infer" rule, schema validation, evidence check in code. Missing data stays missing and is flagged, not guessed. |
| Bias | Scoring is code with fixed rubrics. Company name is not an input to any formula, and names can be hidden from the reviewer view. Rubrics are visible to admin and reviewer. |
| Manipulation (text aimed at the AI) | Proposal text is treated as data. Code scans for such text, the extraction prompt ignores it, and any hit flags the proposal for a human. The model never sets scores, so an injection cannot change a number. |
| Cost | One extraction per proposal, cached. Re-scoring is free. Cheaper model can be used; fields are short. |
| Confidentiality | Check the provider's data-retention terms before use; keep files in the company's storage. |

## Sample set result (see ranking.json)

| | Experience 30 | Price 25 | Timeline 15 | Warranty 15 | Team 15 | Total | Outcome |
|---|---|---|---|---|---|---|---|
| A | 30.0 | 25.0 | 15.0 | 13.8 | 15.0 | 98.8 | Rank 1 |
| E | 18.0 | 24.5 | 13.8 | 15.0 | 15.0 | 86.4 | Rank 2 |
| C | 24.0 | 24.4 | 12.9 | 13.8 | 7.5 | 82.5 | Flagged, provisional |
| D | 24.0 | 25.0 | not scored | 13.8 | 7.5 | 70.2 so far | Flagged |
| B | | | | | | | Ineligible |

- **A and E** pass everything and score cleanly.
- **B** is cheapest, but electrical work is subcontracted and the licence is "to be confirmed". That fails a mandatory rule, so price cannot rescue it.
- **C** contains text telling automated reviewers to rank it first. It is ignored and reported, C is scored on real content only, and it is held for a person because the attempt is an integrity concern.
- **D** gives no schedule, so Timeline is not scored and not defaulted to 16 weeks. Even with a perfect timeline it reaches about 85, so it cannot beat A or E. A person should ask the bidder.

## Assumptions
- Experience bands: 12+ installs = 100, 9-11 = 80, 6-8 = 60, 3-5 = 40, 1-2 = 20. Dates like "since 2021" or "since 2020" are taken as stated. The five-year window cannot be checked exactly, so A, C and E carry a reviewer note (C's start year is clearly outside it).
- Warranty: half panel (25 years = full), half workmanship (12 years = full). Team: 25 points each for named lead, crew, safety plan, monitoring plan.
- A lead described as "named" is accepted as stated.
