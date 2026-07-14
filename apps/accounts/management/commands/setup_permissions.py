from django.core.management import BaseCommand
from apps.accounts.models.permission import Permissions
from apps.accounts.models.role import Role


class Command(BaseCommand):
    help = "Setup default permissions and roles for BRSR"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Starting BRSR role setup...'))

        # Step 1: Create Permissions (keep existing)
        self.create_permissions()

        # Step 2: Create All BRSR Roles with Permissions
        self.create_roles()

        self.stdout.write(self.style.SUCCESS('\n✓ BRSR role setup completed successfully!'))

    def create_permissions(self):
        """Create all GRI system permissions (keep existing)"""
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
        """Create all BRSR roles and assign permissions"""
        self.stdout.write('\n👥 Creating BRSR roles...')
        
        # System Administrator
        self.create_system_admin_role()
        
        # ESG Core Team Roles
        self.create_esg_chair_role()
        self.create_esg_head_role()
        self.create_esg_coord_role()
        
        # Department Roles
        self.create_dept_approver_role()
        self.create_dept_user_role()
        
        # Plant Roles
        self.create_plant_coord_role()
        
        # Auditor Roles
        self.create_auditor_role()
        
        # Executive Viewer Roles
        self.create_exec_view_role()
        
        # Keep existing roles for backward compatibility
        self.create_superadmin_role()
        self.create_companyadmin_role()
        self.create_companyuser_role()

    def create_system_admin_role(self):
        """Create System Administrator role with full permissions"""
        role, created = Role.objects.get_or_create(
            role_code='ADMIN',
            defaults={
                'role_name': 'System Administrator',
                'description': 'Configures users, roles, plants, departments, master data and workflow rules',
                'is_active': True
            }
        )
        
        # ADMIN gets ALL permissions
        all_perms = Permissions.objects.all()
        role.permissions.set(all_perms)
        self.stdout.write(f'  ✓ {"Created" if created else "Updated"}: ADMIN role ({all_perms.count()} permissions)')

    def create_esg_chair_role(self):
        """Create ESG Chairperson role"""
        role, created = Role.objects.get_or_create(
            role_code='ESG-CHAIR',
            defaults={
                'role_name': 'ESG Core Team — Chairperson / CXO Sponsor',
                'description': 'Overall sustainability sponsor; final sign-off before BRSR submission to Board',
                'is_active': True
            }
        )
        
        perm_codes = [
            # View and approve access
            'ACCESS_COMPANY_MODULE',
            'VIEW_COMPANY',
            'ACCESS_ORGANIZATIONS_MODULE',
            'ACCESS_USER_MODULE',
            'VIEW_USER',
        ]
        perms = Permissions.objects.filter(code__in=perm_codes)
        role.permissions.set(perms)
        self.stdout.write(f'  ✓ {"Created" if created else "Updated"}: ESG-CHAIR role ({perms.count()} permissions)')

    def create_esg_head_role(self):
        """Create ESG Head role"""
        role, created = Role.objects.get_or_create(
            role_code='ESG-HEAD',
            defaults={
                'role_name': 'ESG Core Team — Head / Manager',
                'description': 'Owns the end-to-end BRSR report; consolidates and reviews department data',
                'is_active': True
            }
        )
        
        perm_codes = [
            'ACCESS_COMPANY_MODULE',
            'EDIT_COMPANY',
            'VIEW_COMPANY',
            'ACCESS_ORGANIZATIONS_MODULE',
            'ACCESS_USER_MODULE',
            'VIEW_USER',
        ]
        perms = Permissions.objects.filter(code__in=perm_codes)
        role.permissions.set(perms)
        self.stdout.write(f'  ✓ {"Created" if created else "Updated"}: ESG-HEAD role ({perms.count()} permissions)')

    def create_esg_coord_role(self):
        """Create ESG Coordinator role"""
        role, created = Role.objects.get_or_create(
            role_code='ESG-COORD',
            defaults={
                'role_name': 'ESG Core Team — Coordinator',
                'description': 'Day-to-day data collection follow-up, reminders, and consolidation support',
                'is_active': True
            }
        )
        
        perm_codes = [
            'ACCESS_COMPANY_MODULE',
            'VIEW_COMPANY',
            'ACCESS_ORGANIZATIONS_MODULE',
            'ACCESS_USER_MODULE',
            'VIEW_USER',
        ]
        perms = Permissions.objects.filter(code__in=perm_codes)
        role.permissions.set(perms)
        self.stdout.write(f'  ✓ {"Created" if created else "Updated"}: ESG-COORD role ({perms.count()} permissions)')

    def create_dept_approver_role(self):
        """Create Department Approver role"""
        role, created = Role.objects.get_or_create(
            role_code='DEPT-APPR',
            defaults={
                'role_name': 'Department Data Reviewer / Approver',
                'description': 'Reviews and approves data submitted by data-entry users within the department',
                'is_active': True
            }
        )
        
        perm_codes = [
            'ACCESS_COMPANY_MODULE',
            'VIEW_COMPANY',
            'ACCESS_ORGANIZATIONS_MODULE',
            'ACCESS_USER_MODULE',
            'VIEW_USER',
        ]
        perms = Permissions.objects.filter(code__in=perm_codes)
        role.permissions.set(perms)
        self.stdout.write(f'  ✓ {"Created" if created else "Updated"}: DEPT-APPR role ({perms.count()} permissions)')

    def create_dept_user_role(self):
        """Create Department User role"""
        role, created = Role.objects.get_or_create(
            role_code='DEPT-USER',
            defaults={
                'role_name': 'Department Data Owner / Contributor',
                'description': 'Enters raw BRSR data points for their department/plant each reporting cycle',
                'is_active': True
            }
        )
        
        perm_codes = [
            'ACCESS_COMPANY_MODULE',
            'VIEW_COMPANY',
            'ACCESS_ORGANIZATIONS_MODULE',
            'ACCESS_USER_MODULE',
            'VIEW_USER',
        ]
        perms = Permissions.objects.filter(code__in=perm_codes)
        role.permissions.set(perms)
        self.stdout.write(f'  ✓ {"Created" if created else "Updated"}: DEPT-USER role ({perms.count()} permissions)')

    def create_plant_coord_role(self):
        """Create Plant Coordinator role"""
        role, created = Role.objects.get_or_create(
            role_code='PLANT-COORD',
            defaults={
                'role_name': 'Plant / Site Coordinator',
                'description': 'Single point of contact for all BRSR data originating from a specific plant',
                'is_active': True
            }
        )
        
        perm_codes = [
            'ACCESS_COMPANY_MODULE',
            'VIEW_COMPANY',
            'ACCESS_ORGANIZATIONS_MODULE',
            'ACCESS_USER_MODULE',
            'VIEW_USER',
        ]
        perms = Permissions.objects.filter(code__in=perm_codes)
        role.permissions.set(perms)
        self.stdout.write(f'  ✓ {"Created" if created else "Updated"}: PLANT-COORD role ({perms.count()} permissions)')

    def create_auditor_role(self):
        """Create Auditor role"""
        role, created = Role.objects.get_or_create(
            role_code='AUDIT',
            defaults={
                'role_name': 'Internal / External Auditor (Assurance Provider)',
                'description': 'Read-only assurance access to verify data and evidence trail before submission',
                'is_active': True
            }
        )
        
        perm_codes = [
            'ACCESS_COMPANY_MODULE',
            'VIEW_COMPANY',
            'ACCESS_ORGANIZATIONS_MODULE',
            'ACCESS_USER_MODULE',
            'VIEW_USER',
        ]
        perms = Permissions.objects.filter(code__in=perm_codes)
        role.permissions.set(perms)
        self.stdout.write(f'  ✓ {"Created" if created else "Updated"}: AUDIT role ({perms.count()} permissions)')

    def create_exec_view_role(self):
        """Create Executive Viewer role"""
        role, created = Role.objects.get_or_create(
            role_code='EXEC-VIEW',
            defaults={
                'role_name': 'Executive / Board Viewer',
                'description': 'Read-only access to final dashboards and reports for leadership visibility',
                'is_active': True
            }
        )
        
        perm_codes = [
            'ACCESS_COMPANY_MODULE',
            'VIEW_COMPANY',
            'ACCESS_ORGANIZATIONS_MODULE',
            'ACCESS_USER_MODULE',
            'VIEW_USER',
        ]
        perms = Permissions.objects.filter(code__in=perm_codes)
        role.permissions.set(perms)
        self.stdout.write(f'  ✓ {"Created" if created else "Updated"}: EXEC-VIEW role ({perms.count()} permissions)')

    # Keep existing roles for backward compatibility
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