from decimal import Decimal

from apps.inventory.models import Stock
from apps.products.models import Producto
from apps.sales.models import Venta
from apps.sales.tests import BaseSetup


class ViandaTests(BaseSetup):
    def setUp(self):
        super().setUp()
        self.vianda = Producto.objects.create(
            nombre='Milanesa', categoria=self.cat, tipo_conservacion='ambiente',
            precio_venta=Decimal('4500.00'), costo_compra=Decimal('0'), es_vianda=True,
        )

    def vender_vianda(self, cantidad=2):
        self.client.force_authenticate(self.user_a)
        return self.client.post('/api/sales/ventas/', {
            'sucursal': self.suc_a.id,
            'items': [{'producto': self.vianda.id, 'cantidad': cantidad}],
        }, format='json')

    def test_vender_vianda_no_toca_stock_y_suma_dinero(self):
        res = self.vender_vianda(2)
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(Venta.objects.get().total, Decimal('9000.00'))
        self.assertFalse(Stock.objects.filter(producto=self.vianda).exists())

    def test_anular_vianda_descuenta_plata_y_no_crea_stock(self):
        self.vender_vianda(2)
        venta = Venta.objects.get()
        res = self.client.post(f'/api/sales/ventas/{venta.id}/anular/')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertFalse(Stock.objects.filter(producto=self.vianda).exists())
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get('/api/sales/balance/').data['total_ventas_kiosco'], 0.0)

    def test_venta_mixta_vianda_y_producto(self):
        self.client.force_authenticate(self.user_a)
        res = self.client.post('/api/sales/ventas/', {
            'sucursal': self.suc_a.id,
            'items': [
                {'producto': self.vianda.id, 'cantidad': 1},
                {'producto': self.prod.id, 'sub_ubicacion_origen': self.sub_a.id, 'cantidad': 3},
            ],
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.stock_a.refresh_from_db()
        self.assertEqual(self.stock_a.cantidad, Decimal('7'))
        self.assertEqual(Venta.objects.get().total, Decimal('4800.00'))

    def test_producto_normal_sigue_exigiendo_sub_ubicacion(self):
        self.client.force_authenticate(self.user_a)
        res = self.client.post('/api/sales/ventas/', {
            'sucursal': self.suc_a.id, 'items': [{'producto': self.prod.id, 'cantidad': 1}],
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_las_viandas_no_manejan_stock_ni_pedidos(self):
        self.client.force_authenticate(self.admin)
        res = self.client.post('/api/inventory/stock/', {
            'producto': self.vianda.id, 'sub_ubicacion': self.sub_a.id, 'cantidad': 5,
        }, format='json')
        self.assertEqual(res.status_code, 400)
        res = self.client.post('/api/inventory/pedidos/', {
            'destino': self.suc_a.id,
            'items': [{'producto': self.vianda.id, 'cantidad': 1, 'precio_costo_momento': '0'}],
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_consumo_de_cocina_rechaza_viandas(self):
        self.client.force_authenticate(self.user_a)
        res = self.client.post('/api/consumos/consumos/', {
            'fecha': '2026-11-24',
            'items': [{'producto': self.vianda.id, 'cantidad': '1', 'sub_ubicacion_origen': self.sub_a.id}],
        }, format='json')
        self.assertEqual(res.status_code, 400)
