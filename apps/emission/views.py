from django.views.generic import TemplateView
from django.http import JsonResponse
from django.views import View
from django.urls import reverse_lazy
from dataclasses import dataclass
from typing import List, Dict, Any
from datetime import datetime
import json
from django.views.generic import (
    ListView,
    CreateView,
    UpdateView,
    DeleteView,
)
from .models import EmissionTransaction
from .forms import EmissionTransactionForm


class EmissionsDashboardView(TemplateView):
    """
    Renders the main Carbon Emissions Dashboard page
    (KPI cards, monthly trend, scope breakdown, by-plant chart,
    task status, recent activity).
    """
    template_name = "emission/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context["kpis"] = [
            {"label": "TOTAL EMISSIONS YTD", "value": 50276, "unit": "tCO2e",
             "delta": -4.2, "accent": "green"},
            {"label": "SCOPE 1 DIRECT", "value": 14470, "unit": "tCO2e",
             "delta": -2.1, "accent": "teal"},
            {"label": "SCOPE 2 INDIRECT", "value": 10266, "unit": "tCO2e",
             "delta": -6.8, "accent": "blue"},
            {"label": "SCOPE 3 VALUE CHAIN", "value": 25540, "unit": "tCO2e",
             "delta": 1.3, "accent": "orange"},
        ]

        context["months"] = ["Apr", "May", "Jun", "Jul", "Aug", "Sep",
                              "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"]
        context["scope1_series"] = [1420, 1390, 1350, 1300, 1480, 1550,
                                     1500, 1380, 1300, 1250, 1300, 1400]
        context["scope2_series"] = [980, 950, 900, 870, 1000, 1050,
                                     1000, 910, 860, 830, 870, 930]
        context["scope3_series"] = [2450, 2380, 2300, 2250, 2500, 2600,
                                     2550, 2300, 2200, 2150, 2250, 2400]

        context["scope_breakdown"] = [
            {"name": "Scope 1", "value": 14470, "pct": 28.8, "color": "#22c07a"},
            {"name": "Scope 2", "value": 10266, "pct": 20.4, "color": "#17b6a7"},
            {"name": "Scope 3", "value": 25540, "pct": 50.8, "color": "#3b6df0"},
        ]

        context["by_plant"] = [
            {"name": "Mundra", "value": 8600},
            {"name": "Tiroda", "value": 8100},
            {"name": "Raipur", "value": 7300},
            {"name": "Kawai", "value": 6600},
            {"name": "Udupi", "value": 5900},
        ]

        context["task_status"] = {
            "total": 142,
            "completed": 98,
            "pending_review": 23,
            "overdue": 7,
        }

        context["recent_activity"] = [
            {"status": "ok", "title": "Q3 Diesel Consumption — Mundra Plant",
             "author": "Priya Sharma", "meta": "2h ago"},
            {"status": "warn", "title": "Nov Grid Electricity — Tiroda Plant",
             "author": "Rahul Mehta", "meta": "3d overdue"},
            {"status": "pending", "title": "Business Travel — Q3 FY25",
             "author": "Neha Gupta", "meta": "5h ago"},
            {"status": "warn", "title": "Refrigerant Leakage — Raipur Plant",
             "author": "Amit Singh", "meta": "1d ago"},
            {"status": "ok", "title": "Water Withdrawal — Kawai Plant",
             "author": "Sunita Rao", "meta": "6h ago"},
        ]

        return context


class EmissionsDashboardDataView(View):
    """
    Optional JSON endpoint — same data as above, useful if the front end
    (e.g. the Chart.js widgets) wants to fetch/refresh the dashboard via AJAX
    instead of relying purely on server-rendered context.
    """

    def get(self, request, *args, **kwargs):
        data = {
            "kpis": {
                "total_ytd": 50276,
                "scope1": 14470,
                "scope2": 10266,
                "scope3": 25540,
            },
            "monthly_trend": {
                "months": ["Apr", "May", "Jun", "Jul", "Aug", "Sep",
                           "Oct", "Nov", "Dec", "Jan", "Feb", "Mar"],
                "scope1": [1420, 1390, 1350, 1300, 1480, 1550,
                          1500, 1380, 1300, 1250, 1300, 1400],
                "scope2": [980, 950, 900, 870, 1000, 1050,
                          1000, 910, 860, 830, 870, 930],
                "scope3": [2450, 2380, 2300, 2250, 2500, 2600,
                          2550, 2300, 2200, 2150, 2250, 2400],
            },
            "by_plant": [
                {"name": "Mundra", "value": 8600},
                {"name": "Tiroda", "value": 8100},
                {"name": "Raipur", "value": 7300},
                {"name": "Kawai", "value": 6600},
                {"name": "Udupi", "value": 5900},
            ],
            "task_status": {
                "total": 142, "completed": 98,
                "pending_review": 23, "overdue": 7,
            },
        }
        return JsonResponse(data)


# =============================================
# TASK LIST VIEWS
# =============================================

@dataclass
class Task:
    """Data class for individual tasks"""
    id: int
    title: str
    from_assignee: str
    to_assignee: str
    date: str
    scope: str
    scope_color: str
    emissions: float
    emissions_unit: str
    status: str
    status_color: str
    is_completed: bool = False
    
    @property
    def task_id(self) -> str:
        return f"T-{str(self.id).zfill(3)}"


class TaskListView(TemplateView):
    """
    Class-based view to display the task list with filtering capabilities.
    No database - all data is in-memory.
    """
    template_name = "emission/task.html"
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get filter parameter from URL
        filter_status = self.request.GET.get('status', 'all')
        
        # Get all tasks
        all_tasks = self._get_sample_tasks()
        
        # Apply filter if not 'all'
        if filter_status != 'all':
            filtered_tasks = [task for task in all_tasks if task.status.lower() == filter_status.lower()]
        else:
            filtered_tasks = all_tasks
        
        context['tasks'] = filtered_tasks
        context['all_tasks'] = all_tasks
        context['filter_status'] = filter_status
        context['task_counts'] = self._get_task_counts(all_tasks)
        context['current_year'] = datetime.now().year
        
        return context
    
    def _get_sample_tasks(self) -> List[Task]:
        """
        Generate sample task data.
        All data is hardcoded - no database needed.
        """
        return [
            Task(
                id=1,
                title="Grid Electricity Consumption",
                from_assignee="Rahul Mehta",
                to_assignee="Priya Sharma",
                date="Nov 2024",
                scope="Scope 2",
                scope_color="scope2",
                emissions=38.3,
                emissions_unit="tCO₂e",
                status="Overdue",
                status_color="overdue",
                is_completed=False
            ),
            Task(
                id=2,
                title="Business Travel — Domestic Air",
                from_assignee="Neha Gupta",
                to_assignee="Arjun Kumar",
                date="Q3 FY25",
                scope="Scope 3",
                scope_color="scope3",
                emissions=18.7,
                emissions_unit="tCO₂e",
                status="Submitted",
                status_color="submitted",
                is_completed=False
            ),
            Task(
                id=3,
                title="Diesel Consumption — DG Sets",
                from_assignee="Amit Singh",
                to_assignee="Sunita Rao",
                date="Nov 2024",
                scope="Scope 1",
                scope_color="scope1",
                emissions=10.1,
                emissions_unit="tCO₂e",
                status="Rejected",
                status_color="rejected",
                is_completed=False
            ),
            Task(
                id=4,
                title="Refrigerant Leakage (HFC-134a)",
                from_assignee="Sunita Rao",
                to_assignee="Arjun Kumar",
                date="Q3 FY25",
                scope="Scope 1",
                scope_color="scope1",
                emissions=16.9,
                emissions_unit="tCO₂e",
                status="Approved",
                status_color="approved",
                is_completed=False
            ),
            Task(
                id=5,
                title="Natural Gas Combustion",
                from_assignee="Vikram Joshi",
                to_assignee="Priya Sharma",
                date="Dec 2024",
                scope="Scope 1",
                scope_color="scope1",
                emissions=104.0,
                emissions_unit="tCO₂e",
                status="Approved",
                status_color="approved",
                is_completed=False
            ),
            Task(
                id=6,
                title="Water Withdrawal",
                from_assignee="Anjali Patel",
                to_assignee="Vikram Joshi",
                date="Nov 2024",
                scope="Scope 3",
                scope_color="scope3",
                emissions=2.1,
                emissions_unit="tCO₂e",
                status="Overdue",
                status_color="overdue",
                is_completed=False
            ),
        ]
    
    def _get_task_counts(self, tasks: List[Task]) -> Dict[str, int]:
        """Get counts for each status"""
        counts = {
            'all': len(tasks),
            'overdue': 0,
            'submitted': 0,
            'rejected': 0,
            'approved': 0,
        }
        
        for task in tasks:
            status_key = task.status.lower()
            if status_key in counts:
                counts[status_key] += 1
        
        return counts


class TaskFilterView(View):
    """
    API view to filter tasks via AJAX without page reload.
    URL: /api/tasks/filter/
    """
    
    def get(self, request, *args, **kwargs):
        status = request.GET.get('status', 'all')
        
        # Get all tasks from the list view
        all_tasks = TaskListView()._get_sample_tasks()
        
        # Filter tasks
        if status != 'all':
            filtered_tasks = [task for task in all_tasks if task.status.lower() == status.lower()]
        else:
            filtered_tasks = all_tasks
        
        # Render tasks as HTML
        html = self._render_task_items(filtered_tasks)
        
        # Get counts
        counts = TaskListView()._get_task_counts(all_tasks)
        
        return JsonResponse({
            'html': html,
            'count': len(filtered_tasks),
            'filter': status,
            'counts': counts
        })
    
    def _render_task_items(self, tasks: List[Task]) -> str:
        """Render task items as HTML string for AJAX response"""
        if not tasks:
            return '''
            <div class="no-tasks visible">
                <i class="fas fa-inbox"></i>
                <p>No tasks found for this filter</p>
            </div>
            '''
        
        html = ''
        for task in tasks:
            html += f'''
            <div class="task-item" data-status="{task.status.lower()}" data-task-id="{task.id}">
                <div class="task-id">{task.task_id}</div>
                <div class="task-content">
                    <div class="task-title">{task.title}</div>
                    <div class="task-assignee">
                        {task.from_assignee} <span class="arrow">→</span> {task.to_assignee}
                    </div>
                    <div class="task-meta">
                        <span class="task-date">{task.date}</span>
                        <span class="task-scope {task.scope_color}">{task.scope}</span>
                        <span class="task-emissions">{task.emissions} {task.emissions_unit}</span>
                    </div>
                </div>
                <div class="task-status">
                    <span class="status-badge {task.status_color}">{task.status}</span>
                    <div class="task-checkbox {'checked' if task.is_completed else ''}" 
                         onclick="toggleCheckbox(this, {task.id})">
                    </div>
                </div>
            </div>
            '''
        return html


class TaskToggleView(View):
    """
    View to toggle task completion status via AJAX.
    URL: /api/tasks/toggle/
    """
    
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            task_id = data.get('task_id')
            is_completed = data.get('is_completed', False)
            
            # In a real app, you would update the database here
            # For demo, we just return success
            return JsonResponse({
                'success': True,
                'message': f'Task {task_id} marked as {"complete" if is_completed else "incomplete"}',
                'task_id': task_id,
                'is_completed': is_completed
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)

class TaskExportView(View):
        """
        View to export tasks in different formats (CSV, JSON).
        URL: /tasks/export/
        """
        
        def get(self, request, *args, **kwargs):
            format_type = request.GET.get('format', 'csv')
            status = request.GET.get('status', 'all')
            
            # Get all tasks
            all_tasks = TaskListView()._get_sample_tasks()
            
            # Filter if needed
            if status != 'all':
                tasks = [task for task in all_tasks if task.status.lower() == status.lower()]
            else:
                tasks = all_tasks
            
            if format_type == 'csv':
                return self._export_csv(tasks)
            elif format_type == 'json':
                return self._export_json(tasks)
            else:
                return JsonResponse({'error': 'Unsupported format'}, status=400)
        
        def _export_csv(self, tasks: List[Task]):
            """Export tasks as CSV"""
            import csv
            from django.http import HttpResponse
            
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="tasks_export.csv"'
            
            writer = csv.writer(response)
            writer.writerow(['Task ID', 'Title', 'From', 'To', 'Date', 'Scope', 'Emissions', 'Status'])
            
            for task in tasks:
                writer.writerow([
                    task.task_id,
                    task.title,
                    task.from_assignee,
                    task.to_assignee,
                    task.date,
                    task.scope,
                    f"{task.emissions} {task.emissions_unit}",
                    task.status
                ])
            
            return response
        
        def _export_json(self, tasks: List[Task]):
            """Export tasks as JSON"""
            from django.http import JsonResponse
            
            data = {
                'export_date': datetime.now().isoformat(),
                'total_tasks': len(tasks),
                'tasks': [
                    {
                        'task_id': task.task_id,
                        'title': task.title,
                        'from_assignee': task.from_assignee,
                        'to_assignee': task.to_assignee,
                        'date': task.date,
                        'scope': task.scope,
                        'emissions': task.emissions,
                        'emissions_unit': task.emissions_unit,
                        'status': task.status,
                    }
                    for task in tasks
                ]
            }
            
            return JsonResponse(data, json_dumps_params={'indent': 2})

@dataclass
class Assignment:
    """Data class for assignments"""
    id: str
    activity: str
    location: str
    location_detail: str
    assignee: str
    reviewer: str
    scope: str
    scope_color: str
    frequency: str
    due_day: str


# ===== IN-MEMORY STORAGE =====
ASSIGNMENTS_STORAGE = []


class AdministratorAssignmentsView(TemplateView):
    """
    View to display administrator assignments.
    """
    template_name = 'emission/assignment.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Initialize with sample data if storage is empty
        if not ASSIGNMENTS_STORAGE:
            sample_assignments = self._get_sample_assignments()
            ASSIGNMENTS_STORAGE.extend(sample_assignments)
        
        context['assignments'] = ASSIGNMENTS_STORAGE
        context['current_year'] = datetime.now().year
        return context
    
    def _get_sample_assignments(self) -> List[Assignment]:
        """Generate sample assignment data"""
        return [
            Assignment(
                id="A-101",
                activity="Grid Electricity Consumption",
                location="Mundra Plant - Operations",
                location_detail="Mundra Plant - Operations",
                assignee="Rahul Mehta",
                reviewer="Priya Sharma",
                scope="Scope 2",
                scope_color="scope2",
                frequency="Monthly",
                due_day="Day 5"
            ),
            Assignment(
                id="A-102",
                activity="Natural Gas Combustion",
                location="Tiroda Plant - Production",
                location_detail="Tiroda Plant - Production",
                assignee="Vikram Joshi",
                reviewer="Priya Sharma",
                scope="Scope 1",
                scope_color="scope1",
                frequency="Monthly",
                due_day="Day 10"
            ),
            Assignment(
                id="A-103",
                activity="Diesel Consumption — DG Sets",
                location="Raipur Plant - Facilities",
                location_detail="Raipur Plant - Facilities",
                assignee="Amit Singh",
                reviewer="Sunita Rao",
                scope="Scope 1",
                scope_color="scope1",
                frequency="Monthly",
                due_day="Day 10"
            ),
            Assignment(
                id="A-104",
                activity="Business Travel — Domestic Air",
                location="Corporate HQ - HR & Admin",
                location_detail="Corporate HQ - HR & Admin",
                assignee="Neha Gupta",
                reviewer="Arjun Kumar",
                scope="Scope 3",
                scope_color="scope3",
                frequency="Quarterly",
                due_day="Day 15"
            ),
            Assignment(
                id="A-105",
                activity="Refrigerant Leakage (HFC-134a)",
                location="Kawai Plant - Maintenance",
                location_detail="Kawai Plant - Maintenance",
                assignee="Sunita Rao",
                reviewer="Arjun Kumar",
                scope="Scope 1",
                scope_color="scope1",
                frequency="Quarterly",
                due_day="Day 20"
            ),
        ]


class CreateAssignmentView(TemplateView):
    """
    View to create a new assignment.
    """
    template_name = 'emission/create_assignment.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['plants'] = self._get_plants()
        context['departments'] = self._get_departments()
        context['people'] = self._get_people()
        context['scope_activities'] = self._get_scope_activities()
        context['frequencies'] = ['Monthly', 'Quarterly', 'Annually']
        return context
    
    def _get_plants(self):
        return [
            {'id': 1, 'name': 'Rewari Plant'},
            {'id': 2, 'name': 'Chakan Plant'},
            {'id': 3, 'name': 'Nettappakkam Plant'},
            {'id': 4, 'name': 'Padi Plant'},
            {'id': 5, 'name': 'PantNagar Plant'},
            {'id': 6, 'name': 'Thiruvandarkoil Plant'},
            {'id': 7, 'name': 'Maraimalainagar Plant'},
        ]
    
    def _get_departments(self):
        return [
            {'id': 1, 'name': 'Operations', 'plant_id': 1},
            {'id': 2, 'name': 'Production', 'plant_id': 2},
            {'id': 3, 'name': 'Facilities', 'plant_id': 3},
            {'id': 4, 'name': 'Maintenance', 'plant_id': 4},
            {'id': 5, 'name': 'HR & Admin', 'plant_id': 5},
            {'id': 6, 'name': 'Corporate', 'plant_id': 1},
            {'id': 7, 'name': 'Operations', 'plant_id': 6},
            {'id': 8, 'name': 'Production', 'plant_id': 6},
            {'id': 9, 'name': 'EHS', 'plant_id': 6},
            {'id': 10, 'name': 'Operations', 'plant_id': 7},
            {'id': 11, 'name': 'Production', 'plant_id': 7},
            {'id': 12, 'name': 'EHS', 'plant_id': 7},
        ]
    
    def _get_people(self):
        return [
            'Divya Sharma',
            'Rohan Lute',
            'Samarth Bhagane',
            'Akshada Kamble',
            'Nehal Ansari',
        ]
    
    def _get_scope_activities(self):
        return {
            'Scope 1': [
                'Diesel Consumption',
                'Petrol Consumption',
                'LPG Consumption',
                'Natural Gas',
                'DG Set Diesel',
                'Refrigerant Leakage',
                'Company Vehicles'
            ],
            'Scope 2': [
                'Purchased Electricity',
                'Purchased Steam',
                'Purchased Cooling',
                'Renewable Electricity'
            ],
            'Scope 3': [
                'Business Travel',
                'Employee Commuting',
                'Waste Disposal',
                'Purchased Goods',
                'Transportation',
                'Water Consumption',
                'Capital Goods',
                'Investments'
            ]
        }


class GetDepartmentsByPlantView(View):
    """
    API view to get departments by plant ID.
    """
    def get(self, request, *args, **kwargs):
        plant_id = request.GET.get('plant_id')
        
        departments = {
            '1': [
                {'id': 1, 'name': 'Operations'},
                {'id': 6, 'name': 'Corporate'},
            ],
            '2': [
                {'id': 2, 'name': 'Production'},
            ],
            '3': [
                {'id': 3, 'name': 'Facilities'},
            ],
            '4': [
                {'id': 4, 'name': 'Maintenance'},
            ],
            '5': [
                {'id': 5, 'name': 'HR & Admin'},
            ],
            '6': [
                {'id': 7, 'name': 'Operations'},
                {'id': 8, 'name': 'Production'},
                {'id': 9, 'name': 'EHS'},
            ],
            '7': [
                {'id': 10, 'name': 'Operations'},
                {'id': 11, 'name': 'Production'},
                {'id': 12, 'name': 'EHS'},
            ],
        }
        
        result = departments.get(str(plant_id), [])
        return JsonResponse({'departments': result})


class CreateAssignmentSubmitView(View):
    """
    View to handle assignment creation form submission.
    """
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            
            # Generate new ID
            if ASSIGNMENTS_STORAGE:
                # Find max ID number
                ids = [int(a.id.replace('A-', '')) for a in ASSIGNMENTS_STORAGE if a.id.startswith('A-')]
                next_num = max(ids) + 1 if ids else 101
            else:
                next_num = 101
            
            new_id = f"A-{next_num}"
            
            # Get scope color
            scope_colors = {
                'Scope 1': 'scope1',
                'Scope 2': 'scope2',
                'Scope 3': 'scope3'
            }
            
            # Get plant and department names
            plant_name = data.get('plant_name', '')
            department_name = data.get('department_name', '')
            location = f"{plant_name} - {department_name}" if plant_name and department_name else plant_name
            
            # Create new assignment
            new_assignment = Assignment(
                id=new_id,
                activity=data.get('activity', ''),
                location=location,
                location_detail=location,
                assignee=data.get('assignee', ''),
                reviewer=data.get('reviewer', ''),
                scope=data.get('scope', ''),
                scope_color=scope_colors.get(data.get('scope', ''), 'scope1'),
                frequency=data.get('frequency', ''),
                due_day=f"Day {data.get('due_day', '')}"
            )
            
            # Add to storage
            ASSIGNMENTS_STORAGE.append(new_assignment)
            
            return JsonResponse({
                'success': True,
                'message': 'Assignment created successfully!',
                'assignment': {
                    'id': new_id,
                    'activity': new_assignment.activity,
                    'location': new_assignment.location,
                    'assignee': new_assignment.assignee,
                    'reviewer': new_assignment.reviewer,
                    'scope': new_assignment.scope,
                    'frequency': new_assignment.frequency,
                    'due_day': new_assignment.due_day
                }
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=400)


class AdministratorAssignmentsDataView(View):
    """
    JSON endpoint for assignments data (AJAX refresh).
    """
    def get(self, request, *args, **kwargs):
        assignments = ASSIGNMENTS_STORAGE if ASSIGNMENTS_STORAGE else AdministratorAssignmentsView()._get_sample_assignments()
        data = {
            'assignments': [
                {
                    'id': a.id,
                    'activity': a.activity,
                    'location': a.location,
                    'assignee': a.assignee,
                    'reviewer': a.reviewer,
                    'scope': a.scope,
                    'scope_color': a.scope_color,
                    'frequency': a.frequency,
                    'due_day': a.due_day,
                }
                for a in assignments
            ]
        }
        return JsonResponse(data)
# emission/views.py

class ESGDisclosureView(TemplateView):
    """
    View to display ESG / BRSR Disclosure page.
    """
    template_name = 'emission/report.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['current_year'] = datetime.now().year
        return context

class EmissionTransactionListView(ListView):

    model = EmissionTransaction

    template_name = "emission/transaction_list.html"

    context_object_name = "transactions"

    paginate_by = 20

    def get_queryset(self):

        queryset = (
            EmissionTransaction.objects
            .select_related(
                "company",
                "plant",
                "financial_year",
                "financial_month",
                "activity",
                "unit",
            )
            .order_by(
                "-financial_year",
                "financial_month",
                "plant",
            )
        )

        search = self.request.GET.get("search")

        if search:

            queryset = queryset.filter(
                activity__name__icontains=search
            )

        return queryset

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        context["search"] = self.request.GET.get(
            "search",
            "",
        )

        context["total_transactions"] = (
            EmissionTransaction.objects.count()
        )

        context["draft_count"] = (
            EmissionTransaction.objects.filter(
                status="DRAFT"
            ).count()
        )

        context["submitted_count"] = (
            EmissionTransaction.objects.filter(
                status="SUBMITTED"
            ).count()
        )

        context["approved_count"] = (
            EmissionTransaction.objects.filter(
                status="APPROVED"
            ).count()
        )

        return context

class EmissionTransactionCreateView(CreateView):

    model = EmissionTransaction

    form_class = EmissionTransactionForm

    template_name = "emission/transaction_form.html"

    success_url = reverse_lazy(
        "emission:transaction_list"
    )

    def form_valid(self, form):

        if self.request.user.is_authenticated:

            form.instance.created_by = self.request.user

        return super().form_valid(form)
    


class EmissionTransactionUpdateView(UpdateView):

    model = EmissionTransaction

    form_class = EmissionTransactionForm

    template_name = "emission/transaction_form.html"

    success_url = reverse_lazy(
        "emission:transaction_list"
    )


class EmissionTransactionDeleteView(DeleteView):

    model = EmissionTransaction

    template_name = "emission/transaction_delete.html"

    success_url = reverse_lazy(
        "emission:transaction_list"
    )













from .models import (
    EmissionTransaction,
    EmissionScope,
    EmissionCategory,
)

from apps.companies.models import Company
from apps.organizations.models import (
    Plant,
    FinancialYear,
    FinancialMonth,
)

from django.utils import timezone
from ..organizations.models import FinancialYear, FinancialMonth

class ScopeDashboardView(ListView):

    model = EmissionTransaction

    template_name = "emission/scope_dataentry.html"

    context_object_name = "transactions"

    paginate_by = 20

    def get_context_data(self, **kwargs):

        context = super().get_context_data(**kwargs)

        scope = (
            EmissionScope.objects
            .prefetch_related("categories")
            .get(code="S1")
        )

        context["scope"] = scope

        context["categories"] = (
            scope.categories
            .filter(is_active=True)
            .order_by("display_order")
        )

        context["companies"] = Company.objects.filter(
            is_active=True
        ).order_by(
            "company_name"
        )

        context["plants"] = Plant.objects.filter(
            is_active=True
        ).order_by(
            "name"
        )

        context["financial_years"] = FinancialYear.objects.all()

        context["financial_months"] = (
            FinancialMonth.objects
            .filter(is_active=True)
            .order_by("display_order")
        )

        today = timezone.now().date()

        current_financial_year = (
            FinancialYear.objects.filter(
                start_date__lte=today,
                end_date__gte=today
            ).first()
        )

        current_month_number = today.month

        # Convert calendar month to your financial month numbering
        month_mapping = {
            4: 1,   # April
            5: 2,
            6: 3,
            7: 4,
            8: 5,
            9: 6,
            10: 7,
            11: 8,
            12: 9,
            1: 10,
            2: 11,
            3: 12,
        }

        current_financial_month = FinancialMonth.objects.filter(
            month_number=month_mapping[current_month_number]
        ).first()

        context["current_financial_year"] = current_financial_year
        context["current_financial_month"] = current_financial_month

        return context
    


from django.http import JsonResponse
from django.views import View

from .models import (
    EmissionActivity,
    EmissionSource,
)


class CategoryActivitiesView(View):

    def get(self, request, *args, **kwargs):

        category_id = request.GET.get("category_id")

        activities = (
            EmissionActivity.objects.filter(
                category_id=category_id,
                is_active=True,
            )
            .select_related(
                "base_unit",
            )
            .prefetch_related(
                "sources",
            )
            .order_by(
                "display_order",
            )
        )

        data = []

        for activity in activities:

            sources = []

            for source in activity.sources.filter(
                is_active=True
            ).order_by(
                "display_order"
            ):

                sources.append(
                    {
                        "id": source.id,
                        "code": source.source_code,
                        "name": source.source_name,
                    }
                )

            data.append(
                {
                    "id": activity.id,
                    "code": activity.code,
                    "name": activity.name,
                    "unit": activity.base_unit.symbol,
                    "base_unit_id": activity.base_unit.id,
                    "sources": sources,
                }
            )

        return JsonResponse(
            {
                "activities": data,
            }
        )
    




from django.utils import timezone

from .models import (
    EmissionFactor,
)


class ActivityFactorView(View):

    def get(self, request, *args, **kwargs):

        activity_id = request.GET.get("activity_id")

        factor = (
            EmissionFactor.objects
            .select_related(
                "unit",
            )
            .filter(
                activity_id=activity_id,
                is_active=True,
                effective_from__lte=timezone.now().date(),
            )
            .order_by(
                "-effective_from",
            )
            .first()
        )

        if not factor:

            return JsonResponse(
                {
                    "success": False,
                    "message": "Emission factor not found.",
                }
            )

        return JsonResponse(
            {
                "success": True,
                "factor": str(factor.emission_factor),
                "unit": factor.unit.symbol,
                "source": factor.source,
                "factor_id": factor.id,
            }
        )



from django.views import View
from django.db import transaction
from django.utils import timezone
from django.http import JsonResponse
import json



class SaveEmissionTransactionsView(View):

    @transaction.atomic
    def post(self, request):

        try:

            data = json.loads(request.body)

            company_id = data["company"]
            plant_id = data["plant"]
            fy_id = data["financial_year"]
            month_id = data["financial_month"]

            rows = data["rows"]

            for row in rows:

                transaction_obj, created = (
                    EmissionTransaction.objects.update_or_create(

                        company_id=company_id,
                        plant_id=plant_id,
                        financial_year_id=fy_id,
                        financial_month_id=month_id,
                        activity_id=row["activity"],
                        source_id=row["source"],

                        defaults={

                            "unit_id": row["unit"],

                            "quantity": row["quantity"],

                            "emission_factor": row.get("factor", 0),

                            "total_emission": row.get("total", 0),

                            "remarks": row.get("remarks", ""),

                            "status": "DRAFT",

                            "created_by": request.user,

                        }

                    )
                )

            return JsonResponse({

                "success": True,

                "message": "Transactions saved."

            })

        except Exception as e:

            return JsonResponse({

                "success": False,

                "message": str(e)

            })





class LoadEmissionTransactionsView(View):

    def get(self, request):

        company = request.GET.get("company")
        plant = request.GET.get("plant")
        financial_year = request.GET.get("financial_year")
        financial_month = request.GET.get("financial_month")

        transactions = (
            EmissionTransaction.objects
            .filter(
                company_id=company,
                plant_id=plant,
                financial_year_id=financial_year,
                financial_month_id=financial_month,
            )
            .select_related(
                "activity",
            )
        )

        data = []

        for transaction in transactions:

            data.append({

                "activity": transaction.activity_id,

                "source": transaction.source_id,

                "quantity": str(transaction.quantity),

                "factor": str(transaction.emission_factor),

                "total": str(transaction.total_emission),

                "status": transaction.status,

            })

        print(
            company,
            plant,
            financial_year,
            financial_month,
        )

        print(
            list(
                transactions.values(
                    "activity_id",
                    "quantity",
                    "total_emission"
                )
            )
        )

        return JsonResponse({

            "success": True,

            "transactions": data,

        })




class ScopeCategoriesView(View):

    def get(self, request):

        scope_code = request.GET.get("scope")

        scope = (
            EmissionScope.objects
            .prefetch_related("categories")
            .filter(code=scope_code)
            .first()
        )

        if not scope:
            return JsonResponse({
                "success": False
            })

        categories = []

        for category in scope.categories.filter(
            is_active=True
        ).order_by("display_order"):

            categories.append({
                "id": category.id,
                "name": category.name,
            })

        return JsonResponse({
            "success": True,
            "scope": scope.name,
            "description": scope.description,
            "categories": categories,
        })