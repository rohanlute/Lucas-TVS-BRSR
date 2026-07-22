"""
Seed script for populating Unit models with conversion data.
Run with: python manage.py runscript seed_conversion
Or: python manage.py shell < seed_conversion.py
"""
from django.core.management.base import BaseCommand
from apps.calculator.models import Unit

# ================================================================
# CONVERSION DATA - All values have max 10 decimal places
# ================================================================

CONVERSION_DATA = {
    'length': {
        'name': 'Length/Distance',
        'icon': '📏',
        'units': [
            {'name': 'Meter', 'symbol': 'm', 'icon': '📏', 'conversion_factor': 1.0, 'is_base_unit': True},
            {'name': 'Kilometer', 'symbol': 'km', 'icon': '📍', 'conversion_factor': 0.001, 'is_base_unit': False},
            {'name': 'Centimeter', 'symbol': 'cm', 'icon': '📐', 'conversion_factor': 100.0, 'is_base_unit': False},
            {'name': 'Millimeter', 'symbol': 'mm', 'icon': '📏', 'conversion_factor': 1000.0, 'is_base_unit': False},
            {'name': 'Mile', 'symbol': 'mi', 'icon': '🏁', 'conversion_factor': 0.000621371, 'is_base_unit': False},
            {'name': 'Yard', 'symbol': 'yd', 'icon': '🎯', 'conversion_factor': 1.09361, 'is_base_unit': False},
            {'name': 'Foot', 'symbol': 'ft', 'icon': '👣', 'conversion_factor': 3.28084, 'is_base_unit': False},
            {'name': 'Inch', 'symbol': 'in', 'icon': '📏', 'conversion_factor': 39.3701, 'is_base_unit': False},
            {'name': 'Nautical Mile', 'symbol': 'nmi', 'icon': '⛵', 'conversion_factor': 0.000539957, 'is_base_unit': False},
        ]
    },
    'weight_mass': {
        'name': 'Weight/Mass',
        'icon': '⚖️',
        'units': [
            {'name': 'Kilogram', 'symbol': 'kg', 'icon': '⚖️', 'conversion_factor': 1.0, 'is_base_unit': True},
            {'name': 'Gram', 'symbol': 'g', 'icon': '⚖️', 'conversion_factor': 1000.0, 'is_base_unit': False},
            {'name': 'Milligram', 'symbol': 'mg', 'icon': '⚖️', 'conversion_factor': 1000000.0, 'is_base_unit': False},
            {'name': 'Pound', 'symbol': 'lb', 'icon': '🏋️', 'conversion_factor': 2.20462, 'is_base_unit': False},
            {'name': 'Ounce', 'symbol': 'oz', 'icon': '⚖️', 'conversion_factor': 35.274, 'is_base_unit': False},
            {'name': 'Ton (Metric)', 'symbol': 't', 'icon': '🏗️', 'conversion_factor': 0.001, 'is_base_unit': False},
            {'name': 'Ton (US)', 'symbol': 'ton', 'icon': '🏗️', 'conversion_factor': 0.00110231, 'is_base_unit': False},
            {'name': 'Stone', 'symbol': 'st', 'icon': '🪨', 'conversion_factor': 0.157473, 'is_base_unit': False},
        ]
    },
    'volume': {
        'name': 'Volume',
        'icon': '🧪',
        'units': [
            {'name': 'Liter', 'symbol': 'L', 'icon': '🧪', 'conversion_factor': 1.0, 'is_base_unit': True},
            {'name': 'Milliliter', 'symbol': 'mL', 'icon': '🧪', 'conversion_factor': 1000.0, 'is_base_unit': False},
            {'name': 'Gallon (US)', 'symbol': 'gal', 'icon': '🛢️', 'conversion_factor': 0.264172, 'is_base_unit': False},
            {'name': 'Quart (US)', 'symbol': 'qt', 'icon': '🛢️', 'conversion_factor': 1.05669, 'is_base_unit': False},
            {'name': 'Pint (US)', 'symbol': 'pt', 'icon': '🛢️', 'conversion_factor': 2.11338, 'is_base_unit': False},
            {'name': 'Cup (US)', 'symbol': 'cup', 'icon': '☕', 'conversion_factor': 4.22675, 'is_base_unit': False},
            {'name': 'Cubic Meter', 'symbol': 'm³', 'icon': '📦', 'conversion_factor': 0.001, 'is_base_unit': False},
            {'name': 'Cubic Foot', 'symbol': 'ft³', 'icon': '📦', 'conversion_factor': 0.0353147, 'is_base_unit': False},
            {'name': 'Gallon (UK)', 'symbol': 'gal (UK)', 'icon': '🛢️', 'conversion_factor': 0.219969, 'is_base_unit': False},
        ]
    },
    'energy': {
        'name': 'Energy',
        'icon': '⚡',
        'units': [
            {'name': 'Joule', 'symbol': 'J', 'icon': '⚡', 'conversion_factor': 1.0, 'is_base_unit': True},
            {'name': 'Kilojoule', 'symbol': 'kJ', 'icon': '⚡', 'conversion_factor': 0.001, 'is_base_unit': False},
            {'name': 'Calorie', 'symbol': 'cal', 'icon': '🔥', 'conversion_factor': 0.239006, 'is_base_unit': False},
            {'name': 'Kilocalorie', 'symbol': 'kcal', 'icon': '🔥', 'conversion_factor': 0.000239006, 'is_base_unit': False},
            {'name': 'Watt-hour', 'symbol': 'Wh', 'icon': '💡', 'conversion_factor': 0.000277778, 'is_base_unit': False},
            {'name': 'Kilowatt-hour', 'symbol': 'kWh', 'icon': '💡', 'conversion_factor': 0.000000278, 'is_base_unit': False},  # Rounded to 10 decimal places
            {'name': 'Megawatt-hour', 'symbol': 'MWh', 'icon': '💡', 'conversion_factor': 0.000000000278, 'is_base_unit': False},  # Rounded to 10 decimal places
            {'name': 'Gigawatt-hour', 'symbol': 'GWh', 'icon': '💡', 'conversion_factor': 0.000000000000278, 'is_base_unit': False},  # Rounded to 10 decimal places
            {'name': 'British Thermal Unit', 'symbol': 'Btu', 'icon': '🔥', 'conversion_factor': 0.000947817, 'is_base_unit': False},
            {'name': 'Therm', 'symbol': 'therm', 'icon': '🔥', 'conversion_factor': 0.000009478, 'is_base_unit': False},
            {'name': 'Electronvolt', 'symbol': 'eV', 'icon': '⚛️', 'conversion_factor': 6241500000.0, 'is_base_unit': False},  # 6.2415e+18 converted
            {'name': 'Gigajoule', 'symbol': 'GJ', 'icon': '⚡', 'conversion_factor': 0.000000001, 'is_base_unit': False},
        ]
    },
    'cooling': {
        'name': 'Cooling',
        'icon': '❄️',
        'units': [
            {'name': 'Ton of Refrigeration Hour', 'symbol': 'TRh', 'icon': '❄️', 'conversion_factor': 1.0, 'is_base_unit': True},
        ]
    },
    'temperature': {
        'name': 'Temperature',
        'icon': '🌡️',
        'units': [
            {'name': 'Celsius', 'symbol': '°C', 'icon': '🌡️', 'conversion_factor': 1.0, 'is_base_unit': True},
            {'name': 'Fahrenheit', 'symbol': '°F', 'icon': '🌡️', 'conversion_factor': 1.0, 'is_base_unit': False},
            {'name': 'Kelvin', 'symbol': 'K', 'icon': '🌡️', 'conversion_factor': 1.0, 'is_base_unit': False},
            {'name': 'Rankine', 'symbol': '°R', 'icon': '🌡️', 'conversion_factor': 1.0, 'is_base_unit': False},
            {'name': 'Réaumur', 'symbol': '°Ré', 'icon': '🌡️', 'conversion_factor': 1.0, 'is_base_unit': False},
        ]
    },
    'area': {
        'name': 'Area',
        'icon': '📐',
        'units': [
            {'name': 'Square Meter', 'symbol': 'm²', 'icon': '📐', 'conversion_factor': 1.0, 'is_base_unit': True},
            {'name': 'Square Kilometer', 'symbol': 'km²', 'icon': '📐', 'conversion_factor': 0.000001, 'is_base_unit': False},
            {'name': 'Square Mile', 'symbol': 'mi²', 'icon': '📐', 'conversion_factor': 0.000000386102, 'is_base_unit': False},
            {'name': 'Square Yard', 'symbol': 'yd²', 'icon': '📐', 'conversion_factor': 1.19599, 'is_base_unit': False},
            {'name': 'Square Foot', 'symbol': 'ft²', 'icon': '📐', 'conversion_factor': 10.7639, 'is_base_unit': False},
            {'name': 'Square Inch', 'symbol': 'in²', 'icon': '📐', 'conversion_factor': 1550.0, 'is_base_unit': False},
            {'name': 'Acre', 'symbol': 'ac', 'icon': '🌾', 'conversion_factor': 0.000247105, 'is_base_unit': False},
            {'name': 'Hectare', 'symbol': 'ha', 'icon': '🌾', 'conversion_factor': 0.0001, 'is_base_unit': False},
        ]
    },
    'speed': {
        'name': 'Speed',
        'icon': '🚀',
        'units': [
            {'name': 'Meter/Second', 'symbol': 'm/s', 'icon': '🚀', 'conversion_factor': 1.0, 'is_base_unit': True},
            {'name': 'Kilometer/Hour', 'symbol': 'km/h', 'icon': '🚀', 'conversion_factor': 3.6, 'is_base_unit': False},
            {'name': 'Mile/Hour', 'symbol': 'mph', 'icon': '🚀', 'conversion_factor': 2.23694, 'is_base_unit': False},
            {'name': 'Knot', 'symbol': 'kn', 'icon': '⛵', 'conversion_factor': 1.94384, 'is_base_unit': False},
            {'name': 'Foot/Second', 'symbol': 'ft/s', 'icon': '🚀', 'conversion_factor': 3.28084, 'is_base_unit': False},
            {'name': 'Mach', 'symbol': 'Mach', 'icon': '✈️', 'conversion_factor': 0.00293858, 'is_base_unit': False},
            {'name': 'Speed of Light', 'symbol': 'c', 'icon': '💫', 'conversion_factor': 0.000000003336, 'is_base_unit': False},  # Rounded to 10 decimal places
        ]
    },
    'time': {
        'name': 'Time',
        'icon': '⏱️',
        'units': [
            {'name': 'Second', 'symbol': 's', 'icon': '⏱️', 'conversion_factor': 1.0, 'is_base_unit': True},
            {'name': 'Minute', 'symbol': 'min', 'icon': '⏱️', 'conversion_factor': 0.0166667, 'is_base_unit': False},
            {'name': 'Hour', 'symbol': 'h', 'icon': '⏱️', 'conversion_factor': 0.000277778, 'is_base_unit': False},
            {'name': 'Day', 'symbol': 'd', 'icon': '📅', 'conversion_factor': 0.0000115741, 'is_base_unit': False},
            {'name': 'Week', 'symbol': 'wk', 'icon': '📅', 'conversion_factor': 0.00000165344, 'is_base_unit': False},
            {'name': 'Month', 'symbol': 'mo', 'icon': '📅', 'conversion_factor': 0.000000380517, 'is_base_unit': False},
            {'name': 'Year', 'symbol': 'yr', 'icon': '📅', 'conversion_factor': 0.0000000316881, 'is_base_unit': False},
            {'name': 'Millisecond', 'symbol': 'ms', 'icon': '⏱️', 'conversion_factor': 1000.0, 'is_base_unit': False},
            {'name': 'Microsecond', 'symbol': 'µs', 'icon': '⏱️', 'conversion_factor': 1000000.0, 'is_base_unit': False},
        ]
    },

}


class Command(BaseCommand):
    help = 'Seed conversion data into the database'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('STARTING CONVERSION DATA SEEDING'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        
        # Delete existing data
        count = Unit.objects.count()
        if count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'{count} units already exist. Existing units will be updated or reused.'
                )
            )
        
        self.stdout.write('\n' + '-' * 40)
        self.stdout.write('Creating new conversion data...')
        self.stdout.write('-' * 40)
        
        total_units = 0
        
        for category_key, category_data in CONVERSION_DATA.items():
            self.stdout.write(f'\n📂 Category: {category_data["name"]} ({category_key})')
            self.stdout.write(f'   Icon: {category_data["icon"]}')
            
            # Create parent unit (category)
            parent, created = Unit.objects.get_or_create(
                parent=None,
                category=category_data['name'],
                name=category_data['name'],
                defaults={
                    'symbol': category_key,
                    'icon': category_data['icon'],
                    'conversion_factor': 1.0,
                    'is_base_unit': False
                }
            )
            
            if created:
                self.stdout.write(self.style.SUCCESS(f'   ✓ Created category: {parent.name}'))
            else:
                self.stdout.write(f'   ℹ️ Category already exists: {parent.name}')
            
            # Create child units
            unit_count = 0
            for unit_data in category_data['units']:
                try:
                    unit, created = Unit.objects.get_or_create(
                        parent=parent,
                        name=unit_data['name'],
                        defaults={
                            'category': category_data['name'],
                            'symbol': unit_data['symbol'],
                            'icon': unit_data.get('icon', category_data['icon']),
                            'conversion_factor': float(unit_data['conversion_factor']),
                            'is_base_unit': unit_data.get('is_base_unit', False)
                        }
                    )
                    
                    if created:
                        unit_count += 1
                        self.stdout.write(f'   ✓ Added: {unit.name} ({unit.symbol}) - Factor: {unit.conversion_factor}')
                    else:
                        # Update existing unit
                        unit.symbol = unit_data['symbol']
                        unit.icon = unit_data.get('icon', category_data['icon'])
                        unit.conversion_factor = float(unit_data['conversion_factor'])
                        unit.is_base_unit = unit_data.get('is_base_unit', False)
                        unit.category = category_data['name']
                        unit.save()
                        self.stdout.write(f'   🔄 Updated: {unit.name} ({unit.symbol})')
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'   ❌ Error adding {unit_data["name"]}: {str(e)}'))
            
            total_units += unit_count
            self.stdout.write(f'   📊 Total units in {category_data["name"]}: {len(category_data["units"])}')
        
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('SEEDING COMPLETED SUCCESSFULLY!'))
        self.stdout.write('=' * 60)
        self.stdout.write(f'\n✅ Total units created: {total_units}')
        self.stdout.write(f'✅ Total categories: {len(CONVERSION_DATA)}')
        
        # Print summary
        self.stdout.write('\n📊 SUMMARY:')
        self.stdout.write('-' * 40)
        for category_key, category_data in CONVERSION_DATA.items():
            count = Unit.objects.filter(
                parent__isnull=False,
                category=category_data['name']
            ).count()
            self.stdout.write(f'   {category_data["icon"]} {category_data["name"]}: {count} units')
        
        self.stdout.write('\n' + '=' * 60)