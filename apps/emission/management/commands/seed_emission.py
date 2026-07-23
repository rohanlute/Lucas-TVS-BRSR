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
                "code": "ELE",
                "name": "Purchased Electricity",
                "description": "Electricity purchased from the grid or third-party supplier.",
                "display_order": 1,
            },

            {
                "scope": "S2",
                "code": "STM",
                "name": "Purchased Steam",
                "description": "Steam purchased from external suppliers.",
                "display_order": 2,
            },

            {
                "scope": "S2",
                "code": "HTG",
                "name": "Purchased Heating",
                "description": "Heating purchased from district heating or external suppliers.",
                "display_order": 3,
            },

            {
                "scope": "S2",
                "code": "CLG",
                "name": "Purchased Cooling",
                "description": "Cooling purchased from district cooling or external suppliers.",
                "display_order": 4,
            },

            # -------------------------------------------------
            # Scope 3
            # -------------------------------------------------

            {
                "scope": "S3",
                "code": "PGS",
                "name": "Purchased Goods & Services",
                "description": "Emissions from purchased goods and services.",
                "display_order": 1,
            },

            {
                "scope": "S3",
                "code": "CAP",
                "name": "Capital Goods",
                "description": "Emissions from the production of capital goods purchased by the company.",
                "display_order": 2,
            },

            {
                "scope": "S3",
                "code": "FEC",
                "name": "Fuel & Energy Related Activities",
                "description": "Fuel- and energy-related activities not included in Scope 1 or Scope 2.",
                "display_order": 3,
            },

            {
                "scope": "S3",
                "code": "UTD",
                "name": "Upstream Transportation & Distribution",
                "description": "Transportation and distribution of purchased goods before they reach the company.",
                "display_order": 4,
            },

            {
                "scope": "S3",
                "code": "WST",
                "name": "Waste Generated in Operations",
                "description": "Treatment and disposal of waste generated in company operations.",
                "display_order": 5,
            },

            {
                "scope": "S3",
                "code": "BUS",
                "name": "Business Travel",
                "description": "Employee business travel by air, rail, road, and hotel stays.",
                "display_order": 6,
            },

            {
                "scope": "S3",
                "code": "EMP",
                "name": "Employee Commuting",
                "description": "Employee commuting between home and workplace.",
                "display_order": 7,
            },

            {
                "scope": "S3",
                "code": "UPA",
                "name": "Upstream Leased Assets",
                "description": "Emissions from leased assets not included in Scope 1 and Scope 2.",
                "display_order": 8,
            },

            {
                "scope": "S3",
                "code": "DTD",
                "name": "Downstream Transportation & Distribution",
                "description": "Transportation and distribution of sold products.",
                "display_order": 9,
            },

            {
                "scope": "S3",
                "code": "PRO",
                "name": "Processing of Sold Products",
                "description": "Processing of intermediate products sold by the company.",
                "display_order": 10,
            },

            {
                "scope": "S3",
                "code": "USP",
                "name": "Use of Sold Products",
                "description": "Emissions during the use phase of products sold.",
                "display_order": 11,
            },

            {
                "scope": "S3",
                "code": "EOL",
                "name": "End-of-Life Treatment of Sold Products",
                "description": "Waste treatment and disposal of sold products.",
                "display_order": 12,
            },

            {
                "scope": "S3",
                "code": "DLA",
                "name": "Downstream Leased Assets",
                "description": "Emissions from downstream leased assets.",
                "display_order": 13,
            },

            {
                "scope": "S3",
                "code": "FRA",
                "name": "Franchises",
                "description": "Emissions associated with franchise operations.",
                "display_order": 14,
            },

            {
                "scope": "S3",
                "code": "INV",
                "name": "Investments",
                "description": "Emissions associated with investments.",
                "display_order": 15,
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
            # Scope 1 -> Process Emissions
            # =====================================================

            {
                "category": "PRC",
                "code": "CLK",
                "name": "Clinker Production",
                "description": "CO₂ emissions from clinker production",
                "unit": "Ton (Metric)",
                "display_order": 1,
            },
            {
                "category": "PRC",
                "code": "LIME",
                "name": "Lime Production",
                "description": "CO₂ emissions from lime production",
                "unit": "Ton (Metric)",
                "display_order": 2,
            },
            {
                "category": "PRC",
                "code": "STEEL",
                "name": "Steel Production",
                "description": "CO₂ emissions from steel manufacturing",
                "unit": "Ton (Metric)",
                "display_order": 3,
            },
            {
                "category": "PRC",
                "code": "AMMONIA",
                "name": "Ammonia Production",
                "description": "CO₂ emissions from ammonia production",
                "unit": "Ton (Metric)",
                "display_order": 4,
            },
            {
                "category": "PRC",
                "code": "NITRIC",
                "name": "Nitric Acid Production",
                "description": "N₂O emissions from nitric acid production",
                "unit": "Ton (Metric)",
                "display_order": 5,
            },

            # =====================================================
            # Scope 1 -> Fugitive Emissions
            # =====================================================

            {
                "category": "FUG",
                "code": "HFC134A",
                "name": "HFC-134a Leakage",
                "description": "Emissions from leakage of HFC-134a refrigerant",
                "unit": "Kilogram",
                "display_order": 1,
            },
            {
                "category": "FUG",
                "code": "HFC410A",
                "name": "HFC-410A Leakage",
                "description": "Emissions from leakage of HFC-410A refrigerant",
                "unit": "Kilogram",
                "display_order": 2,
            },
            {
                "category": "FUG",
                "code": "R22",
                "name": "R-22 Leakage",
                "description": "Emissions from leakage of R-22 refrigerant",
                "unit": "Kilogram",
                "display_order": 3,
            },
            {
                "category": "FUG",
                "code": "SF6",
                "name": "SF₆ Leakage",
                "description": "Emissions from SF₆ leakage from electrical switchgear",
                "unit": "Kilogram",
                "display_order": 4,
            },
            {
                "category": "FUG",
                "code": "CO2EXT",
                "name": "CO₂ Fire Extinguisher Discharge",
                "description": "CO₂ emissions from fire extinguisher discharge and testing",
                "unit": "Kilogram",
                "display_order": 5,
            },

            # =====================================================
            # Scope 2 -> Purchased Electricity
            # =====================================================

            {
                "category": "ELE",
                "code": "ELE",
                "name": "Purchased Electricity",
                "description": "Electricity purchased from the grid or third-party supplier",
                "unit": "Kilowatt-hour",
                "display_order": 1,
            },

            # =====================================================
            # Scope 2 -> Purchased Steam
            # =====================================================

            {
                "category": "STM",
                "code": "STM",
                "name": "Purchased Steam",
                "description": "Steam purchased from an external supplier",
                "unit": "Ton (Metric)",
                "display_order": 1,
            },

            # =====================================================
            # Scope 2 -> Purchased Heating
            # =====================================================

            {
                "category": "HTG",
                "code": "HTG",
                "name": "Purchased Heating",
                "description": "Heating purchased from district heating or external suppliers",
                "unit": "Gigajoule",
                "display_order": 1,
            },

            # =====================================================
            # Scope 2 -> Purchased Cooling
            # =====================================================

            {
                "category": "CLG",
                "code": "CLG",
                "name": "Purchased Cooling",
                "description": "Cooling purchased from district cooling or external suppliers",
                "unit": "Ton of Refrigeration Hour",
                "display_order": 1,
            },

            # =====================================================
            # Scope 3 -> Purchased Goods & Services
            # =====================================================

            {
                "category": "PGS",
                "code": "PGS",
                "name": "Purchased Goods & Services",
                "description": "Purchased raw materials, consumables and services",
                "unit": "Ton (Metric)",
                "display_order": 1,
            },

            # =====================================================
            # Scope 3 -> Capital Goods
            # =====================================================

            {
                "category": "CAP",
                "code": "CAP",
                "name": "Capital Goods",
                "description": "Capital equipment and machinery",
                "unit": "Ton (Metric)",
                "display_order": 1,
            },

            # =====================================================
            # Scope 3 -> Fuel & Energy Related Activities
            # =====================================================

            {
                "category": "FEC",
                "code": "FEC",
                "name": "Fuel & Energy Related Activities",
                "description": "Fuel and energy activities outside Scope 1 & 2",
                "unit": "Kilowatt-hour",
                "display_order": 1,
            },

            # =====================================================
            # Scope 3 -> Upstream Transportation & Distribution
            # =====================================================

            {
                "category": "UTD",
                "code": "UTD",
                "name": "Upstream Transportation & Distribution",
                "description": "Inbound transportation",
                "unit": "Ton (Metric)",
                "display_order": 1,
            },

            # =====================================================
            # Scope 3 -> Waste Generated in Operations
            # =====================================================

            {
                "category": "WST",
                "code": "WST",
                "name": "Waste Generated in Operations",
                "description": "Waste generated from operations",
                "unit": "Ton (Metric)",
                "display_order": 1,
            },

            # =====================================================
            # Scope 3 -> Business Travel
            # =====================================================

            {
                "category": "BUS",
                "code": "BUS",
                "name": "Business Travel",
                "description": "Business travel by employees",
                "unit": "Kilometer",
                "display_order": 1,
            },

            # =====================================================
            # Scope 3 -> Employee Commuting
            # =====================================================

            {
                "category": "EMP",
                "code": "EMP",
                "name": "Employee Commuting",
                "description": "Employee daily commuting",
                "unit": "Kilometer",
                "display_order": 1,
            },

            # =====================================================
            # Scope 3 -> Upstream Leased Assets
            # =====================================================

            {
                "category": "UPA",
                "code": "UPA",
                "name": "Upstream Leased Assets",
                "description": "Leased assets upstream",
                "unit": "Kilowatt-hour",
                "display_order": 1,
            },

            # =====================================================
            # Scope 3 -> Downstream Transportation & Distribution
            # =====================================================

            {
                "category": "DTD",
                "code": "DTD",
                "name": "Downstream Transportation & Distribution",
                "description": "Outbound transportation",
                "unit": "Ton (Metric)",
                "display_order": 1,
            },

            # =====================================================
            # Scope 3 -> Processing of Sold Products
            # =====================================================

            {
                "category": "PRO",
                "code": "PRO",
                "name": "Processing of Sold Products",
                "description": "Processing of sold products",
                "unit": "Ton (Metric)",
                "display_order": 1,
            },

            # =====================================================
            # Scope 3 -> Use of Sold Products
            # =====================================================

            {
                "category": "USP",
                "code": "USP",
                "name": "Use of Sold Products",
                "description": "Use phase emissions",
                "unit": "Kilowatt-hour",
                "display_order": 1,
            },

            # =====================================================
            # Scope 3 -> End-of-Life Treatment of Sold Products
            # =====================================================

            {
                "category": "EOL",
                "code": "EOL",
                "name": "End-of-Life Treatment of Sold Products",
                "description": "Disposal and recycling",
                "unit": "Ton (Metric)",
                "display_order": 1,
            },

            # =====================================================
            # Scope 3 -> Downstream Leased Assets
            # =====================================================

            {
                "category": "DLA",
                "code": "DLA",
                "name": "Downstream Leased Assets",
                "description": "Downstream leased assets",
                "unit": "Kilowatt-hour",
                "display_order": 1,
            },

            # =====================================================
            # Scope 3 -> Franchises
            # =====================================================

            {
                "category": "FRA",
                "code": "FRA",
                "name": "Franchises",
                "description": "Franchise operations",
                "unit": "Kilowatt-hour",
                "display_order": 1,
            },

            # =====================================================
            # Scope 3 -> Investments
            # =====================================================

            {
                "category": "INV",
                "code": "INV",
                "name": "Investments",
                "description": "Investment portfolio emissions",
                "unit": "Ton (Metric)",
                "display_order": 1,
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
            # Process Emissions -> Clinker Production
            # =====================================================

            {
                "activity": "CLK",
                "code": "KILN1",
                "name": "Kiln 1",
                "display_order": 1,
            },
            {
                "activity": "CLK",
                "code": "KILN2",
                "name": "Kiln 2",
                "display_order": 2,
            },

            # =====================================================
            # Lime Production
            # =====================================================

            {
                "activity": "LIME",
                "code": "LIME1",
                "name": "Lime Kiln",
                "display_order": 1,
            },

            # =====================================================
            # Steel Production
            # =====================================================

            {
                "activity": "STEEL",
                "code": "BF1",
                "name": "Blast Furnace",
                "display_order": 1,
            },
            {
                "activity": "STEEL",
                "code": "EAF1",
                "name": "Electric Arc Furnace",
                "display_order": 2,
            },

            # =====================================================
            # Ammonia Production
            # =====================================================

            {
                "activity": "AMMONIA",
                "code": "APLANT",
                "name": "Ammonia Plant",
                "display_order": 1,
            },

            # =====================================================
            # Nitric Acid Production
            # =====================================================

            {
                "activity": "NITRIC",
                "code": "NAPLANT",
                "name": "Nitric Acid Plant",
                "display_order": 1,
            },

            # =====================================================
            # HFC-134a Leakage
            # =====================================================

            {
                "activity": "HFC134A",
                "code": "ACPLANT",
                "name": "Plant Air Conditioner",
                "display_order": 1,
            },
            {
                "activity": "HFC134A",
                "code": "CHILLER",
                "name": "Chiller Unit",
                "display_order": 2,
            },

            # =====================================================
            # HFC-410A Leakage
            # =====================================================

            {
                "activity": "HFC410A",
                "code": "ACADMIN",
                "name": "Admin Building Air Conditioner",
                "display_order": 1,
            },
            {
                "activity": "HFC410A",
                "code": "ACPROD",
                "name": "Production Office Air Conditioner",
                "display_order": 2,
            },

            # =====================================================
            # R-22 Leakage
            # =====================================================

            {
                "activity": "R22",
                "code": "COLDST",
                "name": "Cold Storage Unit",
                "display_order": 1,
            },

            # =====================================================
            # SF₆ Leakage
            # =====================================================

            {
                "activity": "SF6",
                "code": "SWGR",
                "name": "Electrical Switchgear",
                "display_order": 1,
            },
            {
                "activity": "SF6",
                "code": "GIS",
                "name": "Gas Insulated Switchgear",
                "display_order": 2,
            },

            # =====================================================
            # CO₂ Fire Extinguisher Discharge
            # =====================================================

            {
                "activity": "CO2EXT",
                "code": "FIREEXT",
                "name": "CO₂ Fire Extinguisher",
                "display_order": 1,
            },
            {
                "activity": "CO2EXT",
                "code": "FIRETEST",
                "name": "Fire Extinguisher Testing",
                "display_order": 2,
            },

            # =====================================================
            # Purchased Electricity
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

            {
                "activity": "ELE",
                "code": "PROD",
                "name": "Production Building",
                "display_order": 3,
            },

            # =====================================================
            # Purchased Steam
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

            # =====================================================
            # Purchased Heating
            # =====================================================

            {
                "activity": "HTG",
                "code": "HEAT1",
                "name": "Heating Network",
                "display_order": 1,
            },

            {
                "activity": "HTG",
                "code": "BOILER",
                "name": "Central Heating System",
                "display_order": 2,
            },

            # =====================================================
            # Purchased Cooling
            # =====================================================

            {
                "activity": "CLG",
                "code": "CHILLER",
                "name": "Central Chiller",
                "display_order": 1,
            },

            {
                "activity": "CLG",
                "code": "COOLNET",
                "name": "District Cooling Network",
                "display_order": 2,
            },

            # =====================================================
            # Purchased Goods & Services
            # =====================================================

            {
                "activity": "PGS",
                "code": "RAWMAT",
                "name": "Raw Materials",
                "display_order": 1,
            },
            {
                "activity": "PGS",
                "code": "PACK",
                "name": "Packaging Materials",
                "display_order": 2,
            },

            # =====================================================
            # Capital Goods
            # =====================================================

            {
                "activity": "CAP",
                "code": "MACH",
                "name": "Machinery",
                "display_order": 1,
            },
            {
                "activity": "CAP",
                "code": "BUILD",
                "name": "Buildings",
                "display_order": 2,
            },

            # =====================================================
            # Fuel & Energy Related Activities
            # =====================================================

            {
                "activity": "FEC",
                "code": "GRIDLOSS",
                "name": "Transmission & Distribution Losses",
                "display_order": 1,
            },
            {
                "activity": "FEC",
                "code": "UPFUEL",
                "name": "Upstream Fuel Production",
                "display_order": 2,
            },

            # =====================================================
            # Upstream Transportation & Distribution
            # =====================================================

            {
                "activity": "UTD",
                "code": "ROAD",
                "name": "Road Transport",
                "display_order": 1,
            },
            {
                "activity": "UTD",
                "code": "SHIP",
                "name": "Sea Freight",
                "display_order": 2,
            },
            {
                "activity": "UTD",
                "code": "RAIL",
                "name": "Rail Transport",
                "display_order": 3,
            },

            # =====================================================
            # Waste Generated in Operations
            # =====================================================

            {
                "activity": "WST",
                "code": "LANDFILL",
                "name": "Landfill",
                "display_order": 1,
            },
            {
                "activity": "WST",
                "code": "RECYCLE",
                "name": "Recycling",
                "display_order": 2,
            },
            {
                "activity": "WST",
                "code": "INCIN",
                "name": "Incineration",
                "display_order": 3,
            },

            # =====================================================
            # Business Travel
            # =====================================================

            {
                "activity": "BUS",
                "code": "AIR",
                "name": "Air Travel",
                "display_order": 1,
            },
            {
                "activity": "BUS",
                "code": "TRAIN",
                "name": "Rail Travel",
                "display_order": 2,
            },
            {
                "activity": "BUS",
                "code": "HOTEL",
                "name": "Hotel Stay",
                "display_order": 3,
            },

            # =====================================================
            # Employee Commuting
            # =====================================================

            {
                "activity": "EMP",
                "code": "CAR",
                "name": "Car",
                "display_order": 1,
            },
            {
                "activity": "EMP",
                "code": "BUS",
                "name": "Bus",
                "display_order": 2,
            },
            {
                "activity": "EMP",
                "code": "TWOWHL",
                "name": "Two Wheeler",
                "display_order": 3,
            },

            # =====================================================
            # Upstream Leased Assets
            # =====================================================

            {
                "activity": "UPA",
                "code": "LEASEOFF",
                "name": "Leased Office",
                "display_order": 1,
            },
            {
                "activity": "UPA",
                "code": "LEASEWH",
                "name": "Leased Warehouse",
                "display_order": 2,
            },

            # =====================================================
            # Downstream Transportation & Distribution
            # =====================================================

            {
                "activity": "DTD",
                "code": "ROAD",
                "name": "Road Distribution",
                "display_order": 1,
            },
            {
                "activity": "DTD",
                "code": "SEA",
                "name": "Sea Distribution",
                "display_order": 2,
            },
            {
                "activity": "DTD",
                "code": "AIR",
                "name": "Air Distribution",
                "display_order": 3,
            },

            # =====================================================
            # Processing of Sold Products
            # =====================================================

            {
                "activity": "PRO",
                "code": "OEM",
                "name": "OEM Processing",
                "display_order": 1,
            },

            # =====================================================
            # Use of Sold Products
            # =====================================================

            {
                "activity": "USP",
                "code": "PRODUCTUSE",
                "name": "Product Usage",
                "display_order": 1,
            },

            # =====================================================
            # End-of-Life Treatment of Sold Products
            # =====================================================

            {
                "activity": "EOL",
                "code": "RECYCLE",
                "name": "Recycling",
                "display_order": 1,
            },
            {
                "activity": "EOL",
                "code": "LANDFILL",
                "name": "Landfill",
                "display_order": 2,
            },

            # =====================================================
            # Downstream Leased Assets
            # =====================================================

            {
                "activity": "DLA",
                "code": "LEASED",
                "name": "Leased Equipment",
                "display_order": 1,
            },

            # =====================================================
            # Franchises
            # =====================================================

            {
                "activity": "FRA",
                "code": "FRANCH1",
                "name": "Franchise Operations",
                "display_order": 1,
            },

            # =====================================================
            # Investments
            # =====================================================

            {
                "activity": "INV",
                "code": "EQUITY",
                "name": "Equity Investments",
                "display_order": 1,
            },
            {
                "activity": "INV",
                "code": "BONDS",
                "name": "Debt Investments",
                "display_order": 2,
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
                "unit": "t",
                "factor": 0.180,
                "source": "Supplier",
                "version": "2025",
                "effective_from": date(2025, 4, 1),
            },

            {
                "activity": "CLK",
                "unit": "t",
                "factor": 0.525,
                "source": "IPCC",
                "version": "2006",
                "effective_from": date(2025, 4, 1),
            },

            {
                "activity": "LIME",
                "unit": "t",
                "factor": 0.785,
                "source": "IPCC",
                "version": "2006",
                "effective_from": date(2025, 4, 1),
            },

            {
                "activity": "STEEL",
                "unit": "t",
                "factor": 1.850,
                "source": "IPCC",
                "version": "2006",
                "effective_from": date(2025, 4, 1),
            },

            {
                "activity": "AMMONIA",
                "unit": "t",
                "factor": 1.620,
                "source": "IPCC",
                "version": "2006",
                "effective_from": date(2025, 4, 1),
            },

            {
                "activity": "NITRIC",
                "unit": "t",
                "factor": 5.100,
                "source": "IPCC",
                "version": "2006",
                "effective_from": date(2025, 4, 1),
            },

            # =====================================================
            # HFC-134a Leakage
            # =====================================================

            {
                "activity": "HFC134A",
                "unit": "kg",
                "factor": 1.430,
                "source": "IPCC AR6",
                "version": "2021",
                "effective_from": date(2025, 4, 1),
            },

            # =====================================================
            # HFC-410A Leakage
            # =====================================================

            {
                "activity": "HFC410A",
                "unit": "kg",
                "factor": 2.088,
                "source": "IPCC AR6",
                "version": "2021",
                "effective_from": date(2025, 4, 1),
            },

            # =====================================================
            # R-22 Leakage
            # =====================================================

            {
                "activity": "R22",
                "unit": "kg",
                "factor": 1.960,
                "source": "IPCC AR6",
                "version": "2021",
                "effective_from": date(2025, 4, 1),
            },

            # =====================================================
            # SF₆ Leakage
            # =====================================================

            {
                "activity": "SF6",
                "unit": "kg",
                "factor": 25.200,
                "source": "IPCC AR6",
                "version": "2021",
                "effective_from": date(2025, 4, 1),
            },

            # =====================================================
            # CO₂ Fire Extinguisher Discharge
            # =====================================================

            {
                "activity": "CO2EXT",
                "unit": "kg",
                "factor": 1.000,
                "source": "IPCC",
                "version": "2006",
                "effective_from": date(2025, 4, 1),
            },

            # =====================================================
            # Purchased Heating
            # =====================================================

            {
                "activity": "HTG",
                "unit": "GJ",
                "factor": 0.056,
                "source": "IPCC",
                "version": "2006",
                "effective_from": date(2025, 4, 1),
            },

            # =====================================================
            # Purchased Cooling
            # =====================================================

            {
                "activity": "CLG",
                "unit": "TRh",
                "factor": 0.070,
                "source": "IPCC",
                "version": "2006",
                "effective_from": date(2025, 4, 1),
            },

            # =====================================================
            # Purchased Goods & Services
            # =====================================================

            {
                "activity": "PGS",
                "unit": "t",
                "factor": 0.450,
                "source": "DEFRA",
                "version": "2025",
                "effective_from": date(2025, 4, 1),
            },

            # =====================================================
            # Capital Goods
            # =====================================================

            {
                "activity": "CAP",
                "unit": "t",
                "factor": 0.520,
                "source": "DEFRA",
                "version": "2025",
                "effective_from": date(2025, 4, 1),
            },

            # =====================================================
            # Fuel & Energy Related Activities
            # =====================================================

            {
                "activity": "FEC",
                "unit": "kWh",
                "factor": 0.084,
                "source": "GHG Protocol",
                "version": "2025",
                "effective_from": date(2025, 4, 1),
            },

            # =====================================================
            # Upstream Transportation & Distribution
            # =====================================================

            {
                "activity": "UTD",
                "unit": "t",
                "factor": 0.105,
                "source": "DEFRA",
                "version": "2025",
                "effective_from": date(2025, 4, 1),
            },

            # =====================================================
            # Waste Generated in Operations
            # =====================================================

            {
                "activity": "WST",
                "unit": "t",
                "factor": 0.586,
                "source": "EPA",
                "version": "2025",
                "effective_from": date(2025, 4, 1),
            },

            # =====================================================
            # Business Travel
            # =====================================================

            {
                "activity": "BUS",
                "unit": "km",
                "factor": 0.146,
                "source": "DEFRA",
                "version": "2025",
                "effective_from": date(2025, 4, 1),
            },

            # =====================================================
            # Employee Commuting
            # =====================================================

            {
                "activity": "EMP",
                "unit": "km",
                "factor": 0.171,
                "source": "DEFRA",
                "version": "2025",
                "effective_from": date(2025, 4, 1),
            },

            # =====================================================
            # Upstream Leased Assets
            # =====================================================

            {
                "activity": "UPA",
                "unit": "kWh",
                "factor": 0.716,
                "source": "CEA India",
                "version": "2025",
                "effective_from": date(2025, 4, 1),
            },

            # =====================================================
            # Downstream Transportation & Distribution
            # =====================================================

            {
                "activity": "DTD",
                "unit": "t",
                "factor": 0.105,
                "source": "DEFRA",
                "version": "2025",
                "effective_from": date(2025, 4, 1),
            },

            # =====================================================
            # Processing of Sold Products
            # =====================================================

            {
                "activity": "PRO",
                "unit": "t",
                "factor": 0.330,
                "source": "GHG Protocol",
                "version": "2025",
                "effective_from": date(2025, 4, 1),
            },

            # =====================================================
            # Use of Sold Products
            # =====================================================

            {
                "activity": "USP",
                "unit": "kWh",
                "factor": 0.716,
                "source": "CEA India",
                "version": "2025",
                "effective_from": date(2025, 4, 1),
            },

            # =====================================================
            # End-of-Life Treatment of Sold Products
            # =====================================================

            {
                "activity": "EOL",
                "unit": "t",
                "factor": 0.410,
                "source": "EPA",
                "version": "2025",
                "effective_from": date(2025, 4, 1),
            },

            # =====================================================
            # Downstream Leased Assets
            # =====================================================

            {
                "activity": "DLA",
                "unit": "kWh",
                "factor": 0.716,
                "source": "CEA India",
                "version": "2025",
                "effective_from": date(2025, 4, 1),
            },

            # =====================================================
            # Franchises
            # =====================================================

            {
                "activity": "FRA",
                "unit": "kWh",
                "factor": 0.716,
                "source": "CEA India",
                "version": "2025",
                "effective_from": date(2025, 4, 1),
            },

            # =====================================================
            # Investments
            # =====================================================

            {
                "activity": "INV",
                "unit": "t",
                "factor": 0.280,
                "source": "PCAF",
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
    