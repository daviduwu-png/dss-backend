from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import DashboardKPIViewSet, PredictionViewSet, BSCViewSet

router = DefaultRouter()
router.register(r'mission-kpis', DashboardKPIViewSet, basename='mission-kpis')
router.register(r'predictions', PredictionViewSet, basename='predictions')
router.register(r'bsc', BSCViewSet, basename='bsc')

urlpatterns = [
    path('', include(router.urls)),
]