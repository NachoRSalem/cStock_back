from django.db import models

class Ubicacion(models.Model):
    TIPOS = (
        ('sucursal', 'Sucursal'),
        ('almacen', 'Almacén Central'),
    )
    nombre = models.CharField(max_length=100) # Ej: Kiosco San Luis
    tipo = models.CharField(max_length=20, choices=TIPOS)

    def __str__(self):
        return self.nombre

class SubUbicacion(models.Model):
    TIPOS_AMBIENTE = (
        ('ambiente', 'Temperatura Ambiente'),
        ('heladera', 'Heladera'),
        ('freezer', 'Freezer'),
    )
    ubicacion = models.ForeignKey(Ubicacion, on_delete=models.CASCADE, related_name='sub_ubicaciones')
    nombre = models.CharField(max_length=100) # Ej: Heladera 1 o Freezer Principal
    tipo = models.CharField(max_length=20, choices=TIPOS_AMBIENTE)

    def __str__(self):
        return f"{self.nombre} ({self.ubicacion.nombre})"