# apps/report/plant_scope.py
"""
Single place that decides WHICH plants a user may see in the report module.

Used by:
  - views.py        (plant dropdown, report-card stats, recent reports)
  - views_brsr.py   (preview / PDF / Excel, "All Plants" combiner)

so the dropdown and the "All Plants" report can never disagree.

Scoping rules
-------------
- Super admin            -> every active plant.
- Everyone else          -> active plants that belong to the user's company.
  "Belongs to" is detected from the Plant model itself: a direct `company`
  field and/or a `created_by` user whose company matches. Either match is
  enough, so it works whichever way your plants were created.
- User with no company   -> no plants.
"""

import logging

from django.db.models import Q

logger = logging.getLogger(__name__)


def company_plants_qs(user):
    from apps.organizations.models import Plant

    qs = Plant.objects.filter(is_active=True)

    if getattr(user, "is_super_admin", False):
        return qs

    company = getattr(user, "company", None)
    if company is None:
        logger.warning("company_plants_qs: user %s has no company -> no plants", getattr(user, "id", None))
        return qs.none()

    field_names = {f.name for f in Plant._meta.get_fields()}
    condition = Q()
    if "company" in field_names:
        condition |= Q(company=company)
    if "created_by" in field_names:
        condition |= Q(created_by__company=company)

    if not condition:
        logger.warning("company_plants_qs: Plant has neither `company` nor `created_by` field")
        return qs.none()

    scoped = qs.filter(condition).distinct()
    if not scoped.exists():
        logger.warning(
            "company_plants_qs: no active plants matched company=%s for user %s",
            company, getattr(user, "id", None),
        )
    return scoped


def company_plant_ids(user):
    return list(company_plants_qs(user).values_list("id", flat=True))