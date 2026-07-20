# apps/goals/views.py

from django.views.generic import TemplateView
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import redirect, reverse, render
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
import uuid
from datetime import datetime
import json
import logging

logger = logging.getLogger(__name__)


# ===== COMPLETE MAPPING OF ALL MATERIAL TOPICS, GOALS, METRICS, AND UNITS =====
MATERIAL_TOPICS_MAPPING = {
    'Stationary Combustion': {
        'goals': {
            'Reduce Fuel Consumption': {
                'metrics': {
                    'Fuel Consumed': {'unit': 'Litres (L), kg, m³'}
                }
            },
            'Lower GHG Emissions': {
                'metrics': {
                    'Scope 1 Emissions': {'unit': 'tCO₂e'}
                }
            },
            'Improve Efficiency': {
                'metrics': {
                    'Fuel Intensity': {'unit': 'L/unit, kg/unit'}
                }
            }
        }
    },
    'Mobile Combustion': {
        'goals': {
            'Reduce Fuel Usage': {
                'metrics': {
                    'Fuel Consumed': {'unit': 'Litres (L)'}
                }
            },
            'Improve Fleet Efficiency': {
                'metrics': {
                    'Fuel Efficiency': {'unit': 'km/L'}
                }
            },
            'Reduce Emissions': {
                'metrics': {
                    'Scope 1 Emissions': {'unit': 'tCO₂e'}
                }
            }
        }
    },
    'Process Emissions': {
        'goals': {
            'Reduce Process Emissions': {
                'metrics': {
                    'Process Emissions': {'unit': 'tCO₂e'}
                }
            },
            'Improve Process Efficiency': {
                'metrics': {
                    'Emission Intensity': {'unit': 'tCO₂e/unit'}
                }
            }
        }
    },
    'Fugitive Emissions': {
        'goals': {
            'Reduce Refrigerant Leakage': {
                'metrics': {
                    'Refrigerant Used': {'unit': 'kg'}
                }
            },
            'Reduce Fugitive Emissions': {
                'metrics': {
                    'Fugitive Emissions': {'unit': 'tCO₂e'}
                }
            },
            'Leak Prevention': {
                'metrics': {
                    'Leakage Rate': {'unit': '%'}
                }
            }
        }
    },
    'Purchased Electricity': {
        'goals': {
            'Reduce Electricity Use': {
                'metrics': {
                    'Electricity Consumption': {'unit': 'kWh'}
                }
            },
            'Increase Renewable Energy': {
                'metrics': {
                    'Renewable Electricity': {'unit': '% or kWh'}
                }
            },
            'Reduce Emissions': {
                'metrics': {
                    'Scope 2 Emissions': {'unit': 'tCO₂e'}
                }
            }
        }
    },
    'Purchased Steam, Heat & Cooling': {
        'goals': {
            'Optimize Energy Use': {
                'metrics': {
                    'Steam Consumption': {'unit': 'Tonnes or GJ'},
                    'Heat Consumption': {'unit': 'GJ'},
                    'Cooling Energy': {'unit': 'kWh'}
                }
            },
            'Reduce Emissions': {
                'metrics': {
                    'Scope 2 Emissions': {'unit': 'tCO₂e'}
                }
            }
        }
    },
    'Purchased Goods & Services': {
        'goals': {
            'Sustainable Procurement': {
                'metrics': {
                    'Supplier Emissions': {'unit': 'tCO₂e'}
                }
            },
            'Responsible Sourcing': {
                'metrics': {
                    'Sustainable Suppliers': {'unit': '%'}
                }
            }
        }
    },
    'Business Travel': {
        'goals': {
            'Reduce Travel Emissions': {
                'metrics': {
                    'Travel Emissions': {'unit': 'tCO₂e'},
                    'Distance Travelled': {'unit': 'km'}
                }
            }
        }
    },
    'Employee Commuting': {
        'goals': {
            'Sustainable Commuting': {
                'metrics': {
                    'Commuting Emissions': {'unit': 'tCO₂e'},
                    'Employees Using Public Transport': {'unit': '%'}
                }
            }
        }
    },
    'Transportation & Distribution': {
        'goals': {
            'Reduce Logistics Emissions': {
                'metrics': {
                    'Transport Emissions': {'unit': 'tCO₂e'},
                    'Distance Transported': {'unit': 'km'},
                    'Fuel Used': {'unit': 'Litres (L)'}
                }
            }
        }
    },
    'Waste Generated in Operations': {
        'goals': {
            'Reduce Waste': {
                'metrics': {
                    'Waste Generated': {'unit': 'kg or tonnes'}
                }
            },
            'Increase Recycling': {
                'metrics': {
                    'Recycled Waste': {'unit': 'kg or %'}
                }
            },
            'Waste Disposal': {
                'metrics': {
                    'Landfill Waste': {'unit': 'kg or tonnes'}
                }
            }
        }
    },
    'Upstream & Downstream Activities': {
        'goals': {
            'Reduce Value Chain Emissions': {
                'metrics': {
                    'Scope 3 Emissions': {'unit': 'tCO₂e'}
                }
            },
            'Improve Supplier Performance': {
                'metrics': {
                    'ESG Assessed Suppliers': {'unit': '%'}
                }
            }
        }
    }
}


# ===== HELPER FUNCTIONS =====

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
        'Business Travel': 'fa-plane',
        'Employee Commuting': 'fa-bus',
        'Transportation & Distribution': 'fa-truck',
        'Waste Generated in Operations': 'fa-trash',
        'Upstream & Downstream Activities': 'fa-exchange-alt',
        'Human Rights and Child Labour': 'fa-hand-holding-heart',
        'Water': 'fa-tint',
        'Energy': 'fa-bolt',
        'Waste': 'fa-trash-alt',
        'Biodiversity': 'fa-leaf',
        'Emissions': 'fa-smog',
        'Social': 'fa-users',
        'Governance': 'fa-gavel',
        'Supply Chain': 'fa-truck',
        'Product Safety': 'fa-shield-alt',
        'Labor Practices': 'fa-hands',
        'Community': 'fa-home',
        'Ethics': 'fa-balance-scale',
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
        'Business Travel': 'transport',
        'Employee Commuting': 'transport',
        'Transportation & Distribution': 'transport',
        'Waste Generated in Operations': 'waste',
        'Upstream & Downstream Activities': 'procurement',
        'Human Rights and Child Labour': 'social',
        'Water': 'environment',
        'Energy': 'energy',
        'Waste': 'waste',
        'Biodiversity': 'environment',
        'Emissions': 'emissions',
        'Social': 'social',
        'Governance': 'default',
        'Supply Chain': 'procurement',
        'Product Safety': 'default',
        'Labor Practices': 'social',
        'Community': 'social',
        'Ethics': 'default',
    }
    return class_map.get(topic, 'default')


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
                })
    
    return goal_metrics


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
        'Business Travel': 'transport',
        'Employee Commuting': 'transport',
        'Transportation & Distribution': 'transport',
        'Waste Generated in Operations': 'waste',
        'Upstream & Downstream Activities': 'procurement',
        'Human Rights and Child Labour': 'social',
        'Water': 'environment',
        'Energy': 'energy',
        'Waste': 'waste',
    }
    return color_map.get(material_topic, 'default')


# ===== VIEWS =====

class DashboardView(LoginRequiredMixin, TemplateView):
    """
    Goals Dashboard View - Shows only goals that have been added to session
    """
    template_name = 'goals/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get goals from session
        session_goals = self.request.session.get('goals', [])
        
        # Group goals by material topic from session only
        grouped_goals = {}
        for goal in session_goals:
            topic = goal.get('material_topic', 'Uncategorized')
            if topic not in grouped_goals:
                grouped_goals[topic] = []
            grouped_goals[topic].append({
                'id': goal.get('id'),
                'name': goal.get('goal_name') or goal.get('name'),
                'last_updated': goal.get('last_updated', datetime.now().strftime('%d/%m/%Y')),
                'dot_color': goal.get('dot_color', 'default'),
                'material_topic': topic,
            })
        
        # Convert to list for template
        grouped_goals_list = []
        for topic, goals_list in grouped_goals.items():
            grouped_goals_list.append({
                'material_topic': topic,
                'goals': goals_list,
                'dot_color': goals_list[0]['dot_color'] if goals_list else 'default',
                'count': len(goals_list)
            })
        
        context['grouped_goals'] = grouped_goals_list
        context['goals_data'] = session_goals
        context['total_goals'] = len(session_goals)
        context['total_topics'] = len(grouped_goals_list)
        
        return context


class AddGoalView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            material_topic = request.POST.get('material_topic')
            goal_name = request.POST.get('goal_name')
            
            if not material_topic or not goal_name:
                return JsonResponse({
                    'status': 'error',
                    'message': 'Please fill in all required fields.',
                    'errors': {
                        'material_topic': ['Material topic is required.'] if not material_topic else [],
                        'goal_name': ['Goal name is required.'] if not goal_name else []
                    }
                }, status=400)
            
            goals = request.session.get('goals', [])
            
            # Check if goal already exists
            for g in goals:
                if g.get('material_topic') == material_topic and (g.get('goal_name') == goal_name or g.get('name') == goal_name):
                    return JsonResponse({
                        'status': 'error',
                        'message': 'This goal already exists for this topic.'
                    }, status=400)
            
            new_goal = {
                'id': str(uuid.uuid4())[:8],
                'material_topic': material_topic,
                'goal_name': goal_name,
                'name': goal_name,
                'last_updated': datetime.now().strftime('%d/%m/%Y'),
                'dot_color': get_dot_color(material_topic),
            }
            
            goals.append(new_goal)
            request.session['goals'] = goals
            request.session.modified = True
            
            return JsonResponse({
                'status': 'success',
                'message': 'Goal added successfully!',
                'goal': new_goal,
                'total_goals': len(goals)
            })
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=500)


class DeleteGoalView(LoginRequiredMixin, View):
    def post(self, request, goal_id, *args, **kwargs):
        try:
            goals = request.session.get('goals', [])
            goals = [g for g in goals if g.get('id') != goal_id]
            request.session['goals'] = goals
            request.session.modified = True
            messages.success(request, 'Goal deleted successfully!')
            return redirect('goals:dashboard')
        except Exception as e:
            messages.error(request, f'Error deleting goal: {str(e)}')
            return redirect('goals:dashboard')


class DeleteTopicView(LoginRequiredMixin, View):
    def post(self, request, topic, *args, **kwargs):
        try:
            goals = request.session.get('goals', [])
            goals = [g for g in goals if g.get('material_topic') != topic]
            request.session['goals'] = goals
            request.session.modified = True
            messages.success(request, f'All goals under "{topic}" deleted successfully!')
            return redirect('goals:dashboard')
        except Exception as e:
            messages.error(request, f'Error deleting topic: {str(e)}')
            return redirect('goals:dashboard')


class GoalDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'goals/goal_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        material_topic = self.kwargs.get('material_topic')
        goal_name = self.request.GET.get('goal', '')
        
        # Get goals from session
        all_goals = self.request.session.get('goals', [])
        
        # Filter goals by material topic from session
        session_goals = []
        for g in all_goals:
            topic = g.get('material_topic', '')
            if topic.lower().strip() == material_topic.lower().strip():
                session_goals.append({
                    'name': g.get('goal_name') or g.get('name') or 'Unknown Goal',
                    'material_topic': topic,
                    'id': g.get('id', ''),
                })
        
        # Use session goals only
        goals = session_goals
        
        # Set selected goal
        selected_goal_name = goal_name
        if not selected_goal_name and goals:
            selected_goal_name = goals[0]['name']
        
        # Get metrics for the selected goal - FIXED: Handle list properly
        metrics_list = []
        active_unit = ''
        if selected_goal_name:
            metrics_list = get_metrics_for_goal(material_topic, selected_goal_name)
            if metrics_list and len(metrics_list) > 0:
                first_metric = metrics_list[0]
                active_unit = first_metric.get('unit', '')
        
        # Convert metrics list to dict for template
        metrics_dict = {}
        for metric in metrics_list:
            metrics_dict[metric.get('name', 'Unknown')] = {
                'current': 0,
                'projected': 0,
                'target': 0,
                'unit': metric.get('unit', ''),
            }
        
        # Get config from session
        configs = self.request.session.get('goal_configs', {})
        config_key = f"{material_topic}_{selected_goal_name}" if selected_goal_name else material_topic
        config = configs.get(config_key, {
            'baseline_year': '',
            'baseline_value': '',
            'target_year': '',
            'target_reduction': '',
            'target_value': '',
            'unit': active_unit,
            'selected_goal': selected_goal_name
        })
        
        if not config.get('unit') and active_unit:
            config['unit'] = active_unit
        
        # Get all material topics from session for dropdown
        all_topics = list(set([g.get('material_topic') for g in all_goals]))
        
        # JSON data for JavaScript
        goals_json = json.dumps(goals)
        metrics_json = json.dumps(metrics_dict)
        
        context.update({
            'material_topic': material_topic,
            'goals': goals,
            'goals_json': goals_json,
            'metrics': metrics_dict,
            'metrics_json': metrics_json,
            'config': config,
            'all_material_topics': all_topics,
            'total_metrics': len(metrics_dict),
            'total_goals': len(goals),
            'selected_goal': selected_goal_name,
            'active_unit': active_unit,
        })
        
        return context


class GoalConfigUpdateView(LoginRequiredMixin, View):
    @method_decorator(csrf_exempt)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        try:
            material_topic = self.kwargs.get('material_topic')
            goal_name = request.POST.get('selected_goal', '')
            
            configs = request.session.get('goal_configs', {})
            config_key = f"{material_topic}_{goal_name}" if goal_name else material_topic
            
            config = configs.get(config_key, {
                'baseline_year': '',
                'baseline_value': '',
                'target_year': '',
                'target_reduction': '',
                'target_value': '',
                'unit': '',
                'selected_goal': goal_name
            })
            
            if request.content_type == 'application/json':
                data = json.loads(request.body)
            else:
                data = request.POST
            
            config['baseline_year'] = data.get('baseline_year', config['baseline_year'])
            config['baseline_value'] = data.get('baseline_value', config['baseline_value'])
            config['target_year'] = data.get('target_year', config['target_year'])
            config['target_reduction'] = data.get('target_reduction', config['target_reduction'])
            config['target_value'] = data.get('target_value', config['target_value'])
            config['unit'] = data.get('unit', config['unit'])
            config['selected_goal'] = data.get('selected_goal', config['selected_goal'])
            
            configs[config_key] = config
            request.session['goal_configs'] = configs
            request.session.modified = True
            
            return JsonResponse({
                'status': 'success',
                'message': 'Configuration saved successfully!',
                'data': config
            })
            
        except Exception as e:
            return JsonResponse({
                'status': 'error',
                'message': str(e)
            }, status=400)


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
            }, status=400)


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
            goal = initiative.get('goal', 'Uncategorized Goal')  # <-- GET GOAL
            
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
                    'goal_name': goal,  # <-- ADD GOAL NAME HERE
                    'initiatives': []
                }
            
            topic_map[topic]['kpis'][kpi]['initiatives'].append(initiative)
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
        total = len(filtered_initiatives)
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
            'total_initiatives': total,
            'in_progress_count': in_progress,
            'completed_count': completed,
            'planning_count': planning,
            'goal_metrics': goal_metrics,
            'has_metrics': has_metrics,
        })
        
        return context
class InitiativeCreateView(LoginRequiredMixin, View):
    """Class-based view for creating a new initiative via AJAX"""
    
    def post(self, request, *args, **kwargs):
        try:
            # Check if it's an AJAX request
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            
            # Get form data
            initiative_name = request.POST.get('initiative_name')
            kpi = request.POST.get('kpi')
            kpi_unit = request.POST.get('kpi_unit', '')
            plant = request.POST.get('plant', 'Default Plant')  # <-- Set default value
            assigned_to = request.POST.get('assigned_to')
            due_date = request.POST.get('due_date')
            description = request.POST.get('description', '')
            selected_topic = request.POST.get('selected_topic', '')
            selected_goal = request.POST.get('selected_goal', '')
            
            # Validate required fields (remove 'plant' from required fields)
            required_fields = {
                'initiative_name': initiative_name,
                'kpi': kpi,
                # 'plant': plant,  # <-- Comment this out or remove it
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
                    context = self.get_context_data()
                    return render(request, 'goals/initiative_list.html', context)
            
            # Get existing initiatives from session
            initiatives = request.session.get('initiatives', [])
            if initiatives is None:
                initiatives = []
            
            # Generate unique ID
            initiative_id = len(initiatives) + 1
            while any(i.get('id') == initiative_id for i in initiatives):
                initiative_id += 1
            
            # Create new initiative - MAKE SURE topic and goal are saved
            new_initiative = {
                'id': initiative_id,
                'name': initiative_name,
                'kpi': kpi,
                'kpi_unit': kpi_unit,
                'plant': plant,  # This will now have a default value
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
                'topic': selected_topic,  # IMPORTANT: This must be saved
                'goal': selected_goal,    # IMPORTANT: This must be saved
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
                context = self.get_context_data()
                return render(request, 'goals/initiative_list.html', context)
class InitiativeDeleteView(LoginRequiredMixin, View):
    """Class-based view for deleting an initiative"""
    
    def post(self, request, initiative_id, *args, **kwargs):
        """Handle POST request - delete initiative"""
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
class DeleteKpiInitiativesView(LoginRequiredMixin, View):
    """Class-based view for deleting all initiatives for a specific KPI"""
    
    def post(self, request, *args, **kwargs):
        """Handle POST request - delete all initiatives for a KPI"""
        try:
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            
            # Parse JSON data
            try:
                data = json.loads(request.body)
                topic = data.get('topic')
                kpi = data.get('kpi')
            except:
                if is_ajax:
                    return JsonResponse({
                        'success': False,
                        'message': 'Invalid JSON data.'
                    }, status=400)
                else:
                    messages.error(request, 'Invalid JSON data.')
                    return redirect('goals:initiative_list')
            
            if not topic or not kpi:
                if is_ajax:
                    return JsonResponse({
                        'success': False,
                        'message': 'Topic and KPI are required.'
                    }, status=400)
                else:
                    messages.error(request, 'Topic and KPI are required.')
                    return redirect('goals:initiative_list')
            
            # Get initiatives from session
            initiatives = request.session.get('initiatives', [])
            
            # Find initiatives to delete
            initiatives_to_delete = [
                i for i in initiatives 
                if i.get('topic') == topic and i.get('kpi') == kpi
            ]
            
            # Filter out initiatives that match the topic and kpi
            remaining_initiatives = [
                i for i in initiatives 
                if not (i.get('topic') == topic and i.get('kpi') == kpi)
            ]
            
            deleted_count = len(initiatives_to_delete)
            
            if deleted_count == 0:
                if is_ajax:
                    return JsonResponse({
                        'success': False,
                        'message': f'No initiatives found for "{kpi}".'
                    }, status=404)
                else:
                    messages.warning(request, f'No initiatives found for "{kpi}".')
                    return redirect('goals:initiative_list')
            
            # Update session
            request.session['initiatives'] = remaining_initiatives
            request.session.modified = True
            request.session.save()
            
            if is_ajax:
                return JsonResponse({
                    'success': True,
                    'message': f'All {deleted_count} initiative(s) for "{kpi}" deleted successfully!',
                    'deleted_count': deleted_count
                })
            else:
                messages.success(request, f'All {deleted_count} initiative(s) for "{kpi}" deleted successfully!')
                return redirect('goals:initiative_list')
                
        except Exception as e:
            logger.error(f"Error deleting KPI initiatives: {str(e)}")
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'message': f'Error deleting initiatives: {str(e)}'
                }, status=500)
            else:
                messages.error(request, f'Error deleting initiatives: {str(e)}')
                return redirect('goals:initiative_list')


class InitiativeEditView(LoginRequiredMixin, View):
    """Class-based view for editing an initiative"""
    
    def get(self, request, initiative_id, *args, **kwargs):
        """Handle GET request - get initiative data for editing"""
        try:
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            
            initiatives = request.session.get('initiatives', [])
            
            # Find the initiative
            initiative = None
            for i in initiatives:
                if i.get('id') == int(initiative_id):
                    initiative = i
                    break
            
            if initiative:
                return JsonResponse({
                    'success': True,
                    'initiative': initiative
                })
            else:
                return JsonResponse({
                    'success': False,
                    'message': 'Initiative not found.'
                }, status=404)
                
        except Exception as e:
            logger.error(f"Error fetching initiative: {str(e)}")
            return JsonResponse({
                'success': False,
                'message': f'Error fetching initiative: {str(e)}'
            }, status=500)
    
    def post(self, request, initiative_id, *args, **kwargs):
        """Handle POST request - update initiative"""
        try:
            is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            
            initiatives = request.session.get('initiatives', [])
            
            # Find and update the initiative
            for i, initiative in enumerate(initiatives):
                if initiative.get('id') == int(initiative_id):
                    # Update fields
                    initiatives[i]['name'] = request.POST.get('initiative_name', initiative['name'])
                    initiatives[i]['kpi'] = request.POST.get('kpi', initiative['kpi'])
                    initiatives[i]['kpi_unit'] = request.POST.get('kpi_unit', initiative.get('kpi_unit', ''))
                    initiatives[i]['plant'] = request.POST.get('plant', initiative['plant'])
                    initiatives[i]['assigned_to'] = request.POST.get('assigned_to', initiative['assigned_to'])
                    initiatives[i]['due_date'] = request.POST.get('due_date', initiative['due_date'])
                    initiatives[i]['description'] = request.POST.get('description', initiative.get('description', ''))
                    initiatives[i]['status'] = request.POST.get('status', initiative.get('status', 'Planning'))
                    initiatives[i]['progress'] = int(request.POST.get('progress', initiative.get('progress', 0)))
                    
                    if request.POST.get('due_date'):
                        initiatives[i]['target_date'] = datetime.strptime(
                            request.POST.get('due_date'), '%Y-%m-%d'
                        ).strftime('%b %Y')
                    
                    request.session['initiatives'] = initiatives
                    request.session.modified = True
                    request.session.save()
                    
                    if is_ajax:
                        return JsonResponse({
                            'success': True,
                            'message': 'Initiative updated successfully!',
                            'initiative': initiatives[i]
                        })
                    else:
                        messages.success(request, 'Initiative updated successfully!')
                        return redirect('goals:initiative_list')
            
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'message': 'Initiative not found.'
                }, status=404)
            else:
                messages.error(request, 'Initiative not found.')
                return redirect('goals:initiative_list')
                
        except Exception as e:
            logger.error(f"Error updating initiative: {str(e)}")
            if is_ajax:
                return JsonResponse({
                    'success': False,
                    'message': f'Error updating initiative: {str(e)}'
                }, status=500)
            else:
                messages.error(request, f'Error updating initiative: {str(e)}')
                return redirect('goals:initiative_list')


class GetMetricsForGoalAPIView(LoginRequiredMixin, View):
    """AJAX view to get metrics for a specific goal"""
    
    def get(self, request, *args, **kwargs):
        try:
            goal = request.GET.get('goal', '')
            topic = request.GET.get('topic', '')
            
            goal_metrics = get_metrics_for_goal(topic, goal)
            
            return JsonResponse({
                'success': True,
                'metrics': goal_metrics
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': str(e)
            }, status=500)


class InitiativeDetailView(LoginRequiredMixin, TemplateView):
    """View for displaying all initiatives under a topic grouped by KPI then Goal"""
    template_name = 'goals/initiative_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        material_topic = self.kwargs.get('material_topic')
        selected_kpi = self.request.GET.get('kpi', '')
        
        # Get all initiatives from session
        all_initiatives = self.request.session.get('initiatives', [])
        
        # Filter initiatives by topic
        topic_initiatives = []
        for i in all_initiatives:
            topic = i.get('topic', '')
            if topic and topic.lower() == material_topic.lower():
                topic_initiatives.append(i)
        
        # If no initiatives found, try partial match
        if not topic_initiatives:
            for i in all_initiatives:
                topic = i.get('topic', '')
                if topic and material_topic.lower() in topic.lower():
                    topic_initiatives.append(i)
        
        # Filter by KPI if selected
        if selected_kpi:
            topic_initiatives = [
                i for i in topic_initiatives 
                if i.get('kpi', '').lower() == selected_kpi.lower()
            ]
        
        # ===== GROUP BY KPI FIRST, THEN GOAL =====
        kpi_map = {}
        for initiative in topic_initiatives:
            kpi = initiative.get('kpi', 'Uncategorized KPI')
            goal = initiative.get('goal', 'Uncategorized Goal')
            
            if kpi not in kpi_map:
                kpi_map[kpi] = {
                    'kpi_name': kpi,
                    'kpi_unit': initiative.get('kpi_unit', ''),
                    'goals': {},
                    'total_initiatives': 0
                }
            
            if goal not in kpi_map[kpi]['goals']:
                # Get metrics for this goal
                metrics = get_metrics_for_goal(material_topic, goal)
                kpi_map[kpi]['goals'][goal] = {
                    'goal_name': goal,
                    'metrics': [m['name'] for m in metrics],
                    'initiatives': []
                }
            
            kpi_map[kpi]['goals'][goal]['initiatives'].append(initiative)
            kpi_map[kpi]['total_initiatives'] += 1
        
        # Convert to list
        grouped_by_kpi = []
        for kpi, data in kpi_map.items():
            grouped_by_kpi.append({
                'kpi_name': data['kpi_name'],
                'kpi_unit': data['kpi_unit'],
                'total_initiatives': data['total_initiatives'],
                'goals': list(data['goals'].values())
            })
        
        # Calculate stats
        total_initiatives = len(topic_initiatives)
        total_kpis = len(grouped_by_kpi)
        completed_count = len([i for i in topic_initiatives if i.get('status') == 'Completed'])
        in_progress_count = len([i for i in topic_initiatives if i.get('status') == 'In Progress'])
        planning_count = len([i for i in topic_initiatives if i.get('status') == 'Planning'])
        
        # Get topic icon
        topic_icon = get_topic_icon(material_topic)
        topic_icon_class = get_topic_icon_class(material_topic)
        
        context.update({
            'material_topic': material_topic,
            'grouped_by_kpi': grouped_by_kpi,  # Changed from grouped_initiatives
            'topic_initiatives': topic_initiatives,
            'total_initiatives': total_initiatives,
            'total_kpis': total_kpis,
            'completed_count': completed_count,
            'in_progress_count': in_progress_count,
            'planning_count': planning_count,
            'topic_icon': topic_icon,
            'topic_icon_class': topic_icon_class,
            'selected_kpi': selected_kpi,
        })
        
        return context
class ClearInitiativesView(LoginRequiredMixin, View):
    def get(self, request):
        request.session['initiatives'] = []
        request.session.modified = True
        messages.success(request, 'All initiatives cleared from session!')
        return redirect('goals:initiative_list')