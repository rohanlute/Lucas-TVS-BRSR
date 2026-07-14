from django.shortcuts import render


def goal_dashboard(request):
    context = {
        "page_title": "Goal Dashboard",
    }
    return render(request, "goals/dashboard.html", context)