from apps.notifications.models import Notification
from apps.goals.models import KPI, KPIPlantTarget


class GoalNotificationService:

    @classmethod
    def check_kpi(
        cls,
        kpi,
        company,
        recipient,
        plant=None,
        financial_year=None,
        financial_month=None,
        assignment=None,
    ):
        """
        Check a KPI against its Baseline and Target
        and create a Goal notification when required.
        """

        # ---------------------------------------------------------
        # Get current KPI value
        # ---------------------------------------------------------
        current_value = kpi.get_current_value(
            company_id=company.id if company else None,
            plant_id=plant.id if plant else None,
            financial_year_id=(
                financial_year.id
                if financial_year else None
            ),
            financial_month_id=(
                financial_month.id
                if financial_month else None
            ),
            assignment_id=(
                assignment.id
                if assignment else None
            ),
        )

        # ---------------------------------------------------------
        # Check whether actual data exists
        # ---------------------------------------------------------
        has_data = kpi.has_current_data(
            company_id=company.id if company else None,
            plant_id=plant.id if plant else None,
            financial_year_id=(
                financial_year.id
                if financial_year else None
            ),
            financial_month_id=(
                financial_month.id
                if financial_month else None
            ),
            assignment_id=(
                assignment.id
                if assignment else None
            ),
        )

        # ---------------------------------------------------------
        # Get plant-specific Baseline / Target
        # ---------------------------------------------------------
        if plant:
            plant_target = (KPIPlantTarget.objects.filter(
                    kpi=kpi,plant=plant,).first()
            )

            if not plant_target:
                return None

            baseline_value = plant_target.baseline_value
            target_value = plant_target.target_value
        else:
            baseline_value = kpi.baseline_value
            target_value = kpi.target_value

        if plant:
            plant_target = (
                KPIPlantTarget.objects.filter(kpi=kpi,plant=plant,).first()
            )

            if plant_target:
                baseline_value = plant_target.baseline_value
                target_value = plant_target.target_value
        # ---------------------------------------------------------
        # Determine KPI status
        # ---------------------------------------------------------
        status = kpi.get_notification_status(
            current_value=current_value,
            baseline_value=baseline_value,
            target_value=target_value,
            has_data=has_data,
        )

        # No data = nothing to notify
        if status == "NO_DATA":
            return None

        # ---------------------------------------------------------
        # Only notify for meaningful conditions
        # ---------------------------------------------------------
        if status not in [
            "AT_RISK",
            "CRITICAL",
            "NEAR_TARGET",
            "TARGET_ACHIEVED",
        ]:
            return None

        # ---------------------------------------------------------
        # Build Goal information
        # ---------------------------------------------------------
        goal = kpi.goal

        title_map = {
            "AT_RISK": "Goal At Risk",
            "CRITICAL": "Goal Critical",
            "NEAR_TARGET": "Goal Nearing Target",
            "TARGET_ACHIEVED": "Goal Target Achieved",
        }

        title = (
            f'{title_map[status]}: '
            f'{kpi.name}'
        )

        message = (
            f'Goal "{goal.name}" KPI "{kpi.name}" '
            f'has reached status "{status}". '
            f'Current: {current_value:.2f}, '
            f'Baseline: {float(baseline_value or 0):.2f}, '
            f'Target: {float(target_value or 0):.2f}.'
        )

        # ---------------------------------------------------------
        # Check the latest notification for this KPI
        # ---------------------------------------------------------
        latest_notification = (
            Notification.objects
            .filter(
                recipient=recipient,
                company=company,
                module=Notification.ModuleChoices.GOALS,
                notification_type=Notification.NotificationTypeChoices.REMINDER,
                reference_id=goal.id,
                title__icontains=kpi.name,
            )
            .order_by("-created_at")
            .first()
        )

        # ---------------------------------------------------------
        # If the latest notification already represents
        # the same status, do not create another one.
        # ---------------------------------------------------------
        if latest_notification:

            if (
                status == "AT_RISK"
                and latest_notification.title.startswith(
                    "Goal At Risk"
                )
            ):
                return {
                    "notification": latest_notification,
                    "created": False,
                }

            if (
                status == "CRITICAL"
                and latest_notification.title.startswith(
                    "Goal Critical"
                )
            ):
                return {
                    "notification": latest_notification,
                    "created": False,
                }

            if (
                status == "NEAR_TARGET"
                and latest_notification.title.startswith(
                    "Goal Nearing Target"
                )
            ):
                return {
                    "notification": latest_notification,
                    "created": False,
                }

            if (
                status == "TARGET_ACHIEVED"
                and latest_notification.title.startswith(
                    "Goal Target Achieved"
                )
            ):
                return {
                    "notification": latest_notification,
                    "created": False,
                }

        # ---------------------------------------------------------
        # Create notification using existing Notification model
        # ---------------------------------------------------------
        notification = Notification.objects.create(
            company=company,
            sender=recipient,
            recipient=recipient,
            module=Notification.ModuleChoices.GOALS,
            notification_type=Notification.NotificationTypeChoices.REMINDER,
            title=title,
            message=message,
            reference_id=goal.id,
            action_url=(
                f"/goals/detail/"
                f"{goal.material_topic.name}/"
                f"?goal={goal.name}"
            ),
            is_read=False,
        )

        return {
            "notification": notification,
            "created": True,
        }