from django.shortcuts import redirect
from django.contrib import messages


def superadmin_required(view_func):

    def wrapper(request, *args, **kwargs):

        if not request.user.is_authenticated:
            return redirect('accounts:login')

        if (
            request.user.role and
            request.user.role.role_code == 'SUPERADMIN'
        ):
            return view_func(request, *args, **kwargs)

        messages.error(
            request,
            'You do not have permission to access this page.'
        )

        return redirect('accounts:dashboard')

    return wrapper