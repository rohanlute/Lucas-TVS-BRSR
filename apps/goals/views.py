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


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'goals/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        goals = self.request.session.get('goals', [])
        
        grouped_goals = {}
        for goal in goals:
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
        
        grouped_goals_list = []
        for topic, goals_list in grouped_goals.items():
            grouped_goals_list.append({
                'material_topic': topic,
                'goals': goals_list,
                'dot_color': goals_list[0]['dot_color'] if goals_list else 'default',
                'count': len(goals_list)
            })
        
        context['grouped_goals'] = grouped_goals_list
        context['goals_data'] = goals
        return context


def get_dot_color(material_topic):
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
        metric_name = self.kwargs.get('metric_name', '')  # Get metric from URL
        goal_name = self.request.GET.get('goal', '')
        
        # Get goals from session
        all_goals = self.request.session.get('goals', [])
        
        # Filter goals by material topic
        goals = []
        for g in all_goals:
            topic = g.get('material_topic', '')
            if topic.lower().strip() == material_topic.lower().strip():
                goals.append({
                    'name': g.get('goal_name') or g.get('name') or 'Unknown Goal',
                    'material_topic': topic,
                    'id': g.get('id', ''),
                })
        
        # If no goals in session, use hardcoded
        if not goals:
            goals = self.get_hardcoded_goals(material_topic)
        
        # Set selected goal
        selected_goal_name = goal_name
        if not selected_goal_name and goals:
            selected_goal_name = goals[0]['name']
        
        # Get metrics for the selected goal
        metrics_data = {}
        if selected_goal_name:
            metrics_data = self.get_metrics_for_goal(material_topic, selected_goal_name)
        
        # Set active metric from URL or first metric
        active_metric = metric_name
        if not active_metric and metrics_data:
            active_metric = list(metrics_data.keys())[0]
        
        # Get unit for the active metric
        active_unit = ''
        if active_metric and active_metric in metrics_data:
            active_unit = metrics_data[active_metric].get('unit', '')
        
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
            'selected_goal': selected_goal_name,
            'active_metric': active_metric
        })
        
        # All topics for dropdown
        all_topics = list(set([g.get('material_topic', 'Unknown') for g in all_goals]))
        if not all_topics:
            all_topics = ['Water', 'Energy', 'Waste', 'Human Rights and Child Labour', 
                         'Stationary Combustion', 'Mobile Combustion', 'Process Emissions',
                         'Fugitive Emissions', 'Purchased Electricity', 'Purchased Steam, Heat & Cooling',
                         'Purchased Goods & Services', 'Business Travel', 'Employee Commuting',
                         'Transportation & Distribution', 'Waste Generated in Operations',
                         'Upstream & Downstream Activities']
        if material_topic not in all_topics:
            all_topics.append(material_topic)
        
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
            'active_metric': active_metric,
            'active_unit': active_unit,
        })
        
        return context
    
    def get_hardcoded_goals(self, material_topic):
        hardcoded = {
            'Water': [
                {'name': 'Water Neutrality', 'material_topic': 'Water', 'id': '1'},
                {'name': 'Reduce Water Consumption', 'material_topic': 'Water', 'id': '2'},
                {'name': 'Improve Water Efficiency', 'material_topic': 'Water', 'id': '3'},
            ],
            'Energy': [
                {'name': 'Net Zero Energy', 'material_topic': 'Energy', 'id': '4'},
                {'name': 'Increase Renewable Energy', 'material_topic': 'Energy', 'id': '5'},
                {'name': 'Improve Energy Efficiency', 'material_topic': 'Energy', 'id': '6'},
            ],
            'Waste': [
                {'name': 'Zero Waste to Landfill', 'material_topic': 'Waste', 'id': '7'},
                {'name': 'Increase Recycling Rate', 'material_topic': 'Waste', 'id': '8'},
                {'name': 'Reduce Waste Generation', 'material_topic': 'Waste', 'id': '9'},
            ],
            'Human Rights and Child Labour': [
                {'name': 'Zero Human Rights Violation', 'material_topic': 'Human Rights and Child Labour', 'id': '10'},
            ],
            'Stationary Combustion': [
                {'name': 'Reduce Fuel Consumption', 'material_topic': 'Stationary Combustion', 'id': '11'},
            ],
            'Mobile Combustion': [
                {'name': 'Reduce Fuel Usage', 'material_topic': 'Mobile Combustion', 'id': '12'},
                {'name': 'Improve Fleet Efficiency', 'material_topic': 'Mobile Combustion', 'id': '13'},
                {'name': 'Reduce Emissions', 'material_topic': 'Mobile Combustion', 'id': '14'},
            ],
            'Process Emissions': [
                {'name': 'Reduce Process Emissions', 'material_topic': 'Process Emissions', 'id': '15'},
                {'name': 'Improve Process Efficiency', 'material_topic': 'Process Emissions', 'id': '16'},
            ],
            'Fugitive Emissions': [
                {'name': 'Reduce Refrigerant Leakage', 'material_topic': 'Fugitive Emissions', 'id': '17'},
                {'name': 'Reduce Fugitive Emissions', 'material_topic': 'Fugitive Emissions', 'id': '18'},
                {'name': 'Leak Prevention', 'material_topic': 'Fugitive Emissions', 'id': '19'},
            ],
            'Purchased Electricity': [
                {'name': 'Reduce Electricity Use', 'material_topic': 'Purchased Electricity', 'id': '20'},
                {'name': 'Increase Renewable Energy', 'material_topic': 'Purchased Electricity', 'id': '21'},
                {'name': 'Reduce Emissions', 'material_topic': 'Purchased Electricity', 'id': '22'},
            ],
            'Purchased Steam, Heat & Cooling': [
                {'name': 'Optimize Energy Use', 'material_topic': 'Purchased Steam, Heat & Cooling', 'id': '23'},
                {'name': 'Reduce Emissions', 'material_topic': 'Purchased Steam, Heat & Cooling', 'id': '24'},
            ],
            'Purchased Goods & Services': [
                {'name': 'Sustainable Procurement', 'material_topic': 'Purchased Goods & Services', 'id': '25'},
                {'name': 'Responsible Sourcing', 'material_topic': 'Purchased Goods & Services', 'id': '26'},
            ],
            'Business Travel': [
                {'name': 'Reduce Travel Emissions', 'material_topic': 'Business Travel', 'id': '27'},
            ],
            'Employee Commuting': [
                {'name': 'Sustainable Commuting', 'material_topic': 'Employee Commuting', 'id': '28'},
            ],
            'Transportation & Distribution': [
                {'name': 'Reduce Logistics Emissions', 'material_topic': 'Transportation & Distribution', 'id': '29'},
            ],
            'Waste Generated in Operations': [
                {'name': 'Reduce Waste', 'material_topic': 'Waste Generated in Operations', 'id': '30'},
                {'name': 'Increase Recycling', 'material_topic': 'Waste Generated in Operations', 'id': '31'},
                {'name': 'Waste Disposal', 'material_topic': 'Waste Generated in Operations', 'id': '32'},
            ],
            'Upstream & Downstream Activities': [
                {'name': 'Reduce Value Chain Emissions', 'material_topic': 'Upstream & Downstream Activities', 'id': '33'},
                {'name': 'Improve Supplier Performance', 'material_topic': 'Upstream & Downstream Activities', 'id': '34'},
            ],
        }
        return hardcoded.get(material_topic, [{'name': 'Default Goal', 'material_topic': material_topic, 'id': 'default'}])
    
    def get_metrics_for_goal(self, material_topic, goal_name):
        """
        Get KPIs/Metrics based on material topic and goal
        Complete mapping from the images
        """
        mapping = {
            # ===== Stationary Combustion =====
            'Stationary Combustion': {
                'Reduce Fuel Consumption': {
                    'Fuel Consumed': {'unit': 'Litres (L), kg, m³'}
                },
                'Lower GHG Emissions': {
                    'Scope 1 Emissions': {'unit': 'tCO₂e'}
                },
                'Improve Efficiency': {
                    'Fuel Intensity': {'unit': 'L/unit, kg/unit'}
                },
            },
            
            # ===== Mobile Combustion =====
            'Mobile Combustion': {
                'Reduce Fuel Usage': {
                    'Fuel Consumed': {'unit': 'Litres (L)'}
                },
                'Improve Fleet Efficiency': {
                    'Fuel Efficiency': {'unit': 'km/L'}
                },
                'Reduce Emissions': {
                    'Scope 1 Emissions': {'unit': 'tCO₂e'}
                },
            },
            
            # ===== Process Emissions =====
            'Process Emissions': {
                'Reduce Process Emissions': {
                    'Process Emissions': {'unit': 'tCO₂e'}
                },
                'Improve Process Efficiency': {
                    'Emission Intensity': {'unit': 'tCO₂e/unit'}
                },
            },
            
            # ===== Fugitive Emissions =====
            'Fugitive Emissions': {
                'Reduce Refrigerant Leakage': {
                    'Refrigerant Used': {'unit': 'kg'}
                },
                'Reduce Fugitive Emissions': {
                    'Fugitive Emissions': {'unit': 'tCO₂e'}
                },
                'Leak Prevention': {
                    'Leakage Rate': {'unit': '%'}
                },
            },
            
            # ===== Purchased Electricity =====
            'Purchased Electricity': {
                'Reduce Electricity Use': {
                    'Electricity Consumption': {'unit': 'kWh'}
                },
                'Increase Renewable Energy': {
                    'Renewable Electricity': {'unit': '% or kWh'}
                },
                'Reduce Emissions': {
                    'Scope 2 Emissions': {'unit': 'tCO₂e'}
                },
            },
            
            # ===== Purchased Steam, Heat & Cooling =====
            'Purchased Steam, Heat & Cooling': {
                'Optimize Energy Use': {
                    'Steam Consumption': {'unit': 'Tonnes or GJ'},
                    'Heat Consumption': {'unit': 'GJ'},
                    'Cooling Energy': {'unit': 'kWh'}
                },
                'Reduce Emissions': {
                    'Scope 2 Emissions': {'unit': 'tCO₂e'}
                },
            },
            
            # ===== Purchased Goods & Services =====
            'Purchased Goods & Services': {
                'Sustainable Procurement': {
                    'Supplier Emissions': {'unit': 'tCO₂e'}
                },
                'Responsible Sourcing': {
                    'Sustainable Suppliers': {'unit': '%'}
                },
            },
            
            # ===== Business Travel =====
            'Business Travel': {
                'Reduce Travel Emissions': {
                    'Travel Emissions': {'unit': 'tCO₂e'},
                    'Distance Travelled': {'unit': 'km'}
                },
            },
            
            # ===== Employee Commuting =====
            'Employee Commuting': {
                'Sustainable Commuting': {
                    'Commuting Emissions': {'unit': 'tCO₂e'},
                    'Employees Using Public Transport': {'unit': '%'}
                },
            },
            
            # ===== Transportation & Distribution =====
            'Transportation & Distribution': {
                'Reduce Logistics Emissions': {
                    'Transport Emissions': {'unit': 'tCO₂e'},
                    'Distance Transported': {'unit': 'km'},
                    'Fuel Used': {'unit': 'Litres (L)'}
                },
            },
            
            # ===== Waste Generated in Operations =====
            'Waste Generated in Operations': {
                'Reduce Waste': {
                    'Waste Generated': {'unit': 'kg or tonnes'}
                },
                'Increase Recycling': {
                    'Recycled Waste': {'unit': 'kg or %'}
                },
                'Waste Disposal': {
                    'Landfill Waste': {'unit': 'kg or tonnes'}
                },
            },
            
            # ===== Upstream & Downstream Activities =====
            'Upstream & Downstream Activities': {
                'Reduce Value Chain Emissions': {
                    'Scope 3 Emissions': {'unit': 'tCO₂e'}
                },
                'Improve Supplier Performance': {
                    'ESG Assessed Suppliers': {'unit': '%'}
                },
            },
            
            # ===== Water =====
            'Water': {
                'Water Neutrality': {
                    'Operational water efficiency': {'unit': 'Kilolitre'}
                },
                'Reduce Water Consumption': {
                    'Water consumption intensity': {'unit': 'Kilolitre/unit'},
                    'Water recycling rate': {'unit': '%'}
                },
                'Improve Water Efficiency': {
                    'Water withdrawal': {'unit': 'Kilolitre'},
                    'Water discharge': {'unit': 'Kilolitre'}
                },
            },
            
            # ===== Energy =====
            'Energy': {
                'Net Zero Energy': {
                    'Energy consumption': {'unit': 'kWh'},
                    'Renewable energy share': {'unit': '%'}
                },
                'Increase Renewable Energy': {
                    'Energy intensity': {'unit': 'kWh/unit'}
                },
                'Improve Energy Efficiency': {
                    'Electricity consumption': {'unit': 'kWh'},
                    'Fuel consumption': {'unit': 'Litres (L)'}
                },
            },
            
            # ===== Waste =====
            'Waste': {
                'Zero Waste to Landfill': {
                    'Waste generated': {'unit': 'tonnes'},
                    'Waste recycling rate': {'unit': '%'}
                },
                'Increase Recycling Rate': {
                    'Hazardous waste': {'unit': 'tonnes'},
                    'Waste diverted from landfill': {'unit': '%'}
                },
                'Reduce Waste Generation': {
                    'Waste intensity': {'unit': 'tonnes/unit'}
                },
            },
            
            # ===== Human Rights and Child Labour =====
            'Human Rights and Child Labour': {
                'Zero Human Rights Violation': {
                    'Equal Pay Across Gender': {'unit': '%'},
                    'Grievances related Unfair Treatment': {'unit': 'Number'},
                    'Coverage of Workers Right to Association': {'unit': '%'},
                    'Reports of Coerced Labor': {'unit': 'Number'},
                    'Decrease in Reports of Human Rights Concerns': {'unit': '%'},
                    'Coverage of Human Rights Training Programs': {'unit': '%'},
                    'Lowered Instances of Child Labor': {'unit': 'Number'},
                    'Paying Living Wage Coverage': {'unit': '%'}
                },
            },
        }
        
        # Return metrics for the specific topic and goal
        if material_topic in mapping and goal_name in mapping[material_topic]:
            metrics_dict = {}
            for name, details in mapping[material_topic][goal_name].items():
                metrics_dict[name] = {
                    'current': 0,
                    'projected': 0,
                    'target': 0,
                    'unit': details.get('unit', ''),
                }
            return metrics_dict
        
        # Return default if not found
        return {
            'KPI 1': {'current': 0, 'projected': 0, 'target': 0, 'unit': '%'},
            'KPI 2': {'current': 0, 'projected': 0, 'target': 0, 'unit': '%'},
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