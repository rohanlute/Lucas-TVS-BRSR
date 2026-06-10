from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from .decorators import superadmin_required

# -----------------------------------------------
# ============= LOGIN ===========================
# -----------------------------------------------

def login_view(request):

    if request.method == 'POST':

        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(
            request,
            username=username,
            password=password
        )

        if user is not None:
            login(request, user)
            if user.role and user.role.role_code == 'SUPERADMIN':
                return redirect('accounts:dashboard')

            return redirect('accounts:dashboard')

        messages.error(
            request,
            'Invalid Username or Password'
        )

    return render(request, 'base/login.html')


# -----------------------------------------------
# ============= LOGOUT ==========================
# -----------------------------------------------

def logout_view(request):

    logout(request)

    messages.success(
        request,
        'Logged out successfully'
    )

    return redirect('accounts:login')


# -----------------------------------------------
# ============= DASHBOARD =======================
# -----------------------------------------------

@login_required(login_url='accounts:login')
@superadmin_required
def dashboard(request):

    context = {
        'user': request.user
    }

    return render(request,'dashboard/dashboard.html',context)


# -----------------------------------------------
# ============= USER LIST =======================
# -----------------------------------------------

@login_required(login_url='accounts:login')
@superadmin_required
def user_list(request):

    return render(
        request,
        'accounts/user_management/user_list.html'
    )

# ============= USER LIST =======================

@login_required(login_url='accounts:login')
@superadmin_required
def user_create(request):

    return render(
        request,
        'accounts/user_management/user_create.html'
    )


# -----------------------------------------------
# ============= Department =======================
# -----------------------------------------------

@login_required(login_url='accounts:login')
@superadmin_required
def department_list(request):

    return render(
        request,
        'accounts/department/department_list.html'
    )

# ================= Department Create ==============
@login_required(login_url='accounts:login')
@superadmin_required
def department_create(request):

    return render(
        request,
        'accounts/department/department_create.html'
    )