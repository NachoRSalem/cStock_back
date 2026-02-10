from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ROLES = (
        ('admin', 'Administrador'),
        ('sucursal', 'Usuario de Sucursal'),
    )
    
    rol = models.CharField(max_length=20, choices=ROLES, default='sucursal')
    # Luego vincularemos esto a la tabla de Sucursales
    sucursal_asignada = models.CharField(max_length=100, blank=True, null=True) 

    def __str__(self):
        return f"{self.username} - {self.get_rol_display()}"