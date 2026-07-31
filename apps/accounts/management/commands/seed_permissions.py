from django.core.management.base import BaseCommand
from apps.accounts.models.permission import Permissions

class Command(BaseCommand):
    help = 'Seeds Permission Master with hierarchical structure'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Starting permission seed...'))
        
        permissions_data = [
            # (code, name, description, permission_type, display_order)

            # COMPANY MODULE
            ('ACCESS_COMPANY_MODULE', 'Access Company Module', 'Can access company module',
             'MODULE_ACCESS', 0),
            ('EDIT_COMPANY', 'Edit Company', 'Can edit company', 
             'EDIT', 1),
            ('VIEW_COMPANY', 'View Company', 'Can view company', 
             'VIEW', 2),

            #Organization Setup
            ('ACCESS_ORGANIZATIONS_MODULE','Access Organizations Module', 'Can access organizations module',
             'MODULE_ACCESS', 0),

            #USER MODULE
            ('ACCESS_USER_MODULE', 'Access User Module', 'Can access user module',
             'MODULE_ACCESS', 0),
            ('CREATE_USER', 'Create User', 'Can create user', 
             'CREATE', 1),
            ('EDIT_USER', 'Edit User', 'Can edit user', 
             'EDIT', 2),
            ('VIEW_USER', 'View User', 'Can view user', 
             'VIEW', 3),
            ('DELETE_USER', 'Delete User', 'Can delete user', 
             'DELETE', 4),

            #BRSR Module
            ('ACCESS_BRSR_MODULE', 'Access BRSR Module', 'Can access BRSR module', 'MODULE_ACCESS', 0),
            ('VIEW_ALL_BRSR_DATA', 'View All BRSR Data', 'Can view all BRSR data', 'VIEW', 1),
        ]

        created = 0
        updated = 0
        
        for code, name, desc, perm_type, order in permissions_data:
            perm, is_created = Permissions.objects.update_or_create(
                code=code,
                defaults={
                    'name': name,
                    'description': desc,
                    'permission_type': perm_type,
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
