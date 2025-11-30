import random
from datetime import datetime, timedelta
from faker import Faker
from django.core.management.base import BaseCommand
from django.db import connection # Usamos la conexión directa de Django

# Configuración de Faker
fake = Faker('es_ES')

# --- PARÁMETROS DE GENERACIÓN [cite: 246] ---
NUM_CLIENTS = 20
NUM_EMPLOYEES = 50
NUM_PROJECTS = 40
AVG_TASKS_PER_PROJECT = 15
AVG_TIME_ENTRIES_PER_TASK = 25
NUM_RESOURCES = 30

# --- DATOS DE DOMINIO [cite: 254] ---
SECTORS = ['Tecnología', 'Finanzas', 'Salud', 'Retail', 'Educación', 'Gobierno']
ROLES = {
    "Project Manager": (80, 120),
    "Senior Developer": (70, 100),
    "Developer": (40, 65),
    "QA Tester": (35, 60),
    "Business Analyst": (60, 90),
    "UI/UX Designer": (50, 80)
}
PROJECT_STATUSES = ['Planned', 'Active', 'Completed', 'On Hold']
RISK_STATUSES = ['Open', 'Closed', 'Mitigated']
TASK_NAMES = [
    'Análisis de Requisitos', 'Diseño de Arquitectura',
    'Desarrollo de Módulo de Autenticación', 'Pruebas Unitarias', 
    'Despliegue a Producción', 'Capacitación de Usuario', 'Revisión de Seguridad'
]
DEFECT_SEVERITY = ['Critico', 'Alto', 'Medio', 'Bajo']
DEFECT_STATUS = ['Abierto', 'Resuelto', 'Cerrado']
RESOURCE_TYPES = {
    'Hardware': ['Servidor Dedicado', 'Cluster GPU', 'Laptop Desarrollo'],
    'Software': ['Licencia IDE', 'Licencia Project Manager', 'Suscripción Cloud'],
    'Service': ['Consultoría Externa', 'Soporte AWS', 'Dominio Web']
}

class Command(BaseCommand):
    help = 'Genera datos sintéticos para poblar la BD OLTP (project_mgmt)'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING("Iniciando generación de datos sintéticos..."))
        
        # Usamos el cursor de Django que ya está conectado a la BD correcta (Local o Neon)
        with connection.cursor() as cur:
            
            # 0. LIMPIEZA (TRUNCATE) [cite: 288]
            self.stdout.write("Limpiando tablas existentes...")
            cur.execute("""
                TRUNCATE project_mgmt.defect, project_mgmt.risk,
                project_mgmt.time_entry, project_mgmt.task, 
                project_mgmt.resource, project_mgmt.project, 
                project_mgmt.employee, project_mgmt.client 
                RESTART IDENTITY CASCADE;
            """)
            
            # 1. POBLAR CLIENTES [cite: 296]
            self.stdout.write(f"Generando {NUM_CLIENTS} clientes...")
            for _ in range(NUM_CLIENTS):
                cur.execute(
                    "INSERT INTO project_mgmt.client (name, sector, contact_email) VALUES (%s, %s, %s)",
                    (fake.company(), random.choice(SECTORS), fake.email())
                )

            # 2. POBLAR EMPLEADOS [cite: 304]
            self.stdout.write(f"Generando {NUM_EMPLOYEES} empleados...")
            for _ in range(NUM_EMPLOYEES):
                role = random.choice(list(ROLES.keys()))
                cost_range = ROLES[role]
                cost = round(random.uniform(cost_range[0], cost_range[1]), 2)
                start_date = fake.date_between(start_date='-5y', end_date='-1M')
                
                cur.execute(
                    "INSERT INTO project_mgmt.employee (name, role, cost_per_hour, start_date, available_hours_per_week) VALUES (%s, %s, %s, %s, %s)",
                    (fake.name(), role, cost, start_date, 40.0)
                )

            # Recuperar IDs generados
            cur.execute("SELECT client_id FROM project_mgmt.client")
            client_ids = [row[0] for row in cur.fetchall()]
            
            cur.execute("SELECT employee_id FROM project_mgmt.employee")
            employee_ids = [row[0] for row in cur.fetchall()]

            project_ids = []
            project_task_map = {}

            # 3. POBLAR PROYECTOS [cite: 325]
            self.stdout.write(f"Generando {NUM_PROJECTS} proyectos...")
            for _ in range(NUM_PROJECTS):
                start_date = fake.date_between(start_date='-2y', end_date='-3M')
                end_date = start_date + timedelta(days=random.randint(90, 730))
                
                cur.execute(
                    """INSERT INTO project_mgmt.project (client_id, name, start_date, end_date, budget, status)
                       VALUES (%s, %s, %s, %s, %s, %s) RETURNING project_id""",
                    (
                        random.choice(client_ids),
                        f"Proyecto {fake.bs().title()}",
                        start_date,
                        end_date,
                        random.randint(15000, 60000),
                        random.choice(PROJECT_STATUSES)
                    )
                )
                project_id = cur.fetchone()[0]
                project_ids.append(project_id)
                project_task_map[project_id] = {'start_date': start_date, 'task_ids': []}

            # 4. POBLAR RECURSOS [cite: 348]
            self.stdout.write(f"Generando {NUM_RESOURCES} recursos...")
            if project_ids:
                for _ in range(NUM_RESOURCES):
                    res_type = random.choice(list(RESOURCE_TYPES.keys()))
                    res_name = random.choice(RESOURCE_TYPES[res_type])
                    cost = round(random.uniform(50, 5000), 2)
                    start_date = fake.date_between(start_date='-1y', end_date='today')
                    
                    # Corrección de lógica para end_date mayor a start_date
                    end_date = start_date + timedelta(days=random.randint(30, 365))
                    
                    assigned_project_id = random.choice(project_ids)
                    
                    cur.execute(
                        """INSERT INTO project_mgmt.resource (project_id, name, type, cost, start_date, end_date)
                           VALUES (%s, %s, %s, %s, %s, %s)""",
                        (assigned_project_id, res_name, res_type, cost, start_date, end_date)
                    )

            # 5. TAREAS, TIEMPOS, RIESGOS Y DEFECTOS [cite: 370]
            self.stdout.write("Generando detalles (tareas, logs, riesgos, defectos)...")
            
            for project_id, data in project_task_map.items():
                p_start = data['start_date']
                
                # --- Tareas ---
                num_tasks = random.randint(5, AVG_TASKS_PER_PROJECT)
                for _ in range(num_tasks):
                    task_start = fake.date_between(start_date=p_start, end_date=p_start + timedelta(days=90))
                    task_end = task_start + timedelta(days=random.randint(7, 60))
                    
                    actual_start = None
                    actual_end = None
                    percent_complete = 0
                    planned_hours = round(random.uniform(20.0, 120.0), 2)

                    # Lógica de progreso simulado
                    if task_start < datetime.now().date():
                        actual_start = task_start + timedelta(days=random.randint(0, 5))
                        if actual_start < datetime.now().date():
                            if random.random() > 0.5: # Tarea completada
                                actual_end = actual_start + timedelta(days=random.randint(7, 65))
                                if actual_end < datetime.now().date():
                                    percent_complete = 100
                            
                            if actual_end is None: # En progreso
                                days_done = (datetime.now().date() - actual_start).days
                                total_days = (task_end - actual_start).days
                                if total_days > 0:
                                    percent_complete = min(99, int((days_done / total_days) * 100))
                    
                    cur.execute(
                        """INSERT INTO project_mgmt.task 
                           (project_id, name, assigned_to, planned_start, planned_end, actual_start, actual_end, percent_complete, planned_hours)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING task_id""",
                        (
                            project_id, random.choice(TASK_NAMES), random.choice(employee_ids),
                            task_start, task_end, actual_start, actual_end, percent_complete, planned_hours
                        )
                    )
                    task_id = cur.fetchone()[0]
                    project_task_map[project_id]['task_ids'].append(task_id)

                    # --- Time Entries (solo si empezó) ---
                    if actual_start:
                        num_entries = random.randint(1, AVG_TIME_ENTRIES_PER_TASK)
                        
                        # Fechas límite para logs
                        log_end_date = datetime.now().date()
                        if actual_end:
                            log_end_date = min(log_end_date, actual_end)
                        
                        # Validación simple de rango
                        if actual_start <= log_end_date:
                            for _ in range(num_entries):
                                entry_date = fake.date_between(start_date=actual_start, end_date=log_end_date)
                                cur.execute(
                                    """INSERT INTO project_mgmt.time_entry (employee_id, task_id, entry_timestamp, hours_worked, activity_type)
                                       VALUES (%s, %s, %s, %s, %s)""",
                                    (
                                        random.choice(employee_ids), task_id, entry_date,
                                        round(random.uniform(1, 8), 2), 
                                        random.choice(['Desarrollo', 'Reunión', 'Investigación'])
                                    )
                                )

                # --- Riesgos ---
                for _ in range(random.randint(0, 5)):
                    cur.execute(
                        """INSERT INTO project_mgmt.risk (project_id, description, probability, impact_score, status, detected_date)
                           VALUES (%s, %s, %s, %s, %s, %s)""",
                        (
                            project_id, fake.sentence(nb_words=10),
                            round(random.random(), 2), random.randint(1, 10),
                            random.choice(RISK_STATUSES),
                            fake.date_between(start_date=p_start, end_date='today')
                        )
                    )

                # --- Defectos ---
                task_ids_list = project_task_map[project_id]['task_ids']
                if task_ids_list:
                    for _ in range(random.randint(0, 10)): # Ajustado a 10 para no saturar
                        task_id = random.choice(task_ids_list)
                        detected_date = fake.date_between(start_date=p_start, end_date='today')
                        status = random.choice(DEFECT_STATUS)
                        
                        resolved_date = None
                        resolved_by = None
                        if status != 'Abierto':
                            resolved_date = fake.date_between(start_date=detected_date, end_date='today')
                            resolved_by = random.choice(employee_ids)

                        cur.execute(
                            """INSERT INTO project_mgmt.defect 
                               (project_id, task_id, detected_by_id, resolved_by_id, detected_date, resolved_date, description, severity, status)
                               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                            (
                                project_id, task_id, random.choice(employee_ids), resolved_by,
                                detected_date, resolved_date, fake.sentence(nb_words=15),
                                random.choice(DEFECT_SEVERITY), status
                            )
                        )

        self.stdout.write(self.style.SUCCESS("¡Datos sintéticos generados exitosamente en OLTP!"))