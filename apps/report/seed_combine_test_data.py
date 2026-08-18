"""
Seed script to verify the "All Plants" combining logic
(get_brsr_report_data_all_plants / _combine_plant_values) with real data.

USAGE
-----
Run inside `python manage.py shell`:

    exec(open("seed_combine_test_data.py").read())

Or paste the body directly into the shell. It's idempotent-ish (uses
update_or_create keyed on assignment+question) so re-running it just
overwrites the same two test answers rather than duplicating rows.

WHAT IT DOES
------------
Uses two real questions from your own diagnostic output:

  1. sc_p1_e8 "Accounts Payables Days"
     - numeric field: e8_days_cy
     - Apex Auto Components (plant 3)   -> "22"
     - Sterling Foundry Solutions (plant 4) -> "44"
     - Expected in the "All Plants" PDF/Excel: "66"

  2. sc_p4_e1 "Describe the processes for identifying key stakeholder
     groups of the entity" (plain textarea, field name
     "identifyingStakeholders")
     - Apex Auto Components (plant 3)   -> "We map stakeholders through
       quarterly business reviews."
     - Sterling Foundry Solutions (plant 4) -> "Stakeholders are
       identified via annual surveys and site visits."
     - Expected in the "All Plants" PDF/Excel: two lines, one per plant
       ("Apex Auto Components: ...", "Sterling Foundry Solutions: ...")

After running this, generate the "All Plants" BRSR PDF/Excel for FY
2026-2027 and check those two questions specifically.
"""

from apps.brsr.models import Assignment, BRSRQuestion, QuestionResponse
from apps.organizations.models import Plant

FINANCIAL_YEAR = "2026-2027"

APEX_PLANT_ID = 3       # Apex Auto Components
STERLING_PLANT_ID = 4   # Sterling Foundry Solutions


def _get_or_create_assignment(plant_id, financial_year):
    """
    Reuses an existing Assignment for this plant/year if one exists
    (you already have assignments for plant 3 and plant 4), otherwise
    creates a minimal one. Adjust required fields below if your
    Assignment model needs more than plant_id/financial_year to save.
    """
    assignment = Assignment.objects.filter(
        plant_id=plant_id, financial_year=financial_year
    ).first()
    if assignment:
        return assignment
    return Assignment.objects.create(
        plant_id=plant_id,
        financial_year=financial_year,
    )


def _set_answer(plant_id, question_id, response_json, response_value=""):
    assignment = _get_or_create_assignment(plant_id, FINANCIAL_YEAR)
    question = BRSRQuestion.objects.get(question_id=question_id)

    obj, created = QuestionResponse.objects.update_or_create(
        assignment=assignment,
        question=question,
        defaults={
            "response_json": response_json,
            "response_value": response_value,
            "status": "submitted",
        },
    )
    verb = "Created" if created else "Updated"
    print(f"{verb} response: plant={plant_id} question={question_id} -> {response_json}")
    return obj


# -- 1. Numeric field: should SUM to 66 in the "All Plants" report -------
_set_answer(
    APEX_PLANT_ID,
    "sc_p1_e8",
    {"e8_days_cy": "22", "e8_days_py": "23"},
)
_set_answer(
    STERLING_PLANT_ID,
    "sc_p1_e8",
    {"e8_days_cy": "44", "e8_days_py": "10"},
)

# -- 2. Text field: should appear as one line per plant -------------------
_set_answer(
    APEX_PLANT_ID,
    "sc_p4_e1",
    {"identifyingStakeholders": "We map stakeholders through quarterly business reviews."},
)
_set_answer(
    STERLING_PLANT_ID,
    "sc_p4_e1",
    {"identifyingStakeholders": "Stakeholders are identified via annual surveys and site visits."},
)

print()
print("Done. Now generate the 'All Plants' BRSR PDF/Excel for FY 2026-2027 and check:")
print("  - Principle 1 > Accounts Payables Days > 'FY 2026-27 Current Financial Year' == 66")
print("  - Principle 4 > 'Describe the processes for identifying key stakeholder groups...'")
print("    should show two lines, one per plant, not a single merged sentence.")