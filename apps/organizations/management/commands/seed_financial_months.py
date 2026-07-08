from django.core.management.base import BaseCommand
from django.db import transaction

from apps.organizations.models import FinancialMonth


class Command(BaseCommand):

    help = "Seed Financial Months"

    MONTHS = [

        (1, "APR", "April", "Q1", "H1"),
        (2, "MAY", "May", "Q1", "H1"),
        (3, "JUN", "June", "Q1", "H1"),

        (4, "JUL", "July", "Q2", "H1"),
        (5, "AUG", "August", "Q2", "H1"),
        (6, "SEP", "September", "Q2", "H1"),

        (7, "OCT", "October", "Q3", "H2"),
        (8, "NOV", "November", "Q3", "H2"),
        (9, "DEC", "December", "Q3", "H2"),

        (10, "JAN", "January", "Q4", "H2"),
        (11, "FEB", "February", "Q4", "H2"),
        (12, "MAR", "March", "Q4", "H2"),
    ]

    @transaction.atomic
    def handle(self, *args, **kwargs):

        created = 0
        updated = 0

        for number, code, name, quarter, half_year in self.MONTHS:

            obj, is_created = FinancialMonth.objects.update_or_create(
                month_number=number,
                defaults={
                    "month_code": code,
                    "month_name": name,
                    "quarter": quarter,
                    "half_year": half_year,
                    "display_order": number,
                    "is_active": True,
                },
            )

            if is_created:
                created += 1
                self.stdout.write(
                    self.style.SUCCESS(f"Created : {name}")
                )
            else:
                updated += 1
                self.stdout.write(
                    self.style.WARNING(f"Updated : {name}")
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Created : {created}"
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Updated : {updated}"
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Financial Month Master Seed Completed Successfully."
            )
        )