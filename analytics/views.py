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
    FactTimelog, DimEmployee, DimProject, 
    DimTask, FactProgressSnapshot
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
        try:
            # 1. Determinar la fecha de corte (último snapshot o hoy)
            try:
                latest_snapshot_date = FactProgressSnapshot.objects.aggregate(
                    max_date=Max('date_key')
                )['max_date'] or now().date()
            except Exception:
                latest_snapshot_date = now().date()

            # 2. Obtener datos financieros (Presupuesto y Costo Real)
            # CORRECCIÓN: Se agrega '_set' a 'factbudget' para acceder a la relación inversa correctamente.
            financials = DimProject.objects.annotate(
                bac=Max('factbudget_set__budget_allocated'),
                ac=Sum('factbudget_set__cost_actual')
            ).values('project_key', 'project_id', 'name', 'bac', 'ac')
            
            # Crear mapa para acceso rápido por ID de proyecto
            fin_map = {p['project_key']: p for p in financials}

            # 3. Obtener Tareas y Progreso para calcular EV (Earned Value)
            tasks = DimTask.objects.values('task_key', 'project_key', 'planned_hours')
            
            snapshots = FactProgressSnapshot.objects.filter(
                date_key=latest_snapshot_date
            ).values('task_key', 'percent_complete')
            
            snapshot_map = {s['task_key']: s['percent_complete'] for s in snapshots}

            # Calcular progreso ponderado por proyecto
            project_progress = {}

            for task in tasks:
                p_key = task['project_key']
                t_key = task['task_key']
                planned = float(task['planned_hours'] or 0)
                
                pct = snapshot_map.get(t_key, 0)
                
                # EV parcial de la tarea = Horas Planeadas * % Completado
                earned = planned * (pct / 100.0)

                if p_key not in project_progress:
                    project_progress[p_key] = {'planned': 0.0, 'earned': 0.0}
                
                project_progress[p_key]['planned'] += planned
                project_progress[p_key]['earned'] += earned

            # 4. Consolidar Resultados y Calcular KPIs
            results = []
            for p_key, p_data in fin_map.items():
                budget = float(p_data['bac'] or 0)
                ac = float(p_data['ac'] or 0)
                
                prog = project_progress.get(p_key, {'planned': 0.0, 'earned': 0.0})
                total_planned = prog['planned']
                total_earned = prog['earned']

                # CORRECCIÓN: Protección contra división por cero si no hay horas planeadas
                if total_planned > 0:
                    percent_complete = total_earned / total_planned
                else:
                    # Si no hay tareas con horas estimadas, asumimos 0 avance para ser conservadores
                    percent_complete = 0.0

                # Valor Ganado (EV) monetario
                ev = budget * percent_complete

                # Variación de Costo (CV) y Índice de Rendimiento de Costo (CPI)
                cv = ev - ac 
                
                # Si AC es 0, el CPI es 1 (rendimiento perfecto) o 0 si no hay avance.
                if ac > 0:
                    cpi = round(ev / ac, 2)
                else:
                    cpi = 1.0 if ev > 0 else 0.0
                
                results.append({
                    'id': p_data['project_id'], 
                    'name': p_data['name'],
                    'budget_allocated': budget,
                    'actual_cost': ac,
                    'cost_variance': round(cv, 2),
                    'cpi': cpi
                })

            return Response(results)

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({"error": str(e)}, status=500)
    

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
        try:
            
            try:
                latest_snapshot_date = FactProgressSnapshot.objects.aggregate(
                    max_date=Max('date_key')
                )['max_date'] or now().date()
            except Exception:
                latest_snapshot_date = now().date()

            
            financials_query = DimProject.objects.annotate(
                bac=Max('factbudget__budget_allocated'),
                ac=Sum('factbudget__cost_actual')
            ).values('project_key', 'bac', 'ac')
            
            fin_map = {p['project_key']: p for p in financials_query}

            
            tasks = DimTask.objects.values('task_key', 'project_key', 'planned_hours')
            snapshots = FactProgressSnapshot.objects.filter(
                date_key=latest_snapshot_date
            ).values('task_key', 'percent_complete')
            
            snapshot_map = {s['task_key']: s['percent_complete'] for s in snapshots}

            # Calcular EV Global Acumulando Proyectos
            total_ev_global = 0.0
            total_ac_global = 0.0
            
            
            project_hours = {}

            
            for task in tasks:
                p_key = task['project_key']
                t_key = task['task_key']
                planned = float(task['planned_hours'] or 0)
                pct = snapshot_map.get(t_key, 0)
                earned = planned * (pct / 100.0)

                if p_key not in project_hours:
                    project_hours[p_key] = {'planned': 0.0, 'earned': 0.0}
                
                project_hours[p_key]['planned'] += planned
                project_hours[p_key]['earned'] += earned

            # Calcular EV monetario por proyecto y sumar al global
            for p_key, fin_data in fin_map.items():
                bac = float(fin_data['bac'] or 0)
                ac = float(fin_data['ac'] or 0)
                
                total_ac_global += ac
                
                phoda = project_hours.get(p_key, {'planned': 0.0, 'earned': 0.0})
                t_planned = phoda['planned']
                t_earned = phoda['earned']
                
                if t_planned > 0:
                    pct_proj = t_earned / t_planned
                else:
                    pct_proj = 0.0
                
                ev_proj = bac * pct_proj
                total_ev_global += ev_proj

            # Cálculo Final CPI Global
            if total_ac_global > 0:
                cpi_global = round(total_ev_global / total_ac_global, 2)
            else:
                cpi_global = 1.0 if total_ev_global > 0 else 0.0

            
            risk_agg = FactRisk.objects.aggregate(
                avg_impact=Avg('impact_score')
            )
            avg_risk_impact = round(risk_agg['avg_impact'] or 0, 2)

          
            quality_agg = FactDefectSummary.objects.aggregate(
                total_new=Sum('defect_count_new'),
                total_resolved=Sum('defect_count_resolved')
            )
            t_new = quality_agg['total_new'] or 0
            t_res = quality_agg['total_resolved'] or 0
            resolution_rate = round((t_res / t_new) * 100, 1) if t_new > 0 else 100

        
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

        except Exception as e:
            import traceback
            traceback.print_exc()
            return Response({"error": str(e)}, status=500)