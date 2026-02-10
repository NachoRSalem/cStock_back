from django.db import models

class Categoria(models.Model):
    nombre = models.CharField(max_length=100) # Ej: Bebidas, Lácteos, Golosinas

    def __str__(self):
        return self.nombre

class Producto(models.Model):
    TIPO_ALMACENAMIENTO = (
        ('ambiente', 'Temperatura Ambiente'),
        ('heladera', 'Heladera'),
        ('freezer', 'Freezer'),
    )
    
    nombre = models.CharField(max_length=150)
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name='productos')
    tipo_conservacion = models.CharField(max_length=20, choices=TIPO_ALMACENAMIENTO)
    precio_venta = models.DecimalField(max_digits=10, decimal_places=2)
    costo_compra = models.DecimalField(max_digits=10, decimal_places=2) # Para el reporte de ganancias
    sku = models.CharField(max_length=50, unique=True, blank=True, null=True) # Código de barras si usás

    def __str__(self):
        return self.nombre