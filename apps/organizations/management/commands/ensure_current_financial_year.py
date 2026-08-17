from django.core.management.base import BaseCommand

from apps.organizations.services.financial_year import (
    ensure_current_financial_year,
)


class Command(BaseCommand):
    help = "Ensure the current Financial Year exists."

    def handle(self, *args, **options):

        financial_year, created = (
            ensure_current_financial_year()
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Financial Year created successfully: "
                    f"{financial_year.financial_year}"
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Financial Year already exists: "
                    f"{financial_year.financial_year}"
                )
            )
            