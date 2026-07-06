"""
Use the command below to import the questions into the database.
python manage.py import_brsr_questions .\apps\brsr\management\commands\BRSR_questions_master_list.csv

Reads the CSV produced from the sample BRSR report and creates/updates:
  - BRSRSection (section_a / section_b / section_c, deduped)
  - BRSRPrinciple (section_c rows are imported first by principle number)
  - BRSRQuestion (one row per question, question_id auto-generated)
"""

import csv
from django.core.management.base import BaseCommand
from django.utils.text import slugify
from apps.brsr.models import BRSRSection, BRSRPrinciple, BRSRQuestion


class Command(BaseCommand):
    help = "Import BRSR questions from the master CSV"

    def add_arguments(self, parser):
        parser.add_argument('csv_path', type=str)

    def get_section(self, section_code, section_cache):
        if section_code not in section_cache:
            section_display_name = {
                'section_a': 'Section A: General Disclosures',
                'section_b': 'Section B: Management and Process Disclosures',
                'section_c': 'Section C: Principle-wise Performance Disclosure',
            }.get(section_code, section_code)
            section_obj, created = BRSRSection.objects.get_or_create(
                code=section_code,
                defaults={
                    'name': section_display_name,
                    'display_order': {'section_a': 1, 'section_b': 2, 'section_c': 3}.get(section_code, 99),
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
                    'principle_name': f'Principle {principle_number}',
                    'title': principle_title,
                },
            )
            principle_cache[principle_number] = principle_obj
        return principle_cache[principle_number]

    def build_question_id(self, section_code, principle_number, sub_section, question_number):
        prefix = section_code.replace('section_', 's')
        principle_part = f'_p{principle_number}' if principle_number is not None and section_code == 'section_c' else ''
        sub_section_text = (sub_section or '').strip().lower()
        if 'essential' in sub_section_text:
            sub_section_part = '_ei'
        elif 'leadership' in sub_section_text:
            sub_section_part = '_li'
        else:
            sub_section_slug = slugify((sub_section or '').strip()).replace('-', '_')
            sub_section_part = f'_{sub_section_slug}' if sub_section_slug else ''
        return f'{prefix}{principle_part}{sub_section_part}_q{question_number}'.lower().replace(' ', '')

    def create_or_update_question(self, section_obj, principle_obj, row, order, question_id):
        qnum = (row.get('question_number') or '').strip()
        sub_section = (row.get('sub_section') or '').strip()
        question_text = (row.get('question_text') or '').strip()
        question_type = (row.get('question_type') or '').strip() or 'textarea'

        return BRSRQuestion.objects.update_or_create(
            question_id=question_id,
            defaults=dict(
                section=section_obj,
                principle=principle_obj,
                question_text=question_text,
                question_number=qnum,
                question_type=question_type,
                sub_section=sub_section,
                display_order=order,
                is_active=True,
            ),
        )

    def handle(self, *args, **options):
        path = options['csv_path']
        created_sections, created_questions, updated_questions = 0, 0, 0

        section_cache = {}
        principle_cache = {}
        section_c_rows = []

        with open(path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        for order, row in enumerate(rows, start=1):
            section_code = (row.get('section_code') or '').strip().lower()
            if not section_code:
                continue

            section_obj, created = self.get_section(section_code, section_cache)
            if created:
                created_sections += 1

            if section_code == 'section_c':
                section_c_rows.append((section_obj, row, order))
                continue

            principle_obj = None
            question_id = self.build_question_id(section_code, None, row.get('sub_section', ''), row.get('question_number', ''))
            _, created_question = self.create_or_update_question(section_obj, principle_obj, row, order, question_id)
            if created_question:
                created_questions += 1
            else:
                updated_questions += 1

        for section_obj, row, order in section_c_rows:
            principle_number = None
            principle_title = None
            raw_principle_number = (row.get('principle_number') or '').strip()
            if raw_principle_number:
                principle_number = int(float(raw_principle_number))
                principle_title = (row.get('section_name') or '').strip()
            if principle_number is not None:
                self.get_or_create_principle(principle_number, principle_title, principle_cache)

        for section_obj, row, order in section_c_rows:
            principle_number = None
            principle_obj = None
            raw_principle_number = (row.get('principle_number') or '').strip()
            if raw_principle_number:
                principle_number = int(float(raw_principle_number))
                principle_obj = self.get_or_create_principle(principle_number, (row.get('section_name') or '').strip(), principle_cache)

            question_id = self.build_question_id(
                'section_c',
                principle_number,
                row.get('sub_section', ''),
                row.get('question_number', ''),
            )
            _, created_question = self.create_or_update_question(section_obj, principle_obj, row, order, question_id)
            if created_question:
                created_questions += 1
            else:
                updated_questions += 1

        self.stdout.write(self.style.SUCCESS(
            f'Sections created: {created_sections} | '
            f'Questions created: {created_questions} | updated: {updated_questions}'
        ))