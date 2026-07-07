from django.core.management.base import BaseCommand
from django.db import transaction

from apps.environmental.models import (
    EmissionScope,
    EmissionCategory,
)


class Command(BaseCommand):
    help = "Seed Environmental Master Data"

    @transaction.atomic
    def handle(self, *args, **options):

        self.stdout.write("")
        self.stdout.write("=" * 70)
        self.stdout.write(
            self.style.SUCCESS("Environmental Master Data Seeder")
        )
        self.stdout.write("=" * 70)

        self.seed_scopes()
        self.seed_categories()

        self.stdout.write("")
        self.stdout.write("=" * 70)
        self.stdout.write(
            self.style.SUCCESS("Environmental Master Data Seed Completed Successfully.")
        )
        self.stdout.write("=" * 70)

    # ==========================================================
    # Scope Master
    # ==========================================================

    def seed_scopes(self):

        self.stdout.write("")
        self.stdout.write(
            self.style.HTTP_INFO("Seeding Emission Scopes...")
        )

        scopes = [
            {
                "code": "S1",
                "name": "Scope 1",
                "description": "Direct greenhouse gas emissions from owned or controlled sources.",
                "display_order": 1,
                "is_active": True,
            },
            {
                "code": "S2",
                "name": "Scope 2",
                "description": "Indirect greenhouse gas emissions from purchased electricity, steam, heating and cooling.",
                "display_order": 2,
                "is_active": True,
            },
            {
                "code": "S3",
                "name": "Scope 3",
                "description": "Other indirect greenhouse gas emissions across the value chain.",
                "display_order": 3,
                "is_active": True,
            },
        ]

        created = 0
        updated = 0

        for scope in scopes:

            obj, is_created = EmissionScope.objects.update_or_create(
                code=scope["code"],
                defaults={
                    "name": scope["name"],
                    "description": scope["description"],
                    "display_order": scope["display_order"],
                    "is_active": scope["is_active"],
                },
            )

            if is_created:
                created += 1
                self.stdout.write(
                    self.style.SUCCESS(f"   Created : {obj.name}")
                )
            else:
                updated += 1
                self.stdout.write(
                    self.style.WARNING(f"   Updated : {obj.name}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Scope Master -> Created: {created}, Updated: {updated}"
            )
        )

    # ==========================================================
    # Category Master
    # ==========================================================

    def seed_categories(self):

        self.stdout.write("")
        self.stdout.write(
            self.style.HTTP_INFO("Seeding Emission Categories...")
        )

        categories = [

            # -------------------------------------------------
            # Scope 1
            # -------------------------------------------------

            {
                "scope": "S1",
                "code": "STC",
                "name": "Stationary Combustion",
                "description": "Fuel burned in boilers, furnaces, DG sets and other stationary equipment.",
                "display_order": 1,
            },

            {
                "scope": "S1",
                "code": "MBC",
                "name": "Mobile Combustion",
                "description": "Fuel consumed by company-owned vehicles.",
                "display_order": 2,
            },

            {
                "scope": "S1",
                "code": "PRC",
                "name": "Process Emissions",
                "description": "Emissions generated during manufacturing processes.",
                "display_order": 3,
            },

            {
                "scope": "S1",
                "code": "FUG",
                "name": "Fugitive Emissions",
                "description": "Leakage of refrigerants and other greenhouse gases.",
                "display_order": 4,
            },

            # -------------------------------------------------
            # Scope 2
            # -------------------------------------------------

            {
                "scope": "S2",
                "code": "ENG",
                "name": "Purchased Energy",
                "description": "Purchased electricity, steam, heating and cooling.",
                "display_order": 1,
            },

            # -------------------------------------------------
            # Scope 3
            # -------------------------------------------------

            {
                "scope": "S3",
                "code": "BUS",
                "name": "Business Travel",
                "description": "Business travel emissions.",
                "display_order": 1,
            },

            {
                "scope": "S3",
                "code": "EMP",
                "name": "Employee Commuting",
                "description": "Employee commuting emissions.",
                "display_order": 2,
            },

            {
                "scope": "S3",
                "code": "WST",
                "name": "Waste",
                "description": "Waste generated in operations.",
                "display_order": 3,
            },

            {
                "scope": "S3",
                "code": "PUR",
                "name": "Purchased Goods & Services",
                "description": "Purchased goods and services.",
                "display_order": 4,
            },

            {
                "scope": "S3",
                "code": "TRN",
                "name": "Transportation & Distribution",
                "description": "Transportation and distribution emissions.",
                "display_order": 5,
            },
        ]

        created = 0
        updated = 0

        for category in categories:

            try:

                scope = EmissionScope.objects.get(
                    code=category["scope"]
                )

            except EmissionScope.DoesNotExist:

                self.stdout.write(
                    self.style.ERROR(
                        f"Scope '{category['scope']}' not found."
                    )
                )

                continue

            obj, is_created = EmissionCategory.objects.update_or_create(

                scope=scope,

                code=category["code"],

                defaults={

                    "name": category["name"],

                    "description": category["description"],

                    "display_order": category["display_order"],

                    "is_active": True,

                },
            )

            if is_created:

                created += 1

                self.stdout.write(
                    self.style.SUCCESS(f"   Created : {obj.name}")
                )

            else:

                updated += 1

                self.stdout.write(
                    self.style.WARNING(f"   Updated : {obj.name}")
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Category Master -> Created: {created}, Updated: {updated}"
            )
        )