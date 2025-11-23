class AnalyticsRouter:
    """
    Un router para controlar todas las operaciones de base de datos
    para la aplicación 'analytics' (hacia project_dss).
    """
    route_app_labels = {'analytics'}

    def db_for_read(self, model, **hints):
        if model._meta.app_label in self.route_app_labels:
            return 'project_dss'
        return None

    def db_for_write(self, model, **hints):
        # El DSS es de SOLO LECTURA desde Django (el ETL lo llena)
        if model._meta.app_label in self.route_app_labels:
            return False 
        return None

    def allow_relation(self, obj1, obj2, **hints):
        if (
            obj1._meta.app_label in self.route_app_labels or
            obj2._meta.app_label in self.route_app_labels
        ):
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        # No se hacen migraciones de Django en el DWH
        if app_label in self.route_app_labels:
            return False
        return None