"""
Pulls live data from the `brsr` app (BRSRSection, BRSRPrinciple, BRSRQuestion,
QuestionResponse) and shapes it for the report / PDF.
"""

from apps.brsr.models import BRSRSection, BRSRPrinciple, BRSRQuestion, QuestionResponse
import logging
import json

logger = logging.getLogger(__name__)

PRINCIPLE_COLUMNS = [f"P{i}" for i in range(1, 10)]  # ["P1", ..., "P9"]


def _fields_of(question):
    """The raw field definitions for this question, straight from the
    JSON that was imported into validation_rules['fields']."""
    rules = question.validation_rules or {}
    return rules.get("fields", []) or []


def _get_field_name(field):
    """Get the name of a field, handling different possible keys."""
    if 'name' in field:
        return field['name']
    if 'id' in field:
        return field['id']
    if 'key' in field:
        return field['key']
    return None


def _get_field_label(field):
    """Get the label of a field."""
    if 'label' in field:
        return field['label']
    if 'title' in field:
        return field['title']
    if 'text' in field:
        return field['text']
    return ''


# ---------------------------------------------------------------------------
# Financial-year placeholder resolution + column cleanup
# ---------------------------------------------------------------------------

def _financial_year_labels(financial_year):
    """
    ('2026-2027' | '2026-27') -> ('2026-27', '2025-26')
    Used to resolve {FY0}/{FY1} placeholders in question column headers.
    """
    if not financial_year:
        return "Current Year", "Previous Year"
    parts = str(financial_year).strip().split("-")
    try:
        start = int(parts[0])
    except (ValueError, IndexError):
        return str(financial_year), ""
    current_label = f"{start}-{str(start + 1)[-2:]}"
    previous_label = f"{start - 1}-{str(start)[-2:]}"
    return current_label, previous_label


def _resolve_placeholders(text, financial_year):
    if not text or "{" not in str(text):
        return text
    current_label, previous_label = _financial_year_labels(financial_year)
    return str(text).replace("{FY0}", current_label).replace("{FY1}", previous_label)


def _clean_columns(columns, financial_year=None):
    """
    Drops blank/placeholder entries from a field's column list and resolves
    {FY0}/{FY1} tokens. The row-label column is always added separately by
    the header-building code below, so a blank string already present in
    the schema's own `columns` creates a duplicate column and shifts every
    answer one column out of place -- this is what caused the Accounts
    Payables Days table to render "56" under a blank header and leave the
    real "FY {FY1}" column empty.
    """
    cleaned = [c for c in (columns or []) if str(c).strip()]
    return [_resolve_placeholders(c, financial_year) for c in cleaned]


def _answer_for(name, response_json, fallback_value):
    if not response_json:
        return fallback_value or ""
    if isinstance(response_json, str):
        try:
            response_json = json.loads(response_json)
        except Exception:
            return fallback_value or ""
    if not isinstance(response_json, dict):
        return fallback_value or ""

    if name in response_json:
        return response_json[name]

    name_lower = name.lower()
    for key, value in response_json.items():
        if key.lower() == name_lower:
            return value

    partial_matches = [
        v for k, v in response_json.items()
        if k.lower() in name_lower or name_lower in k.lower()
    ]
    if len(partial_matches) == 1:
        return partial_matches[0]

    return fallback_value or ""


def _has_value(value):
    """True if a value (scalar, list, or dict) contains meaningful data."""
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() not in ("", "-")
    if isinstance(value, bool):
        return True
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, (list, tuple)):
        return any(_has_value(item) for item in value)
    if isinstance(value, dict):
        return any(_has_value(v) for v in value.values())
    return bool(value)


def _row_has_data(row):
    """
    True if this top-level row (or any of its sub_questions) carries an
    actual submitted answer. Used to drop unanswered questions from the
    report entirely instead of rendering them blank, and reused by
    get_brsr_stats() below as the single source of truth for what counts
    as "answered" -- since for table/matrix/checkbox_group questions the
    real answer lives in sub_questions / table_rows / matrix_rows, not in
    the row's own top-level answer_value.
    """
    if _has_value(row.get("answer_value")):
        return True
    if _has_value(row.get("answer_json")):
        return True

    for sub in row.get("sub_questions", []) or []:
        sub_type = sub.get("question_type")

        if sub_type == "matrix":
            for mrow in sub.get("matrix_rows", []) or []:
                if any(_has_value(v) for v in (mrow.get("values") or {}).values()):
                    return True
            continue

        if sub_type == "table":
            for trow in sub.get("table_rows", []) or []:
                # skip index 0 -- that's the row label, not an answer cell
                if any(_has_value(cell) for cell in trow[1:]):
                    return True
            continue

        if _has_value(sub.get("answer_value")):
            return True

    return False


def _is_principle_matrix(field):
    """True if this table field's columns end in exactly P1..P9."""
    columns = field.get("columns", [])
    return len(columns) >= 9 and columns[-9:] == PRINCIPLE_COLUMNS


def _has_year_headers(columns):
    """True if any column looks like a per-year header."""
    return any(("FY" in col or "Financial Year" in col) for col in columns)


def _split_label_and_data_columns(columns, rows):
    """
    A schema's `columns` list sometimes includes one leading entry that's
    really the header for the row-label column itself (e.g. "Parameter"
    labeling rows like "Environmental and social parameters relevant to
    the product"), not a second data column -- the row only actually has
    one answer field ("As a percentage to total turnover").

    The header-building code below always prepends a label-column slot on
    top of whatever's in `columns`, so when `columns` already has one more
    entry than any row has real fields for, that surplus entry ends up as
    a phantom data-column header. The row's one real value then lands
    under it (here, under "Parameter"), leaving the true last column
    ("As a percentage to total turnover") blank.

    Detects that surplus by comparing declared column count against the
    actual number of answer fields per row, and returns
    (label_header, data_columns) so the caller uses the surplus column as
    the label header instead of manufacturing a blank one.
    """
    if not rows or not columns:
        return "", columns

    max_fields = max((len(row.get("fields", []) or []) for row in rows), default=len(columns))
    if len(columns) <= max_fields:
        return "", columns

    surplus = len(columns) - max_fields
    label_header = columns[surplus - 1]
    data_columns = columns[surplus:]
    return label_header, data_columns


def _build_matrix_subquestion(field, response_json):
    """Builds a principle-matrix table grouped as one sub_question."""
    matrix_rows = []
    for row in field.get("rows", []):
        row_label = row.get("label") or ""
        values = {}
        for cell in row.get("fields", []):
            col = cell.get("column")  # "P1".."P9"
            name = _get_field_name(cell)
            if not col or not name:
                continue
            values[col] = _answer_for(name, response_json, "")
        matrix_rows.append({"label": row_label, "values": values})

    return {
        "question_number": "",
        "question_text": _get_field_label(field),
        "question_type": "matrix",
        "matrix_columns": PRINCIPLE_COLUMNS,
        "matrix_rows": matrix_rows,
        "answer_value": "",
        "answer_json": {},
        "sub_questions": [],
    }


"""
PATCH for apps/report/brsr_report_data.py -- _build_table_subquestion()

BUG
---
_build_table_subquestion() only recognized two answer shapes for a table
field:

  1. Flat dict at the top level of response_json, keyed by each row's
     schema field name (e.g. {'e8_days_cy': '56', 'e8_days_py': '23'})
     -> handled by "Case 2" (schema-driven rows/fields lookup).

  2. A list of row-dicts under response_json[field_name], where each
     dict is keyed by DISPLAY COLUMN NAME (e.g.
     [{'S. No.': '1', 'Description of Main Activity': '...'}])
     -> handled by "Case 1" (list-of-row-objects).

A third real shape exists and wasn't handled: a list of row-dicts under
response_json[field_name], where each dict is keyed by the row schema's
own per-cell FIELD NAMES instead of display columns, e.g. for
"Input material sourcing" (sc_p8_e4):

    response_json['inputSourcing'] == [
        {'e4_msme_cy': '55', 'e4_msme_py': '44'},
        {'e4_local_cy': '44', 'e4_local_py': '55'},
    ]

Because field.get("columns") for this question is NOT empty
(["Source", "FY {FY0}...", "FY {FY1}..."]), Case 1 uses those as
data_cols and does `entry.get(col, "")` -- but entry's keys are
'e4_msme_cy' etc., never equal to a column header string, so every
lookup misses and every cell renders blank ("-"), while the row label
still falls back to a bare serial number ("1", "2") -- exactly the
"headers show up, every cell is a dash" symptom.

FIX
---
Before running Case 1, collect every row.fields[].name declared in this
table's schema. If the list entries' keys overlap with those schema
field names (rather than matching display columns), flatten the list of
row-dicts into one flat dict and merge it into response_json, then let
execution fall through to Case 2 -- which already knows how to look up
each cell by its declared field name via _answer_for(). This required
NO changes to Case 1 or Case 2's existing logic; it only adds detection
+ a merge step before them.

Apply by replacing the whole _build_table_subquestion() function in
apps/report/brsr_report_data.py with the version below.
"""


def _build_table_subquestion(field, response_json, fallback_question_text, financial_year=None):
    columns = _clean_columns(field.get("columns", []), financial_year)
    rows = field.get("rows", [])
    field_name = _get_field_name(field)

    logger.info(f"Building table for: {_get_field_label(field)}")
    logger.info(f"Columns: {columns}")
    logger.info(f"Rows count: {len(rows)}")

    raw_value = _answer_for(field_name, response_json, None) if field_name else None

    # ------------------------------------------------------------------
    # Collect every per-cell field name declared across this table's own
    # row schema (e.g. {"e4_msme_cy", "e4_msme_py", "e4_local_cy",
    # "e4_local_py"} for "Input material sourcing"). Used just below to
    # tell apart "list keyed by display columns" (Case 1) from "list
    # keyed by the row schema's own field names" (Case 1b).
    # ------------------------------------------------------------------
    schema_field_names = set()
    for row in rows:
        for cell in row.get("fields", []) or []:
            n = _get_field_name(cell)
            if n:
                schema_field_names.add(n)

    if isinstance(raw_value, list) and raw_value and all(isinstance(r, dict) for r in raw_value):
        entry_keys = set()
        for entry in raw_value:
            entry_keys.update(entry.keys())

        # --------------------------------------------------------------
        # Case 1b: each list entry is keyed by the row schema's own
        # per-cell field names rather than by display column headers.
        # Column-name lookup (Case 1 below) always misses on this shape
        # since these keys are never equal to a column header string --
        # every cell would render blank. Flatten these row-dicts into
        # one flat dict keyed by field name, merge into response_json,
        # and fall through to the schema-driven Case 2 path below, which
        # already knows how to look up a value by its declared
        # row.fields[].name.
        # --------------------------------------------------------------
        if schema_field_names and (entry_keys & schema_field_names):
            logger.info(
                f"Detected list-of-row-dicts keyed by schema field names "
                f"for '{_get_field_label(field)}' -- flattening and routing "
                f"through schema-driven lookup instead of column-name match."
            )
            flattened = {}
            for entry in raw_value:
                flattened.update(entry)
            response_json = {**response_json, **flattened}
            raw_value = None  # force fallthrough past Case 1 to Case 2

    # ------------------------------------------------------------------
    # Case 1: the answer is stored as a ready-made list of row-objects,
    # e.g. response_json["businessActivities"] = [
    #     {"S. No.": "1", "Description of Main Activity": "...", ...},
    #     ...
    # ] keyed by DISPLAY COLUMN NAME, not by a schema field name.
    # ------------------------------------------------------------------
    if isinstance(raw_value, list) and raw_value and all(isinstance(r, dict) for r in raw_value):
        fallback_cols = [k for k in raw_value[0].keys() if str(k).strip()]
        table_columns = columns or fallback_cols
        label_col = table_columns[0]
        data_cols = table_columns[1:]

        headers = [[""] + data_cols]
        table_rows = []
        for idx, entry in enumerate(raw_value):
            row_label = entry.get(label_col, "") or str(idx + 1)
            row_values = [row_label]
            for col in data_cols:
                val = entry.get(col, "")
                if val is True or val == "True":
                    val = "Yes"
                elif val is False or val == "False":
                    val = "No"
                row_values.append(val)
            table_rows.append(row_values)

        logger.info(f"Built {len(table_rows)} table rows from list-of-row-objects shape")

        return {
            "question_number": "",
            "question_text": _get_field_label(field) or fallback_question_text or "",
            "question_type": "table",
            "answer_value": "",
            "answer_json": response_json,
            "sub_questions": [],
            "table_headers": headers,
            "table_rows": table_rows,
        }

    # ------------------------------------------------------------------
    # Case 2 (fallback, and where Case 1b routes to): schema-driven
    # table -- rows/columns come from validation_rules, each cell looked
    # up individually by name against response_json (now including any
    # flattened Case 1b values merged in above).
    # ------------------------------------------------------------------
    label_header, columns = _split_label_and_data_columns(columns, rows)

    if _has_year_headers(columns):
        header_row1 = [label_header]
        header_row2 = [""]
        for col in columns:
            if "FY" in col or "Financial Year" in col:
                header_row1.append(col)
                header_row2.append("")
            else:
                header_row1.append("")
                header_row2.append(col)
        headers = [header_row1, header_row2] if any(header_row2[1:]) else [header_row1]
    else:
        headers = [[label_header] + columns]

    table_rows = []
    for row in rows:
        row_label = row.get("label") or ""
        row_values = [row_label]

        for cell in row.get("fields", []):
            name = _get_field_name(cell)
            value = _answer_for(name, response_json, "") if name else ""

            if value is True or value == "True":
                value = "Yes"
            elif value is False or value == "False":
                value = "No"

            row_values.append(value)
        table_rows.append(row_values)

    logger.info(f"Built {len(table_rows)} table rows")

    return {
        "question_number": "",
        "question_text": _get_field_label(field) or fallback_question_text or "",
        "question_type": "table",
        "answer_value": "",
        "answer_json": response_json,
        "sub_questions": [],
        "table_headers": headers,
        "table_rows": table_rows,
    }


def _expand_fields_as_subquestions(question, response, financial_year=None):
    """
    Turns one BRSRQuestion's validation_rules['fields'] into a flat list of
    sub_questions.
    """
    response_json = (response.response_json if response else {}) or {}
    fallback_value = response.response_value if response else ""

    # If response_json is a string, try to parse it as JSON
    if isinstance(response_json, str):
        try:
            response_json = json.loads(response_json)
        except Exception:
            response_json = {}

    sub_questions = []

    logger.info(f"Processing question: {question.question_id} - {question.question_text}")
    logger.info(f"Response JSON keys: {list(response_json.keys()) if isinstance(response_json, dict) else 'not a dict'}")

    fields = _fields_of(question)
    logger.info(f"Fields found: {len(fields)}")

    for field in fields:
        kind = field.get("kind")
        field_label = _get_field_label(field)
        field_name = _get_field_name(field)

        logger.info(f"Processing field: {field_label} - kind: {kind} - name: {field_name}")

        if kind == "table" and _is_principle_matrix(field):
            sub_questions.append(_build_matrix_subquestion(field, response_json))
            continue

        if kind == "table":
            sub_questions.append(
                _build_table_subquestion(field, response_json, question.question_text, financial_year)
            )
            continue

        if kind == "checkbox_group":
            group_label = field_label
            for item in field.get("items", []):
                name = _get_field_name(item)
                value = item.get("value", "")
                if not name:
                    continue
                selected_values = _answer_for(name, response_json, fallback_value)
                if not isinstance(selected_values, (list, tuple)):
                    selected_values = [selected_values] if selected_values else []
                sub_questions.append({
                    "question_number": "",
                    "question_text": f"{group_label} — {item.get('label', value)}",
                    "question_type": "checkbox",
                    "answer_value": "Yes" if value in selected_values else ("" if not selected_values else "No"),
                    "answer_json": {},
                    "sub_questions": [],
                })
            continue

        if not field_name:
            # If no name, try to use the field itself as the answer
            # This handles cases where the field is the whole answer
            answer_value = response_json if isinstance(response_json, dict) else fallback_value
            sub_questions.append({
                "question_number": "",
                "question_text": field_label or question.question_text,
                "question_type": kind or "text",
                "answer_value": str(answer_value) if answer_value else "",
                "answer_json": {},
                "sub_questions": [],
            })
            continue

        answer_value = _answer_for(field_name, response_json, fallback_value)

        # If we still don't have an answer and there's a fallback
        if not answer_value and fallback_value:
            answer_value = fallback_value

        sub_questions.append({
            "question_number": "",
            "question_text": field_label,
            "question_type": field.get("type") or kind or "text",
            "answer_value": answer_value,
            "answer_json": {},
            "sub_questions": [],
        })

    return sub_questions


def _attach_answers(questions, financial_year=None, assignment_id=None, plant_id=None):
    """
    Takes a list of top-level BRSRQuestion objects and returns render-ready
    rows, each carrying its own answer plus a sub_questions list.
    """
    if not questions:
        return []

    question_ids = [q.id for q in questions]
    logger.info(f"Looking for responses for {len(question_ids)} questions")

    responses = QuestionResponse.objects.filter(question_id__in=question_ids)

    if assignment_id:
        responses = responses.filter(assignment_id=assignment_id)
        logger.info(f"Filtered by assignment_id: {assignment_id}")
    elif financial_year or plant_id:
        try:
            from apps.brsr.models import Assignment
            assignments = Assignment.objects.all()
            if financial_year:
                assignments = assignments.filter(financial_year=financial_year)
            if plant_id:
                assignments = assignments.filter(plant_id=plant_id)
            assignment_ids = list(assignments.values_list('id', flat=True))
            if assignment_ids:
                responses = responses.filter(assignment_id__in=assignment_ids)
            else:
                responses = responses.none()   # <-- everything goes blank
        except (ImportError, AttributeError) as e:
            logger.warning(f"Cannot filter by financial_year/plant_id: {e}")

    logger.info(f"Found {responses.count()} responses total")
    response_map = {}
    for r in responses.select_related("assignment").order_by("-updated_at"):
        if r.question_id not in response_map:
            response_map[r.question_id] = r
            logger.info(f"Response for question {r.question_id}: {r.response_value}")

    # Build rows
    rows = []
    for q in questions:
        response = response_map.get(q.id)

        # Get answer value
        answer_value = ""
        answer_json = {}
        status = "draft"

        if response:
            answer_value = response.response_value or ""
            answer_json = response.response_json or {}
            status = response.status or "draft"

            # If answer_json is a string, try to parse it
            if isinstance(answer_json, str):
                try:
                    answer_json = json.loads(answer_json)
                except Exception:
                    answer_json = {}

        row_data = {
            "question": q,
            "question_id": q.question_id,
            "question_number": q.question_number or "",
            "question_text": q.question_text or "",
            "question_type": q.question_type or "",
            "sub_section": q.sub_section or "",
            "help_text": q.help_text or "",
            "options": q.options or [],
            "table_schema": (q.validation_rules or {}).get("table_schema", {}) or {},
            "is_required": q.is_required,
            "answer_value": answer_value,
            "answer_json": answer_json,
            "status": status,
            "sub_questions": _expand_fields_as_subquestions(q, response, financial_year),
        }

        logger.info(f"Row for question {q.question_id}: sub_questions={len(row_data['sub_questions'])}")
        rows.append(row_data)

    return rows


def get_brsr_stats(financial_year=None, assignment_id=None, plant_id=None):
    """
    Returns (total_questions, answered_questions) across ALL active BRSR
    questions for this financial_year/plant.

    Unlike get_brsr_report_data(), this does NOT drop unanswered questions
    from the count -- that function filters each section down to only
    `_row_has_data(row) == True` rows before returning them (by design,
    since the report/PDF should only render submitted answers), which
    means the returned structure can never be used to recover the true
    denominator: "total" there is always silently equal to "answered".

    This function queries the full active question set directly so the
    "X of Y answered" stat has a real Y, and reuses the same
    _row_has_data() check the report itself uses (rather than only
    looking at a row's own top-level answer_value) so "answered" doesn't
    miss questions whose answer actually lives in sub_questions,
    table_rows, or matrix_rows -- e.g. table/matrix/checkbox_group
    question types, where the top-level answer_value is always blank by
    design and the real answer is nested.
    """
    logger.info(
        f"Getting BRSR stats for financial_year={financial_year}, "
        f"assignment_id={assignment_id}, plant_id={plant_id}"
    )

    sections = BRSRSection.objects.filter(is_active=True)

    total = 0
    answered = 0

    for section in sections:
        questions_qs = BRSRQuestion.objects.filter(
            section=section,
            is_active=True
        )
        questions = list(questions_qs)

        if section.code == "section_c":
            # Section C - only principle-linked questions count here
            relevant_questions = [q for q in questions if q.principle_id is not None]
        else:
            # Section A/B - only non-principle questions
            relevant_questions = [q for q in questions if q.principle_id is None]

        if not relevant_questions:
            continue

        rows = _attach_answers(relevant_questions, financial_year, assignment_id, plant_id)
        total += len(rows)
        answered += sum(1 for r in rows if _row_has_data(r))

    logger.info(f"BRSR stats result: total={total}, answered={answered}")
    return total, answered


def get_brsr_report_data(financial_year=None, assignment_id=None, plant_id=None):
    """
    Returns section blocks in display order.
    """
    logger.info(
        f"Getting BRSR report data for financial_year={financial_year}, "
        f"assignment_id={assignment_id}, plant_id={plant_id}"
    )

    sections = BRSRSection.objects.filter(is_active=True).order_by("display_order", "code")
    principles = list(BRSRPrinciple.objects.filter(is_active=True).order_by("principle_number"))

    report_sections = []

    for section in sections:
        questions_qs = BRSRQuestion.objects.filter(
            section=section,
            is_active=True
        ).select_related("principle").order_by("display_order", "question_number")

        questions = list(questions_qs)

        if section.code == "section_c":
            # Section C - Principle-wise
            principle_blocks = []
            for principle in principles:
                p_questions = [q for q in questions if q.principle_id == principle.id]
                if not p_questions:
                    continue
                logger.info(f"Processing principle {principle.principle_number} with {len(p_questions)} questions")

                attached_rows = _attach_answers(p_questions, financial_year, assignment_id, plant_id)
                answered_rows = [r for r in attached_rows if _row_has_data(r)]

                if not answered_rows:
                    # Nothing submitted for this principle at all -- skip it entirely
                    continue

                principle_blocks.append({
                    "principle": principle,
                    "rows": answered_rows,
                })

            report_sections.append({
                "section": section,
                "is_principle_section": True,
                "principle_blocks": principle_blocks,
            })
        else:
            # Section A or B - Regular questions
            plain_questions = [q for q in questions if q.principle_id is None]
            logger.info(f"Processing {len(plain_questions)} plain questions for section {section.code}")

            attached_rows = _attach_answers(plain_questions, financial_year, assignment_id, plant_id)
            answered_rows = [r for r in attached_rows if _row_has_data(r)]

            # Group by sub_section
            grouped = {}
            order = []
            for row in answered_rows:
                key = row["sub_section"] or "General"
                if key not in grouped:
                    grouped[key] = []
                    order.append(key)
                grouped[key].append(row)

            sub_sections = [{"title": key, "rows": grouped[key]} for key in order]

            report_sections.append({
                "section": section,
                "is_principle_section": False,
                "sub_sections": sub_sections,
            })

    logger.info(f"Generated {len(report_sections)} report sections")
    return report_sections


# ---------------------------------------------------------------------------
# Cross-plant combining ("All Plants" report)
# ---------------------------------------------------------------------------
#
# get_brsr_report_data(financial_year, plant_id=None) used to be the only
# way to get "all plants" data, and it went through _attach_answers with
# plant_id=None -- which filters Assignments by financial_year across every
# plant, then response_map keeps only the MOST RECENTLY UPDATED response
# per question. That silently discards every other plant's answer for that
# question instead of combining them.
#
# The functions below fetch each plant's answers separately (via the
# existing per-plant _attach_answers/_expand_fields_as_subquestions path,
# so table/matrix/checkbox shaping is untouched) and then merge them
# leaf-by-leaf:
#   - numeric answers (e.g. "23", "34") are SUMMED -> "57"
#   - non-numeric answers (text/sentences) are kept as {plant_name: value}
#     so nothing gets dropped
# The merged rows keep the exact same shape (answer_value / sub_questions /
# table_rows / matrix_rows) as a single-plant row, so the PDF/Excel/preview
# renderers don't need new code paths -- only
# format_combined_answer_for_display() below needs to be called wherever a
# value is finally stringified, since a combined text answer may now be a
# dict instead of a plain string.

def _try_parse_number(value):
    """Returns a float if value looks like a plain number, else None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", "")
        if cleaned.endswith("%"):
            cleaned = cleaned[:-1].strip()
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def _format_number(n):
    if float(n).is_integer():
        return str(int(n))
    return str(round(n, 2))


def _combine_plant_values(pairs):
    """
    pairs: [(plant_name, value), ...] -- one entry per plant for the SAME
    question/field.

    - All-numeric answers are summed into one total ("23" + "34" -> "57").
    - Any non-numeric answer means the field can't be summed, so every
      plant's answer is kept as {plant_name: value} instead of picking one
      and losing the rest.
    - Plants with no answer for this field are left out entirely.
    - A single plant answering is returned as a plain scalar (not a
      1-entry dict) since there's nothing to combine.
    """
    present = [(name, v) for name, v in pairs if _has_value(v)]
    if not present:
        return ""
    if len(present) == 1:
        return present[0][1]

    numbers = []
    all_numeric = True
    for _, v in present:
        n = _try_parse_number(v)
        if n is None:
            all_numeric = False
            break
        numbers.append(n)

    if all_numeric:
        return _format_number(sum(numbers))

    return {name: v for name, v in present}


def format_combined_answer_for_display(value):
    """
    Renders a _combine_plant_values() result as plain text for the
    PDF/Excel/HTML renderers, which only know how to print strings/None --
    a combined {plant_name: answer} dict becomes one "Plant: answer" line
    per plant. Non-dict values pass through unchanged.
    """
    if isinstance(value, dict):
        return "\n".join(f"{plant}: {v}" for plant, v in value.items())
    return value


def _merge_leaf(sub_by_plant):
    """Merges one sub_question (same field, one dict per plant) into one."""
    sample = next(iter(sub_by_plant.values()))
    sub_type = sample.get("question_type")
    merged = dict(sample)

    if sub_type == "matrix":
        columns = sample.get("matrix_columns", [])
        row_count = max(len(s.get("matrix_rows", [])) for s in sub_by_plant.values())
        merged_rows = []
        for idx in range(row_count):
            label = ""
            for s in sub_by_plant.values():
                mrows = s.get("matrix_rows", [])
                if idx < len(mrows) and mrows[idx].get("label"):
                    label = mrows[idx]["label"]
                    break
            merged_values = {}
            for col in columns:
                pairs = []
                for plant_name, s in sub_by_plant.items():
                    mrows = s.get("matrix_rows", [])
                    val = mrows[idx].get("values", {}).get(col, "") if idx < len(mrows) else ""
                    pairs.append((plant_name, val))
                merged_values[col] = _combine_plant_values(pairs)
            merged_rows.append({"label": label, "values": merged_values})
        merged["matrix_rows"] = merged_rows
        return merged

    if sub_type == "table":
        # Schema-driven tables (the common case) use the same fixed row
        # template for every plant, so rows align positionally. The
        # list-of-row-objects shape (see _build_table_subquestion Case 1)
        # can have a different submitted row COUNT per plant -- there's no
        # reliable cross-plant key to match those rows on, so we align
        # positionally up to the longest plant's row count and leave
        # shorter plants' missing cells blank rather than guessing a match.
        row_count = max((len(s.get("table_rows", [])) for s in sub_by_plant.values()), default=0)
        merged_table_rows = []
        for idx in range(row_count):
            row_label = ""
            num_cols = 0
            for s in sub_by_plant.values():
                trows = s.get("table_rows", [])
                if idx < len(trows) and trows[idx]:
                    if not row_label:
                        row_label = trows[idx][0]
                    num_cols = max(num_cols, len(trows[idx]))
            merged_row = [row_label]
            for col_idx in range(1, num_cols):
                pairs = []
                for plant_name, s in sub_by_plant.items():
                    trows = s.get("table_rows", [])
                    val = trows[idx][col_idx] if idx < len(trows) and col_idx < len(trows[idx]) else ""
                    pairs.append((plant_name, val))
                merged_row.append(_combine_plant_values(pairs))
            merged_table_rows.append(merged_row)
        merged["table_rows"] = merged_table_rows
        return merged

    pairs = [(plant_name, s.get("answer_value", "")) for plant_name, s in sub_by_plant.items()]
    merged["answer_value"] = _combine_plant_values(pairs)
    return merged


def _merge_row_across_plants(row_by_plant):
    """row_by_plant: {plant_name: row_dict} -- all for the SAME question."""
    sample = next(iter(row_by_plant.values()))
    merged = dict(sample)

    sub_count = len(sample.get("sub_questions", []) or [])
    if sub_count:
        merged_subs = []
        for i in range(sub_count):
            sub_by_plant = {}
            for plant_name, row in row_by_plant.items():
                subs = row.get("sub_questions", []) or []
                if i < len(subs):
                    sub_by_plant[plant_name] = subs[i]
            if sub_by_plant:
                merged_subs.append(_merge_leaf(sub_by_plant))
        merged["sub_questions"] = merged_subs
    else:
        pairs = [(plant_name, row.get("answer_value", "")) for plant_name, row in row_by_plant.items()]
        merged["answer_value"] = _combine_plant_values(pairs)

    return merged


def get_brsr_report_data_all_plants(financial_year=None, assignment_id=None, plant_ids=None):
    """
    Same output shape as get_brsr_report_data() (list of section blocks),
    but for every question, the answer is combined across ALL plants
    instead of picking one plant's most-recently-updated response:
      - numeric answers are summed
      - text answers are kept per-plant in a dict

    plant_ids: optional list to restrict which plants are combined (e.g.
    the caller's company's plants). Defaults to all active plants.
    """
    from apps.organizations.models import Plant

    if plant_ids:
        plants = list(Plant.objects.filter(id__in=plant_ids, is_active=True))
    else:
        plants = list(Plant.objects.filter(is_active=True))

    if not plants:
        return []

    logger.info(
        f"Combining BRSR report across {len(plants)} plants for "
        f"financial_year={financial_year}, assignment_id={assignment_id}"
    )

    sections = BRSRSection.objects.filter(is_active=True).order_by("display_order", "code")
    principles = list(BRSRPrinciple.objects.filter(is_active=True).order_by("principle_number"))

    report_sections = []

    for section in sections:
        questions = list(
            BRSRQuestion.objects.filter(section=section, is_active=True)
            .select_related("principle")
            .order_by("display_order", "question_number")
        )

        if section.code == "section_c":
            principle_blocks = []
            for principle in principles:
                p_questions = [q for q in questions if q.principle_id == principle.id]
                if not p_questions:
                    continue

                per_plant_rows = {
                    plant.name: _attach_answers(p_questions, financial_year, assignment_id, plant.id)
                    for plant in plants
                }

                merged_rows = []
                for idx in range(len(p_questions)):
                    row_by_plant = {
                        name: rows[idx] for name, rows in per_plant_rows.items() if idx < len(rows)
                    }
                    if row_by_plant:
                        merged_rows.append(_merge_row_across_plants(row_by_plant))

                answered_rows = [r for r in merged_rows if _row_has_data(r)]
                if not answered_rows:
                    continue

                principle_blocks.append({"principle": principle, "rows": answered_rows})

            report_sections.append({
                "section": section,
                "is_principle_section": True,
                "principle_blocks": principle_blocks,
            })
        else:
            plain_questions = [q for q in questions if q.principle_id is None]

            per_plant_rows = {
                plant.name: _attach_answers(plain_questions, financial_year, assignment_id, plant.id)
                for plant in plants
            }

            merged_rows = []
            for idx in range(len(plain_questions)):
                row_by_plant = {
                    name: rows[idx] for name, rows in per_plant_rows.items() if idx < len(rows)
                }
                if row_by_plant:
                    merged_rows.append(_merge_row_across_plants(row_by_plant))

            answered_rows = [r for r in merged_rows if _row_has_data(r)]

            grouped, order = {}, []
            for row in answered_rows:
                key = row["sub_section"] or "General"
                if key not in grouped:
                    grouped[key] = []
                    order.append(key)
                grouped[key].append(row)

            report_sections.append({
                "section": section,
                "is_principle_section": False,
                "sub_sections": [{"title": key, "rows": grouped[key]} for key in order],
            })

    logger.info(f"Generated {len(report_sections)} combined report sections")
    return report_sections