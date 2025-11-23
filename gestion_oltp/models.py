# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class Client(models.Model):
    client_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    sector = models.CharField(max_length=50, blank=True, null=True)
    contact_email = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'project_mgmt"."client'


class Defect(models.Model):
    defect_id = models.AutoField(primary_key=True)
    project = models.ForeignKey('Project', models.DO_NOTHING)
    task = models.ForeignKey('Task', models.DO_NOTHING, blank=True, null=True)
    detected_by = models.ForeignKey('Employee', models.DO_NOTHING, blank=True, null=True)
    resolved_by = models.ForeignKey('Employee', models.DO_NOTHING, related_name='defect_resolved_by_set', blank=True, null=True)
    detected_date = models.DateField()
    resolved_date = models.DateField(blank=True, null=True)
    description = models.TextField(blank=True, null=True)
    severity = models.CharField(max_length=20, blank=True, null=True)
    status = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'project_mgmt"."defect'


class Employee(models.Model):
    employee_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=100)
    role = models.CharField(max_length=50, blank=True, null=True)
    cost_per_hour = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    available_hours_per_week = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        managed = False
        db_table = 'project_mgmt"."employee'


class Project(models.Model):
    project_id = models.AutoField(primary_key=True)
    client = models.ForeignKey(Client, models.DO_NOTHING)
    name = models.CharField(max_length=100)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)
    budget = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    status = models.CharField(max_length=20, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'project_mgmt"."project'


class Resource(models.Model):
    resource_id = models.AutoField(primary_key=True)
    project = models.ForeignKey(Project, models.DO_NOTHING)
    name = models.CharField(max_length=100, blank=True, null=True)
    type = models.CharField(max_length=50, blank=True, null=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    start_date = models.DateField(blank=True, null=True)
    end_date = models.DateField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'project_mgmt"."resource'


class Risk(models.Model):
    risk_id = models.AutoField(primary_key=True)
    project = models.ForeignKey(Project, models.DO_NOTHING)
    description = models.TextField(blank=True, null=True)
    probability = models.DecimalField(max_digits=3, decimal_places=2, blank=True, null=True)
    impact_score = models.IntegerField(blank=True, null=True)
    status = models.CharField(max_length=20, blank=True, null=True)
    detected_date = models.DateField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'project_mgmt"."risk'


class Task(models.Model):
    task_id = models.AutoField(primary_key=True)
    project = models.ForeignKey(Project, models.DO_NOTHING)
    name = models.CharField(max_length=100, blank=True, null=True)
    assigned_to = models.ForeignKey(Employee, models.DO_NOTHING, db_column='assigned_to', blank=True, null=True)
    planned_start = models.DateField(blank=True, null=True)
    planned_end = models.DateField(blank=True, null=True)
    actual_start = models.DateField(blank=True, null=True)
    actual_end = models.DateField(blank=True, null=True)
    percent_complete = models.IntegerField(blank=True, null=True)
    parent_task = models.ForeignKey('self', models.DO_NOTHING, db_column='parent_task', blank=True, null=True)
    planned_hours = models.DecimalField(max_digits=7, decimal_places=2, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'project_mgmt"."task'


class TimeEntry(models.Model):
    entry_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(Employee, models.DO_NOTHING)
    task = models.ForeignKey(Task, models.DO_NOTHING)
    entry_timestamp = models.DateTimeField()
    hours_worked = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    activity_type = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'project_mgmt"."time_entry'

