"""
Glue: runs the three stages over a list of reports.

    report_text --parse.py--> parsed --card.py--> card --rules.py--> {criterion: [ids]}

Used by both evaluate.py (train) and run.py (test).
"""
from card import build_card
from parse import parse_report
from rules import RULES


def cards_for(reports):
    """[{id, report_text, ...}] -> {id: card}"""
    return {r["id"]: build_card(parse_report(r["report_text"])) for r in reports}


def match_all(cards):
    """Select-all-that-apply: every card vs every rule -> {criterion: [ids]}."""
    return {cid: [rid for rid, card in cards.items() if rule(card)]
            for cid, rule in RULES.items()}
