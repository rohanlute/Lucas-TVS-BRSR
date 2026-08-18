"""
Cleanup script -- undoes what seed_combine_test_data.py wrote.

USAGE (Windows, from Django shell):
    exec(open(r"C:\\path\\to\\cleanup_combine_test_data.py").read())

WHAT THIS RESTORES
-------------------
1. Apex Auto Components (plant 3), question sc_p1_e8 (Accounts Payables
   Days): your own diagnostic output BEFORE seeding showed this was
   already answered as {'e8_days_cy': '56', 'e8_days_py': '23'}. The
   seed script overwrote it to 22/23. This restores the original 56/23.

2. Apex Auto Components (plant 3), question sc_p4_e1 (stakeholder
   identification textarea): your diagnostic showed this was UNANSWERED
   before seeding (response_value: None, response_json: {}). This
   restores it to that empty state.

3. Sterling Foundry Solutions (plant 4), both questions: we have no
   pre-seed diagnostic for plant 4 specifically (only plant 3 was
   queried), so rather than guess at "original" values, this DELETES
   those two QuestionResponse rows outright, returning that question to
   "unanswered" for plant 4 -- the same as if the seed script had never
   run. If Sterling genuinely had real answers to these two questions
   before you ran the seed script, do NOT run the plant-4 deletion below
   -- check first (see the print statements this script produces; it
   shows you what it's about to delete before doing so).

Run this, read the printed "about to delete" lines, and only proceed if
they match what you expect (i.e. the same 22/44 test values you seeded).
"""

from apps.brsr.models import Assignment, BRSRQuestion, QuestionResponse

FINANCIAL_YEAR = "2026-2027"
APEX_PLANT_ID = 3
STERLING_PLANT_ID = 4


def _get_response(plant_id, question_id):
    q = BRSRQuestion.objects.get(question_id=question_id)
    assignment = Assignment.objects.filter(
        plant_id=plant_id, financial_year=FINANCIAL_YEAR
    ).first()
    if not assignment:
        return None
    return QuestionResponse.objects.filter(assignment=assignment, question=q).first()


# ---------------------------------------------------------------------
# 1. Restore Apex's original Accounts Payables Days answer
# ---------------------------------------------------------------------
r = _get_response(APEX_PLANT_ID, "sc_p1_e8")
if r:
    print(f"Restoring Apex sc_p1_e8 from {r.response_json} to original 56/23")
    r.response_json = {"e8_days_cy": "56", "e8_days_py": "23"}
    r.save(update_fields=["response_json"])
else:
    print("No response found for Apex sc_p1_e8 -- nothing to restore.")

# ---------------------------------------------------------------------
# 2. Restore Apex's original (empty) stakeholder-identification answer
# ---------------------------------------------------------------------
r = _get_response(APEX_PLANT_ID, "sc_p4_e1")
if r:
    print(f"Restoring Apex sc_p4_e1 from {r.response_json} to empty (unanswered)")
    r.response_json = {}
    r.response_value = None
    r.save(update_fields=["response_json", "response_value"])
else:
    print("No response found for Apex sc_p4_e1 -- nothing to restore.")

# ---------------------------------------------------------------------
# 3. Remove Sterling's test-only answers entirely
# ---------------------------------------------------------------------
for qid in ("sc_p1_e8", "sc_p4_e1"):
    r = _get_response(STERLING_PLANT_ID, qid)
    if r:
        print(f"About to DELETE Sterling {qid} response: {r.response_json}")
        # Uncomment the next line once you've confirmed the printed
        # value above matches the test data you seeded (44/10, and the
        # test sentence), not real Sterling data:
        r.delete()
    else:
        print(f"No response found for Sterling {qid} -- nothing to remove.")

print()
print("Review the output above. Uncomment the r.delete() line for step 3")
print("and re-run once you've confirmed those are the test values, not real data.")
