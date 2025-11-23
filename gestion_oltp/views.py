from rest_framework import viewsets, permissions
from .models import (
    Client, Project, Employee, Task, 
    TimeEntry, Risk, Defect, Resource
)
from .serializers import (
    ClientSerializer, ProjectSerializer, EmployeeSerializer, TaskSerializer,
    TimeEntrySerializer, RiskSerializer, DefectSerializer, ResourceSerializer
)
from rest_framework_simplejwt.views import TokenObtainPairView
from .serializers import MyTokenObtainPairSerializer

# El permiso IsAuthenticated asegura que solo usuarios logueados puedan usar la API

class ClientViewSet(viewsets.ModelViewSet):
    """
    API endpoint que permite ver o editar Clientes.
    """
    queryset = Client.objects.all().order_by('name')
    serializer_class = ClientSerializer
    permission_classes = [permissions.IsAuthenticated]

class ProjectViewSet(viewsets.ModelViewSet):
    """
    API endpoint que permite ver o editar Proyectos.
    """
    queryset = Project.objects.all().order_by('-start_date')
    serializer_class = ProjectSerializer
    permission_classes = [permissions.IsAuthenticated]

class EmployeeViewSet(viewsets.ModelViewSet):
    """
    API endpoint que permite ver o editar Empleados.
    """
    queryset = Employee.objects.all().order_by('name')
    serializer_class = EmployeeSerializer
    permission_classes = [permissions.IsAuthenticated]

class TaskViewSet(viewsets.ModelViewSet):
    """
    API endpoint que permite ver o editar Tareas.
    """
    queryset = Task.objects.all()
    serializer_class = TaskSerializer
    permission_classes = [permissions.IsAuthenticated]

class TimeEntryViewSet(viewsets.ModelViewSet):
    """
    API endpoint que permite ver o editar Registros de Tiempo.
    """
    queryset = TimeEntry.objects.all().order_by('-entry_timestamp')
    serializer_class = TimeEntrySerializer
    permission_classes = [permissions.IsAuthenticated]

class RiskViewSet(viewsets.ModelViewSet):
    """
    API endpoint que permite ver o editar Riesgos.
    """
    queryset = Risk.objects.all()
    serializer_class = RiskSerializer
    permission_classes = [permissions.IsAuthenticated]

class DefectViewSet(viewsets.ModelViewSet):
    """
    API endpoint que permite ver o editar Defectos.
    """
    queryset = Defect.objects.all().order_by('-detected_date')
    serializer_class = DefectSerializer
    permission_classes = [permissions.IsAuthenticated]

class ResourceViewSet(viewsets.ModelViewSet):
    """
    API endpoint que permite ver o editar Recursos.
    """
    queryset = Resource.objects.all().order_by('name')
    serializer_class = ResourceSerializer
    permission_classes = [permissions.IsAuthenticated]


class MyTokenObtainPairView(TokenObtainPairView):
    serializer_class = MyTokenObtainPairSerializer