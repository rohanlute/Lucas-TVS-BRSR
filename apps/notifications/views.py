from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import get_object_or_404
from django.utils import timezone
import json
from apps.accounts.mixins import SuperAdminRequiredMixin
from .models import Notification,Timesheet, NotificationUserState
from django.core.paginator import Paginator

class NotificationListView(LoginRequiredMixin, TemplateView):
    login_url = "accounts:login"
    template_name = "applications/notification_list.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        user = self.request.user

        notification_filter = self.request.GET.get("filter", "all")
        # -------------------------------------------------------
        # Notifications for current user
        # -------------------------------------------------------
        notifications = (Notification.objects.filter(recipient=user).exclude(
                user_states__user=user,user_states__is_deleted=True,)
            .select_related("sender","company",)
            .prefetch_related("user_states",).order_by("-created_at")
        )

        if notification_filter == "favourite":
            notifications = notifications.filter(
                user_states__user=user,user_states__is_favourite=True,)

        if notification_filter == "unread":
            notifications = notifications.filter(is_read=False)

        if notification_filter == "brsr":
            notifications = notifications.filter(module=Notification.ModuleChoices.BRSR)

        if notification_filter == "emission":
            notifications = notifications.filter(module=Notification.ModuleChoices.EMISSION)

        if notification_filter == "goals":
            notifications = notifications.filter(module=Notification.ModuleChoices.GOALS)

        if notification_filter == "archived":
            notifications = notifications.filter(
                user_states__user=user,user_states__is_archived=True,)

        # ==========================================
        # PAGINATION: 10 NOTIFICATIONS PER PAGE
        # ==========================================

        paginator = Paginator(notifications, 10)

        page_number = self.request.GET.get("page")
        page_obj = paginator.get_page(page_number)

        # -------------------------------------------------------
        # Attach current user's notification state
        # -------------------------------------------------------
        notification_states = {
            state.notification_id: state
            for state in NotificationUserState.objects.filter(
                user=user,
                notification__recipient=user,
            )
        }

        for notification in notifications:
            notification.user_state = notification_states.get(
                notification.id
            )

        context["page_title"] = "Notification Master"
        context["notifications"] = notifications
        context["page_obj"] = page_obj
        context["paginator"] = paginator

        return context



@login_required
@csrf_exempt
def delete_notification(request, notification_id):

    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "error": "Invalid method",
            },
            status=405,
        )

    notification = get_object_or_404(Notification,id=notification_id,recipient=request.user,)

    state, created = NotificationUserState.objects.get_or_create(notification=notification,user=request.user,)

    state.is_deleted = True

    state.save(update_fields=["is_deleted","updated_at",])

    return JsonResponse({
        "success": True,
        "message": "Notification deleted successfully.",
    })


# Add these new functions
@login_required
@csrf_exempt
def mark_notification_as_read(request, notification_id):
    """Mark a single notification as read"""
    if request.method == 'POST':
        try:
            notification = get_object_or_404(
                Notification,
                id=notification_id,
                recipient=request.user
            )
            notification.is_read = True
            notification.read_at = timezone.now()  # Assuming you have this field
            notification.save()
            return JsonResponse({'success': True})
        except Notification.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Notification not found'}, status=404)
    return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)


@login_required
@csrf_exempt
def toggle_notification_favourite(request, notification_id):

    print("\n=================================")
    print("⭐ FAVOURITE API CALLED")
    print("User:", request.user.username)
    print("Notification ID:", notification_id)
    print("Method:", request.method)
    print("Body:", request.body)
    print("=================================")

    if request.method != "POST":
        return JsonResponse(
            {
                "success": False,
                "error": "Invalid method",
            },
            status=405,
        )

    notification = get_object_or_404(
        Notification,
        id=notification_id,
        recipient=request.user,
    )

    try:
        data = json.loads(request.body)

        print("Parsed data:", data)

        is_favourite = bool(
            data.get("is_favourite", False)
        )

        print("Requested favourite:", is_favourite)

    except (json.JSONDecodeError, TypeError) as e:

        print("❌ JSON ERROR:", e)

        return JsonResponse(
            {
                "success": False,
                "error": "Invalid request data",
            },
            status=400,
        )

    state, created = NotificationUserState.objects.get_or_create(
        notification=notification,
        user=request.user,
    )

    print("State created:", created)
    print("Previous favourite:", state.is_favourite)

    state.is_favourite = is_favourite

    state.save(
        update_fields=[
            "is_favourite",
            "updated_at",
        ]
    )

    print("New favourite:", state.is_favourite)
    print("=================================\n")

    return JsonResponse({
        "success": True,
        "is_favourite": state.is_favourite,
    })




@login_required
@csrf_exempt
def mark_all_notifications_as_read(request):
    """Mark all notifications as read for the current user"""
    if request.method == 'POST':
        count = Notification.objects.filter(
            recipient=request.user,
            is_read=False
        ).update(is_read=True, read_at=timezone.now())
        return JsonResponse({'success': True, 'count': count})
    return JsonResponse({'success': False, 'error': 'Invalid method'}, status=405)
@login_required
@csrf_exempt
def mark_timesheet_viewed(request, timesheet_id):
    """
    API endpoint to mark a timesheet as viewed
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        timesheet = Timesheet.objects.get(id=timesheet_id)
        
        # Check if user has permission (is the owner or assignee)
        if timesheet.user != request.user:
            return JsonResponse(
                {
                    "success": False,
                    "error": "Permission denied",
                },
                status=403,
            )
        
        # Mark as viewed
        timesheet.mark_as_viewed()
        
        return JsonResponse({
            'success': True,
            'message': 'Timesheet marked as viewed'
        })
        
    except Timesheet.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Timesheet not found'}, status=404)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@csrf_exempt
def mark_all_timesheets_viewed(request):
    """
    API endpoint to mark all timesheets as viewed
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Method not allowed'}, status=405)
    
    try:
        data = json.loads(request.body)
        timesheet_ids = data.get('timesheet_ids', [])
        
        if not timesheet_ids:
            return JsonResponse({'success': False, 'error': 'No timesheet IDs provided'}, status=400)
        
        # Mark all as viewed
        timesheets = Timesheet.objects.filter(
            id__in=timesheet_ids,
            user=request.user
        )
        
        updated_count = 0
        for timesheet in timesheets:
            timesheet.mark_as_viewed()
            updated_count += 1
        
        return JsonResponse({
            'success': True,
            'message': f'{updated_count} timesheets marked as viewed'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)