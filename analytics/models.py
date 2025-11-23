# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class DimClient(models.Model):
    client_key = models.AutoField(primary_key=True)
    client_id = models.IntegerField(blank=True, null=True)
    name = models.CharField(max_length=100, blank=True, null=True)
    sector = models.CharField(max_length=50, blank=True, null=True)
    priority_level = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'dwh"."dim_client'


class DimDate(models.Model):
    date_key = models.DateField(primary_key=True)
    year = models.IntegerField(blank=True, null=True)
    quarter = models.IntegerField(blank=True, null=True)
    month = models.IntegerField(blank=True, null=True)
    day = models.IntegerField(blank=True, null=True)
    week = models.IntegerField(blank=True, null=True)
    is_workday = models.BooleanField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'dwh"."dim_date'


class DimEmployee(models.Model):
    employee_key = models.AutoField(primary_key=True)
    employee_id = models.IntegerField(blank=True, null=True)
    name = models.CharField(max_length=100, blank=True, null=True)
    role = models.CharField(max_length=50, blank=True, null=True)
    available_hours_per_week = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'dwh"."dim_employee'


class DimProject(models.Model):
    project_key = models.AutoField(primary_key=True)
    project_id = models.IntegerField(blank=True, null=True)
    name = models.CharField(max_length=100, blank=True, null=True)
    client_id = models.IntegerField(blank=True, null=True)
    status_key = models.ForeignKey('DimStatus', models.DO_NOTHING, db_column='status_key', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'dwh"."dim_project'


class DimResource(models.Model):
    resource_key = models.AutoField(primary_key=True)
    resource_id = models.IntegerField(blank=True, null=True)
    type = models.CharField(max_length=50, blank=True, null=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'dwh"."dim_resource'


class DimStatus(models.Model):
    status_key = models.AutoField(primary_key=True)
    status_id = models.CharField(unique=True, max_length=20, blank=True, null=True)
    description = models.CharField(max_length=100, blank=True, null=True)
    category = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'dwh"."dim_status'


class DimTask(models.Model):
    task_key = models.AutoField(primary_key=True)
    task_id = models.IntegerField(blank=True, null=True)
    project_key = models.ForeignKey(DimProject, models.DO_NOTHING, db_column='project_key', blank=True, null=True)
    name = models.CharField(max_length=100, blank=True, null=True)
    planned_hours = models.DecimalField(max_digits=7, decimal_places=2, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'dwh"."dim_task'


class FactBudget(models.Model):
    pk = models.CompositePrimaryKey('date_key', 'project_key')
    date_key = models.ForeignKey(DimDate, models.DO_NOTHING, db_column='date_key')
    project_key = models.ForeignKey(DimProject, models.DO_NOTHING, db_column='project_key')
    budget_allocated = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    cost_actual = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'dwh"."fact_budget'


class FactDefectSummary(models.Model):
    pk = models.CompositePrimaryKey('date_key', 'project_key')
    date_key = models.ForeignKey(DimDate, models.DO_NOTHING, db_column='date_key')
    project_key = models.ForeignKey(DimProject, models.DO_NOTHING, db_column='project_key')
    defect_count_new = models.IntegerField(blank=True, null=True)
    defect_count_resolved = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'dwh"."fact_defect_summary'


class FactProgressSnapshot(models.Model):
    pk = models.CompositePrimaryKey('date_key', 'task_key')
    date_key = models.ForeignKey(DimDate, models.DO_NOTHING, db_column='date_key')
    task_key = models.ForeignKey(DimTask, models.DO_NOTHING, db_column='task_key')
    percent_complete = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'dwh"."fact_progress_snapshot'


class FactResource(models.Model):
    pk = models.CompositePrimaryKey('resource_key', 'project_key', 'date_key')
    resource_key = models.ForeignKey(DimResource, models.DO_NOTHING, db_column='resource_key')
    project_key = models.ForeignKey(DimProject, models.DO_NOTHING, db_column='project_key')
    date_key = models.ForeignKey(DimDate, models.DO_NOTHING, db_column='date_key')
    resource_cost = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    usage_hours = models.DecimalField(max_digits=7, decimal_places=2, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'dwh"."fact_resource'


class FactRisk(models.Model):
    pk = models.CompositePrimaryKey('risk_id', 'date_key')
    risk_id = models.IntegerField()
    date_key = models.ForeignKey(DimDate, models.DO_NOTHING, db_column='date_key')
    project_key = models.ForeignKey(DimProject, models.DO_NOTHING, db_column='project_key', blank=True, null=True)
    probability = models.DecimalField(max_digits=3, decimal_places=2, blank=True, null=True)
    impact_score = models.IntegerField(blank=True, null=True)
    status_key = models.ForeignKey(DimStatus, models.DO_NOTHING, db_column='status_key', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'dwh"."fact_risk'


class FactTimelog(models.Model):
    pk = models.CompositePrimaryKey('date_key', 'task_key', 'employee_key')
    date_key = models.ForeignKey(DimDate, models.DO_NOTHING, db_column='date_key')
    task_key = models.ForeignKey(DimTask, models.DO_NOTHING, db_column='task_key')
    employee_key = models.ForeignKey(DimEmployee, models.DO_NOTHING, db_column='employee_key')
    hours_worked = models.DecimalField(max_digits=7, decimal_places=2, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'dwh"."fact_timelog'
