from rest_framework import serializers
from .models import Client, Project, Employee, Task, TimeEntry, Risk, Defect, Resource
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class ProjectSerializer(serializers.ModelSerializer):
    budget = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Presupuesto monetario total asignado. Usado en el DWH para calcular el CPI (Cost Performance Index)."
    )
    status = serializers.CharField(
        max_length=20,
        help_text="Estado actual del proyecto (ej. 'Active', 'Planned')."
    )
    
    class Meta:
        model = Project
        fields = '__all__'

class RiskSerializer(serializers.ModelSerializer):
    probability = serializers.DecimalField(
        max_digits=3,
        decimal_places=2,
        help_text="Probabilidad de ocurrencia (0.00 a 1.00). Usado para matriz de riesgos."
    )
    impact_score = serializers.IntegerField(
        help_text="Impacto del riesgo (1-10). Alimenta el KPI de 'Impacto Promedio' en el BSC."
    )
    
    class Meta:
        model = Risk
        fields = '__all__'


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = '__all__'

class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = '__all__'

class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = '__all__'

class TimeEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = TimeEntry
        fields = '__all__'

class DefectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Defect
        fields = '__all__'

class ResourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Resource
        fields = '__all__'

# --- TOKEN PERSONALIZADO ---

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)

        # 1. Datos básicos
        token['username'] = user.username
        token['email'] = user.email
        
        # 2. PERMISOS (Usamos Grupos de Django)
        token['groups'] = list(user.groups.values_list('name', flat=True))
        token['is_superuser'] = user.is_superuser

        return token