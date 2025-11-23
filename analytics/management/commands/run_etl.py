import time
import pandas as pd
import numpy as np
from datetime import datetime
from sqlalchemy import create_engine, text
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = 'Ejecuta el proceso ETL completo para mover y transformar datos de OLTP (project_mgmt) a DSS (project_dss)'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING("Iniciando proceso ETL..."))
        start_total_time = time.time()

        try:
            # 1. Configuración de Motores de Base de Datos
            # Se conectan automáticamente usando las credenciales de settings.py (Neon/Render)
            source_engine = self.get_engine('default')      # Base OLTP
            target_engine = self.get_engine('project_dss')  # Base DWH (DSS)

            # 2. Fase de Extracción
            extracted_data = self.extract_data(source_engine)
            
            # 3. Fase de Transformación y Carga
            if extracted_data:
                self.transform_and_load(extracted_data, target_engine)
                
            duration_total = time.time() - start_total_time
            self.stdout.write(self.style.SUCCESS(f"¡Éxito! Proceso ETL completado en {duration_total:.2f} segundos."))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"ERROR CRÍTICO EN ETL: {e}"))
            import traceback
            traceback.print_exc()

    def get_engine(self, db_alias):
        """Crea un motor SQLAlchemy usando la configuración de Django."""
        db_conf = settings.DATABASES[db_alias]
        # Construye la URI de conexión: postgresql://user:pass@host:port/dbname
        db_url = f"postgresql://{db_conf['USER']}:{db_conf['PASSWORD']}@{db_conf['HOST']}:{db_conf['PORT']}/{db_conf['NAME']}"
        return create_engine(db_url)

    def extract_data(self, engine):
        """Extrae todas las tablas necesarias de la fuente OLTP."""
        self.stdout.write("--- [1/2] Extrayendo datos de OLTP ---")
        
        queries = {
            "client": "SELECT client_id, name, sector FROM project_mgmt.client",
            "employee": "SELECT employee_id, name, role, cost_per_hour, available_hours_per_week FROM project_mgmt.employee",
            "project": "SELECT project_id, name, client_id, status FROM project_mgmt.project",
            "task": "SELECT task_id, project_id, name, planned_hours, percent_complete FROM project_mgmt.task",
            "time_entry": "SELECT employee_id, task_id, entry_timestamp, hours_worked FROM project_mgmt.time_entry",
            "defect": "SELECT project_id, detected_date, resolved_date, status FROM project_mgmt.defect",
            "risk": "SELECT risk_id, project_id, probability, impact_score, detected_date, status FROM project_mgmt.risk",
            "resource": "SELECT resource_id, project_id, type, cost, start_date, end_date FROM project_mgmt.resource"
        }
        
        dataframes = {}
        for name, query in queries.items():
            try:
                dataframes[name] = pd.read_sql(query, engine)
                self.stdout.write(f"   > Extraído {name}: {len(dataframes[name])} filas")
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"Error extrayendo {name}: {e}"))
                return None
        
        # Extracción especial para presupuesto
        try:
            dataframes["project_budget"] = pd.read_sql("SELECT project_id, budget, start_date FROM project_mgmt.project", engine)
            self.stdout.write(f"   > Extraído project_budget: {len(dataframes['project_budget'])} filas")
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error extrayendo budget: {e}"))
            return None
            
        return dataframes

    def transform_and_load(self, data, engine):
        """Realiza la limpieza, transformación y carga en el Data Warehouse."""
        self.stdout.write("\n--- [2/2] Transformando y Cargando en DWH ---")
        
        # A. LIMPIEZA INICIAL (TRUNCATE)
        with engine.connect() as conn:
            self.stdout.write("   > Limpiando tablas DWH existentes...")
            # Se usa CASCADE para limpiar en orden correcto y RESTART IDENTITY para reiniciar contadores
            conn.execute(text("TRUNCATE dwh.fact_timelog, dwh.fact_budget, dwh.fact_defect_summary, dwh.fact_risk, dwh.fact_resource, dwh.fact_progress_snapshot RESTART IDENTITY CASCADE;"))
            conn.execute(text("TRUNCATE dwh.dim_task, dwh.dim_project, dwh.dim_employee, dwh.dim_client, dwh.dim_resource, dwh.dim_status RESTART IDENTITY CASCADE;"))
            conn.commit()

        # B. CARGA DE DIMENSIONES
        
        # 1. Dim Status (Creada manualmente según documentación)
        status_data = [
            ('Planned', 'Proyecto Planeado', 'Project'), ('Active', 'Proyecto Activo', 'Project'),
            ('Completed', 'Proyecto Completado', 'Project'), ('On Hold', 'Proyecto en Pausa', 'Project'),
            ('Open', 'Riesgo Abierto', 'Risk'), ('Closed', 'Riesgo Cerrado', 'Risk'), ('Mitigated', 'Riesgo Mitigado', 'Risk'),
            ('Abierto', 'Defecto Abierto', 'Defect'), ('Resuelto', 'Defecto Resuelto', 'Defect'), ('Cerrado', 'Defecto Cerrado', 'Defect')
        ]
        dim_status = pd.DataFrame(status_data, columns=['status_id', 'description', 'category'])
        dim_status.to_sql('dim_status', engine, schema='dwh', if_exists='append', index=False)
        
        # Recuperar mapa de Status Keys (Surrogate Key)
        dim_status_map = pd.read_sql("SELECT status_key, status_id FROM dwh.dim_status", engine).set_index('status_id')

        # 2. Dim Project
        df_proj = data['project'].copy()
        # Transformación: Reemplazar status texto por status_key
        df_proj = pd.merge(df_proj, dim_status_map, left_on='status', right_on='status_id', how='left')
        df_proj = df_proj[['project_id', 'name', 'client_id', 'status_key']]
        df_proj.to_sql('dim_project', engine, schema='dwh', if_exists='append', index=False)
        
        # 3. Dim Employee
        data['employee'][['employee_id', 'name', 'role', 'available_hours_per_week']].to_sql('dim_employee', engine, schema='dwh', if_exists='append', index=False)
        
        # 4. Dim Client
        df_cli = data['client'][['client_id', 'name', 'sector']].copy()
        df_cli['priority_level'] = None # Campo nuevo en DWH
        df_cli.to_sql('dim_client', engine, schema='dwh', if_exists='append', index=False)
        
        # 5. Dim Resource
        data['resource'][['resource_id', 'type', 'cost', 'start_date', 'end_date']].to_sql('dim_resource', engine, schema='dwh', if_exists='append', index=False)

        # --- MAPAS DE CLAVES SUSTITUTAS (SURROGATE KEYS) ---
        # Consultamos el DWH para saber qué IDs seriales asignó Postgres a cada registro original
        dim_proj_map = pd.read_sql("SELECT project_key, project_id FROM dwh.dim_project", engine).set_index('project_id')
        dim_emp_map = pd.read_sql("SELECT employee_key, employee_id FROM dwh.dim_employee", engine).set_index('employee_id')
        dim_res_map = pd.read_sql("SELECT resource_key, resource_id FROM dwh.dim_resource", engine).set_index('resource_id')

        # 6. Dim Task (Esquema Snowflake: Tarea -> Proyecto)
        df_task = data['task'][['task_id', 'project_id', 'name', 'planned_hours']].copy()
        # Unir con mapa de proyectos para obtener project_key
        df_task = pd.merge(df_task, dim_proj_map, on='project_id', how='left')
        df_task.dropna(subset=['project_key'], inplace=True) # Ignorar tareas huérfanas
        df_task = df_task[['task_id', 'project_key', 'name', 'planned_hours']]
        df_task.to_sql('dim_task', engine, schema='dwh', if_exists='append', index=False)
        
        # Mapa de Task Keys
        dim_task_map = pd.read_sql("SELECT task_key, task_id FROM dwh.dim_task", engine).set_index('task_id')

        self.stdout.write("   > Dimensiones cargadas exitosamente.")

        # C. CARGA DE HECHOS (FACTS)
        
        # 1. Fact Timelog (Horas trabajadas)
        if not data['time_entry'].empty:
            ft = data['time_entry'].copy()
            # Convertir timestamp a fecha (date_key)
            ft['date_key'] = pd.to_datetime(ft['entry_timestamp']).dt.date
            
            # Unir con claves sustitutas
            ft = pd.merge(ft, dim_task_map, on='task_id', how='left')
            ft = pd.merge(ft, dim_emp_map, on='employee_id', how='left')
            
            ft.dropna(subset=['task_key', 'employee_key'], inplace=True)
            
            # Agregación: Sumar horas por día, tarea y empleado
            if not ft.empty:
                ft_agg = ft.groupby(['date_key', 'task_key', 'employee_key'])['hours_worked'].sum().reset_index()
                ft_agg.to_sql('fact_timelog', engine, schema='dwh', if_exists='append', index=False)
                self.stdout.write(f"   > Fact Timelog: {len(ft_agg)} filas")

        # 2. Fact Budget (Costos Reales vs Presupuesto)
        if not data['time_entry'].empty:
            # Calcular costo real = horas * tarifa del empleado
            costs = pd.merge(data['time_entry'], data['task'][['task_id', 'project_id']], on='task_id')
            costs = pd.merge(costs, data['employee'][['employee_id', 'cost_per_hour']], on='employee_id')
            costs['cost_actual'] = costs['hours_worked'] * costs['cost_per_hour']
            costs['date_key'] = pd.to_datetime(costs['entry_timestamp']).dt.date
            
            # Agrupar costos por día y proyecto
            daily_costs = costs.groupby(['date_key', 'project_id'])['cost_actual'].sum().reset_index()
            
            # Obtener presupuestos (se registran en la fecha de inicio del proyecto)
            budgets = data['project_budget'].rename(columns={'start_date': 'date_key', 'budget': 'budget_allocated'})
            budgets['cost_actual'] = 0.0
            
            # Unir ambos flujos de datos (Costos diarios + Presupuesto inicial)
            fb = pd.concat([daily_costs, budgets], ignore_index=True)
            fb = pd.merge(fb, dim_proj_map, on='project_id', how='left')
            fb.dropna(subset=['project_key'], inplace=True)
            fb.fillna(0, inplace=True)
            
            if not fb.empty:
                # Agregación final
                fb_final = fb.groupby(['date_key', 'project_key']).agg({
                    'budget_allocated': 'max', # Max para no sumar duplicados si hay multiples entradas ese dia
                    'cost_actual': 'sum'       # Sumar todos los costos del día
                }).reset_index()
                
                fb_final.to_sql('fact_budget', engine, schema='dwh', if_exists='append', index=False)
                self.stdout.write(f"   > Fact Budget: {len(fb_final)} filas")

        # 3. Fact Defect Summary (Calidad)
        if not data['defect'].empty:
             df_d = data['defect'].copy()
             
             # Defectos Nuevos
             new_d = df_d.groupby(['detected_date', 'project_id']).size().reset_index(name='defect_count_new')
             new_d.rename(columns={'detected_date': 'date_key'}, inplace=True)
             
             # Defectos Resueltos
             res_d = df_d.dropna(subset=['resolved_date']).groupby(['resolved_date', 'project_id']).size().reset_index(name='defect_count_resolved')
             res_d.rename(columns={'resolved_date': 'date_key'}, inplace=True)
             
             # Full Outer Join para combinar días con solo nuevos o solo resueltos
             fact_def = pd.merge(new_d, res_d, on=['date_key', 'project_id'], how='outer')
             fact_def.fillna(0, inplace=True)
             
             # Obtener Project Key
             fact_def = pd.merge(fact_def, dim_proj_map, on='project_id', how='left')
             fact_def.dropna(subset=['project_key'], inplace=True)
             
             if not fact_def.empty:
                 fact_def = fact_def[['date_key', 'project_key', 'defect_count_new', 'defect_count_resolved']]
                 fact_def.to_sql('fact_defect_summary', engine, schema='dwh', if_exists='append', index=False)
                 self.stdout.write(f"   > Fact Defect Summary: {len(fact_def)} filas")

        # 4. Fact Risk (Riesgos)
        if not data['risk'].empty:
            fr = data['risk'].copy()
            fr.rename(columns={'detected_date': 'date_key'}, inplace=True)
            
            fr = pd.merge(fr, dim_proj_map, on='project_id', how='left')
            fr = pd.merge(fr, dim_status_map, left_on='status', right_on='status_id', how='left')
            fr.dropna(subset=['project_key', 'status_key'], inplace=True)
            
            if not fr.empty:
                # Promedios de probabilidad e impacto según la documentación
                fr_agg = fr.groupby(['risk_id', 'date_key', 'project_key', 'status_key'])[['probability', 'impact_score']].mean().reset_index()
                fr_agg.to_sql('fact_risk', engine, schema='dwh', if_exists='append', index=False)
                self.stdout.write(f"   > Fact Risk: {len(fr_agg)} filas")

        # 5. Fact Resource (Costos de Recursos)
        if not data['resource'].empty:
            fres = data['resource'].copy()
            fres.rename(columns={'start_date': 'date_key', 'cost': 'resource_cost'}, inplace=True)
            fres['usage_hours'] = 0 # Placeholder para futura funcionalidad
            
            fres = pd.merge(fres, dim_proj_map, on='project_id', how='left')
            fres = pd.merge(fres, dim_res_map, on='resource_id', how='left')
            fres.dropna(subset=['resource_key', 'project_key'], inplace=True)
            
            if not fres.empty:
                fres_agg = fres.groupby(['resource_key', 'project_key', 'date_key'])[['resource_cost', 'usage_hours']].sum().reset_index()
                fres_agg.to_sql('fact_resource', engine, schema='dwh', if_exists='append', index=False)
                self.stdout.write(f"   > Fact Resource: {len(fres_agg)} filas")

        # 6. Fact Progress Snapshot (Snapshot diario)
        if not data['task'].empty:
            today = datetime.now().date()
            fps = data['task'][['task_id', 'percent_complete']].copy()
            # Unimos con dim_task_map para obtener task_key
            fps = pd.merge(fps, dim_task_map, on='task_id', how='left')
            # Asignamos la fecha de hoy como date_key
            fps['date_key'] = today
            fps.dropna(subset=['task_key'], inplace=True)
            
            if not fps.empty:
                fps = fps[['date_key', 'task_key', 'percent_complete']]
                fps.to_sql('fact_progress_snapshot', engine, schema='dwh', if_exists='append', index=False)
                self.stdout.write(f"   > Fact Progress Snapshot: {len(fps)} filas para el día {today}")