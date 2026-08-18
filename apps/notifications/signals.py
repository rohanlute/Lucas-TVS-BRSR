# notifications/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from apps.emission.models import EmissionAssignment
from .models import Timesheet, Notification
from apps.common_events.adapters.emission_adapter import EmissionAdapter

@receiver(post_save, sender=EmissionAssignment)
def update_timesheet_on_assignment_update(sender, instance, created, **kwargs):
    """
    Update timesheet when assignment is updated (status change, dates, etc.)
    """
    if not created and instance.assignee:
        try:
            timesheet = Timesheet.objects.get(assignment=instance)
            
            # Update title if changed
            if hasattr(instance, 'title') and instance.title:
                timesheet.title = f"Timesheet: {instance.title}"
            elif hasattr(instance, 'name') and instance.name:
                timesheet.title = f"Timesheet: {instance.name}"
            
            # Update dates if changed
            start_date, end_date = EmissionAdapter.calculate_timesheet_dates(instance)
            timesheet.start_date = start_date
            timesheet.end_date = end_date
            
            # Update status based on assignment
            print(f"\n📝 Updating timesheet for assignment {instance.id}")
            timesheet.update_status_from_assignment()
            
            timesheet.save()
            print(f"✅ Timesheet updated for assignment {instance.id}\n")
            
        except Timesheet.DoesNotExist:
            print(
                f"⚠️ Timesheet not found for assignment "
                f"{instance.assignment_code}"
            )
        except Exception as e:
            print(f"❌ Error updating timesheet for assignment {instance.id}: {e}")


@receiver(post_save, sender=Timesheet)
def update_assignment_on_timesheet_completion(sender, instance, created, **kwargs):
    """
    Update assignment when timesheet is completed (optional)
    """
    if not created and instance.status == 'completed' and instance.assignment:
        try:
            # If timesheet is marked as completed, you might want to update assignment
            # This is optional - uncomment if needed
            # if instance.assignment.status not in ['APPROVED', 'REJECTED']:
            #     instance.assignment.status = 'SUBMITTED'
            #     instance.assignment.save(update_fields=['status'])
            print(f"✅ Timesheet {instance.id} completed for assignment {instance.assignment.id}")
        except Exception as e:
            print(f"❌ Error updating assignment: {e}")