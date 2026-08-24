from decimal import Decimal

from django.conf import settings
from django.db import models, transaction

from apps.inventory.models import Stock
from apps.locations.models import SubUbicacion
from apps.products.models import Producto


class ConsumoCocina(models.Model):
    ubicacion = models.ForeignKey('locations.Ubicacion', on_delete=models.PROTECT, related_name='consumos_cocina')
    fecha = models.DateField()
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creado_en = models.DateTimeField(auto_now_add=True)
    total_costo = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0'))

    class Meta:
        ordering = ['-fecha', '-creado_en']
        verbose_name = 'Consumo de cocina'
        verbose_name_plural = 'Consumos de cocina'

    def __str__(self):
        return f"Consumo {self.id} - {self.ubicacion.nombre} ({self.fecha})"

    def procesar_consumo(self, items_data):
        """
        items_data: lista de dicts con:
          - producto (Producto instance)
          - cantidad (Decimal/str/number)
          - sub_ubicacion_origen (SubUbicacion instance)
        """
        from decimal import Decimal

        with transaction.atomic():
            total_costo = Decimal('0')

            for item in items_data:
                producto = item['producto']
                cantidad = Decimal(str(item['cantidad']))
                sub_origen = item['sub_ubicacion_origen']

                if cantidad <= 0:
                    raise ValueError(f"La cantidad debe ser mayor a 0 para {producto.nombre}.")

                stocks = Stock.objects.select_for_update().filter(
                    producto=producto,
                    sub_ubicacion=sub_origen,
                    cantidad__gt=0,
                ).order_by('fecha_ingreso', 'id')

                total_disponible = sum(s.cantidad for s in stocks)
                if total_disponible < cantidad:
                    raise ValueError(
                        f"Stock insuficiente de {producto.nombre} en {sub_origen.nombre}. "
                        f"Disponible: {total_disponible}, requerido: {cantidad}."
                    )

                cantidad_restante = cantidad
                for stock_item in stocks:
                    if cantidad_restante <= 0:
                        break

                    consumir = min(stock_item.cantidad, cantidad_restante)
                    stock_item.cantidad = (stock_item.cantidad - consumir).quantize(Decimal('0.001'))
                    stock_item.save(update_fields=['cantidad', 'ultima_actualizacion'])
                    cantidad_restante -= consumir

                costo_unitario = producto.costo_compra or Decimal('0')
                total_costo += (cantidad * costo_unitario)

                ConsumoCocinaItem.objects.create(
                    consumo=self,
                    producto=producto,
                    cantidad=cantidad,
                    sub_ubicacion_origen=sub_origen,
                    costo_unitario_momento=costo_unitario,
                )

            self.total_costo = total_costo
            self.save(update_fields=['total_costo'])


class ConsumoCocinaItem(models.Model):
    consumo = models.ForeignKey(ConsumoCocina, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.DecimalField(max_digits=12, decimal_places=3)
    sub_ubicacion_origen = models.ForeignKey(SubUbicacion, on_delete=models.PROTECT)
    costo_unitario_momento = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre}"


class ProduccionVianda(models.Model):
    ubicacion = models.ForeignKey('locations.Ubicacion', on_delete=models.PROTECT, related_name='producciones_vianda')
    sub_ubicacion_destino = models.ForeignKey(SubUbicacion, on_delete=models.PROTECT)
    fecha = models.DateField()
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-creado_en']
        verbose_name = 'Producción de vianda'
        verbose_name_plural = 'Producciones de vianda'

    def __str__(self):
        return f"Prod. vianda {self.id} - {self.ubicacion.nombre} ({self.fecha})"

    def procesar_produccion(self, items_data):
        with transaction.atomic():
            for item in items_data:
                producto = item['producto']
                cantidad = item['cantidad']

                if cantidad <= 0:
                    raise ValueError(f"La cantidad debe ser mayor a 0 para {producto.nombre}.")

                stock, _ = Stock.objects.get_or_create(
                    producto=producto,
                    sub_ubicacion=self.sub_ubicacion_destino,
                    lote=None,
                    defaults={'cantidad': Decimal('0')},
                )
                stock.cantidad = stock.cantidad + Decimal(str(cantidad))
                stock.save(update_fields=['cantidad', 'ultima_actualizacion'])

                ProduccionViandaItem.objects.create(
                    produccion=self,
                    producto=producto,
                    cantidad=cantidad,
                    precio_venta_momento=producto.precio_venta,
                )


class ProduccionViandaItem(models.Model):
    produccion = models.ForeignKey(ProduccionVianda, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey(Producto, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField()
    precio_venta_momento = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre}"
