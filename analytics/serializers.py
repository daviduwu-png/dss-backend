from rest_framework import serializers
from .models import FactBudget, DimProject


class DashboardKPISerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    budget_allocated = serializers.DecimalField(max_digits=12, decimal_places=2)
    actual_cost = serializers.DecimalField(max_digits=12, decimal_places=2)
    cost_variance = serializers.DecimalField(max_digits=12, decimal_places=2)
    cpi = serializers.FloatField(help_text="Cost Performance Index")


class PredictionInputSerializer(serializers.Serializer):
    estimated_duration = serializers.IntegerField(default=12, help_text="Duración total estimada en meses")
    peak_month = serializers.IntegerField(default=4, help_text="Mes donde ocurre el pico de defectos")
    total_defects_estimate = serializers.IntegerField(default=100, help_text="Volumen total esperado")

class ChartPointSerializer(serializers.Serializer):
    month = serializers.IntegerField()
    predicted_defects = serializers.FloatField()

class PredictionOutputSerializer(serializers.Serializer):
    input_params = serializers.DictField()
    chart_data = ChartPointSerializer(many=True)
    message = serializers.CharField()


class KPIItemSerializer(serializers.Serializer):
    name = serializers.CharField()
    value = serializers.FloatField()
    target = serializers.FloatField()
    unit = serializers.CharField()

class BSCPerspectiveSerializer(serializers.Serializer):
    title = serializers.CharField()
    okr = serializers.CharField()
    kpis = KPIItemSerializer(many=True)
    status = serializers.CharField()

class BSCResponseSerializer(serializers.Serializer):
    financial = BSCPerspectiveSerializer()
    customer = BSCPerspectiveSerializer()
    internal = BSCPerspectiveSerializer()
    learning = BSCPerspectiveSerializer()
