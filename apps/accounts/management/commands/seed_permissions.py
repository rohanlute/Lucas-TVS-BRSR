from django.core.management.base import BaseCommand
from apps.accounts.models.permission import Permissions

class Command(BaseCommand):
    help = 'Seeds Permission Master with hierarchical structure'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Starting permission seed...'))
        
        permissions_data = [
            # (code, name, description, permission_type, module_name, display_order)

            # COMPANY MODULE
            ('ACCESS_COMPANY_MODULE', 'Access Company Module', 'Can access company module', 'MODULE_ACCESS', 'Company', 0),
            ('EDIT_COMPANY', 'Edit Company', 'Can edit company', 'EDIT', 'Company', 1),
            ('VIEW_COMPANY', 'View Company', 'Can view company', 'VIEW', 'Company', 2),

            # Organization Setup
            ('ACCESS_ORGANIZATIONS_MODULE', 'Access Organizations Module', 'Can access organizations module', 'MODULE_ACCESS', 'Organization', 0),

            # USER MODULE
            ('ACCESS_USER_MODULE', 'Access User Module', 'Can access user module', 'MODULE_ACCESS', 'User', 0),
            ('CREATE_USER', 'Create User', 'Can create user', 'CREATE', 'User', 1),
            ('EDIT_USER', 'Edit User', 'Can edit user', 'EDIT', 'User', 2),
            ('VIEW_USER', 'View User', 'Can view user', 'VIEW', 'User', 3),
            ('DELETE_USER', 'Delete User', 'Can delete user', 'DELETE', 'User', 4),

            # BRSR Module
            ('ACCESS_BRSR_MODULE', 'Access BRSR Module', 'Can access BRSR module', 'MODULE_ACCESS', 'BRSR', 0),
            ('VIEW_ALL_BRSR_DATA', 'View All BRSR Data', 'Can view all BRSR data', 'VIEW', 'BRSR', 1),
            ('CAN_ASSIGN_QUESTIONS', 'Can Assign Questions', 'Can assign questions to users', 'ASSIGN', 'BRSR', 2),
            ('VIEW_BRSR_ASSIGNMENT_DASHBOARD', 'View Assignment Dashboard', 'View all BRSR assignments and their status', 'VIEW', 'BRSR', 3),
            ('VIEW_BRSR_APPROVAL_DASHBOARD', 'View Approval Dashboard', 'View BRSR assignments pending for review and approval', 'VIEW', 'BRSR', 4),
            
            # Goal Module
            ('ACCESS_GOAL_MODULE', 'Access Goal Module', 'Can access goal module', 'MODULE_ACCESS', 'Goal', 0),
            
            # Emission Module
            ('ACCESS_EMISSION_MODULE', 'Access Emission Module', 'Can access emission module', 'MODULE_ACCESS', 'Emission', 0),
            ('VIEW_EMISSION_DASHBOARD', 'View Emission Dashboard', 'View emission dashboard', 'VIEW', 'Emission', 1),
            ('ACCESS_SCOPE_DATA_ENTRY', 'Access Scope Data Entry', 'Can access scope data entry', 'VIEW', 'Emission', 2),
            ('VIEW_ASSIGNMENT_DASHBOARD', 'View Assignment Dashboard', 'view assignment dashboard', 'VIEW', 'Emission', 3),
            ('VIEW_EMISSION_REPORT', 'View Emission Report', 'View Emission Report', 'VIEW', 'Emission', 4),
        ]

        created = 0
        updated = 0
        
        # Unpack all 6 values (code, name, desc, permission_type, module_name, order)
        for code, name, desc, permission_type, module_name, order in permissions_data:
            perm, is_created = Permissions.objects.update_or_create(
                code=code,
                defaults={
                    'name': name,
                    'description': desc,
                    'permission_type': permission_type,  # This should be 'MODULE_ACCESS', 'VIEW', 'EDIT', etc.
                    'module_name': module_name,          # This should be 'Company', 'BRSR', 'User', etc.
                    'display_order': order
                }
            )
            if is_created:
                created += 1
                self.stdout.write(self.style.SUCCESS(f'✓ Created: {code}'))
            else:
                updated += 1
                self.stdout.write(self.style.WARNING(f'⟳ Updated: {code}'))
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ Created: {created}'))
        self.stdout.write(self.style.WARNING(f'⟳ Updated: {updated}'))
        self.stdout.write(self.style.SUCCESS(f'━ Total: {created + updated}\n'))