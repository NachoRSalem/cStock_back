from decimal import Decimal
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

    ESTADO_COMPLETADA = 'completada'
    ESTADO_ANULADA = 'anulada'
    ESTADOS = (
        (ESTADO_COMPLETADA, 'Completada'),
        (ESTADO_ANULADA, 'Anulada'),
    )
    estado = models.CharField(max_length=20, choices=ESTADOS, default=ESTADO_COMPLETADA)
    anulada_en = models.DateTimeField(null=True, blank=True)
    anulada_por = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='ventas_anuladas',
    )

    def anular(self, usuario):
        """
        Anula la venta: devuelve el stock a los lotes de los que salió y deja de
        contarla en los totales de dinero (los reportes solo suman ventas completadas).
        """
        from django.utils import timezone

        with transaction.atomic():
            venta = Venta.objects.select_for_update().get(pk=self.pk)
            if venta.estado == self.ESTADO_ANULADA:
                raise ValueError('La venta ya fue anulada.')

            for item in venta.items.select_related('producto', 'sub_ubicacion_origen'):
                # Las viandas no usan stock: anularlas solo descuenta el dinero.
                if item.producto.es_vianda or item.sub_ubicacion_origen_id is None:
                    continue
                devuelto = Decimal('0')
                for consumo in item.lotes.select_related('stock'):
                    if consumo.stock_id is None:
                        continue
                    stock = Stock.objects.select_for_update().get(pk=consumo.stock_id)
                    stock.cantidad += consumo.cantidad
                    stock.save()
                    devuelto += consumo.cantidad

                # Ventas anteriores a este registro de lotes (o lotes borrados): se devuelve al stock sin lote.
                restante = Decimal(item.cantidad) - devuelto
                if restante > 0:
                    stock, _ = Stock.objects.select_for_update().get_or_create(
                        producto=item.producto,
                        sub_ubicacion=item.sub_ubicacion_origen,
                        lote=None,
                        defaults={'cantidad': Decimal('0')},
                    )
                    stock.cantidad += restante
                    stock.save()

            venta.estado = self.ESTADO_ANULADA
            venta.anulada_en = timezone.now()
            venta.anulada_por = usuario
            venta.save(update_fields=['estado', 'anulada_en', 'anulada_por'])

        self.estado = venta.estado
        self.anulada_en = venta.anulada_en
        self.anulada_por = venta.anulada_por

    def procesar_venta(self, items_data):
        """
        Lógica atómica: registra items y descuenta stock.
        items_data: lista de diccionarios con producto, sub_ubicacion, cantidad y precio.
        """
        with transaction.atomic():
            total_venta = Decimal('0')
            for item in items_data:
                # El precio lo define el servidor, nunca el cliente.
                item['precio_venta_momento'] = item['producto'].precio_venta
                consumos = []

                if item['producto'].es_vianda:
                    # Vianda: no hay stock que descontar, solo entra el dinero de la venta.
                    VentaItem.objects.create(
                        venta=self,
                        producto=item['producto'],
                        sub_ubicacion_origen=None,
                        cantidad=item['cantidad'],
                        precio_venta_momento=item['precio_venta_momento'],
                    )
                    total_venta += item['cantidad'] * item['precio_venta_momento']
                    continue

                # 1. Validar y descontar Stock usando FIFO (First In, First Out)
                # Obtener todos los lotes del producto en esta sub-ubicación
                stocks_disponibles = Stock.objects.select_for_update().filter(
                    producto=item['producto'],
                    sub_ubicacion=item['sub_ubicacion_origen'],
                    cantidad__gt=0
                ).order_by('fecha_ingreso', 'id')
                
                if not stocks_disponibles.exists():
                    raise Exception(f"No hay stock de {item['producto'].nombre} en {item['sub_ubicacion_origen'].nombre}")
                
                # Verificar que hay stock suficiente en total
                total_disponible = sum(s.cantidad for s in stocks_disponibles)
                if total_disponible < item['cantidad']:
                    raise Exception(f"Stock insuficiente de {item['producto'].nombre} en {item['sub_ubicacion_origen'].nombre}")

                # Descontar de los lotes usando FIFO
                cantidad_restante = item['cantidad']
                for stock_actual in stocks_disponibles:
                    if cantidad_restante <= 0:
                        break
                    
                    cantidad_a_descontar = min(stock_actual.cantidad, cantidad_restante)
                    stock_actual.cantidad -= cantidad_a_descontar
                    stock_actual.save()
                    consumos.append((stock_actual, cantidad_a_descontar))

                    cantidad_restante -= cantidad_a_descontar

                # 2. Crear el item de venta y registrar de qué lotes salió el stock
                venta_item = VentaItem.objects.create(
                    venta=self,
                    producto=item['producto'],
                    sub_ubicacion_origen=item['sub_ubicacion_origen'],
                    cantidad=item['cantidad'],
                    precio_venta_momento=item['precio_venta_momento']
                )
                for stock_usado, cantidad_usada in consumos:
                    VentaItemLote.objects.create(
                        venta_item=venta_item, stock=stock_usado, cantidad=cantidad_usada
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
    # Null en las viandas, que no salen de ninguna sub-ubicación.
    sub_ubicacion_origen = models.ForeignKey(SubUbicacion, on_delete=models.PROTECT, null=True, blank=True)
    cantidad = models.PositiveIntegerField()
    precio_venta_momento = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.cantidad} x {self.producto.nombre}"


class VentaItemLote(models.Model):
    """De qué registro de stock (lote) salió cada unidad vendida; sirve para devolverlo al anular."""
    venta_item = models.ForeignKey(VentaItem, on_delete=models.CASCADE, related_name='lotes')
    stock = models.ForeignKey(Stock, on_delete=models.SET_NULL, null=True, related_name='+')
    cantidad = models.DecimalField(max_digits=12, decimal_places=3)


class Ingreso(models.Model):
    TIPO_CHOICES = (
        ('cuota_comedor', 'Cuota Comedor'),
    )

    MEDIO_PAGO_CHOICES = (
        ('mercado_pago', 'Mercado Pago'),
        ('efectivo', 'Efectivo'),
        ('cuenta_bancaria', 'Cuenta Bancaria'),
    )

    monto = models.DecimalField(max_digits=12, decimal_places=2)
    fecha = models.DateField()
    descripcion = models.CharField(max_length=255, blank=True)
    tipo = models.CharField(max_length=30, choices=TIPO_CHOICES, default='cuota_comedor')
    medio_pago = models.CharField(max_length=20, choices=MEDIO_PAGO_CHOICES, default='efectivo')
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-creado_en']

    def __str__(self):
        return f"Ingreso {self.tipo} - ${self.monto} ({self.fecha})"


class GastoOperativo(models.Model):
    CONCEPTO_CHOICES = (
        ('luz', 'Luz / Electricidad'),
        ('gas', 'Gas'),
        ('agua', 'Agua'),
        ('mantenimiento', 'Mantenimiento / Reparación'),
        ('alquiler', 'Alquiler'),
        ('internet', 'Internet / Servicios'),
        ('impuestos', 'Impuestos / Tasas'),
        ('sueldos', 'Sueldos y Honorarios'),
        ('otro', 'Otro Gasto Operativo'),
    )

    monto = models.DecimalField(max_digits=12, decimal_places=2)
    fecha = models.DateField()
    concepto = models.CharField(max_length=30, choices=CONCEPTO_CHOICES, default='otro')
    descripcion = models.CharField(max_length=255, blank=True)
    sucursal = models.ForeignKey(Ubicacion, on_delete=models.SET_NULL, null=True, blank=True, related_name='gastos_operativos', help_text="Sucursal asociada si aplica")
    registrado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha', '-creado_en']

    def __str__(self):
        return f"Gasto {self.get_concepto_display()} - ${self.monto} ({self.fecha})"