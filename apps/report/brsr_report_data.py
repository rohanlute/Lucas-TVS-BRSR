# apps/report/brsr_report_data.py
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
    # Check for 'name' key first
    if 'name' in field:
        return field['name']
    # Check for 'id' key
    if 'id' in field:
        return field['id']
    # Check for 'key' key
    if 'key' in field:
        return field['key']
    # Return None if no name found
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


def _answer_for(name, response_json, fallback_value):
    """
    Look up a single field's answer by its JSON key.
    """
    logger.info(f"Looking for answer for field: {name}")
    logger.info(f"Response JSON: {response_json}")
    
    if not response_json:
        logger.info("No response_json found")
        return fallback_value or ""
    
    # If response_json is a string, try to parse it
    if isinstance(response_json, str):
        try:
            response_json = json.loads(response_json)
        except:
            logger.info(f"Failed to parse response_json as JSON: {response_json}")
            return fallback_value or ""
    
    if not isinstance(response_json, dict):
        logger.info(f"response_json is not a dict: {type(response_json)}")
        return fallback_value or ""
    
    # Try exact match
    if name in response_json:
        value = response_json[name]
        logger.info(f"Found exact match for {name}: {value}")
        return value
    
    # Try case-insensitive match
    name_lower = name.lower()
    for key, value in response_json.items():
        if key.lower() == name_lower:
            logger.info(f"Found case-insensitive match for {name}: {value}")
            return value
    
    # Try partial match (if the field name contains the key or vice versa)
    for key, value in response_json.items():
        if key.lower() in name_lower or name_lower in key.lower():
            logger.info(f"Found partial match for {name} using {key}: {value}")
            return value
    
    logger.info(f"No match found for {name} in {list(response_json.keys())}")
    return fallback_value or ""


def _is_principle_matrix(field):
    """True if this table field's columns end in exactly P1..P9."""
    columns = field.get("columns", [])
    return len(columns) >= 9 and columns[-9:] == PRINCIPLE_COLUMNS


def _has_year_headers(columns):
    """True if any column looks like a per-year header."""
    return any(("FY" in col or "Financial Year" in col) for col in columns)


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


def _build_table_subquestion(field, response_json, fallback_question_text):
    """
    Builds a grouped table sub_question with header row(s) + data rows.
    """
    columns = field.get("columns", [])
    rows = field.get("rows", [])
    
    logger.info(f"Building table for: {_get_field_label(field)}")
    logger.info(f"Columns: {columns}")
    logger.info(f"Rows count: {len(rows)}")

    # Build headers
    if _has_year_headers(columns):
        header_row1 = [""]
        header_row2 = [""]
        for col in columns:
            if "FY" in col or "Financial Year" in col:
                header_row1.append(col)
                header_row2.append("")
            else:
                header_row1.append("")
                header_row2.append(col)
        headers = [header_row1, header_row2]
    else:
        headers = [[""] + columns]

    # Build data rows
    table_rows = []
    for row in rows:
        row_label = row.get("label") or ""
        row_values = [row_label]
        
        for cell in row.get("fields", []):
            name = _get_field_name(cell)
            value = _answer_for(name, response_json, "") if name else ""
            
            # Handle boolean values
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


def _expand_fields_as_subquestions(question, response):
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
        except:
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
                _build_table_subquestion(field, response_json, question.question_text)
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


def _attach_answers(questions, financial_year=None, assignment_id=None):
    """
    Takes a list of top-level BRSRQuestion objects and returns render-ready
    rows, each carrying its own answer plus a sub_questions list.
    """
    if not questions:
        return []
    
    question_ids = [q.id for q in questions]
    logger.info(f"Looking for responses for {len(question_ids)} questions")
    
    # Build the queryset
    responses = QuestionResponse.objects.filter(question_id__in=question_ids)
    
    # Try to filter by assignment_id or financial_year
    if assignment_id:
        responses = responses.filter(assignment_id=assignment_id)
        logger.info(f"Filtered by assignment_id: {assignment_id}")
    elif financial_year:
        # Try to filter by financial_year through assignment
        try:
            from apps.organizations.models import Assignment
            assignments = Assignment.objects.filter(financial_year=financial_year)
            assignment_ids = list(assignments.values_list('id', flat=True))
            if assignment_ids:
                responses = responses.filter(assignment_id__in=assignment_ids)
                logger.info(f"Filtered by financial_year: {financial_year} with {len(assignment_ids)} assignments")
            else:
                logger.warning(f"No assignments found for financial_year: {financial_year}")
        except (ImportError, AttributeError):
            logger.warning(f"Cannot filter by financial_year: {financial_year}")
    
    logger.info(f"Found {responses.count()} responses total")

    # Build response map
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
                except:
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
            "sub_questions": _expand_fields_as_subquestions(q, response),
        }
        
        logger.info(f"Row for question {q.question_id}: sub_questions={len(row_data['sub_questions'])}")
        rows.append(row_data)
    
    return rows


def get_brsr_report_data(financial_year=None, assignment_id=None):
    """
    Returns section blocks in display order.
    """
    logger.info(f"Getting BRSR report data for financial_year={financial_year}, assignment_id={assignment_id}")
    
    # Get all active sections
    sections = BRSRSection.objects.filter(is_active=True).order_by("display_order", "code")
    logger.info(f"Found {sections.count()} active sections")
    
    # Get all active principles
    principles = list(BRSRPrinciple.objects.filter(is_active=True).order_by("principle_number"))
    logger.info(f"Found {len(principles)} active principles")

    report_sections = []

    for section in sections:
        logger.info(f"Processing section: {section.code} - {section.name}")
        
        # Get questions for this section
        questions_qs = BRSRQuestion.objects.filter(
            section=section, 
            is_active=True
        ).select_related("principle").order_by("display_order", "question_number")
        
        questions = list(questions_qs)
        logger.info(f"Found {len(questions)} questions for section {section.code}")

        if section.code == "section_c":
            # Section C - Principle-wise
            principle_blocks = []
            for principle in principles:
                p_questions = [q for q in questions if q.principle_id == principle.id]
                if not p_questions:
                    continue
                logger.info(f"Processing principle {principle.principle_number} with {len(p_questions)} questions")
                
                # Attach answers to principle questions
                attached_rows = _attach_answers(p_questions, financial_year, assignment_id)
                
                principle_blocks.append({
                    "principle": principle,
                    "rows": attached_rows,
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
            
            # Attach answers to plain questions
            attached_rows = _attach_answers(plain_questions, financial_year, assignment_id)

            # Group by sub_section
            grouped = {}
            order = []
            for row in attached_rows:
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