from django.core.management import BaseCommand
from apps.accounts.models.permission import Permissions
from apps.accounts.models.role import Role


class Command(BaseCommand):
    help = "Setup default permissions and roles for GRI"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Starting GRI permission setup...'))

        # Step 1: Create Permissions
        self.create_permissions()

        # Step 2: Create Roles with Permissions
        self.create_roles()

        self.stdout.write(self.style.SUCCESS('\n✓ GRI permission setup completed successfully!'))

    def create_permissions(self):
        """Create all GRI system permissions"""
        self.stdout.write('\n📋 Creating GRI permissions...')
        
        permissions_data = [
            # (code, name, description, permission_type, display_order)

            # COMPANY MODULE
            ('ACCESS_COMPANY_MODULE', 'Access Company Module', 'Can access company module',
             'MODULE_ACCESS', 0),
            ('EDIT_COMPANY', 'Edit Company', 'Can edit company', 
             'EDIT', 1),
            ('VIEW_COMPANY', 'View Company', 'Can view company', 
             'VIEW', 2),

            # Organization Setup
            ('ACCESS_ORGANIZATIONS_MODULE', 'Access Organizations Module', 'Can access organizations module',
             'MODULE_ACCESS', 0),

            # USER MODULE
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
        ]
        
        created_count = 0
        updated_count = 0
        
        for code, name, description, perm_type, display_order in permissions_data:
            perm, created = Permissions.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'description': description,
                    'permission_type': perm_type,
                    'display_order': display_order
                }
            )
            if created:
                created_count += 1
                self.stdout.write(f'  ✓ Created: {code}')
            else:
                # Update existing permissions
                perm.name = name
                perm.description = description
                perm.permission_type = perm_type
                perm.display_order = display_order
                perm.save()
                updated_count += 1
                self.stdout.write(f'  - Updated: {code}')
        
        self.stdout.write(self.style.SUCCESS(f'\n  ✓ Created: {created_count} permissions'))
        self.stdout.write(self.style.WARNING(f'  ⟳ Updated: {updated_count} permissions'))
        self.stdout.write(self.style.SUCCESS(f'  ━ Total: {created_count + updated_count} permissions'))

    def create_roles(self):
        """Create roles and assign permissions"""
        self.stdout.write('\n👥 Creating roles...')
        
        # SUPERADMIN Role
        self.create_superadmin_role()
        
        # COMPANYADMIN Role
        self.create_companyadmin_role()
        
        # COMPANYUSER Role
        self.create_companyuser_role()

    def create_superadmin_role(self):
        """Create SUPERADMIN role with all permissions"""
        role, created = Role.objects.get_or_create(
            role_code='SUPERADMIN',
            defaults={
                'role_name': 'Super Admin',
                'description': 'Super Administrator with full system access to all modules',
                'is_active': True
            }
        )
        
        # SUPERADMIN gets ALL permissions
        all_perms = Permissions.objects.all()
        role.permissions.set(all_perms)
        self.stdout.write(f'  ✓ {"Created" if created else "Updated"}: SUPERADMIN role ({all_perms.count()} permissions)')

    def create_companyadmin_role(self):
        """Create COMPANYADMIN role with company management rights"""
        role, created = Role.objects.get_or_create(
            role_code='COMPANYADMIN',
            defaults={
                'role_name': 'Company Admin',
                'description': 'Company Administrator with company and user management rights',
                'is_active': True
            }
        )
        
        perm_codes = [
            # Company Module - Full access
            'ACCESS_COMPANY_MODULE',
            'EDIT_COMPANY',
            'VIEW_COMPANY',
            
            # Organizations Module
            'ACCESS_ORGANIZATIONS_MODULE',
            
            # User Module - Full access
            'ACCESS_USER_MODULE',
            'CREATE_USER',
            'EDIT_USER',
            'VIEW_USER',
            'DELETE_USER',
        ]
        perms = Permissions.objects.filter(code__in=perm_codes)
        role.permissions.set(perms)
        self.stdout.write(f'  ✓ {"Created" if created else "Updated"}: COMPANYADMIN role ({perms.count()} permissions)')

    def create_companyuser_role(self):
        """Create COMPANYUSER role with view-only access"""
        role, created = Role.objects.get_or_create(
            role_code='COMPANYUSER',
            defaults={
                'role_name': 'Company User',
                'description': 'Company User with view-only access',
                'is_active': True
            }
        )
        
        perm_codes = [
            # Company Module - View only
            'ACCESS_COMPANY_MODULE',
            'VIEW_COMPANY',
            
            # Organizations Module - View only
            'ACCESS_ORGANIZATIONS_MODULE',
            
            # User Module - View only
            'ACCESS_USER_MODULE',
            'VIEW_USER',
        ]
        perms = Permissions.objects.filter(code__in=perm_codes)
        role.permissions.set(perms)
        self.stdout.write(f'  ✓ {"Created" if created else "Updated"}: COMPANYUSER role ({perms.count()} permissions)')