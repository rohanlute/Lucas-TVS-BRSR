from django.core.management.base import BaseCommand
from django.db import transaction

from apps.emission.models import (
    EmissionScope,EmissionCategory,EmissionActivity,EmissionSource,EmissionFactor,)
from apps.calculator.models import Unit
from datetime import date

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
        self.seed_activities()
        self.seed_emission_sources()
        self.seed_emission_factors()

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

    # ==========================================================
    # Activity Master
    # ==========================================================

    def seed_activities(self):

        self.stdout.write("")
        self.stdout.write(
            self.style.HTTP_INFO("Seeding Emission Activities...")
        )

        activities = [

            # =====================================================
            # Scope 1 -> Stationary Combustion
            # =====================================================

            {
                "category": "STC",
                "code": "DSL",
                "name": "Diesel",
                "description": "Diesel fuel consumption",
                "unit": "Liter",
                "display_order": 1,
            },
            {
                "category": "STC",
                "code": "LPG",
                "name": "LPG",
                "description": "Liquefied Petroleum Gas",
                "unit": "Kilogram",
                "display_order": 2,
            },
            {
                "category": "STC",
                "code": "FO",
                "name": "Furnace Oil",
                "description": "Furnace Oil",
                "unit": "Liter",
                "display_order": 3,
            },
            {
                "category": "STC",
                "code": "COAL",
                "name": "Coal",
                "description": "Coal Consumption",
                "unit": "Kilogram",
                "display_order": 4,
            },

            # =====================================================
            # Scope 1 -> Mobile Combustion
            # =====================================================

            {
                "category": "MBC",
                "code": "PET",
                "name": "Petrol",
                "description": "Petrol Consumption",
                "unit": "Liter",
                "display_order": 1,
            },
            {
                "category": "MBC",
                "code": "DSLV",
                "name": "Diesel Vehicle",
                "description": "Vehicle Diesel",
                "unit": "Liter",
                "display_order": 2,
            },
            {
                "category": "MBC",
                "code": "CNG",
                "name": "CNG",
                "description": "Compressed Natural Gas",
                "unit": "Kilogram",
                "display_order": 3,
            },

            # =====================================================
            # Scope 2 -> Purchased Energy
            # =====================================================

            {
                "category": "ENG",
                "code": "ELE",
                "name": "Electricity",
                "description": "Purchased Electricity",
                "unit": "Kilowatt-hour",
                "display_order": 1,
            },
            {
                "category": "ENG",
                "code": "STM",
                "name": "Steam",
                "description": "Purchased Steam",
                "unit": "Ton (Metric)",
                "display_order": 2,
            },
        ]

        created = 0
        updated = 0

        for item in activities:

            try:
                category = EmissionCategory.objects.get(
                    code=item["category"]
                )

                unit = Unit.objects.filter(name__iexact=item["unit"]).first()

                if not unit:
                    raise Unit.DoesNotExist

            except (EmissionCategory.DoesNotExist, Unit.DoesNotExist):

                self.stdout.write(
                    self.style.ERROR(
                        f"Missing Category/Unit for {item['name']}"
                    )
                )
                continue

            obj, is_created = EmissionActivity.objects.update_or_create(

                code=item["code"],

                defaults={
                    "category": category,
                    "name": item["name"],
                    "description": item["description"],
                    "base_unit": unit,
                    "requires_emission_factor": True,
                    "allow_manual_entry": True,
                    "allow_excel_import": True,
                    "display_order": item["display_order"],
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
                f"Activity Master -> Created: {created}, Updated: {updated}"
            )
        )


    # ==========================================================
    # Emission Source Master
    # ==========================================================

    def seed_emission_sources(self):

        self.stdout.write("")
        self.stdout.write(
            self.style.HTTP_INFO("Seeding Emission Sources...")
        )

        sources = [

            # =====================================================
            # Diesel
            # =====================================================

            {
                "activity": "DSL",
                "code": "DG1",
                "name": "DG Set 1",
                "display_order": 1,
            },

            {
                "activity": "DSL",
                "code": "DG2",
                "name": "DG Set 2",
                "display_order": 2,
            },

            {
                "activity": "DSL",
                "code": "BLR",
                "name": "Boiler",
                "display_order": 3,
            },

            {
                "activity": "DSL",
                "code": "FUR",
                "name": "Furnace",
                "display_order": 4,
            },

            # =====================================================
            # LPG
            # =====================================================

            {
                "activity": "LPG",
                "code": "BOILER",
                "name": "Boiler",
                "display_order": 1,
            },

            {
                "activity": "LPG",
                "code": "CANTEEN",
                "name": "Canteen",
                "display_order": 2,
            },

            # =====================================================
            # Petrol
            # =====================================================

            {
                "activity": "PET",
                "code": "CAR1",
                "name": "Company Car 1",
                "display_order": 1,
            },

            {
                "activity": "PET",
                "code": "CAR2",
                "name": "Company Car 2",
                "display_order": 2,
            },

            # =====================================================
            # Diesel Vehicle
            # =====================================================

            {
                "activity": "DSLV",
                "code": "TRK1",
                "name": "Truck 1",
                "display_order": 1,
            },

            {
                "activity": "DSLV",
                "code": "TRK2",
                "name": "Truck 2",
                "display_order": 2,
            },

            {
                "activity": "DSLV",
                "code": "FORK1",
                "name": "Forklift 1",
                "display_order": 3,
            },

            # =====================================================
            # Electricity
            # =====================================================

            {
                "activity": "ELE",
                "code": "MAIN",
                "name": "Main Meter",
                "display_order": 1,
            },

            {
                "activity": "ELE",
                "code": "ADMIN",
                "name": "Admin Building",
                "display_order": 2,
            },

            # =====================================================
            # Furnace Oil
            # =====================================================

            {
                "activity": "FO",
                "code": "BOILER",
                "name": "Boiler",
                "display_order": 1,
            },

            {
                "activity": "FO",
                "code": "THERMIC",
                "name": "Thermic Fluid Heater",
                "display_order": 2,
            },

            {
                "activity": "FO",
                "code": "FURNACE",
                "name": "Industrial Furnace",
                "display_order": 3,
            },
            # =====================================================
            # Coal
            # =====================================================

            {
                "activity": "COAL",
                "code": "BOILER",
                "name": "Coal Boiler",
                "display_order": 1,
            },

            {
                "activity": "COAL",
                "code": "KILN",
                "name": "Kiln",
                "display_order": 2,
            },

            {
                "activity": "COAL",
                "code": "FURNACE",
                "name": "Coal Furnace",
                "display_order": 3,
            },

            # =====================================================
            # CNG
            # =====================================================

            {
                "activity": "CNG",
                "code": "CAR1",
                "name": "Company Car 1",
                "display_order": 1,
            },

            {
                "activity": "CNG",
                "code": "CAR2",
                "name": "Company Car 2",
                "display_order": 2,
            },

            {
                "activity": "CNG",
                "code": "VAN1",
                "name": "Delivery Van",
                "display_order": 3,
            },
            # =====================================================
            # Steam
            # =====================================================

            {
                "activity": "STM",
                "code": "PLANT1",
                "name": "Production Line 1",
                "display_order": 1,
            },

            {
                "activity": "STM",
                "code": "PLANT2",
                "name": "Production Line 2",
                "display_order": 2,
            },

            {
                "activity": "STM",
                "code": "UTILITY",
                "name": "Utility Section",
                "display_order": 3,
            },
        ]

        created = 0
        updated = 0

        for item in sources:

            try:

                activity = EmissionActivity.objects.get(
                    code=item["activity"]
                )

            except EmissionActivity.DoesNotExist:

                self.stdout.write(
                    self.style.ERROR(
                        f"Activity not found : {item['activity']}"
                    )
                )

                continue

            obj, is_created = EmissionSource.objects.update_or_create(

                activity=activity,

                source_code=item["code"],

                defaults={

                    "source_name": item["name"],

                    "display_order": item["display_order"],

                    "is_active": True,

                },

            )

            if is_created:

                created += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"   Created : {activity.name} -> {obj.source_name}"
                    )
                )

            else:

                updated += 1

                self.stdout.write(
                    self.style.WARNING(
                        f"   Updated : {activity.name} -> {obj.source_name}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Emission Source Master -> Created: {created}, Updated: {updated}"
            )
        )



    # ==========================================================
    # Emission Factor Master
    # ==========================================================

    def seed_emission_factors(self):

        self.stdout.write("")
        self.stdout.write(
            self.style.HTTP_INFO("Seeding Emission Factors...")
        )

        factors = [

            {
                "activity": "DSL",
                "unit": "L",
                "factor": 2.68,
                "source": "IPCC",
                "version": "2006",
                "effective_from": date(2025, 4, 1),
            },

            {
                "activity": "PET",
                "unit": "L",
                "factor": 2.31,
                "source": "IPCC",
                "version": "2006",
                "effective_from": date(2025, 4, 1),
            },

            {
                "activity": "LPG",
                "unit": "kg",
                "factor": 3.00,
                "source": "IPCC",
                "version": "2006",
                "effective_from": date(2025, 4, 1),
            },

            {
                "activity": "FO",
                "unit": "L",
                "factor": 3.15,
                "source": "IPCC",
                "version": "2006",
                "effective_from": date(2025, 4, 1),
            },

            {
                "activity": "COAL",
                "unit": "kg",
                "factor": 2.42,
                "source": "IPCC",
                "version": "2006",
                "effective_from": date(2025, 4, 1),
            },

            {
                "activity": "DSLV",
                "unit": "L",
                "factor": 2.68,
                "source": "IPCC",
                "version": "2006",
                "effective_from": date(2025, 4, 1),
            },

            {
                "activity": "CNG",
                "unit": "kg",
                "factor": 2.75,
                "source": "IPCC",
                "version": "2006",
                "effective_from": date(2025, 4, 1),
            },

            {
                "activity": "ELE",
                "unit": "kWh",
                "factor": 0.716,
                "source": "CEA India",
                "version": "2025",
                "effective_from": date(2025, 4, 1),
            },

            {
                "activity": "STM",
                "unit": "Ton",
                "factor": 0.180,
                "source": "Supplier",
                "version": "2025",
                "effective_from": date(2025, 4, 1),
            },

        ]

        created = 0
        updated = 0

        for item in factors:

            try:
                activity = EmissionActivity.objects.get(code=item["activity"]                )
                unit = Unit.objects.get(symbol=item["unit"])

            except (EmissionActivity.DoesNotExist, Unit.DoesNotExist):

                self.stdout.write(
                    self.style.ERROR(
                        f"Missing Activity/Unit : {item['activity']}"
                    )
                )
                continue

            obj, is_created = EmissionFactor.objects.update_or_create(

                activity=activity,
                unit=unit,
                effective_from=item["effective_from"],

                defaults={
                    "emission_factor": item["factor"],
                    "source": item["source"],
                    "version": item["version"],
                    "is_active": True,
                }
            )

            if is_created:
                created += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"   Created : {activity.name}"
                    )
                )
            else:
                updated += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"   Updated : {activity.name}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Emission Factor Master -> Created: {created}, Updated: {updated}"
            )
        )
    