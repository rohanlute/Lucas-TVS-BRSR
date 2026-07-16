# apps/goals/views.py

from django.views.generic import TemplateView
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import redirect
from django.contrib import messages
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
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


# apps/goals/views.py

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
        
        # Get metrics for the selected goal
        metrics_data = {}
        active_unit = ''
        if selected_goal_name:
            metrics_data = self.get_metrics_for_goal(material_topic, selected_goal_name)
            # Get the first metric's unit as active_unit
            if metrics_data:
                first_metric = list(metrics_data.values())[0]
                active_unit = first_metric.get('unit', '')
        
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
        
        # If config has no unit but we have active_unit, set it
        if not config.get('unit') and active_unit:
            config['unit'] = active_unit
        
        # Get all material topics from session for dropdown
        all_topics = list(set([g.get('material_topic') for g in all_goals]))
        
        # JSON data for JavaScript
        goals_json = json.dumps(goals)
        metrics_json = json.dumps(metrics_data)
        
        context.update({
            'material_topic': material_topic,
            'goals': goals,
            'goals_json': goals_json,
            'metrics': metrics_data,
            'metrics_json': metrics_json,
            'config': config,
            'all_material_topics': all_topics,
            'total_metrics': len(metrics_data),
            'total_goals': len(goals),
            'selected_goal': selected_goal_name,
            'active_unit': active_unit,
        })
        
        return context
    
    def get_metrics_for_goal(self, material_topic, goal_name):
        """Get KPIs/Metrics based on material topic and goal"""
        if material_topic in MATERIAL_TOPICS_MAPPING:
            topic_data = MATERIAL_TOPICS_MAPPING[material_topic]
            if goal_name in topic_data['goals']:
                metrics_dict = {}
                for name, details in topic_data['goals'][goal_name]['metrics'].items():
                    metrics_dict[name] = {
                        'current': 0,
                        'projected': 0,
                        'target': 0,
                        'unit': details.get('unit', ''),
                    }
                return metrics_dict
        
        return {
            'KPI 1': {'current': 0, 'projected': 0, 'target': 0, 'unit': '%'},
        }
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
            
            temp_view = GoalDetailView()
            metrics = temp_view.get_metrics_for_goal(material_topic, goal_name)
            
            metrics_data = []
            for name, values in metrics.items():
                metrics_data.append({
                    'name': name,
                    'current': 0,
                    'projected': 0,
                    'target': 0,
                    'unit': values.get('unit', ''),
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