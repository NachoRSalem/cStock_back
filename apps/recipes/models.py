from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.locations.models import SubUbicacion, Ubicacion
from apps.products.models import Producto


class Receta(models.Model):
    producto_final = models.OneToOneField(
        Producto,
        on_delete=models.CASCADE,
        related_name='receta'
    )
    activa = models.BooleanField(default=True)
    notas = models.TextField(blank=True, null=True)
    creado_en = models.DateTimeField(auto_now_add=True)
    actualizado_en = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['producto_final__nombre']

    def __str__(self):
        return f"Receta: {self.producto_final.nombre}"


class RecetaInsumo(models.Model):
    receta = models.ForeignKey(Receta, on_delete=models.CASCADE, related_name='insumos')
    producto_insumo = models.ForeignKey(Producto, on_delete=models.PROTECT, related_name='es_insumo_de')
    cantidad_requerida = models.DecimalField(max_digits=12, decimal_places=3, default=Decimal('0.000'))

    class Meta:
        unique_together = ('receta', 'producto_insumo')
        ordering = ['producto_insumo__nombre']

    def __str__(self):
        return f"{self.receta.producto_final.nombre}: {self.cantidad_requerida} x {self.producto_insumo.nombre}"


class Fabricacion(models.Model):
    receta = models.ForeignKey(Receta, on_delete=models.PROTECT, related_name='fabricaciones')
    ubicacion = models.ForeignKey(Ubicacion, on_delete=models.PROTECT, related_name='fabricaciones')
    sub_ubicacion_destino = models.ForeignKey(SubUbicacion, on_delete=models.PROTECT, related_name='fabricaciones_destino')
    cantidad_producida = models.PositiveIntegerField()
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-creado_en']

    def __str__(self):
        return f"Fabricacion {self.id}: {self.receta.producto_final.nombre} x {self.cantidad_producida}"


class FabricacionConsumo(models.Model):
    fabricacion = models.ForeignKey(Fabricacion, on_delete=models.CASCADE, related_name='consumos')
    receta_insumo = models.ForeignKey(RecetaInsumo, on_delete=models.PROTECT)
    sub_ubicacion_origen = models.ForeignKey(SubUbicacion, on_delete=models.PROTECT)
    lote = models.CharField(max_length=100, null=True, blank=True)
    cantidad_consumida = models.DecimalField(max_digits=12, decimal_places=3)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.receta_insumo.producto_insumo.nombre} - {self.cantidad_consumida}"
