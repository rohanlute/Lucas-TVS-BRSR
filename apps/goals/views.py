# apps/goals/views.py

from django.views.generic import TemplateView
from django.views import View
from apps.accounts.models import Role
from apps.organizations.models import Plant
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import redirect, reverse, render
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from decimal import Decimal, InvalidOperation
import uuid
from datetime import datetime
from django.db import models
from django.contrib.auth import get_user_model
from django.db.models import Sum, Q
import logging
import json

from apps.goals.models import *  # noqa: F401,F403  (includes KPIPlantTarget)

logger = logging.getLogger(__name__)




# ===== COMPLETE MAPPING OF ALL MATERIAL TOPICS, GOALS, METRICS, AND UNITS =====
MATERIAL_TOPICS_MAPPING = {
    # ===== SCOPE 1 =====
    'Stationary Combustion': {
        'goals': {
            'Reduce Fuel Consumption': {
                'metrics': {
                    'Diesel Consumption': {
                        'unit': 'L',
                        'activity_keyword': 'Diesel',
                        'source_keyword': '',
                        'category_keyword': 'Stationary Combustion'
                    },
                    'LPG Consumption': {
                        'unit': 'kg',
                        'activity_keyword': 'LPG',
                        'source_keyword': '',
                        'category_keyword': 'Stationary Combustion'
                    },
                    'Furnace Oil Consumption': {
                        'unit': 'L',
                        'activity_keyword': 'Furnace Oil',
                        'source_keyword': '',
                        'category_keyword': 'Stationary Combustion'
                    },
                    'Coal Consumption': {
                        'unit': 'kg',
                        'activity_keyword': 'Coal',
                        'source_keyword': '',
                        'category_keyword': 'Stationary Combustion'
                    },
                    'Total Fuel Consumption': {
                        'unit': 'L, kg',
                        'activity_keyword': 'Diesel,LPG,Furnace Oil,Coal',
                        'source_keyword': '',
                        'category_keyword': 'Stationary Combustion'
                    },
                }
            },
            'Lower GHG Emissions': {
                'metrics': {
                    'Scope 1 Stationary Emissions': {
                        'unit': 'tCO₂e',
                        'activity_keyword': '',
                        'source_keyword': '',
                        'category_keyword': 'Stationary Combustion',
                    }
                }
            },
        }
    },
    'Mobile Combustion': {
        'goals': {
            'Reduce Fuel Consumption': {
                'metrics': {
                    'Diesel Consumption': {
                        'unit': 'L',
                        'activity_keyword': 'Diesel Vehicle',  # ✅ Fixed
                        'source_keyword': '',
                        'category_keyword': 'Mobile Combustion'
                    },
                    'Petrol Consumption': {
                        'unit': 'L',
                        'activity_keyword': 'Petrol',
                        'source_keyword': '',
                        'category_keyword': 'Mobile Combustion'
                    },
                    'CNG Consumption': {
                        'unit': 'kg',
                        'activity_keyword': 'CNG',
                        'source_keyword': '',
                        'category_keyword': 'Mobile Combustion'
                    },
                    'Total Fuel Consumption': {
                        'unit': 'L, kg',
                        'activity_keyword': 'Diesel Vehicle,Petrol,CNG',  # ✅ Fixed
                        'source_keyword': '',
                        'category_keyword': 'Mobile Combustion'
                    },
                }
            },
            'Lower GHG Emissions': {
                'metrics': {
                    'Scope 1 Mobile Emissions': {
                        'unit': 'tCO₂e',
                        'activity_keyword': '',
                        'source_keyword': '',
                        'category_keyword': 'Mobile Combustion',
                    },
                }
            },
        }
    },
    'Process Emissions': {
        'goals': {
            'Reduce Process GHG Emissions': {
                'metrics': {
                    'Process GHG Emissions': {
                        'unit': 'tCO₂e',
                        'activity_keyword': '',
                        'source_keyword': '',
                        'category_keyword': 'Process Emissions'
                    },
                    'Clinker Production': {
                        'unit': 't',
                        'activity_keyword': 'Clinker Production',  # ✅ Fixed - exact match
                        'source_keyword': '',
                        'category_keyword': 'Process Emissions'
                    },
                    'Lime Production': {
                        'unit': 't',
                        'activity_keyword': 'Lime Production',  # ✅ Fixed - exact match
                        'source_keyword': '',
                        'category_keyword': 'Process Emissions'
                    },
                    'Steel Production': {
                        'unit': 't',
                        'activity_keyword': 'Steel Production',  # ✅ Fixed - exact match
                        'source_keyword': '',
                        'category_keyword': 'Process Emissions'
                    },
                    'Ammonia Production': {
                        'unit': 't',
                        'activity_keyword': 'Ammonia Production',  # ✅ Fixed - exact match
                        'source_keyword': '',
                        'category_keyword': 'Process Emissions'
                    },
                    'Nitric Acid Production': {
                        'unit': 't',
                        'activity_keyword': 'Nitric Acid Production',  # ✅ Fixed - exact match
                        'source_keyword': '',
                        'category_keyword': 'Process Emissions'
                    },
                }
            },
        }
    },
    'Fugitive Emissions': {
        'goals': {
            'Reduce Fugitive Emissions': {
                'metrics': {
                    'Total Fugitive Emissions': {
                        'unit': 'tCO₂e',
                        'activity_keyword': '',
                        'source_keyword': '',
                        'category_keyword': 'Fugitive Emissions'
                    },
                    'Total Refrigerant & Gas Leakage': {
                        'unit': 'kg',
                        'activity_keyword': 'HFC-134a Leakage,HFC-410A Leakage,R-22 Leakage,SF₆ Leakage,CO₂ Fire Extinguisher Discharge',  # ✅ Fixed - exact match
                        'source_keyword': '',
                        'category_keyword': 'Fugitive Emissions'
                    },
                }
            },
        }
    },
    # ===== SCOPE 2 =====
    'Purchased Electricity': {
        'goals': {
            'Reduce Electricity Consumption': {
                'metrics': {
                    'Total Electricity Consumption': {
                        'unit': 'kWh',
                        'activity_keyword': 'Purchased Electricity',
                        'source_keyword': '',
                        'category_keyword': 'Purchased Electricity'
                    },
                    'Purchased Electricity GHG Emissions': {
                        'unit': 'tCO₂e',
                        'activity_keyword': '',  # ✅ Fixed - emission KPI
                        'source_keyword': '',
                        'category_keyword': 'Purchased Electricity'
                    },
                }
            },
        }
    },
    'Purchased Steam, Heat & Cooling': {
        'goals': {
            'Optimize Energy Consumption': {
                'metrics': {
                    'Purchased Steam Consumption': {
                        'unit': 'Tonnes or GJ',
                        'activity_keyword': 'Purchased Steam',  # ✅ Fixed - exact match
                        'source_keyword': '',
                        'category_keyword': 'Purchased Steam'
                    },
                    'Purchased Heat Consumption': {
                        'unit': 'GJ',
                        'activity_keyword': 'Purchased Heating',  # ✅ Fixed - exact match
                        'source_keyword': '',
                        'category_keyword': 'Purchased Heating'
                    },
                    'Purchased Cooling Consumption': {
                        'unit': 'kWh',
                        'activity_keyword': 'Purchased Cooling',  # ✅ Fixed - exact match
                        'source_keyword': '',
                        'category_keyword': 'Purchased Cooling'
                    },
                    'Scope 2 GHG Emissions': {
                        'unit': 'tCO₂e',
                        'activity_keyword': '',
                        'source_keyword': '',
                        'category_keyword': 'Purchased Steam,Purchased Heating,Purchased Cooling'
                    },
                }
            },
        }
    },
    # ===== SCOPE 3 =====
    'Purchased Goods & Services': {
        'goals': {
            'Reduce Supply Chain Emissions': {
                'metrics': {
                    'Purchased Goods & Services Emissions': {
                        'unit': 'tCO₂e',
                        'activity_keyword': '',
                        'source_keyword': '',
                        'category_keyword': 'Purchased Goods & Services'  # ✅ Fixed - exact match
                    },
                }
            },
        }
    },
    'Capital Goods': {
        'goals': {
            'Reduce Capital Goods Emissions': {
                'metrics': {
                    'Capital Goods Emissions': {
                        'unit': 'tCO₂e',
                        'activity_keyword': '',
                        'source_keyword': '',
                        'category_keyword': 'Capital Goods'  # ✅ Fixed - exact match
                    },
                }
            },
        }
    },
    'Fuel & Energy Related Activities': {
        'goals': {
            'Reduce Upstream Energy Emissions': {
                'metrics': {
                    'Fuel & Energy Related Emissions': {
                        'unit': 'tCO₂e',
                        'activity_keyword': '',
                        'source_keyword': '',
                        'category_keyword': 'Fuel & Energy Related Activities'
                    },
                }
            },
        }
    },
    'Upstream Transportation & Distribution': {
        'goals': {
            'Reduce Logistics Emissions': {
                'metrics': {
                    'Upstream Transportation Emissions': {
                        'unit': 'tCO₂e',
                        'activity_keyword': '',
                        'source_keyword': '',
                        'category_keyword': 'Upstream Transportation & Distribution'
                    },
                }
            },
        }
    },
    'Waste Generated in Operations': {
        'goals': {
            'Reduce Waste-related Emissions': {
                'metrics': {
                    'Waste-related Emissions': {
                        'unit': 'tCO₂e',
                        'activity_keyword': '',
                        'source_keyword': '',
                        'category_keyword': 'Waste Generated in Operations'
                    },
                }
            },
        }
    },
}
# ===== HELPER FUNCTIONS =====

# apps/goals/views.py

# Add this after the imports
from apps.accounts.models import Role  # Already imported, but ensure it's there

# ===== ROLE-BASED ACCESS CONTROL HELPERS =====

def get_user_role_code(user):
    """
    Helper function to get user role code from User model
    Supports both FK to Role model and CharField
    """
    if not user or not user.is_authenticated:
        return 'VIEWER'
    
    if hasattr(user, 'role') and user.role:
        if hasattr(user.role, 'role_code'):
            return user.role.role_code
        elif hasattr(user.role, 'role_name'):
            # Try to get role code from role name
            role_name = user.role.role_name
            if 'ESG Head' in role_name or 'ESG Coordinator' in role_name or 'Super Admin' in role_name:
                if 'Head' in role_name:
                    return 'ESG_HEAD'
                elif 'Coordinator' in role_name:
                    return 'ESG_COORDINATOR'
                elif 'Super' in role_name:
                    return 'SUPERADMIN'
            return 'VIEWER'
        else:
            return str(user.role)
    return 'VIEWER'

def user_has_goal_management_permission(user):
    """
    Check if user has permission to manage goals (add, delete, edit)
    """
    role_code = get_user_role_code(user)
    allowed_roles = ['ESG_HEAD', 'ESG_COORDINATOR', 'SUPERADMIN']
    # Also check by role name
    if hasattr(user, 'role') and user.role:
        if hasattr(user.role, 'role_name'):
            allowed_names = ['ESG Head', 'ESG Coordinator', 'Super Admin']
            if user.role.role_name in allowed_names:
                return True
    return role_code in allowed_roles

def user_has_delete_permission(user):
    """
    Check if user has delete permissions
    """
    return user_has_goal_management_permission(user)
def get_topic_icon(topic):
    """Get FontAwesome icon for a material topic"""
    icon_map = {
        'Stationary Combustion': 'fa-fire',
        'Mobile Combustion': 'fa-car',
        'Process Emissions': 'fa-industry',
        'Fugitive Emissions': 'fa-wind',
        'Purchased Electricity': 'fa-bolt',
        'Purchased Steam, Heat & Cooling': 'fa-thermometer-half',
        'Purchased Goods & Services': 'fa-shopping-cart',
        'Capital Goods': 'fa-building',
        'Fuel & Energy Related Activities': 'fa-oil-can',
        'Upstream Transportation & Distribution': 'fa-truck-fast',
        'Business Travel': 'fa-plane',
        'Employee Commuting': 'fa-bus',
        'Transportation & Distribution': 'fa-truck',
        'Waste Generated in Operations': 'fa-trash',
        'Upstream & Downstream Activities': 'fa-exchange-alt',
    }
    return icon_map.get(topic, 'fa-tag')


def get_topic_icon_class(topic):
    """Get CSS class for topic icon color"""
    class_map = {
        'Stationary Combustion': 'energy',
        'Mobile Combustion': 'energy',
        'Process Emissions': 'emissions',
        'Fugitive Emissions': 'emissions',
        'Purchased Electricity': 'energy',
        'Purchased Steam, Heat & Cooling': 'energy',
        'Purchased Goods & Services': 'procurement',
        'Capital Goods': 'procurement',
        'Fuel & Energy Related Activities': 'energy',
        'Upstream Transportation & Distribution': 'transport',
        'Business Travel': 'transport',
        'Employee Commuting': 'transport',
        'Transportation & Distribution': 'transport',
        'Waste Generated in Operations': 'waste',
        'Upstream & Downstream Activities': 'procurement',
    }
    return class_map.get(topic, 'default')


def get_dot_color(material_topic):
    """Get dot color based on material topic"""
    color_map = {
        'Stationary Combustion': 'energy',
        'Mobile Combustion': 'energy',
        'Process Emissions': 'emissions',
        'Fugitive Emissions': 'emissions',
        'Purchased Electricity': 'energy',
        'Purchased Steam, Heat & Cooling': 'energy',
        'Purchased Goods & Services': 'procurement',
        'Capital Goods': 'procurement',
        'Fuel & Energy Related Activities': 'energy',
        'Upstream Transportation & Distribution': 'transport',
        'Business Travel': 'transport',
        'Employee Commuting': 'transport',
        'Transportation & Distribution': 'transport',
        'Waste Generated in Operations': 'waste',
        'Upstream & Downstream Activities': 'procurement',
    }
    return color_map.get(material_topic, 'default')


def get_metrics_for_goal(topic, goal):
    """Get metrics for a specific goal from MATERIAL_TOPICS_MAPPING"""
    goal_metrics = []

    if topic in MATERIAL_TOPICS_MAPPING:
        topic_data = MATERIAL_TOPICS_MAPPING[topic]
        if goal in topic_data.get('goals', {}):
            metrics_data = topic_data['goals'][goal].get('metrics', {})
            for metric_name, metric_info in metrics_data.items():
                goal_metrics.append({
                    'name': metric_name,
                    'unit': metric_info.get('unit', ''),
                    'topic': topic,
                    'goal': goal,
                    'activity_keyword': metric_info.get('activity_keyword', ''),
                    'source_keyword': metric_info.get('source_keyword', ''),
                })

    return goal_metrics


def ensure_goal_and_kpis_exist(material_topic_name, goal_name, user):
    """
    Ensure a MaterialTopic, Goal, and its KPIs exist in the database,
    creating them from MATERIAL_TOPICS_MAPPING if necessary.

    This is used so that any view that needs to persist data against a
    Goal (e.g. saving baseline/target config) always has a real row to
    write into, regardless of whether the goal was previously created
    via AddGoalView or only exists in the session.

    Returns the Goal instance (or None if it can't be resolved).
    """
    if not material_topic_name or not goal_name:
        return None

    material_topic, _ = MaterialTopic.objects.get_or_create(
        name=material_topic_name,
        defaults={
            'is_active': True,
            'created_by': user,
            'updated_by': user,
        }
    )
    # Re-activate if it had been soft-deleted
    if not material_topic.is_active:
        material_topic.is_active = True
        material_topic.updated_by = user
        material_topic.save()

    goal, _ = Goal.objects.get_or_create(
        material_topic=material_topic,
        name=goal_name,
        defaults={
            'is_active': True,
            'created_by': user,
            'updated_by': user,
        }
    )
    if not goal.is_active:
        goal.is_active = True
        goal.updated_by = user
        goal.save()

    # Create KPIs from the mapping if none exist yet for this goal
    if not goal.kpis.filter(is_active=True).exists():
        topic_data = MATERIAL_TOPICS_MAPPING.get(material_topic_name, {})
        metrics = topic_data.get('goals', {}).get(goal_name, {}).get('metrics', {})
        for metric_name, metric_info in metrics.items():
            unit = metric_info.get('unit', '')
            activity_keyword = metric_info.get('activity_keyword', '')
            category_keyword = metric_info.get('category_keyword', '')

            # Emission KPIs should only filter by category
            if 'tco2e' in unit.lower() or 'tco2' in unit.lower():
                activity_keyword = ''

            KPI.objects.get_or_create(
                goal=goal,
                name=metric_name,
                defaults={
                    'unit': unit,
                    'is_active': True,
                    'baseline_value': 0,
                    'target_value': 0,
                    'activity_keyword': activity_keyword,
                    'source_keyword': '',
                    'category_keyword': category_keyword,
                    'created_by': user,
                    'updated_by': user,
                }
            )
            logger.info(f"Auto-created KPI '{metric_name}' for goal '{goal_name}' during config save")

    return goal


def normalize_plant_id(raw_value):
    """
    Normalize a plant_id value coming from a request (string, None, '', 'null', etc.)
    into either an int or None. Raises ValueError if it's a non-empty, non-numeric value.
    """
    if raw_value in (None, '', 'null', 'undefined', 'None'):
        return None
    try:
        return int(raw_value)
    except (ValueError, TypeError):
        raise ValueError(f"Invalid plant_id: {raw_value}")


# ===== DASHBOARD VIEW =====

class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Goals Dashboard View - Shows only goals that have been added
    """
    template_name = 'goals/dashboard.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # ===== ADD USER ROLE TO CONTEXT =====
        user = self.request.user
        context['user_role'] = get_user_role_code(user)
        context['user_role_name'] = user.role.role_name if hasattr(user, 'role') and user.role else 'Viewer'
        context['can_manage_goals'] = user_has_goal_management_permission(user)
        context['can_delete_goals'] = user_has_delete_permission(user)

        # ===== GET GOALS FROM SESSION =====
        session_goals = self.request.session.get('goals', [])

        # ===== GET GOALS FROM DATABASE =====
        db_goals = Goal.objects.filter(
            is_active=True,
            material_topic__is_active=True
        ).select_related('material_topic')

        # Get context filters from request
        company_id = self.request.GET.get('company_id')
        plant_id = self.request.GET.get('plant_id')
        financial_year_id = self.request.GET.get('financial_year_id')
        financial_month_id = self.request.GET.get('financial_month_id')
        assignment_id = self.request.GET.get('assignment_id')

        # ===== BUILD DICTIONARY OF ADDED TOPICS =====
        added_topics = {}

        # ===== TRACK GOALS THAT EXIST IN DATABASE =====
        db_goal_keys = set()  # (topic_name, goal_name) tuples

        # ===== ADD DATABASE GOALS =====
        for db_goal in db_goals:
            topic_name = db_goal.material_topic.name
            goal_name = db_goal.name
            db_goal_keys.add((topic_name, goal_name))

            if topic_name not in added_topics:
                added_topics[topic_name] = {
                    'material_topic': topic_name,
                    'goals': [],
                    'dot_color': get_dot_color(topic_name),
                    'icon': get_topic_icon(topic_name),
                    'icon_class': get_topic_icon_class(topic_name),
                    'total_kpis': 0,
                }

            # Get KPIs for this goal with current values
            db_kpis = db_goal.kpis.filter(is_active=True)
            kpi_list = []
            for kpi in db_kpis:
                current_value = kpi.get_current_value(
                    company_id=company_id,
                    plant_id=plant_id,
                    financial_year_id=financial_year_id,
                    financial_month_id=financial_month_id,
                    assignment_id=assignment_id
                )

                kpi_list.append({
                    'name': kpi.name,
                    'unit': kpi.unit,
                    'kpi_id': kpi.id,
                    'current_value': current_value,
                    'target_value': float(kpi.target_value) if kpi.target_value else 0,
                    'baseline_value': float(kpi.baseline_value) if kpi.baseline_value else 0,
                })

            # Check if goal already exists in the topic's goals list
            goal_exists = False
            for existing_goal in added_topics[topic_name]['goals']:
                if existing_goal.get('name') == goal_name:
                    goal_exists = True
                    existing_goal['kpis'] = kpi_list
                    existing_goal['is_from_db'] = True
                    existing_goal['goal_id'] = str(db_goal.id)
                    existing_goal['kpi_count'] = len(kpi_list)
                    break

            if not goal_exists:
                added_topics[topic_name]['goals'].append({
                    'name': goal_name,
                    'kpis': kpi_list,
                    'is_from_db': True,
                    'goal_id': str(db_goal.id),
                    'kpi_count': len(kpi_list),
                })
                added_topics[topic_name]['total_kpis'] += len(kpi_list)

        # ===== ADD SESSION GOALS (ONLY IF NOT ALREADY IN DATABASE) =====
        for session_goal in session_goals:
            topic_name = session_goal.get('material_topic', 'Uncategorized')
            goal_name = session_goal.get('goal_name') or session_goal.get('name', 'Unknown')

            # Skip if this goal already exists in database
            if (topic_name, goal_name) in db_goal_keys:
                continue

            # Initialize topic if not exists
            if topic_name not in added_topics:
                added_topics[topic_name] = {
                    'material_topic': topic_name,
                    'goals': [],
                    'dot_color': get_dot_color(topic_name),
                    'icon': get_topic_icon(topic_name),
                    'icon_class': get_topic_icon_class(topic_name),
                    'total_kpis': 0,
                }

            # Check if goal already exists in this topic
            goal_exists = False
            for existing_goal in added_topics[topic_name]['goals']:
                if existing_goal.get('name') == goal_name:
                    goal_exists = True
                    break

            if goal_exists:
                continue

            # ===== GET KPIs FROM MAPPING =====
            kpi_list = []
            if topic_name in MATERIAL_TOPICS_MAPPING:
                topic_data = MATERIAL_TOPICS_MAPPING[topic_name]
                if goal_name in topic_data.get('goals', {}):
                    metrics = topic_data['goals'][goal_name].get('metrics', {})
                    for metric_name, metric_info in metrics.items():
                        # Try to get current value from database if KPI exists
                        current_value = 0
                        kpi_id = None
                        try:
                            kpi = KPI.objects.get(
                                goal__material_topic__name=topic_name,
                                goal__name=goal_name,
                                name=metric_name,
                                is_active=True
                            )
                            current_value = kpi.get_current_value(
                                company_id=company_id,
                                plant_id=plant_id,
                                financial_year_id=financial_year_id,
                                financial_month_id=financial_month_id,
                                assignment_id=assignment_id
                            )
                            kpi_id = kpi.id
                        except KPI.DoesNotExist:
                            pass

                        kpi_list.append({
                            'name': metric_name,
                            'unit': metric_info.get('unit', ''),
                            'kpi_id': kpi_id,
                            'current_value': current_value,
                            'target_value': 0,
                            'baseline_value': 0,
                            'from_mapping': True,
                        })

            # Add the goal with its KPIs
            if kpi_list:
                added_topics[topic_name]['goals'].append({
                    'name': goal_name,
                    'kpis': kpi_list,
                    'is_from_db': False,
                    'goal_id': session_goal.get('id', ''),
                    'kpi_count': len(kpi_list),
                })
                added_topics[topic_name]['total_kpis'] += len(kpi_list)
            else:
                # Even if no KPIs found in mapping, still add the goal
                added_topics[topic_name]['goals'].append({
                    'name': goal_name,
                    'kpis': [],
                    'is_from_db': False,
                    'goal_id': session_goal.get('id', ''),
                    'kpi_count': 0,
                })

        # ===== CONVERT TO LIST =====
        grouped_goals_list = []
        for topic_name, topic_data in added_topics.items():
            # Sort goals alphabetically
            topic_data['goals'].sort(key=lambda x: x.get('name', ''))

            grouped_goals_list.append({
                'material_topic': topic_name,
                'goals': topic_data['goals'],
                'dot_color': topic_data['dot_color'],
                'icon': topic_data.get('icon', 'fa-tag'),
                'icon_class': topic_data.get('icon_class', 'default'),
                'count': len(topic_data['goals']),
                'total_kpis': topic_data['total_kpis'],
            })

        # Sort by topic name
        grouped_goals_list.sort(key=lambda x: x['material_topic'])

        # Calculate totals
        total_goals = sum(topic['count'] for topic in grouped_goals_list)
        total_kpis = sum(topic['total_kpis'] for topic in grouped_goals_list)

        context['grouped_goals'] = grouped_goals_list
        context['total_goals'] = total_goals
        context['total_topics'] = len(grouped_goals_list)
        context['total_kpis'] = total_kpis

        return context


# ===== ADD GOAL VIEW =====
class AddGoalView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            # ===== CHECK USER PERMISSIONS =====
            if not user_has_goal_management_permission(request.user):
                return JsonResponse({
                    'status': 'error',
                    'message': 'You do not have permission to add goals. Only ESG Heads and ESG Coordinators can add goals.'
                }, status=403)

            material_topic_name = request.POST.get('material_topic')
            goal_name = request.POST.get('goal_name')

            if not material_topic_name or not goal_name:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Please fill in all required fields.',
                }, status=400)


            # ===== CREATE/GET MATERIAL TOPIC =====
            material_topic, created = MaterialTopic.objects.get_or_create(
                name=material_topic_name,
                defaults={
                    'is_active': True,
                    'created_by': request.user,
                    'updated_by': request.user,
                }
            )

            # ===== CREATE/GET GOAL =====
            goal, created = Goal.objects.get_or_create(
                material_topic=material_topic,
                name=goal_name,
                defaults={
                    'is_active': True,
                    'created_by': request.user,
                    'updated_by': request.user,
                }
            )

            # ===== CREATE KPIs FROM MAPPING =====
            topic_data = MATERIAL_TOPICS_MAPPING.get(material_topic_name, {})
            goals_data = topic_data.get('goals', {})
            goal_metrics = goals_data.get(goal_name, {}).get('metrics', {})

            kpi_count = 0
            for metric_name, metric_info in goal_metrics.items():
                # Get keywords from mapping
                activity_keyword = metric_info.get('activity_keyword', '')
                source_keyword = metric_info.get('source_keyword', '')
                category_keyword = metric_info.get('category_keyword', '')
                unit = metric_info.get('unit', '')

                # ===== SMART KEYWORD INFERENCE (Fallback) =====
                name_lower = metric_name.lower()

                # For emission KPIs (tCO₂e) - ALWAYS clear source and activity
                if 'tco2e' in unit.lower() or 'tco2' in unit.lower():
                    activity_keyword = ''
                    source_keyword = ''
                    logger.info(f"Emission KPI detected: {metric_name} - clearing activity and source keywords")

                # For fuel consumption KPIs - infer activity from name
                elif not activity_keyword:
                    if 'diesel' in name_lower:
                        activity_keyword = 'Diesel'
                    elif 'lpg' in name_lower:
                        activity_keyword = 'LPG'
                    elif 'furnace' in name_lower and 'oil' in name_lower:
                        activity_keyword = 'Furnace Oil'
                    elif 'coal' in name_lower:
                        activity_keyword = 'Coal'
                    elif 'petrol' in name_lower:
                        activity_keyword = 'Petrol'
                    elif 'cng' in name_lower:
                        activity_keyword = 'CNG'
                    elif 'electricity' in name_lower:
                        activity_keyword = 'Purchased Electricity'
                    elif 'steam' in name_lower:
                        activity_keyword = 'Steam'
                    elif 'heat' in name_lower:
                        activity_keyword = 'Heat'
                    elif 'cooling' in name_lower:
                        activity_keyword = 'Cooling'
                    elif 'clinker' in name_lower:
                        activity_keyword = 'Clinker'
                    elif 'lime' in name_lower:
                        activity_keyword = 'Lime'
                    elif 'steel' in name_lower:
                        activity_keyword = 'Steel'
                    elif 'ammonia' in name_lower:
                        activity_keyword = 'Ammonia'
                    elif 'nitric acid' in name_lower:
                        activity_keyword = 'Nitric Acid'
                    elif 'refrigerant' in name_lower or 'leakage' in name_lower:
                        activity_keyword = 'HFC,R22,SF6,CO2'

                source_keyword = ''

                # Create or get KPI
                kpi, created = KPI.objects.get_or_create(
                    goal=goal,
                    name=metric_name,
                    defaults={
                        'unit': unit,
                        'is_active': True,
                        'baseline_value': 0,
                        'target_value': 0,
                        'activity_keyword': activity_keyword,
                        'source_keyword': source_keyword,
                        'category_keyword': category_keyword,
                        'created_by': request.user,
                        'updated_by': request.user,
                    }
                )

                if not created:
                    needs_update = False
                    if kpi.activity_keyword != activity_keyword:
                        kpi.activity_keyword = activity_keyword
                        needs_update = True
                    if kpi.source_keyword != source_keyword:
                        kpi.source_keyword = source_keyword
                        needs_update = True
                    if kpi.category_keyword != category_keyword:
                        kpi.category_keyword = category_keyword
                        needs_update = True
                    if kpi.unit != unit:
                        kpi.unit = unit
                        needs_update = True

                    if needs_update:
                        kpi.updated_by = request.user
                        kpi.save()
                        logger.info(f"Updated KPI: {metric_name} with keywords")
                else:
                    kpi_count += 1
                    logger.info(f"Created KPI: {metric_name}")

            # ===== SAVE TO SESSION =====
            goals = request.session.get('goals', [])
            
            # ✅ FIX: Initialize new_goal as None
            new_goal = None
            goal_exists = False
            
            for g in goals:
                if g.get('material_topic') == material_topic_name and (g.get('goal_name') == goal_name or g.get('name') == goal_name):
                    goal_exists = True
                    break

            if not goal_exists:
                new_goal = {
                    'id': str(uuid.uuid4())[:8],
                    'material_topic': material_topic_name,
                    'goal_name': goal_name,
                    'name': goal_name,
                    'last_updated': datetime.now().strftime('%d/%m/%Y'),
                    'dot_color': get_dot_color(material_topic_name),
                }
                goals.append(new_goal)
                request.session['goals'] = goals
                request.session.modified = True

            # ✅ FIX: Return appropriate response
            return JsonResponse({
                'status': 'success',
                'message': f'Goal "{goal_name}" added successfully! Created {kpi_count} KPI(s).',
                'goal': new_goal,  # Will be None if goal already existed
                'total_goals': len(goals)
            })

        except Exception as e:
            logger.error(f"Error adding goal: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)


# ===== DELETE GOAL VIEW =====

class DeleteGoalView(LoginRequiredMixin, View):
    def post(self, request, goal_id, *args, **kwargs):
        try:
            # ===== CHECK USER PERMISSIONS =====
            if not user_has_delete_permission(request.user):
                is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                if is_ajax:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'You do not have permission to delete goals.'
                    }, status=403)
                messages.error(request, 'You do not have permission to delete goals.')
                return redirect('goals:dashboard')

            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            deleted_name = None

            # ===== DELETE FROM DATABASE =====
            try:
                goal = Goal.objects.get(id=goal_id, is_active=True)
                deleted_name = goal.name
                goal.is_active = False
                goal.save()
                logger.info(f"Goal '{goal.name}' deactivated in database")
            except Goal.DoesNotExist:
                logger.warning(f"Goal with ID {goal_id} not found in database")
            except (ValueError, TypeError):
                logger.info(f"Goal ID {goal_id} is not a database ID, checking session")

            # ===== DELETE FROM SESSION =====
            goals = request.session.get('goals', [])
            goal_name_to_remove = None

            for g in goals:
                if g.get('id') == goal_id:
                    goal_name_to_remove = g.get('goal_name') or g.get('name')
                    if not deleted_name:
                        deleted_name = goal_name_to_remove
                    break

            goals = [g for g in goals if g.get('id') != goal_id]

            if goal_name_to_remove:
                goals = [g for g in goals if (g.get('goal_name') != goal_name_to_remove and g.get('name') != goal_name_to_remove)]

            request.session['goals'] = goals
            request.session.modified = True

            if is_ajax:
                return JsonResponse({
                    'status': 'success',
                    'message': f'Goal "{deleted_name or "Unknown"}" deleted successfully!'
                })

            messages.success(request, 'Goal deleted successfully!')
            return redirect('goals:dashboard')

        except Exception as e:
            logger.error(f"Error deleting goal: {str(e)}")
            if is_ajax:
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                }, status=500)
            messages.error(request, f'Error deleting goal: {str(e)}')
            return redirect('goals:dashboard')


# ===== DELETE TOPIC VIEW =====

class DeleteTopicView(LoginRequiredMixin, View):
    def post(self, request, topic, *args, **kwargs):
        try:
            # ===== CHECK USER PERMISSIONS =====
            if not user_has_delete_permission(request.user):
                is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
                if is_ajax:
                    return JsonResponse({
                        'status': 'error',
                        'message': 'You do not have permission to delete topics.'
                    }, status=403)
                messages.error(request, 'You do not have permission to delete topics.')
                return redirect('goals:dashboard')

            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            count = 0

            # ===== DELETE FROM DATABASE =====
            try:
                material_topic = MaterialTopic.objects.get(name=topic, is_active=True)
                goals = Goal.objects.filter(material_topic=material_topic, is_active=True)
                count = goals.count()
                for goal in goals:
                    goal.is_active = False
                    goal.save()
                logger.info(f"Deactivated {count} goals under topic '{topic}' in database")
            except MaterialTopic.DoesNotExist:
                logger.warning(f"Topic '{topic}' not found in database")

            # ===== DELETE FROM SESSION =====
            goals = request.session.get('goals', [])
            goals = [g for g in goals if g.get('material_topic') != topic]
            request.session['goals'] = goals
            request.session.modified = True

            if is_ajax:
                return JsonResponse({
                    'status': 'success',
                    'message': f'All goals under "{topic}" deleted successfully!'
                })

            messages.success(request, f'All goals under "{topic}" deleted successfully!')
            return redirect('goals:dashboard')

        except Exception as e:
            logger.error(f"Error deleting topic: {str(e)}")
            if is_ajax:
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                }, status=500)
            messages.error(request, f'Error deleting topic: {str(e)}')
            return redirect('goals:dashboard')


# ===== GOAL DETAIL VIEW =====

class GoalDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'goals/goal_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        material_topic = self.kwargs.get('material_topic')
        goal_name = self.request.GET.get('goal', '')

        # ===== GET PLANT FILTER FROM REQUEST =====
        selected_plant_id = self.request.GET.get('plant_id')
        if selected_plant_id:
            try:
                selected_plant_id = int(selected_plant_id)
            except (ValueError, TypeError):
                selected_plant_id = None

        # ===== GET PLANTS FROM ORGANIZATION APP =====
        all_plants = []
        try:
            from apps.organizations.models import Plant
            plants = Plant.objects.filter(is_active=True).order_by('name')
            all_plants = list(plants)
        except (ImportError, AttributeError) as e:
            logger.warning(f"Plant model not found: {e}")
            all_plants = []

        # ===== GET ALL TOPICS FROM MAPPING =====
        all_topics = sorted(list(MATERIAL_TOPICS_MAPPING.keys()))

        # ===== GET GOALS FROM DATABASE =====
        db_goals = Goal.objects.filter(
            material_topic__name=material_topic,
            material_topic__is_active=True,
            is_active=True
        ).select_related('material_topic')

        # ===== GET GOALS FROM SESSION =====
        session_goals = self.request.session.get('goals', [])
        session_goals_for_topic = []
        for g in session_goals:
            if g.get('material_topic', '').lower() == material_topic.lower():
                session_goals_for_topic.append(g)

        # ===== MERGE GOALS =====
        goals = []
        goal_names_in_db = set()

        # Add database goals first
        for db_goal in db_goals:
            db_kpis = db_goal.kpis.filter(is_active=True)
            kpi_list = []
            for kpi in db_kpis:
                current_value = kpi.get_current_value(
                    plant_id=selected_plant_id
                ) if hasattr(kpi, 'get_current_value') else 0
                plant_config = kpi.get_config_for_plant(selected_plant_id)
                kpi_list.append({
                    'name': kpi.name,
                    'unit': plant_config['unit'] or kpi.unit,
                    'kpi_id': kpi.id,
                    'current_value': current_value,
                    'target_value': float(plant_config['target_value']) if plant_config['target_value'] else 0,
                    'baseline_value': float(plant_config['baseline_value']) if plant_config['baseline_value'] else 0,
                    'baseline_year': plant_config['baseline_year'],
                    'target_year': plant_config['target_year'],
                    'target_reduction': float(plant_config['target_reduction']) if plant_config['target_reduction'] else 0,
                    'from_mapping': False,
                    'is_from_db': True,
                    'is_plant_specific': plant_config['is_plant_specific'],
                })

            goals.append({
                'name': db_goal.name,
                'material_topic': material_topic,
                'is_from_db': True,
                'is_from_mapping': False,
                'kpi_count': len(kpi_list),
                'kpis': kpi_list,
                'goal_id': str(db_goal.id),
            })
            goal_names_in_db.add(db_goal.name)

        # Add session goals
        for session_goal in session_goals_for_topic:
            session_name = session_goal.get('goal_name') or session_goal.get('name', '')

            if session_name and session_name not in goal_names_in_db:
                kpi_list = []
                if material_topic in MATERIAL_TOPICS_MAPPING:
                    topic_data = MATERIAL_TOPICS_MAPPING[material_topic]
                    if session_name in topic_data.get('goals', {}):
                        metrics = topic_data['goals'][session_name].get('metrics', {})
                        for metric_name, metric_info in metrics.items():
                            current_value = 0
                            kpi_id = None
                            try:
                                kpi = KPI.objects.get(
                                    goal__material_topic__name=material_topic,
                                    goal__name=session_name,
                                    name=metric_name,
                                    is_active=True
                                )
                                current_value = kpi.get_current_value(
                                    plant_id=selected_plant_id
                                )
                                kpi_id = kpi.id
                            except KPI.DoesNotExist:
                                pass

                            kpi_list.append({
                                'name': metric_name,
                                'unit': metric_info.get('unit', ''),
                                'kpi_id': kpi_id,
                                'current_value': current_value,
                                'from_mapping': True,
                            })

                goals.append({
                    'name': session_name,
                    'material_topic': material_topic,
                    'is_from_db': False,
                    'is_from_mapping': False,
                    'kpi_count': len(kpi_list),
                    'kpis': kpi_list,
                    'goal_id': session_goal.get('id', ''),
                })
                goal_names_in_db.add(session_name)

        # Set selected goal
        selected_goal_name = goal_name
        if not selected_goal_name and goals:
            selected_goal_name = goals[0]['name']

        # ===== GET METRICS/KPIs FOR SELECTED GOAL =====
        metrics_dict = {}
        active_unit = ''
        per_kpi_configs = {}

        # Key used to namespace per-KPI config by plant selection ('all' when no plant chosen)
        plant_key = selected_plant_id if selected_plant_id else 'all'

        if selected_goal_name:
            # First try to get from database
            try:
                goal = Goal.objects.get(
                    material_topic__name=material_topic,
                    name=selected_goal_name,
                    is_active=True
                )
                db_kpis = goal.kpis.filter(is_active=True)

                for kpi in db_kpis:
                    current_value = kpi.get_current_value(
                        plant_id=selected_plant_id
                    ) if hasattr(kpi, 'get_current_value') else 0

                    # ===== RESOLVE PLANT-SPECIFIC (OR AGGREGATE) CONFIG =====
                    plant_config = kpi.get_config_for_plant(selected_plant_id)

                    metrics_dict[kpi.name] = {
                        'current': current_value,
                        'projected': 0,
                        'target': float(plant_config['target_value']) if plant_config['target_value'] else 0,
                        'unit': plant_config['unit'] or kpi.unit,
                        'kpi_id': kpi.id,
                        'baseline_value': float(plant_config['baseline_value']) if plant_config['baseline_value'] else 0,
                        'target_value': float(plant_config['target_value']) if plant_config['target_value'] else 0,
                        'baseline_year': plant_config['baseline_year'] or '',
                        'target_year': plant_config['target_year'] or '',
                        'target_reduction': float(plant_config['target_reduction']) if plant_config['target_reduction'] else 0,
                        'is_from_db': True,
                        'is_plant_specific': plant_config['is_plant_specific'],
                    }

                    # Build per-kpi config from database, namespaced by plant
                    config_key = f"{material_topic}_{selected_goal_name}_{kpi.name}_{plant_key}"
                    per_kpi_configs[config_key] = {
                        'baseline_year': plant_config['baseline_year'] or '',
                        'baseline_value': str(plant_config['baseline_value']) if plant_config['baseline_value'] else '',
                        'target_year': plant_config['target_year'] or '',
                        'target_reduction': str(plant_config['target_reduction']) if plant_config['target_reduction'] else '',
                        'target_value': str(plant_config['target_value']) if plant_config['target_value'] else '',
                        'unit': plant_config['unit'] or kpi.unit or '',
                        'selected_goal': selected_goal_name,
                        'selected_kpi': kpi.name,
                        'kpi_id': kpi.id,
                        'plant_id': selected_plant_id,
                    }

                if db_kpis.exists():
                    first_kpi = db_kpis.first()
                    active_unit = first_kpi.unit

            except Goal.DoesNotExist:
                # Fallback to MATERIAL_TOPICS_MAPPING
                metrics_list = get_metrics_for_goal(material_topic, selected_goal_name)
                for metric in metrics_list:
                    # Try to find if KPI exists in database
                    kpi_id = None
                    try:
                        kpi = KPI.objects.get(
                            goal__material_topic__name=material_topic,
                            goal__name=selected_goal_name,
                            name=metric.get('name', ''),
                            is_active=True
                        )
                        kpi_id = kpi.id
                    except KPI.DoesNotExist:
                        pass

                    metrics_dict[metric.get('name', 'Unknown')] = {
                        'current': 0,
                        'projected': 0,
                        'target': 0,
                        'unit': metric.get('unit', ''),
                        'kpi_id': kpi_id,
                        'baseline_value': 0,
                        'target_value': 0,
                        'baseline_year': '',
                        'target_year': '',
                        'target_reduction': 0,
                        'is_from_db': False,
                    }

                if metrics_list and len(metrics_list) > 0:
                    active_unit = metrics_list[0].get('unit', '')

        # If no metrics found, use mapping data
        if not metrics_dict and selected_goal_name:
            if material_topic in MATERIAL_TOPICS_MAPPING:
                topic_data = MATERIAL_TOPICS_MAPPING[material_topic]
                goal_data = topic_data.get('goals', {}).get(selected_goal_name, {})
                metrics_from_mapping = goal_data.get('metrics', {})
                for metric_name, metric_info in metrics_from_mapping.items():
                    # Try to find if KPI exists in database
                    kpi_id = None
                    try:
                        kpi = KPI.objects.get(
                            goal__material_topic__name=material_topic,
                            goal__name=selected_goal_name,
                            name=metric_name,
                            is_active=True
                        )
                        kpi_id = kpi.id
                    except KPI.DoesNotExist:
                        pass

                    metrics_dict[metric_name] = {
                        'current': 0,
                        'projected': 0,
                        'target': 0,
                        'unit': metric_info.get('unit', ''),
                        'kpi_id': kpi_id,
                        'baseline_value': 0,
                        'target_value': 0,
                        'baseline_year': '',
                        'target_year': '',
                        'target_reduction': 0,
                        'is_from_db': False,
                    }
                if metrics_from_mapping:
                    active_unit = list(metrics_from_mapping.values())[0].get('unit', '')

        # ===== MERGE SESSION CONFIGS WITH DATABASE CONFIGS =====
        session_configs = self.request.session.get('goal_configs', {})

        # Database configs take precedence over session configs
        for key, value in per_kpi_configs.items():
            session_configs[key] = value

        # Save merged configs back to session
        self.request.session['goal_configs'] = session_configs
        self.request.session.modified = True

        # ===== GET DEFAULT CONFIG (first KPI, for current plant) =====
        default_config = {}
        if selected_goal_name and metrics_dict:
            first_kpi_name = list(metrics_dict.keys())[0] if metrics_dict else None
            if first_kpi_name:
                config_key = f"{material_topic}_{selected_goal_name}_{first_kpi_name}_{plant_key}"
                default_config = session_configs.get(config_key, {})

        # ===== PREPARE METRICS WITH THEIR CONFIGS (plant-namespaced) =====
        metrics_with_config = {}
        for metric_name, metric_data in metrics_dict.items():
            config_key = f"{material_topic}_{selected_goal_name}_{metric_name}_{plant_key}"
            metrics_with_config[metric_name] = {
                **metric_data,
                'config': session_configs.get(config_key, {})
            }

        # Add topics from database
        db_topics = MaterialTopic.objects.filter(is_active=True).values_list('name', flat=True)
        all_topics.extend(list(db_topics))
        all_topics = sorted(list(set(all_topics)))

        # ===== BUILD PLANT LIST FOR DROPDOWN =====
        plant_list = []
        for plant in all_plants:
            plant_list.append({
                'id': plant.id,
                'name': plant.name,
                'selected': selected_plant_id == plant.id
            })

        # JSON data for JavaScript
        goals_json = json.dumps(goals)
        metrics_json = json.dumps(metrics_with_config)
        per_kpi_configs_json = json.dumps(session_configs)
        plants_json = json.dumps(plant_list)

        context.update({
            'material_topic': material_topic,
            'goals': goals,
            'goals_json': goals_json,
            'metrics': metrics_with_config,
            'metrics_json': metrics_json,
            'config': default_config,
            'per_kpi_configs': session_configs,
            'per_kpi_configs_json': per_kpi_configs_json,
            'all_material_topics': all_topics,
            'total_metrics': len(metrics_dict),
            'total_goals': len(goals),
            'selected_goal': selected_goal_name,
            'active_unit': active_unit,
            # Plant filter data
            'plants': plant_list,
            'selected_plant_id': selected_plant_id,
            'plants_json': plants_json,
        })

        return context


# ===== GOAL CONFIG UPDATE VIEW =====

class GoalConfigUpdateView(LoginRequiredMixin, View):
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        try:
            material_topic = self.kwargs.get('material_topic')

            # Get data from POST or JSON
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST

            goal_name = data.get('selected_goal', '')
            kpi_name = data.get('kpi_name', '')
            kpi_id = data.get('kpi_id', '')
            plant_id_raw = data.get('plant_id', '')

            baseline_year = data.get('baseline_year', '')
            baseline_value = data.get('baseline_value', '')
            target_year = data.get('target_year', '')
            target_reduction = data.get('target_reduction', '')
            target_value = data.get('target_value', '')
            unit = data.get('unit', '')

            # Log the received data for debugging
            logger.info("=" * 50)
            logger.info(f"Received POST data: {data}")
            logger.info(f"goal_name: {goal_name}")
            logger.info(f"kpi_name: {kpi_name}")
            logger.info(f"kpi_id: {kpi_id}")
            logger.info(f"plant_id: {plant_id_raw}")
            logger.info("=" * 50)

            # VALIDATION
            if not goal_name:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Goal name is required'
                }, status=400)

            if not kpi_name and not kpi_id:
                return JsonResponse({
                    'status': 'error',
                    'message': 'KPI name or ID is required'
                }, status=400)

            # ===== NORMALIZE plant_id =====
            try:
                plant_id = normalize_plant_id(plant_id_raw)
            except (ValueError, TypeError):
                return JsonResponse({
                    'status': 'error',
                    'message': 'Invalid plant_id'
                }, status=400)

            # Get or create the goal
            goal = ensure_goal_and_kpis_exist(material_topic, goal_name, request.user)

            if goal is None:
                return JsonResponse({
                    'status': 'error',
                    'message': f'Could not find or create goal: {goal_name}'
                }, status=404)

            def to_decimal(val):
                if val in (None, ''):
                    return None
                try:
                    return Decimal(str(val))
                except (InvalidOperation, ValueError, TypeError):
                    logger.warning(f"Could not convert '{val}' to Decimal, skipping")
                    return None

            baseline_value_dec = to_decimal(baseline_value)
            target_reduction_dec = to_decimal(target_reduction)
            target_value_dec = to_decimal(target_value)

            # FIND THE SPECIFIC KPI
            kpi = None
            try:
                if kpi_id:
                    kpi = KPI.objects.get(id=kpi_id, goal=goal, is_active=True)
                    kpi_name = kpi.name
                elif kpi_name:
                    kpi = KPI.objects.get(goal=goal, name__iexact=kpi_name, is_active=True)

                if not kpi:
                    return JsonResponse({
                        'status': 'error',
                        'message': f'KPI not found: {kpi_name or kpi_id}'
                    }, status=404)

                if plant_id:
                    # ===== SAVE / UPDATE PLANT-SPECIFIC TARGET =====
                    plant_target, _ = KPIPlantTarget.objects.get_or_create(
                        kpi=kpi,
                        plant_id=plant_id,
                        defaults={
                            'created_by': request.user,
                            'updated_by': request.user,
                        }
                    )
                    if baseline_year:
                        plant_target.baseline_year = baseline_year
                    if baseline_value_dec is not None:
                        plant_target.baseline_value = baseline_value_dec
                    if target_year:
                        plant_target.target_year = target_year
                    if target_reduction_dec is not None:
                        plant_target.target_reduction = target_reduction_dec
                    if target_value_dec is not None:
                        plant_target.target_value = target_value_dec
                    if unit:
                        plant_target.unit = unit
                    plant_target.updated_by = request.user
                    plant_target.save()

                    logger.info(
                        f"Updated plant-specific target for KPI '{kpi.name}' "
                        f"(ID: {kpi.id}) / Plant {plant_id} for goal: {goal_name}"
                    )

                    response_data = {
                        'kpi_id': kpi.id,
                        'kpi_name': kpi.name,
                        'goal': goal_name,
                        'topic': material_topic,
                        'plant_id': plant_id,
                        'baseline_year': plant_target.baseline_year,
                        'baseline_value': str(plant_target.baseline_value) if plant_target.baseline_value else '',
                        'target_year': plant_target.target_year,
                        'target_reduction': str(plant_target.target_reduction) if plant_target.target_reduction else '',
                        'target_value': str(plant_target.target_value) if plant_target.target_value else '',
                        'unit': plant_target.unit or kpi.unit,
                    }
                    config_key = f"{material_topic}_{goal_name}_{kpi.name}_{plant_id}"
                    success_message = f'Configuration saved for KPI: {kpi.name} (Plant ID {plant_id})'

                else:
                    # ===== SAVE / UPDATE AGGREGATE ("All Plants") TARGET =====
                    if baseline_year:
                        kpi.baseline_year = baseline_year
                    if baseline_value_dec is not None:
                        kpi.baseline_value = baseline_value_dec
                    if target_year:
                        kpi.target_year = target_year
                    if target_reduction_dec is not None:
                        kpi.target_reduction = target_reduction_dec
                    if target_value_dec is not None:
                        kpi.target_value = target_value_dec
                    if unit:
                        kpi.unit = unit
                    kpi.updated_by = request.user
                    kpi.save()

                    logger.info(f"Updated aggregate KPI '{kpi.name}' (ID: {kpi.id}) for goal: {goal_name}")

                    response_data = {
                        'kpi_id': kpi.id,
                        'kpi_name': kpi.name,
                        'goal': goal_name,
                        'topic': material_topic,
                        'plant_id': None,
                        'baseline_year': kpi.baseline_year,
                        'baseline_value': str(kpi.baseline_value) if kpi.baseline_value else '',
                        'target_year': kpi.target_year,
                        'target_reduction': str(kpi.target_reduction) if kpi.target_reduction else '',
                        'target_value': str(kpi.target_value) if kpi.target_value else '',
                        'unit': kpi.unit,
                    }
                    config_key = f"{material_topic}_{goal_name}_{kpi.name}_all"
                    success_message = f'Configuration saved for KPI: {kpi.name} (All Plants)'

                # ===== UPDATE SESSION CONFIG (namespaced by plant) =====
                configs = request.session.get('goal_configs', {})
                configs[config_key] = {
                    **response_data,
                    'selected_goal': goal_name,
                    'selected_kpi': kpi.name,
                }
                request.session['goal_configs'] = configs
                request.session.modified = True

                return JsonResponse({
                    'status': 'success',
                    'message': success_message,
                    'data': response_data
                })

            except KPI.DoesNotExist:
                return JsonResponse({
                    'status': 'error',
                    'message': f'KPI "{kpi_name}" not found for goal "{goal_name}"'
                }, status=404)

        except Exception as e:
            logger.error(f"Error saving config: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)


# ===== GOAL METRICS API VIEW =====

class GoalMetricsAPIView(LoginRequiredMixin, View):
    def get(self, request, *args, **kwargs):
        try:
            material_topic = self.kwargs.get('material_topic')
            goal_name = request.GET.get('goal', '')

            metrics = get_metrics_for_goal(material_topic, goal_name)

            metrics_data = []
            for metric in metrics:
                metrics_data.append({
                    'name': metric['name'],
                    'current': 0,
                    'projected': 0,
                    'target': 0,
                    'unit': metric.get('unit', ''),
                })

            return JsonResponse({
                'status': 'success',
                'data': metrics_data
            })

        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)


# ===== KPI CURRENT VALUE API VIEW =====

# apps/goals/views.py

class KPICurrentValueAPIView(LoginRequiredMixin, View):
    """
    API to get current values for KPIs from EmissionTransaction,
    scored against a plant-specific baseline/target when a plant is selected.
    """

    def get(self, request, *args, **kwargs):
        try:
            # Get parameters
            kpi_id = request.GET.get('kpi_id')
            metric_name = request.GET.get('metric_name')
            topic = request.GET.get('topic')
            goal_name = request.GET.get('goal')
            plant_id_raw = request.GET.get('plant_id')
            
            # Log the request
            logger.info(f"=== KPI Current Value Request ===")
            logger.info(f"metric_name: {metric_name}")
            logger.info(f"plant_id_raw: {plant_id_raw}")
            
            # Find KPI
            kpi = None

            if kpi_id:
                try:
                    kpi = KPI.objects.get(id=kpi_id, is_active=True)
                except KPI.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'message': 'KPI not found'
                    }, status=404)
            elif metric_name and topic and goal_name:
                try:
                    kpi = KPI.objects.get(
                        name__iexact=metric_name,
                        goal__name__iexact=goal_name,
                        goal__material_topic__name__iexact=topic,
                        is_active=True
                    )
                except KPI.DoesNotExist:
                    try:
                        kpi = KPI.objects.get(
                            name__iexact=metric_name,
                            is_active=True
                        )
                    except KPI.DoesNotExist:
                        return JsonResponse({
                            'success': False,
                            'message': f'KPI "{metric_name}" not found'
                        }, status=404)
                except KPI.MultipleObjectsReturned:
                    kpi = KPI.objects.filter(
                        name__iexact=metric_name,
                        goal__name__iexact=goal_name,
                        goal__material_topic__name__iexact=topic,
                        is_active=True
                    ).first()
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Please provide either kpi_id or (metric_name, topic, goal)'
                }, status=400)

            if not kpi:
                return JsonResponse({
                    'success': False,
                    'message': 'KPI not found'
                }, status=404)

            # Get context filters from request
            company_id = request.GET.get('company_id')
            financial_year_id = request.GET.get('financial_year_id')
            financial_month_id = request.GET.get('financial_month_id')
            assignment_id = request.GET.get('assignment_id')

            # Normalize plant_id
            plant_id = None
            if plant_id_raw and plant_id_raw not in ('null', 'undefined', 'None', ''):
                try:
                    plant_id = int(plant_id_raw)
                except (ValueError, TypeError):
                    return JsonResponse({
                        'success': False,
                        'message': 'Invalid plant_id'
                    }, status=400)
            
            logger.info(f"Normalized plant_id: {plant_id}")
            
            # ===== RESOLVE PLANT-SPECIFIC (OR AGGREGATE) BASELINE/TARGET =====
            plant_config = kpi.get_config_for_plant(plant_id)

            # ✅ FIX: Get current value with ALL filters, but don't filter by status
            # Only filter by status if specifically requested
            statuses = request.GET.get('statuses')
            if statuses:
                statuses = statuses.split(',')
            else:
                # ✅ Include all statuses by default (DRAFT, SUBMITTED, APPROVED, REJECTED)
                statuses = None  # None means include ALL statuses
            
            current_value = kpi.get_current_value(
                company_id=company_id,
                plant_id=plant_id,
                financial_year_id=financial_year_id,
                financial_month_id=financial_month_id,
                assignment_id=assignment_id,
                statuses=statuses  # None = all statuses
            )

            # Log the result
            logger.info(f"Current value for {kpi.name} (plant {plant_id}): {current_value}")

            progress = kpi.get_progress_percentage(
                company_id=company_id,
                plant_id=plant_id,
                financial_year_id=financial_year_id,
                financial_month_id=financial_month_id,
                assignment_id=assignment_id,
                baseline_value=plant_config['baseline_value'],
                target_value=plant_config['target_value'],
            )

            status_val = kpi.get_status(
                company_id=company_id,
                plant_id=plant_id,
                financial_year_id=financial_year_id,
                financial_month_id=financial_month_id,
                assignment_id=assignment_id,
                baseline_value=plant_config['baseline_value'],
                target_value=plant_config['target_value'],
            )

            return JsonResponse({
                'success': True,
                'data': {
                    'kpi_id': kpi.id,
                    'kpi_name': kpi.name,
                    'goal_name': kpi.goal.name if kpi.goal else goal_name,
                    'topic_name': kpi.goal.material_topic.name if kpi.goal and kpi.goal.material_topic else topic,
                    'unit': plant_config['unit'] or kpi.unit,
                    'current_value': current_value,
                    'baseline_value': float(plant_config['baseline_value']) if plant_config['baseline_value'] else 0,
                    'target_value': float(plant_config['target_value']) if plant_config['target_value'] else 0,
                    'baseline_year': plant_config['baseline_year'] or '',
                    'target_year': plant_config['target_year'] or '',
                    'target_reduction': float(plant_config['target_reduction']) if plant_config['target_reduction'] else 0,
                    'is_plant_specific': plant_config['is_plant_specific'],
                    'progress': progress if progress is not None else 0,
                    'status': status_val or 'Not Started',
                }
            })

        except Exception as e:
            logger.error(f"Error fetching KPI current value: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': f'Error fetching current value: {str(e)}'
            }, status=500)

# ===== KPI CONFIG API VIEW =====

class KPIConfigAPIView(LoginRequiredMixin, View):
    """
    API to get KPI configuration (baseline, target, unit) for a specific plant.
    Returns plant-specific config if it exists, otherwise falls back to aggregate config.
    """
    
    def get(self, request, *args, **kwargs):
        try:
            # Get parameters
            metric_name = request.GET.get('metric_name')
            topic = request.GET.get('topic')
            goal_name = request.GET.get('goal')
            plant_id = request.GET.get('plant_id')
            
            # Validate required parameters
            if not metric_name:
                return JsonResponse({
                    'success': False,
                    'message': 'metric_name is required'
                }, status=400)
            
            if not topic or not goal_name:
                return JsonResponse({
                    'success': False,
                    'message': 'topic and goal are required'
                }, status=400)
            
            # Normalize plant_id
            try:
                plant_id = normalize_plant_id(plant_id)
            except (ValueError, TypeError):
                return JsonResponse({
                    'success': False,
                    'message': 'Invalid plant_id'
                }, status=400)
            
            # Find the KPI
            kpi = None
            try:
                kpi = KPI.objects.get(
                    name__iexact=metric_name,
                    goal__name__iexact=goal_name,
                    goal__material_topic__name__iexact=topic,
                    is_active=True
                )
            except KPI.DoesNotExist:
                # Try to find KPI by name only (fallback)
                try:
                    kpi = KPI.objects.get(
                        name__iexact=metric_name,
                        is_active=True
                    )
                except KPI.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'message': f'KPI "{metric_name}" not found'
                    }, status=404)
            except KPI.MultipleObjectsReturned:
                # If multiple found, get the first one
                kpi = KPI.objects.filter(
                    name__iexact=metric_name,
                    goal__name__iexact=goal_name,
                    goal__material_topic__name__iexact=topic,
                    is_active=True
                ).first()
            
            if not kpi:
                return JsonResponse({
                    'success': False,
                    'message': 'KPI not found'
                }, status=404)
            
            # Get plant-specific or aggregate config
            plant_config = kpi.get_config_for_plant(plant_id)
            
            # Build the config key for session storage
            plant_key = plant_id if plant_id else 'all'
            config_key = f"{topic}_{goal_name}_{kpi.name}_{plant_key}"
            
            return JsonResponse({
                'success': True,
                'config': {
                    'baseline_year': plant_config.get('baseline_year', ''),
                    'baseline_value': str(plant_config.get('baseline_value', 0)),
                    'target_year': plant_config.get('target_year', ''),
                    'target_reduction': str(plant_config.get('target_reduction', 0)),
                    'target_value': str(plant_config.get('target_value', 0)),
                    'unit': plant_config.get('unit', kpi.unit),
                    'kpi_id': kpi.id,
                    'plant_id': plant_id,
                    'is_plant_specific': plant_config.get('is_plant_specific', False),
                }
            })
            
        except Exception as e:
            logger.error(f"Error fetching KPI config: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': f'Error fetching config: {str(e)}'
            }, status=500)


# ===== INITIATIVE LIST VIEW =====

class InitiativeListView(LoginRequiredMixin, TemplateView):
    template_name = 'goals/initiative_list.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get initiatives from session
        session_initiatives = self.request.session.get('initiatives', [])
        if session_initiatives is None:
            session_initiatives = []
            self.request.session['initiatives'] = []
            self.request.session.modified = True

        # Get filter parameters
        search = self.request.GET.get('search', '')
        status_filter = self.request.GET.get('status', '')
        plant_filter = self.request.GET.get('plant', '')
        selected_topic = self.request.GET.get('topic', '')
        selected_goal = self.request.GET.get('goal', '')
        selected_kpi = self.request.GET.get('kpi', '')

        # Calculate TOTAL before filtering
        total_all_initiatives = len(session_initiatives)

        # Filter initiatives
        filtered_initiatives = session_initiatives.copy()

        if search:
            filtered_initiatives = [
                i for i in filtered_initiatives
                if search.lower() in i.get('name', '').lower()
                or search.lower() in i.get('plant', '').lower()
                or search.lower() in i.get('assigned_to', '').lower()
                or search.lower() in i.get('kpi', '').lower()
            ]

        if status_filter:
            filtered_initiatives = [
                i for i in filtered_initiatives
                if i.get('status', '').lower() == status_filter.lower()
            ]

        if plant_filter:
            filtered_initiatives = [
                i for i in filtered_initiatives
                if i.get('plant', '').lower() == plant_filter.lower()
            ]

        if selected_topic:
            filtered_initiatives = [
                i for i in filtered_initiatives
                if selected_topic.lower() in i.get('topic', '').lower()
            ]

        if selected_goal:
            filtered_initiatives = [
                i for i in filtered_initiatives
                if selected_goal.lower() in i.get('goal', '').lower()
            ]

        if selected_kpi:
            filtered_initiatives = [
                i for i in filtered_initiatives
                if selected_kpi.lower() in i.get('kpi', '').lower()
            ]

        # ===== GROUP BY KPI =====
        grouped_initiatives = []
        topic_map = {}

        for initiative in filtered_initiatives:
            topic = initiative.get('topic', 'Uncategorized')
            kpi = initiative.get('kpi', 'Uncategorized KPI')
            goal = initiative.get('goal', 'Uncategorized Goal')
            status = initiative.get('status', '')

            if topic not in topic_map:
                topic_map[topic] = {
                    'material_topic': topic,
                    'icon': get_topic_icon(topic),
                    'icon_class': get_topic_icon_class(topic),
                    'kpis': {},
                    'total_initiatives': 0
                }

            # Group by KPI
            if kpi not in topic_map[topic]['kpis']:
                topic_map[topic]['kpis'][kpi] = {
                    'kpi_name': kpi,
                    'kpi_unit': initiative.get('kpi_unit', ''),
                    'goal_name': goal,
                    'initiatives': [],
                    'total_count': 0,
                    'in_progress_count': 0,
                    'completed_count': 0,
                    'planning_count': 0
                }

            # Add initiative and update counts
            topic_map[topic]['kpis'][kpi]['initiatives'].append(initiative)
            topic_map[topic]['kpis'][kpi]['total_count'] += 1

            # Update status counts
            if status == 'In Progress':
                topic_map[topic]['kpis'][kpi]['in_progress_count'] += 1
            elif status == 'Completed':
                topic_map[topic]['kpis'][kpi]['completed_count'] += 1
            elif status == 'Planning':
                topic_map[topic]['kpis'][kpi]['planning_count'] += 1

            topic_map[topic]['total_initiatives'] += 1

        # Convert to list
        for topic, data in topic_map.items():
            grouped_initiatives.append({
                'material_topic': data['material_topic'],
                'icon': data['icon'],
                'icon_class': data['icon_class'],
                'total_initiatives': data['total_initiatives'],
                'kpis': list(data['kpis'].values())
            })

        # Get unique data for dropdowns
        all_plants = sorted(set([i.get('plant', '') for i in session_initiatives if i.get('plant')]))
        if not all_plants:
            all_plants = [
                'Plant A - Mumbai',
                'Plant B - Pune',
                'Plant C - Chennai',
                'Plant D - Bangalore',
                'Plant E - Hyderabad',
                'Plant F - Delhi'
            ]

        all_statuses = ['Planning', 'In Progress', 'Completed', 'On Hold']

        # Calculate stats
        total_filtered = len(filtered_initiatives)
        in_progress = len([i for i in filtered_initiatives if i.get('status') == 'In Progress'])
        completed = len([i for i in filtered_initiatives if i.get('status') == 'Completed'])
        planning = len([i for i in filtered_initiatives if i.get('status') == 'Planning'])

        # Get metrics for the selected goal (for modal)
        goal_metrics = []
        has_metrics = False

        if selected_topic and selected_goal:
            goal_metrics = get_metrics_for_goal(selected_topic, selected_goal)
            has_metrics = len(goal_metrics) > 0

        context.update({
            'grouped_initiatives': grouped_initiatives,
            'all_plants': all_plants,
            'all_statuses': all_statuses,
            'search_query': search,
            'selected_status': status_filter,
            'selected_plant': plant_filter,
            'selected_topic': selected_topic,
            'selected_goal': selected_goal,
            'selected_kpi': selected_kpi,
            'total_all_initiatives': total_all_initiatives,
            'total_initiatives': total_filtered,
            'in_progress_count': in_progress,
            'completed_count': completed,
            'planning_count': planning,
            'goal_metrics': goal_metrics,
            'has_metrics': has_metrics,
        })

        return context


# ===== INITIATIVE CREATE VIEW =====

class InitiativeCreateView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

            # Get form data
            initiative_name = request.POST.get('initiative_name')
            kpi = request.POST.get('kpi')
            kpi_unit = request.POST.get('kpi_unit', '')
            plant = request.POST.get('plant', 'Default Plant')
            assigned_to = request.POST.get('assigned_to')
            due_date = request.POST.get('due_date')
            description = request.POST.get('description', '')
            selected_topic = request.POST.get('selected_topic', '')
            selected_goal = request.POST.get('selected_goal', '')

            # Validate required fields
            required_fields = {
                'initiative_name': initiative_name,
                'kpi': kpi,
                'assigned_to': assigned_to,
                'due_date': due_date,
            }

            missing_fields = [field for field, value in required_fields.items() if not value]

            if missing_fields:
                error_message = f"Please fill in all required fields: {', '.join(missing_fields)}"
                if is_ajax:
                    return JsonResponse({
                        'success': False,
                        'message': error_message,
                        'errors': {field: ['This field is required.'] for field in missing_fields}
                    }, status=400)
                else:
                    messages.error(request, error_message)
                    return render(request, 'goals/initiative_list.html')

            # Get existing initiatives from session
            initiatives = request.session.get('initiatives', [])
            if initiatives is None:
                initiatives = []

            # Generate unique ID
            initiative_id = len(initiatives) + 1
            while any(i.get('id') == initiative_id for i in initiatives):
                initiative_id += 1

            # Create new initiative
            new_initiative = {
                'id': initiative_id,
                'name': initiative_name,
                'kpi': kpi,
                'kpi_unit': kpi_unit,
                'plant': plant,
                'assigned_to': assigned_to,
                'due_date': due_date,
                'target_date': datetime.strptime(due_date, '%Y-%m-%d').strftime('%b %Y') if due_date else '',
                'description': description,
                'status': 'Planning',
                'priority': 'Medium',
                'start_date': datetime.now().strftime('%b %Y'),
                'current_value': 0,
                'target_value': 100,
                'unit': kpi_unit,
                'progress': 0,
                'metric_description': description[:50] if description else kpi,
                'created_at': datetime.now().strftime('%d/%m/%Y'),
                'topic': selected_topic,
                'goal': selected_goal,
            }

            # Add to session
            initiatives.append(new_initiative)
            request.session['initiatives'] = initiatives
            request.session.modified = True
            request.session.save()

            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'message': f'Initiative "{initiative_name}" added successfully!',
                    'initiative': new_initiative,
                    'total_initiatives': len(initiatives)
                })
            else:
                messages.success(request, f'Initiative "{initiative_name}" added successfully!')
                redirect_url = reverse('goals:initiative_list')
                params = []
                if selected_topic:
                    params.append(f'topic={selected_topic}')
                if selected_goal:
                    params.append(f'goal={selected_goal}')

                if params:
                    redirect_url += '?' + '&'.join(params)

                return redirect(redirect_url)

        except Exception as e:
            logger.error(f"Error creating initiative: {str(e)}")
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'message': f'Error creating initiative: {str(e)}'
                }, status=500)
            else:
                messages.error(request, f'Error creating initiative: {str(e)}')
                return render(request, 'goals/initiative_list.html')


# ===== INITIATIVE DELETE VIEW =====

class InitiativeDeleteView(LoginRequiredMixin, View):
    def post(self, request, initiative_id, *args, **kwargs):
        try:
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

            initiatives = request.session.get('initiatives', [])

            # Find and remove the initiative
            initiative_to_delete = None
            for i in initiatives:
                if i.get('id') == int(initiative_id):
                    initiative_to_delete = i
                    break

            if initiative_to_delete:
                initiatives = [i for i in initiatives if i.get('id') != int(initiative_id)]
                request.session['initiatives'] = initiatives
                request.session.modified = True
                request.session.save()

                if is_ajax:
                    return JsonResponse({
                        'success': True,
                        'message': f'Initiative "{initiative_to_delete.get("name")}" deleted successfully!'
                    })
                else:
                    messages.success(request, f'Initiative "{initiative_to_delete.get("name")}" deleted successfully!')
            else:
                if is_ajax:
                    return JsonResponse({
                        'success': False,
                        'message': 'Initiative not found.'
                    }, status=404)
                else:
                    messages.error(request, 'Initiative not found.')

            return redirect('goals:initiative_list')

        except Exception as e:
            logger.error(f"Error deleting initiative: {str(e)}")
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'message': f'Error deleting initiative: {str(e)}'
                }, status=500)
            else:
                messages.error(request, f'Error deleting initiative: {str(e)}')
                return redirect('goals:initiative_list')


# ===== CLEAR INITIATIVES VIEW =====

class ClearInitiativesView(LoginRequiredMixin, View):
    def get(self, request):
        request.session['initiatives'] = []
        request.session.modified = True
        messages.success(request, 'All initiatives cleared from session!')
        return redirect('goals:initiative_list')


# ===== TEST VIEW =====

class TestView(View):
    def get(self, request):
        return JsonResponse({'message': 'Test view is working!'})