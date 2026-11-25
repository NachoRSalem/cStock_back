from django.db import models

from .units import UNIDAD_CHOICES

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
    es_fabricable = models.BooleanField(
        default=False,
        help_text="Indica si este producto se fabrica a partir de otros insumos"
    )
    sku = models.CharField(max_length=50, unique=True, blank=True, null=True) # Código de barras si usás
    dias_caducidad = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Días de caducidad desde la compra al distribuidor. Ej: 90 días = 3 meses"
    )
    unidad_medida = models.CharField(
        max_length=20,
        default='unidad',
        help_text="Ej: kg, g, l, ml, unidad"
    )
    # Datos del envase de compra. costo_compra se calcula a partir de ellos (precio normalizado).
    cantidad_envase = models.DecimalField(
        max_digits=12, decimal_places=3, null=True, blank=True,
        help_text="Cantidad que trae un envase, expresada en unidad_envase"
    )
    unidad_envase = models.CharField(max_length=10, choices=UNIDAD_CHOICES, null=True, blank=True)
    precio_envase = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Precio final pagado por un envase"
    )
    es_vianda = models.BooleanField(
        default=False,
        help_text="Las viandas no manejan stock ni costo de compra: solo se vende con su precio de venta"
    )

    def __str__(self):
        return self.nombre