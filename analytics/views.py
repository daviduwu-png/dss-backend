from django.shortcuts import render
from rest_framework import viewsets
from rest_framework.response import Response
from django.db.models import Sum, Max, F, Avg, Count
from django.utils.timezone import now
from datetime import timedelta
import numpy as np
from scipy.stats import rayleigh

from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import PermissionDenied

# --- IMPORTACIONES PARA DOCUMENTACIÓN ---
from drf_spectacular.utils import extend_schema
from .serializers import (
    DashboardKPISerializer, 
    PredictionInputSerializer, PredictionOutputSerializer,
    BSCResponseSerializer
)

from .models import (
    FactBudget, FactRisk, FactDefectSummary, 
    FactTimelog, DimEmployee, DimProject
)

class DashboardKPIViewSet(viewsets.ViewSet):
    """
    Endpoint para calcular KPIs de alto nivel para el Dashboard de Misión.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses=DashboardKPISerializer(many=True),
        summary="Obtener KPIs de Misión",
        description="Devuelve una lista de proyectos con sus métricas EVM (Budget, Cost, CPI)."
    )
    def list(self, request):
        kpi_data = FactBudget.objects.values(
            'project_key__project_id', 
            'project_key__name'        
        ).annotate(
            total_budget=Max('budget_allocated'), 
            total_ac=Sum('cost_actual')
        ).order_by('project_key__name')

        results = []
        for item in kpi_data:
            budget = item['total_budget'] or 0
            ac = item['total_ac'] or 0
            cv = budget - ac 
            
            results.append({
                'id': item['project_key__project_id'],
                'name': item['project_key__name'],
                'budget_allocated': budget,
                'actual_cost': ac,
                'cost_variance': cv,
                'cpi': round(budget / ac, 2) if ac > 0 else 0 
            })

        return Response(results)
    

class PredictionViewSet(viewsets.ViewSet):
    """
    Endpoint para simulación predictiva de defectos.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(
        request=PredictionInputSerializer,
        responses=PredictionOutputSerializer,
        summary="Generar Predicción Rayleigh",
        description="Simula la curva de defectos basada en parámetros de entrada. Restringido a Project Managers."
    )
    @action(detail=False, methods=['post'])
    def predict_defects(self, request):
        is_manager = request.user.groups.filter(name='Project Managers').exists()
        
        if not is_manager and not request.user.is_superuser:
            raise PermissionDenied(
                detail="Acceso denegado: Esta herramienta es exclusiva para el rol de 'Project Managers'."
            )

        input_serializer = PredictionInputSerializer(data=request.data)
        input_serializer.is_valid(raise_exception=True)
        data = input_serializer.validated_data
        
        duration = data['estimated_duration']
        peak_time = data['peak_month']
        total_volume = data['total_defects_estimate']

        x_timeline = np.linspace(0, duration, num=duration+1)
        y_pdf = rayleigh.pdf(x_timeline, scale=peak_time)
        predicted_defects = y_pdf * total_volume * (duration / peak_time)
        
        chart_data = []
        for month, defects in zip(x_timeline, predicted_defects):
            chart_data.append({
                "month": int(month),
                "predicted_defects": round(defects, 2)
            })

        return Response({
            "input_params": data,
            "chart_data": chart_data,
            "message": "Predicción generada exitosamente. Acceso autorizado por Grupo."
        })


class BSCViewSet(viewsets.ViewSet):
    """
    Endpoint que consolida los KPIs para el Balanced Scorecard.
    """
    permission_classes = [IsAuthenticated] 

    @extend_schema(
        responses=BSCResponseSerializer,
        summary="Obtener Tablero BSC",
        description="Devuelve los 4 pilares de la visión con sus KPIs calculados."
    )
    @action(detail=False, methods=['get'])
    def dashboard(self, request):
        # 1. Financiera
        fin_agg = FactBudget.objects.aggregate(
            total_budget=Sum('budget_allocated'),
            total_cost=Sum('cost_actual')
        )
        t_budget = fin_agg['total_budget'] or 0
        t_cost = fin_agg['total_cost'] or 0
        cpi_global = round(t_budget / t_cost, 2) if t_cost > 0 else 0

        # 2. Cliente
        risk_agg = FactRisk.objects.aggregate(
            avg_impact=Avg('impact_score'),
            total_risks=Count('risk_id')
        )
        avg_risk_impact = round(risk_agg['avg_impact'] or 0, 2)

        # 3. Procesos
        quality_agg = FactDefectSummary.objects.aggregate(
            total_new=Sum('defect_count_new'),
            total_resolved=Sum('defect_count_resolved')
        )
        t_new = quality_agg['total_new'] or 0
        t_res = quality_agg['total_resolved'] or 0
        resolution_rate = round((t_res / t_new) * 100, 1) if t_new > 0 else 100

        # 4. Aprendizaje
        start_date = now().date() - timedelta(days=30)
        time_agg = FactTimelog.objects.filter(date_key__gte=start_date).aggregate(
            total_worked=Sum('hours_worked')
        )
        total_worked = time_agg['total_worked'] or 0

        emp_agg = DimEmployee.objects.aggregate(total_available=Sum('available_hours_per_week'))
        total_available = emp_agg['total_available'] or 0
        monthly_available = (total_available or 0) * 4
        
        utilization_rate = round((total_worked / monthly_available) * 100, 1) if monthly_available > 0 else 0

        data = {
            "financial": {
                "title": "Financiera",
                "okr": "Liderazgo en Eficiencia",
                "kpis": [
                    {"name": "CPI Global", "value": cpi_global, "target": 1.0, "unit": "Idx"}
                ],
                "status": "success" if cpi_global >= 1 else "warning"
            },
            "customer": {
                "title": "Cliente",
                "okr": "Confianza y Solidez",
                "kpis": [
                    {"name": "Impacto de Riesgo Promedio", "value": avg_risk_impact, "target": 5.0, "unit": "Pts"}
                ],
                "status": "success" if avg_risk_impact < 5 else "warning"
            },
            "internal": {
                "title": "Procesos Internos",
                "okr": "Calidad y Trazabilidad",
                "kpis": [
                    {"name": "Tasa Resolución Defectos", "value": resolution_rate, "target": 90, "unit": "%"}
                ],
                "status": "success" if resolution_rate >= 90 else "error"
            },
            "learning": {
                "title": "Aprendizaje",
                "okr": "Gestión del Conocimiento",
                "kpis": [
                    {"name": "Utilización de Recursos", "value": utilization_rate, "target": 80, "unit": "%"}
                ],
                "status": "success" if utilization_rate >= 80 else "warning"
            }
        }

        return Response(data)