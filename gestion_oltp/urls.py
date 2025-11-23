from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# El router genera las URLs para los ViewSets
router = DefaultRouter()
router.register(r'clients', views.ClientViewSet)
router.register(r'projects', views.ProjectViewSet)
router.register(r'employees', views.EmployeeViewSet)
router.register(r'tasks', views.TaskViewSet)
router.register(r'timeentries', views.TimeEntryViewSet)
router.register(r'risks', views.RiskViewSet)
router.register(r'defects', views.DefectViewSet)
router.register(r'resources', views.ResourceViewSet)

urlpatterns = [
    path('', include(router.urls)),
]