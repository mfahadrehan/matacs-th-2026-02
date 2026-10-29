# Written with AI assistance (Claude). See README.md for how AI was used.
"""Proposal triage prototype.

python triage.py             score example_extractions.json (no API key needed)
python triage.py --extract   read samples/*.txt, extract facts with the model, then score

Only extraction uses the model. Gates, scores and ranking are plain code.
"""
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
CRITERIA = json.loads((HERE / "criteria.json").read_text())
WEIGHTS = CRITERIA["weights"]

# Phrases that talk to the system instead of describing a bid.
SUSPICIOUS = [
    r"automated (review|scoring|evaluation)",
    r"note to (the )?(ai|llm|assistant|reviewer|automated)",
    r"pre-?approved",
    r"rank (it|this proposal|this) (first|#?1)",
    r"full marks",
    r"ignore (all |any )?(previous|prior) instructions",
]


def looks_suspicious(text):
    for pattern in SUSPICIOUS:
        if re.search(pattern, text, re.I):
            return True
    return False


# ---------- AI step: extraction ----------

def get_prompt(name):
    # prompts live in PROMPTS.md so there is one copy only
    md = (HERE.parent / "PROMPTS.md").read_text()
    found = re.search(r"<!-- BEGIN %s -->\n```text\n(.*?)\n```\n<!-- END %s -->" % (name, name), md, re.S)
    return found.group(1)


def quote_is_real(quote, text):
    # the quote must appear word for word in the proposal (ignoring spaces and case)
    squash = lambda t: " ".join(t.lower().split())
    return bool(quote) and squash(quote) in squash(text)


MANDATORY = {"licence_held_by_bidder", "wsib_clearance_confirmed", "liability_insurance_5m_confirmed"}


def clean_facts(raw, text):
    """Turn {field: {"value":..., "evidence":...}} into {field: value}.
    A number or true with no real quote is not trusted, so it becomes None."""
    facts = {}
    for key, item in raw.items():
        if not (isinstance(item, dict) and "value" in item):
            facts[key] = item
            continue
        value = item["value"]
        is_number = isinstance(value, (int, float)) and not isinstance(value, bool)
        needs_quote = value is True or is_number or (value is False and key in MANDATORY)
        if needs_quote and not quote_is_real(item.get("evidence"), text):
            value = None
        facts[key] = value
    return facts


def extract_with_model(text):
    import anthropic  # pip install anthropic

    text = text.replace("</proposal_text>", "")  # stop the proposal closing the data block early
    client = anthropic.Anthropic()  # key comes from ANTHROPIC_API_KEY
    user_prompt = get_prompt("EXTRACTION_USER")
    user_prompt = user_prompt.replace("{{CATEGORY}}", CRITERIA["category"])
    user_prompt = user_prompt.replace("{{BUDGET}}", str(CRITERIA["budget_ceiling_cad"]))
    user_prompt = user_prompt.replace("{{MAX_WEEKS}}", str(CRITERIA["max_weeks"]))
    user_prompt = user_prompt.replace("{{PROPOSAL_TEXT}}", text)

    reply = client.messages.create(
        model=os.getenv("MODEL", "claude-sonnet-5-5"),
        max_tokens=1500,
        temperature=0,
        system=get_prompt("EXTRACTION_SYSTEM"),
        messages=[{"role": "user", "content": user_prompt}],
    )
    answer = re.sub(r"^```(?:json)?\s*|\s*```$", "", reply.content[0].text.strip())  # remove code fences if present
    return clean_facts(json.loads(answer), text)


# ---------- rules: mandatory gate ----------

def check(*values):
    """'fail' if any value is False, 'unknown' if any is None, else 'pass'."""
    if False in values:
        return "fail"
    if None in values:
        return "unknown"
    return "pass"


# ---------- rules: score formulas, each gives 0-100 ----------

def experience_score(installs):
    if installs is None:
        return None
    if installs >= 12:
        return 100
    if installs >= 9:
        return 80
    if installs >= 6:
        return 60
    if installs >= 3:
        return 40
    if installs >= 1:
        return 20
    return 0


def warranty_score(panel_years, work_years):
    if panel_years is None or work_years is None:
        return None
    panel = min(panel_years / 25, 1)
    work = min(work_years / 12, 1)
    return 50 * panel + 50 * work


def team_score(p):
    points = 0
    for item in ["named_project_lead", "crew_stated", "safety_plan", "monitoring_plan"]:
        if p.get(item):
            points += 25
    return points


def missing_facts(p):
    needed = ["total_price_cad", "completion_weeks", "commercial_installs_100kw_plus",
              "panel_warranty_years", "workmanship_warranty_years"]
    return [k for k in needed if p[k] is None]


def score_all(proposals):
    results = {}

    # step 1: flags and mandatory gate
    for name, p in proposals.items():
        r = {"status": "ranked", "flags": [], "score": None, "rank": None, "reason": ""}
        if p.get("embedded_instructions"):
            r["flags"].append("text aimed at the AI or reviewer")

        licence = check(p["licence_held_by_bidder"])
        wsib_ins = check(p["wsib_clearance_confirmed"], p["liability_insurance_5m_confirmed"])
        if licence == "fail":
            r["status"] = "ineligible"
            r["reason"] = "fails the mandatory licence check (bidder does not hold its own licence)"
        elif wsib_ins == "fail":
            r["status"] = "ineligible"
            r["reason"] = "fails the mandatory WSIB / insurance check"
        elif p["total_price_cad"] is not None and p["total_price_cad"] > CRITERIA["budget_ceiling_cad"]:
            r["status"] = "ineligible"
            r["reason"] = "price is over the budget ceiling"
        elif p["completion_weeks"] is not None and p["completion_weeks"] > CRITERIA["max_weeks"]:
            r["status"] = "ineligible"
            r["reason"] = "schedule is longer than the 16-week limit"
        elif licence == "unknown" or wsib_ins == "unknown":
            r["flags"].append("mandatory item not stated")
        results[name] = r

    # step 2: best price and best schedule. Only clean, complete proposals set the benchmark,
    # so a flagged proposal (missing data, injected text) cannot shift anyone else's score.
    clean = [n for n in proposals
             if results[n]["status"] == "ranked" and not results[n]["flags"] and not missing_facts(proposals[n])]
    best_price = min((proposals[n]["total_price_cad"] for n in clean), default=None)
    best_weeks = min((proposals[n]["completion_weeks"] for n in clean), default=None)

    # step 3: weighted score
    scored = [n for n in proposals if results[n]["status"] != "ineligible"]
    for name in scored:
        p = proposals[name]
        r = results[name]
        parts = {
            "experience": experience_score(p["commercial_installs_100kw_plus"]),
            "price": None,
            "timeline": None,
            "warranty": warranty_score(p["panel_warranty_years"], p["workmanship_warranty_years"]),
            "team": team_score(p),
        }
        if p["total_price_cad"] and best_price:
            parts["price"] = min(best_price / p["total_price_cad"] * 100, 100)
        if p["completion_weeks"] and best_weeks:
            parts["timeline"] = min(best_weeks / p["completion_weeks"] * 100, 100)

        total = 0
        missing = []
        for criterion, value in parts.items():
            if value is None:
                missing.append(criterion)
            else:
                total += WEIGHTS[criterion] * value / 100

        r["parts"] = parts
        if missing:
            # never guess a missing value: flag it and show the range instead
            r["flags"].append("cannot score " + ", ".join(missing))
            r["partial"] = round(total, 1)
            r["best_case"] = round(total + sum(WEIGHTS[m] for m in missing), 1)
        else:
            r["score"] = round(total, 1)

        if r["flags"]:
            r["status"] = "flagged"

    # step 4: rank only clean proposals. Ties: lower price, then faster, then letter.
    ranked = [n for n in scored if results[n]["status"] == "ranked"]
    ranked.sort(key=lambda n: (-results[n]["score"], proposals[n]["total_price_cad"], proposals[n]["completion_weeks"], n))
    for position, name in enumerate(ranked, start=1):
        results[name]["rank"] = position
    return results


def make_reason(p, r):
    """One-line reason built from the numbers. In the full design an AI step (Prompt 2) writes this."""
    if r["status"] == "ranked":
        return "%s installs, $%s CAD, %s weeks, %s-year workmanship warranty, %s/100 team and approach." % (
            p["commercial_installs_100kw_plus"], format(p["total_price_cad"], ","), p["completion_weeks"],
            p["workmanship_warranty_years"], r["parts"]["team"])
    if r["status"] == "flagged":
        text = "; ".join(r["flags"])
        if "partial" in r:
            text += " (partial %s, best case %s)" % (r["partial"], r["best_case"])
        elif r["score"] is not None:
            text += " (provisional score %s)" % r["score"]
        return text
    return r["reason"]


def make_ranking(results, proposals):
    rows = []
    for name in sorted(results, key=lambda n: (results[n]["rank"] or 99, n)):
        r = results[name]
        rows.append({"proposal": name, "rank": r["rank"], "status": r["status"],
                     "score": r["score"], "reason": make_reason(proposals[name], r)})
    return rows


if __name__ == "__main__":
    if "--extract" in sys.argv:
        proposals = {}
        for path in sorted((HERE / "samples").glob("*.txt")):
            text = path.read_text()
            facts = extract_with_model(text)
            if looks_suspicious(text):  # the code scan overrides the model
                facts["embedded_instructions"] = True
            proposals[path.stem.upper()] = facts
    else:
        proposals = json.loads((HERE / "example_extractions.json").read_text())

    results = score_all(proposals)
    for name in sorted(results):
        r = results[name]
        print(name, r["status"], "score:", r["score"], "| partial:", r.get("partial"),
              "| best case:", r.get("best_case"), "| flags:", r["flags"])
    (HERE / "output_ranking.json").write_text(json.dumps(make_ranking(results, proposals), indent=1))
