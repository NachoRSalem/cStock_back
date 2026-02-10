from django.db import models
from django.conf import settings
from django.db import transaction
from apps.products.models import Producto
from apps.locations.models import Ubicacion, SubUbicacion
from apps.inventory.models import Stock

class Venta(models.Model):
    vendedor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    sucursal = models.ForeignKey(Ubicacion, on_delete=models.CASCADE, related_name='ventas')
    fecha = models.DateTimeField(auto_now_add=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    def procesar_venta(self, items_data):
        """
        Lógica atómica: registra items y descuenta stock.
        items_data: lista de diccionarios con producto, sub_ubicacion, cantidad y precio.
        """
        with transaction.atomic():
            total_venta = 0
            for item in items_data:
                # 1. Validar y descontar Stock
                stock_actual = Stock.objects.select_for_update().get(
                    producto=item['producto'],
                    sub_ubicacion=item['sub_ubicacion_origen']
                )

                if stock_actual.cantidad < item['cantidad']:
                    raise Exception(f"Stock insuficiente de {item['producto'].nombre} en {item['sub_ubicacion_origen'].nombre}")

                stock_actual.cantidad -= item['cantidad']
                stock_actual.save()

                # 2. Crear el item de venta
                VentaItem.objects.create(
                    venta=self,
                    producto=item['producto'],
                    sub_ubicacion_origen=item['sub_ubicacion_origen'],
                    cantidad=item['cantidad'],
                    precio_venta_momento=item['precio_venta_momento']
                )
                total_venta += (item['cantidad'] * item['precio_venta_momento'])

            # 3. Actualizar el total de la venta
            self.total = total_venta
            self.save()

    def __str__(self):
        return f"Venta {self.id} - {self.sucursal.nombre} ({self.fecha.strftime('%d/%m/%Y')})"

class VentaItem(models.Model):
    venta = models.ForeignKey(Venta, on_delete=models.CASCADE, related_name='items')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    sub_ubicacion_origen = models.ForeignKey(SubUbicacion, on_delete=models.PROTECT)
    cantidad = models.PositiveIntegerField()
    precio_venta_momento = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre}"
    
    