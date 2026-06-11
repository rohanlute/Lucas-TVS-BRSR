from rest_framework import serializers

from .models import User, Role


class RoleSerializer(serializers.ModelSerializer):

    class Meta:
        model = Role
        fields = [
            'id',
            'role_code',
            'role_name'
        ]


class UserSerializer(serializers.ModelSerializer):

    role = RoleSerializer(read_only=True)

    class Meta:
        model = User
        fields = [
            'id',
            'username',
            'first_name',
            'last_name',
            'email',
            'mobile_number',
            'employee_code',
            'role',
            'company',
            'is_active'
        ]