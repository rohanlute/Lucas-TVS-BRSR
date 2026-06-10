from django.shortcuts import redirect
from django.contrib import messages


class SuperAdminRequiredMixin:

    def dispatch(self, request, *args, **kwargs):

        if not request.user.is_authenticated:
            return redirect('accounts:login')

        if request.user.is_super_admin:
            return super().dispatch(
                request,
                *args,
                **kwargs
            )

        messages.error(
            request,
            'You do not have permission to access this page.'
        )

        return redirect('accounts:dashboard')