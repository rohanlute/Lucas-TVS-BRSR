"""
Import BRSR questions directly from brsr_question_structures.json 
python manage.py import_brsr_question_structures .\apps\brsr\management\commands\data\brsr_question_structures.json
"""
 
from __future__ import annotations
import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
 
from apps.brsr.models import BRSRPrinciple, BRSRQuestion, BRSRSection
 
PRINCIPLE_TITLES = {
    1: "Businesses should conduct and govern themselves with integrity, and in a manner "
       "that is Ethical, Transparent and Accountable",
    2: "Businesses should provide goods and services in a manner that is sustainable and safe",
    3: "Businesses should respect and promote the well-being of all employees, including "
       "those in their value chains",
    4: "Businesses should respect the interests of and be responsive to all its stakeholders",
    5: "Businesses should respect and promote human rights",
    6: "Businesses should respect and make efforts to protect and restore the environment",
    7: "Businesses, when engaging in influencing public and regulatory policy, should do so "
       "in a manner that is responsible and transparent",
    8: "Businesses should promote inclusive growth and equitable development",
    9: "Businesses should engage with and provide value to their consumers in a responsible manner",
}
 
SECTION_DISPLAY_NAMES = {
    "section_a": "Section A: General Disclosures",
    "section_b": "Section B: Management and Process Disclosures",
    "section_c": "Section C: Principle-wise Performance Disclosure",
}
 
SECTION_DISPLAY_ORDER = {"section_a": 1, "section_b": 2, "section_c": 3}
 
 
def infer_question_type(fields: list[dict]) -> str:
    """
    A question can carry multiple fields (e.g. a table + a follow-up
    textarea — see Principle 1 / E1 in the extraction). question_type is
    still useful as a coarse filter/icon in the UI, so pick the field kind
    that best represents the question as a whole; the full multi-field
    detail always lives in validation_rules['fields'] regardless.
    """
    kinds = [f["kind"] for f in fields]
    if not kinds:
        return "textarea"
    if "table" in kinds:
        return "table"
    if "radio" in kinds:
        return "radio"
    if "checkbox_group" in kinds:
        return "checkbox"
    if "select" in kinds:
        return "dropdown"
    if "input" in kinds:
        # use the actual input type (email/url/number/text/...) if there's exactly one
        input_fields = [f for f in fields if f["kind"] == "input"]
        if len(input_fields) == 1:
            return input_fields[0].get("type") or "text"
        return "text"
    return "textarea"
 
 
class Command(BaseCommand):
    help = "Import BRSR questions from the extracted template-structure JSON"
 
    def add_arguments(self, parser):
        parser.add_argument("json_path", type=str)
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Parse and report without writing to the database",
        )
        parser.add_argument(
            "--reset",
            action="store_true",
            help=(
                "Delete ALL existing BRSRQuestion rows before importing. Use this once "
                "when switching over from an earlier importer (e.g. the CSV-based one) "
                "so its rows don't collide with this command's unique_together constraint "
                "on (section, principle, question_number, sub_section, version)."
            ),
        )
 
    def handle(self, *args, **options):
        json_path = Path(options["json_path"])
        if not json_path.exists():
            raise CommandError(f"File not found: {json_path}")
 
        data = json.loads(json_path.read_text(encoding="utf-8"))
 
        if options["reset"] and not options["dry_run"]:
            deleted_count, _ = BRSRQuestion.objects.all().delete()
            self.stdout.write(self.style.WARNING(f"--reset: deleted {deleted_count} existing BRSRQuestion rows"))
 
        section_cache: dict[str, BRSRSection] = {}
        principle_cache: dict[int, BRSRPrinciple] = {}
        stats = {"sections": 0, "principles": 0, "created": 0, "updated": 0, "skipped": 0}
 
        dry_run = options["dry_run"]
 
        with transaction.atomic():
            for block_key, block in data.items():
                section_code = "section_c" if block_key.startswith("principle_") else block_key
                principle_number = block.get("principle_number")
 
                section_obj = self._get_section(section_code, section_cache, stats, dry_run)
                principle_obj = None
                if principle_number is not None:
                    principle_obj = self._get_principle(principle_number, principle_cache, stats, dry_run)
 
                for order, q in enumerate(block["questions"], start=1):
                    fields = q.get("fields", [])
                    if not fields:
                        stats["skipped"] += 1
                        self.stdout.write(self.style.WARNING(
                            f"  no fields extracted for {block_key} / {q['local_id']} "
                            f"('{q['title'][:60]}') — skipping"
                        ))
                        continue
 
                    question_id = self._build_question_id(section_code, principle_number, q)
                    question_type = infer_question_type(fields)
 
                    validation_rules = {
                        "fields": fields,           # the full, exact structure — table/radio/textarea/etc.
                        "source_template": block_key,
                        "source_local_id": q["local_id"],
                    }
 
                    if dry_run:
                        self.stdout.write(f"  would upsert {question_id} ({question_type})")
                        continue
 
                    defaults = dict(
                        section=section_obj,
                        principle=principle_obj,
                        question_text=q["title"],
                        question_number=q["question_number"],
                        question_type=question_type,
                        is_required=False,  # not encoded in the source templates
                        display_order=order,
                        help_text=q.get("help_text") or None,
                        placeholder_text=None,
                        options=[],  # per-field options live inside validation_rules['fields']
                        validation_rules=validation_rules,
                        sub_section=q.get("sub_section") or "",
                        is_active=True,
                    )
                    created = self._upsert_question(question_id, defaults)
                    stats["created" if created else "updated"] += 1
 
        self.stdout.write(self.style.SUCCESS(
            f"Sections: {stats['sections']} | Principles: {stats['principles']} | "
            f"Questions created: {stats['created']} | updated: {stats['updated']} | "
            f"skipped (no fields): {stats['skipped']}"
        ))
 
    # -----------------------------------------------------------------
    def _upsert_question(self, question_id, defaults):
        """
        There are two unique constraints on BRSRQuestion that can each
        independently already "own" the row we're about to write:
          (a) question_id itself (unique=True)
          (b) (section, principle, question_number, sub_section, version)
              (unique_together)
        A rerun can collide on EITHER one depending on whether question_id
        or the natural key drifted since the last import (e.g. the JSON
        was regenerated with slightly different question_number text, or
        a previous importer run used a different question_id scheme for
        the same logical question). So: try question_id first: if a row
        exists there, update it in place — including its natural-key
        fields, since a legitimate re-extraction can shift those. If
        question_id isn't found, check whether a different row already
        occupies the natural-key slot we're about to insert into; if so,
        adopt that row (repoint its question_id) instead of inserting a
        duplicate. Only insert fresh if neither lookup finds anything.
        """
        try:
            obj = BRSRQuestion.objects.get(question_id=question_id)
            for field, value in defaults.items():
                setattr(obj, field, value)
            obj.save()
            return False  # updated
        except BRSRQuestion.DoesNotExist:
            pass
 
        natural_key = dict(
            section=defaults["section"],
            principle=defaults["principle"],
            question_number=defaults["question_number"],
            sub_section=defaults["sub_section"],
            version=1,
        )
        existing = BRSRQuestion.objects.filter(**natural_key).first()
        if existing:
            existing.question_id = question_id
            for field, value in defaults.items():
                setattr(existing, field, value)
            existing.save()
            self.stdout.write(self.style.WARNING(
                f"  adopted existing row (was question_id={existing.question_id!r}) -> {question_id}"
            ))
            return False  # updated
 
        BRSRQuestion.objects.create(question_id=question_id, **defaults)
        return True  # created
 
    # -----------------------------------------------------------------
    def _get_section(self, section_code, cache, stats, dry_run):
        if section_code in cache:
            return cache[section_code]
        if dry_run:
            return None
        obj, created = BRSRSection.objects.get_or_create(
            code=section_code,
            defaults={
                "name": SECTION_DISPLAY_NAMES.get(section_code, section_code),
                "display_order": SECTION_DISPLAY_ORDER.get(section_code, 99),
            },
        )
        if created:
            stats["sections"] += 1
        cache[section_code] = obj
        return obj
 
    def _get_principle(self, principle_number, cache, stats, dry_run):
        if principle_number in cache:
            return cache[principle_number]
        if dry_run:
            return None
        obj, created = BRSRPrinciple.objects.update_or_create(
            principle_number=principle_number,
            defaults={
                "principle_name": f"Principle {principle_number}",
                "title": PRINCIPLE_TITLES.get(principle_number, ""),
            },
        )
        if created:
            stats["principles"] += 1
        cache[principle_number] = obj
        return obj
 
    def _build_question_id(self, section_code, principle_number, q):
        """
        Keep IDs stable and human-readable, matching the E1/L1/q1 convention
        already used in your templates and JS (question_save_api_url etc.
        reference question_id directly) — e.g. sc_p6_e1, sa_q1, sb_q10.
        """
        prefix = section_code.replace("section_", "s")
        principle_part = f"_p{principle_number}" if principle_number is not None else ""
        return f"{prefix}{principle_part}_{q['local_id']}".lower()