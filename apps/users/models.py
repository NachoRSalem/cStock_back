from django.contrib.auth.models import AbstractUser
from django.db import models

class User(AbstractUser):
    ROLES = (
        ('admin', 'Administrador'),
        ('sucursal', 'Usuario de Sucursal'),
    )
    
    rol = models.CharField(max_length=20, choices=ROLES, default='sucursal')
    sucursal_asignada = models.ForeignKey(
        'locations.Ubicacion',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='usuarios',
        limit_choices_to={'tipo': 'sucursal'},
        verbose_name='Sucursal Asignada'
    )

    def __str__(self):
        return f"{self.username} - {self.get_rol_display()}"