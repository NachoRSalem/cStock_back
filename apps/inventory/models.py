from django.db import models, transaction
from apps.products.models import Producto
from apps.locations.models import SubUbicacion, Ubicacion
from core import settings
import json

class Stock(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name='stocks')
    sub_ubicacion = models.ForeignKey(SubUbicacion, on_delete=models.CASCADE, related_name='stocks')
    cantidad = models.PositiveIntegerField(default=0)
    ultima_actualizacion = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('producto', 'sub_ubicacion')
        verbose_name_plural = "Stocks"

    def __str__(self):
        return f"{self.producto.nombre} - {self.sub_ubicacion.nombre}: {self.cantidad}"
    
class Pedido(models.Model):
    ESTADOS = (
        ('borrador', 'Borrador'),
        ('pendiente', 'Pendiente de Aprobación'),
        ('aprobado', 'Aprobado'),
        ('rechazado', 'Rechazado'),
        ('recibido', 'Recibido'),
    )
    
    TIPO_ORIGEN = (
        ('distribuidor', 'Distribuidor'),
        ('sucursal', 'Sucursal'),
    )
    
    creado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    destino = models.ForeignKey(Ubicacion, on_delete=models.CASCADE, related_name='pedidos_destino')
    estado = models.CharField(max_length=20, choices=ESTADOS, default='borrador')
    fecha_creacion = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    pdf_archivo = models.FileField(upload_to='pedidos_pdf/', null=True, blank=True)
    
    # Origen del pedido
    origen_tipo = models.CharField(max_length=20, choices=TIPO_ORIGEN, default='distribuidor', help_text="Origen del stock para este pedido")
    origen_sucursal = models.ForeignKey(Ubicacion, on_delete=models.SET_NULL, null=True, blank=True, related_name='pedidos_origen', help_text="Sucursal/almacén de origen si origen_tipo='sucursal'")

    def marcar_como_recibido(self):
        """
        Lógica para pasar de Aprobado a Recibido y sumar stock.
        """
        if self.estado != 'aprobado':
            raise Exception("Solo se pueden recibir pedidos que estén en estado Aprobado.")

        with transaction.atomic():
            for item in self.items.all():
                if not item.sub_ubicacion_destino:
                    raise Exception(f"El producto {item.producto.nombre} no tiene una sub-ubicación asignada.")
                
                
                stock_existente, created = Stock.objects.get_or_create(
                    producto=item.producto,
                    sub_ubicacion=item.sub_ubicacion_destino,
                    defaults={'cantidad': 0}
                )

                stock_existente.cantidad += item.cantidad
                stock_existente.save()

            self.estado = 'recibido'
            self.save()

    def __str__(self):
        return f"Pedido {self.id} - {self.destino.nombre} ({self.get_estado_display()})"

class PedidoItem(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad = models.PositiveIntegerField()
    precio_costo_momento = models.DecimalField(max_digits=10, decimal_places=2)
    
    # se llena al momento de recibir
    sub_ubicacion_destino = models.ForeignKey(
        SubUbicacion, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='pedido_items_destino',
        help_text="Donde se guardó el producto al recibirlo"
    )
    
    # se llena al momento de aprobar si proviene del almacén
    sub_ubicacion_origen = models.ForeignKey(
        SubUbicacion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='pedido_items_origen',
        help_text="De donde se tomó el producto en el almacén del admin (campo legacy)"
    )
    
    # Múltiples sub-ubicaciones origen (cuando se distribuye entre varias)
    sub_ubicaciones_origen_detalle = models.JSONField(
        null=True,
        blank=True,
        help_text="Array de {sub_ubicacion_id, cantidad} cuando el stock se toma de múltiples sub-ubicaciones"
    )

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre} (Pedido {self.pedido.id})"