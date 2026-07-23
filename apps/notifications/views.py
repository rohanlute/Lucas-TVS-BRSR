from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from apps.accounts.mixins import SuperAdminRequiredMixin
from .models import Notification


class NotificationListView(LoginRequiredMixin,TemplateView):

    login_url = "accounts:login"

    template_name = "applications/notification_list.html"

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        context["page_title"] = "Notification Master"

        context["notifications"] = (
            Notification.objects.filter(recipient=self.request.user).select_related("sender","company",).order_by("-created_at")
        )

        return context