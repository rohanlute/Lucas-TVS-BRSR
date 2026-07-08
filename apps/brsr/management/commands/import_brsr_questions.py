"""
Import BRSR questions and PDF-derived rendering metadata into the database.

Usage:
  python manage.py import_brsr_questions .\apps\brsr\management\commands\BRSR_questions_master_list.csv
  python manage.py import_brsr_questions .\apps\brsr\management\commands\BRSR_questions_master_list.csv --pdf-path .\apps\brsr\management\commands\report.pdf

The CSV is still the source of row ordering and hierarchy. The PDF is used
when present to enrich the stored metadata with layout, table, and option
information that the CSV does not contain.
"""

from __future__ import annotations
import csv
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify
from apps.brsr.models import BRSRPrinciple, BRSRQuestion, BRSRSection


class Command(BaseCommand):
    help = "Import BRSR questions from the master CSV"

    QUESTION_TYPE_ALIASES = {
        "select": "dropdown",
        "dropdown": "dropdown",
        "multi select": "multi_select",
        "multi-select": "multi_select",
        "multiselect": "multi_select",
        "yes/no": "yes_no",
        "yes_no": "yes_no",
        "y/n": "yes_no",
        "long text": "textarea",
        "integer": "number",
        "float": "decimal",
        "numeric": "number",
    }

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=str)
        parser.add_argument("--pdf-path", type=str, default="")

    def get_section(self, section_code, section_cache):
        if section_code not in section_cache:
            section_display_name = {
                "section_a": "Section A: General Disclosures",
                "section_b": "Section B: Management and Process Disclosures",
                "section_c": "Section C: Principle-wise Performance Disclosure",
            }.get(section_code, section_code)
            section_obj, created = BRSRSection.objects.get_or_create(
                code=section_code,
                defaults={
                    "name": section_display_name,
                    "display_order": {"section_a": 1, "section_b": 2, "section_c": 3}.get(section_code, 99),
                },
            )
            section_cache[section_code] = section_obj
            return section_obj, created
        return section_cache[section_code], False

    def get_or_create_principle(self, principle_number, principle_title, principle_cache):
        if principle_number not in principle_cache:
            principle_obj, _ = BRSRPrinciple.objects.update_or_create(
                principle_number=principle_number,
                defaults={
                    "principle_name": f"Principle {principle_number}",
                    "title": principle_title,
                },
            )
            principle_cache[principle_number] = principle_obj
        return principle_cache[principle_number]

    def build_question_id(self, section_code, principle_number, sub_section, question_number):
        prefix = section_code.replace("section_", "s")
        principle_part = f"_p{principle_number}" if principle_number is not None and section_code == "section_c" else ""
        sub_section_text = (sub_section or "").strip().lower()
        if "essential" in sub_section_text:
            sub_section_part = "_ei"
        elif "leadership" in sub_section_text:
            sub_section_part = "_li"
        else:
            sub_section_slug = slugify((sub_section or "").strip()).replace("-", "_")
            sub_section_part = f"_{sub_section_slug}" if sub_section_slug else ""
        return f"{prefix}{principle_part}{sub_section_part}_q{question_number}".lower().replace(" ", "")

    def normalize_text(self, value):
        return re.sub(r"\s+", " ", (value or "").strip()).lower()

    def normalize_question_type(self, raw_type, question_text):
        normalized = self.normalize_text(raw_type) or "textarea"
        normalized = self.QUESTION_TYPE_ALIASES.get(normalized, normalized)

        text = self.normalize_text(question_text)
        if normalized == "radio" and self._looks_like_yes_no(text):
            return "yes_no"
        if normalized == "text" and any(token in text for token in ("provide details", "describe", "briefly describe")):
            return "textarea"
        return normalized
    
    def generate_placeholder_text(self, question_type, question_text):
        text = (question_text or "").lower()

        if question_type == "email":
            return "Enter the official company email address."

        elif question_type == "phone":
            return "Enter the official contact number."

        elif question_type == "url":
            return "Enter a valid website URL."

        elif question_type == "date":
            return "Select the applicable date."

        elif question_type == "year":
            return "Enter the reporting financial year."

        elif question_type == "number":
            return "Enter a numeric value."

        elif question_type == "decimal":
            return "Enter a decimal value."

        elif question_type == "currency":
            return "Enter the amount in INR."

        elif question_type == "percentage":
            return "Enter the percentage without the % symbol."

        elif question_type == "yes_no":
            return "Select either Yes or No."

        elif question_type == "dropdown":
            return "Choose one option from the list."

        elif question_type == "multi_select":
            return "Select one or more applicable options."

        elif question_type == "textarea":
            return "Provide detailed information."

        elif question_type in ("table", "nested_table", "matrix"):
            return "Complete all applicable rows and columns."

        return ""

    def _looks_like_yes_no(self, text):
        return any(marker in text for marker in ("(yes/no)", "(y/n)", " yes/no", " yes / no", "yes or no"))

    def _looks_like_yes_no_not_applicable(self, text):
        return any(marker in text for marker in ("(yes/no/not applicable)", "(yes / no / not applicable)", "not applicable"))

    def _extract_option_labels(self, question_type, question_text, excerpt_text):
        text = self.normalize_text(f"{question_text} {excerpt_text}")
        labels = []

        if question_type == "yes_no":
            labels = ["Yes", "No"]
            if self._looks_like_yes_no_not_applicable(text):
                labels.append("Not Applicable")
            return labels

        if "standalone basis" in text and "consolidated basis" in text:
            return ["Standalone basis", "Consolidated basis"]

        if self._looks_like_yes_no(text):
            labels = ["Yes", "No"]
            if "not applicable" in text:
                labels.append("Not Applicable")
            return labels

        if question_type in {"radio", "dropdown", "multi_select", "checkbox"}:
            # Pull out slash/comma separated labels from short prompts.
            candidate_text = question_text or excerpt_text
            for chunk in re.split(r"[;|]", candidate_text):
                chunk = chunk.strip()
                if not chunk:
                    continue
                if re.search(r"\b(yes|no|not applicable)\b", chunk, re.I):
                    continue
                if " / " in chunk:
                    parts = [part.strip(" .") for part in chunk.split(" / ") if part.strip(" .")]
                    if 2 <= len(parts) <= 6:
                        return parts
            if question_type == "checkbox":
                return []
            if question_type == "dropdown":
                return []
        return []

    def _option_objects(self, labels):
        return [
            {"value": label, "label": label, "order": index + 1}
            for index, label in enumerate(labels)
        ]

    def _extract_units(self, question_text, excerpt_text):
        text = self.normalize_text(f"{question_text} {excerpt_text}")
        unit_patterns = [
            ("%", "%"),
            ("inr", "INR"),
            ("rs.", "INR"),
            ("rs", "INR"),
            ("kiloliters", "kilolitres"),
            ("kilolitres", "kilolitres"),
            ("litres", "litres"),
            ("tonnes", "tonnes"),
            ("kg", "kg"),
            ("tco2e", "tCO2e"),
        ]
        for needle, unit in unit_patterns:
            if needle in text:
                return unit
        return ""

    def _split_table_line(self, line):
        parts = [part.strip() for part in re.split(r"\s{2,}", line.strip()) if part.strip()]
        return parts

    def _parse_table_schema(self, question_type, question_text, excerpt_text, units):
        if question_type not in {"table", "nested_table", "matrix", "repeating_section"}:
            return {}

        lines = [line.rstrip() for line in (excerpt_text or "").splitlines() if line.strip()]
        if not lines:
            return {
                "layout": "table",
                "header_rows": [],
                "columns": [],
                "column_count": 0,
                "units": units,
                "repeatable_rows": True,
                "dynamic_rows": True,
                "min_rows": 1,
                "max_rows": None,
                "source_excerpt": excerpt_text,
            }

        header_lines = []
        for line in lines[1:]:
            stripped = line.strip()
            if not stripped:
                continue
            if re.match(r"^(?:\d+[a-z]?|[a-z]\.|[ivx]+\.)\b", stripped.lower()) and header_lines:
                break
            header_lines.append(stripped)
            if len(header_lines) >= 4:
                break

        if not header_lines:
            header_lines = lines[1:2]

        token_rows = [self._split_table_line(line) for line in header_lines if self._split_table_line(line)]
        max_width = max((len(row) for row in token_rows), default=0)
        flattened = []
        for idx in range(max_width):
            parts = []
            for row in token_rows:
                if idx < len(row) and row[idx] and row[idx] not in parts:
                    parts.append(row[idx])
            if parts:
                flattened.append(" / ".join(parts))

        if not flattened:
            flattened = [line.strip() for line in header_lines if line.strip()]

        def infer_cell_type(label):
            label_text = self.normalize_text(label)
            if any(token in label_text for token in ("%", "percentage")):
                return "percentage"
            if any(token in label_text for token in ("date", "year")):
                return "date" if "date" in label_text else "year"
            if any(token in label_text for token in ("email", "e-mail")):
                return "email"
            if "url" in label_text or "web link" in label_text or "website" in label_text:
                return "url"
            if "phone" in label_text or "tel" in label_text or "contact" in label_text:
                return "phone"
            if any(token in label_text for token in ("amount", "value", "cost", "number", "count", "total", "share")):
                return "number"
            return "text"

        columns = []
        for index, label in enumerate(flattened, start=1):
            key = slugify(label).replace("-", "_") or f"column_{index}"
            columns.append(
                {
                    "key": key,
                    "label": label,
                    "order": index,
                    "type": infer_cell_type(label),
                    "required": not any(marker in self.normalize_text(label) for marker in ("optional", "remarks")),
                }
            )

        layout = "matrix" if question_type == "matrix" else "nested_table" if len(header_lines) > 1 else "table"
        return {
            "layout": layout,
            "header_rows": [self._split_table_line(line) for line in header_lines],
            "columns": columns,
            "column_count": len(columns),
            "header_groups": [self._split_table_line(line) for line in header_lines[:-1]],
            "nested_headers": len(header_lines) > 1,
            "footer_rows": [],
            "static_rows": [],
            "dynamic_rows": True,
            "repeatable_rows": True,
            "min_rows": 1,
            "max_rows": None,
            "row_headers": [],
            "column_headers": [column["label"] for column in columns],
            "cell_type": "text",
            "units": units,
            "source_excerpt": excerpt_text,
        }

    def _extract_parent_number(self, question_number):
        match = re.match(r"^(?P<prefix>\d+)(?P<suffix>[a-zivx]+)?$", self.normalize_text(question_number))
        if not match:
            return "", ""
        return match.group("prefix"), match.group("suffix") or ""

    def _build_visibility_rule(self, parent_qid, question_text):
        if not parent_qid:
            return {}
        text = self.normalize_text(question_text)
        trigger_value = ""
        if "if yes" in text:
            trigger_value = "Yes"
        elif "if no" in text:
            trigger_value = "No"
        elif "not applicable" in text:
            trigger_value = "Not Applicable"
        return {
            "parent_question_id": parent_qid,
            "trigger_value": trigger_value,
            "child_question_id": None,
            "visibility_rule": "show_when_parent_matches" if trigger_value else "linked_subquestion",
        }

    def _load_pdf_lines(self, pdf_path):
        if not pdf_path:
            return []

        pdf_file = Path(pdf_path)
        if not pdf_file.exists():
            raise CommandError(f"PDF path not found: {pdf_path}")

        pdftotext_exe = shutil.which("pdftotext") or r"C:\Program Files\Git\mingw64\bin\pdftotext.exe"
        if not Path(pdftotext_exe).exists():
            self.stderr.write(self.style.WARNING("pdftotext was not found; continuing without PDF metadata."))
            return []

        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
            tmp_path = Path(tmp.name)

        try:
            subprocess.run([pdftotext_exe, "-layout", str(pdf_file), str(tmp_path)], check=True)
            return tmp_path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except Exception as exc:
            self.stderr.write(self.style.WARNING(f"PDF metadata extraction failed: {exc}"))
            return []
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except Exception:
                pass

    def _find_excerpt_for_row(self, pdf_lines, row, fallback_index):
        if not pdf_lines:
            return "", fallback_index

        question_number = self.normalize_text(row.get("question_number"))
        question_text = self.normalize_text(row.get("question_text"))
        first_terms = " ".join(question_text.split()[:8])
        search_terms = [
            f"{question_number} {question_text}",
            f"{question_number} {first_terms}",
            question_text,
            first_terms,
        ]

        start_index = fallback_index
        match_index = None
        lower_lines = [self.normalize_text(line) for line in pdf_lines]
        for needle in search_terms:
            if not needle.strip():
                continue
            for idx in range(start_index, len(lower_lines)):
                window = " ".join(lower_lines[idx : min(len(lower_lines), idx + 4)])
                if needle in window:
                    match_index = idx
                    break
            if match_index is not None:
                break

        if match_index is None:
            return "", fallback_index

        end_index = min(len(pdf_lines), match_index + 18)
        excerpt = "\n".join(pdf_lines[match_index:end_index]).strip()
        return excerpt, match_index

    def _build_validation_rules(self, row, question_type, excerpt_text, units, options, parent_question_id):
        question_text = row.get("question_text") or ""
        rules = {
            "required": False,
            "numeric_only": question_type in {"number", "decimal", "currency", "percentage", "year"},
            "min_length": None,
            "max_length": None,
            "decimal_precision": 2 if question_type in {"decimal", "currency", "percentage"} else None,
            "regex": None,
            "date_validation": question_type == "date",
            "email_validation": question_type == "email",
            "url_validation": question_type == "url",
            "range_limits": None,
            "default_value": None,
            "units": units,
            "allowed_values": options,
            "source_excerpt": excerpt_text,
        }

        if question_type == "year":
            rules["range_limits"] = {"min": 1900, "max": 2100}
        if question_type == "phone":
            rules["regex"] = r"^[0-9+\-\s()]{7,}$"
        if question_type == "email":
            rules["regex"] = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
        if question_type == "url":
            rules["regex"] = r"^https?://"
        if question_type in {"radio", "yes_no", "dropdown", "multi_select", "checkbox"} and options:
            rules["allowed_values"] = options

        table_schema = self._parse_table_schema(question_type, question_text, excerpt_text, units)
        if table_schema:
            rules["table_schema"] = table_schema
            if table_schema.get("layout") in {"nested_table", "matrix"}:
                rules["component_type"] = table_schema["layout"]

        visibility_rule = self._build_visibility_rule(parent_question_id, question_text)
        if visibility_rule:
            rules["conditional_logic"] = visibility_rule

        return rules

    def _build_question_payload(self, row, question_id, parent_question_id, pdf_lines, fallback_index):
        qnum = (row.get("question_number") or "").strip()
        sub_section = (row.get("sub_section") or "").strip()
        question_text = (row.get("question_text") or "").strip()
        raw_question_type = (row.get("question_type") or "").strip()
        question_type = self.normalize_question_type(raw_question_type, question_text)
        excerpt_text, match_index = self._find_excerpt_for_row(pdf_lines, row, fallback_index)
        csv_options = (row.get("options") or "").strip()
        if csv_options:
            option_labels = [opt.strip() for opt in csv_options.split("|") if opt.strip()]
        else:
            option_labels = self._extract_option_labels(
                question_type,
                question_text,
                excerpt_text,
            )

        option_objects = self._option_objects(option_labels)
        units = self._extract_units(question_text, excerpt_text)
        validation_rules = self._build_validation_rules(
            row=row,
            question_type=question_type,
            excerpt_text=excerpt_text,
            units=units,
            options=option_objects,
            parent_question_id=parent_question_id,
        )
        placeholder_text = {
            "text": "Enter response",
            "textarea": "Enter detailed response",
            "number": "Enter number",
            "decimal": "Enter decimal value",
            "currency": "Enter amount",
            "percentage": "Enter percentage",
            "year": "Enter year",
            "email": "name@example.com",
            "url": "https://example.com",
            "phone": "Enter phone number",
            "dropdown": "Select an option",
            "select": "Select an option",
            "radio": "",
            "yes_no": "",
        }.get(question_type, "")

        placeholder_text = (row.get("placeholder_text") or "").strip()
        if not placeholder_text and excerpt_text:
            lines = [line.strip() for line in excerpt_text.splitlines() if line.strip()]
            if len(lines) > 1 and not lines[1].startswith(
                ("S. No", "S. no", "Particulars", "Location", "Data privacy")
            ):
                        placeholder_text = lines[1]

        if not placeholder_text:
            placeholder_text = self.generate_placeholder_text(question_type, question_text)

        return {
            "question_number": qnum,
            "sub_section": sub_section,
            "question_text": question_text,
            "question_type": question_type,
            "placeholder_text": placeholder_text or None,
            "options": option_objects,
            "validation_rules": validation_rules,
            "pdf_excerpt": excerpt_text,
            "pdf_match_index": match_index,
        }

    def create_or_update_question(self, section_obj, principle_obj, row, order, question_id, parent_question=None, pdf_lines=None, fallback_index=0):
        payload = self._build_question_payload(
            row=row,
            question_id=question_id,
            parent_question_id=parent_question.question_id if parent_question else "",
            pdf_lines=pdf_lines or [],
            fallback_index=fallback_index,
        )
        return BRSRQuestion.objects.update_or_create(
            question_id=question_id,
            defaults=dict(
                section=section_obj,
                principle=principle_obj,
                question_text=payload["question_text"],
                question_number=payload["question_number"],
                question_type=payload["question_type"],
                is_required=payload["validation_rules"].get("required", False),
                display_order=order,
                placeholder_text=payload["placeholder_text"],
                options=payload["options"],
                validation_rules=payload["validation_rules"],
                sub_section=payload["sub_section"],
                parent_question=parent_question,
                is_active=True,
            ),
        )

    def handle(self, *args, **options):
        path = options["csv_path"]
        pdf_path = options.get("pdf_path") or ""
        created_sections, created_questions, updated_questions = 0, 0, 0

        section_cache = {}
        principle_cache = {}
        section_c_rows = []
        group_roots = {}
        pdf_lines = self._load_pdf_lines(pdf_path)
        pdf_cursor = 0

        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        with transaction.atomic():
            for order, row in enumerate(rows, start=1):
                section_code = (row.get("section_code") or "").strip().lower()
                if not section_code:
                    continue

                section_obj, created = self.get_section(section_code, section_cache)
                if created:
                    created_sections += 1

                if section_code == "section_c":
                    section_c_rows.append((section_obj, row, order))
                    continue

                question_number = (row.get("question_number") or "").strip()
                group_key, suffix = self._extract_parent_number(question_number)
                parent_question = group_roots.get((section_code, group_key))
                question_id = self.build_question_id(section_code, None, row.get("sub_section", ""), question_number)

                question_obj, created_question = self.create_or_update_question(
                    section_obj=section_obj,
                    principle_obj=None,
                    row=row,
                    order=order,
                    question_id=question_id,
                    parent_question=parent_question,
                    pdf_lines=pdf_lines,
                    fallback_index=pdf_cursor,
                )
                _, matched_index = self._find_excerpt_for_row(pdf_lines, row, pdf_cursor)
                if matched_index is not None:
                    pdf_cursor = max(pdf_cursor, matched_index)
                if created_question:
                    created_questions += 1
                else:
                    updated_questions += 1

                if group_key and suffix in {"a", "i", ""}:
                    group_roots[(section_code, group_key)] = question_obj

            for section_obj, row, order in section_c_rows:
                principle_number = None
                principle_title = None
                raw_principle_number = (row.get("principle_number") or "").strip()
                if raw_principle_number:
                    principle_number = int(float(raw_principle_number))
                    principle_title = (row.get("section_name") or "").strip()
                if principle_number is not None:
                    self.get_or_create_principle(principle_number, principle_title, principle_cache)

            for section_obj, row, order in section_c_rows:
                raw_principle_number = (row.get("principle_number") or "").strip()
                principle_number = int(float(raw_principle_number)) if raw_principle_number else None
                principle_obj = None
                if principle_number is not None:
                    principle_obj = self.get_or_create_principle(
                        principle_number,
                        (row.get("section_name") or "").strip(),
                        principle_cache,
                    )

                question_number = (row.get("question_number") or "").strip()
                group_key, suffix = self._extract_parent_number(question_number)
                parent_question = group_roots.get(("section_c", principle_number, group_key))
                question_id = self.build_question_id(
                    "section_c",
                    principle_number,
                    row.get("sub_section", ""),
                    question_number,
                )

                question_obj, created_question = self.create_or_update_question(
                    section_obj=section_obj,
                    principle_obj=principle_obj,
                    row=row,
                    order=order,
                    question_id=question_id,
                    parent_question=parent_question,
                    pdf_lines=pdf_lines,
                    fallback_index=pdf_cursor,
                )
                _, matched_index = self._find_excerpt_for_row(pdf_lines, row, pdf_cursor)
                if matched_index is not None:
                    pdf_cursor = max(pdf_cursor, matched_index)
                if created_question:
                    created_questions += 1
                else:
                    updated_questions += 1

                if group_key and suffix in {"a", "i", ""}:
                    group_roots[("section_c", principle_number, group_key)] = question_obj

        self.stdout.write(
            self.style.SUCCESS(
                f"Sections created: {created_sections} | Questions created: {created_questions} | updated: {updated_questions}"
            )
        )
