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
    FactTimelog, DimEmployee, DimProject, DimTask, FactProgressSnapshot
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
        
        # Obtener la fecha del ÚLTIMO snapshot disponible
        latest_snapshot_date = FactProgressSnapshot.objects.aggregate(
            max_date=Max('date_key')
        )['max_date'] or now().date()

        # Datos Financieros (Budget y Costo Real AC)
        financials = DimProject.objects.annotate(
            bac=Max('factbudget__budget_allocated'), 
            ac=Sum('factbudget__cost_actual')        
        ).values('project_key', 'project_id', 'name', 'bac', 'ac')
        
        fin_map = {p['project_key']: p for p in financials}

        # Datos de Progreso Real (Valor Ganado EV)
        progress_data = DimTask.objects.filter(
            factprogresssnapshot__date_key=latest_snapshot_date
        ).values('project_key').annotate(
            total_planned=Sum('planned_hours'),
            # EV en Horas = Horas Planificadas de la Tarea * % Completado Real de la Tarea
            earned_hours=Sum(F('planned_hours') * F('factprogresssnapshot__percent_complete') / 100.0)
        )

        prog_map = {
            p['project_key']: {
                'planned': p['total_planned'] or 0, 
                'earned': p['earned_hours'] or 0
            } for p in progress_data
        }

        # Combinar y Calcular
        results = []
        for p_key, p_data in fin_map.items():
            budget = p_data['bac'] or 0
            ac = p_data['ac'] or 0
            
            p_prog = prog_map.get(p_key, {'planned': 0, 'earned': 0})
            total_planned = p_prog['planned']
            total_earned = p_prog['earned']

            # % Avance Ponderado del Proyecto = (Horas Ganadas Totales / Horas Planificadas Totales)
            if total_planned > 0:
                percent_complete = total_earned / total_planned
            else:
                percent_complete = 0

            # EV Monetario = Presupuesto Total * % Avance
            ev = budget * percent_complete

            # CV = EV - AC
            cv = ev - ac 
            
            # CPI = EV / AC
            cpi = round(ev / ac, 2) if ac > 0 else 0 
            
            results.append({
                'id': p_data['project_id'], 
                'name': p_data['name'],
                'budget_allocated': budget,
                'actual_cost': ac,
                'cost_variance': round(cv, 2),
                'cpi': cpi
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
        
        # Financiera - CPI GLOBAL
        # Fecha de corte para el avance
        latest_snapshot_date = FactProgressSnapshot.objects.aggregate(
            max_date=Max('date_key')
        )['max_date'] or now().date()

        # Obtener Finanzas Globales (agrupado por proyecto para unir después)
        financials_query = DimProject.objects.annotate(
            bac=Max('factbudget__budget_allocated'),
            ac=Sum('factbudget__cost_actual')
        ).values('project_key', 'bac', 'ac')
        
        fin_map = {
            item['project_key']: {'bac': item['bac'] or 0, 'ac': item['ac'] or 0} 
            for item in financials_query
        }

        # Obtener Progreso Global (filtrado por la fecha más reciente)
        progress_query = DimTask.objects.filter(
            factprogresssnapshot__date_key=latest_snapshot_date
        ).values('project_key').annotate(
            total_planned=Sum('planned_hours'),
            earned_hours=Sum(F('planned_hours') * F('factprogresssnapshot__percent_complete') / 100.0)
        )

        total_ev_global = 0 
        total_ac_global = 0 

        for item in progress_query:
            p_key = item['project_key']
            
            if p_key in fin_map:
                fin_data = fin_map[p_key]
                t_planned = item['total_planned'] or 0
                t_earned = item['earned_hours'] or 0
                
                # Cálculo de EV Individual
                pct_complete = (t_earned / t_planned) if t_planned > 0 else 0
                project_ev = fin_data['bac'] * pct_complete
                
                # Suma a totales globales
                total_ev_global += project_ev
                total_ac_global += fin_data['ac']

        # Cálculo Final CPI Global
        if total_ac_global > 0:
            cpi_global = round(total_ev_global / total_ac_global, 2)
        else:
            cpi_global = 1.0 if total_ev_global > 0 else 0.0

        # Cliente 
        risk_agg = FactRisk.objects.aggregate(
            avg_impact=Avg('impact_score'),
            total_risks=Count('risk_id')
        )
        avg_risk_impact = round(risk_agg['avg_impact'] or 0, 2)

        # Procesos 
        quality_agg = FactDefectSummary.objects.aggregate(
            total_new=Sum('defect_count_new'),
            total_resolved=Sum('defect_count_resolved')
        )
        t_new = quality_agg['total_new'] or 0
        t_res = quality_agg['total_resolved'] or 0
        resolution_rate = round((t_res / t_new) * 100, 1) if t_new > 0 else 100

        # Aprendizaje 
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