from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from apps.inventory.models import Pedido, PedidoItem, Stock
from apps.locations.models import SubUbicacion, Ubicacion
from apps.products.models import Categoria, Producto
from apps.sales.models import Venta

User = get_user_model()


class BaseSetup(APITestCase):
    def setUp(self):
        self.suc_a = Ubicacion.objects.create(nombre='Kiosco A', tipo='sucursal')
        self.suc_b = Ubicacion.objects.create(nombre='Kiosco B', tipo='sucursal')
        self.sub_a = SubUbicacion.objects.create(ubicacion=self.suc_a, nombre='Heladera A', tipo='ambiente')
        self.sub_b = SubUbicacion.objects.create(ubicacion=self.suc_b, nombre='Heladera B', tipo='ambiente')
        self.cat = Categoria.objects.create(nombre='Bebidas')
        self.prod = Producto.objects.create(
            nombre='Agua', categoria=self.cat, tipo_conservacion='ambiente',
            precio_venta=Decimal('100.00'), costo_compra=Decimal('60.00'),
        )
        self.admin = User.objects.create_user('admin', password='x', rol='admin')
        self.user_a = User.objects.create_user('ua', password='x', rol='sucursal', sucursal_asignada=self.suc_a)
        self.user_b = User.objects.create_user('ub', password='x', rol='sucursal', sucursal_asignada=self.suc_b)
        self.stock_a = Stock.objects.create(producto=self.prod, sub_ubicacion=self.sub_a, cantidad=Decimal('10'))
        self.stock_b = Stock.objects.create(producto=self.prod, sub_ubicacion=self.sub_b, cantidad=Decimal('10'))

    def vender(self, user, sucursal, sub, cantidad=3, precio='1'):
        self.client.force_authenticate(user)
        return self.client.post('/api/sales/ventas/', {
            'sucursal': sucursal.id,
            'items': [{
                'producto': self.prod.id, 'sub_ubicacion_origen': sub.id,
                'cantidad': cantidad, 'precio_venta_momento': precio,
            }],
        }, format='json')


class VentaTests(BaseSetup):
    def test_precio_lo_define_el_servidor(self):
        res = self.vender(self.user_a, self.suc_a, self.sub_a, precio='1')
        self.assertEqual(res.status_code, 201, res.data)
        venta = Venta.objects.get()
        self.assertEqual(venta.total, Decimal('300.00'))

    def test_no_puede_vender_en_otra_sucursal(self):
        res = self.vender(self.user_a, self.suc_b, self.sub_b)
        self.assertEqual(res.status_code, 400)
        self.stock_b.refresh_from_db()
        self.assertEqual(self.stock_b.cantidad, Decimal('10'))

    def test_no_puede_vender_desde_sububicacion_ajena(self):
        res = self.vender(self.user_a, self.suc_a, self.sub_b)
        self.assertEqual(res.status_code, 400)

    def test_venta_fallida_no_deja_registros(self):
        res = self.vender(self.user_a, self.suc_a, self.sub_a, cantidad=999)
        self.assertEqual(res.status_code, 400)
        self.assertEqual(Venta.objects.count(), 0)

    def test_sucursal_solo_ve_sus_ventas(self):
        self.vender(self.user_a, self.suc_a, self.sub_a)
        self.vender(self.user_b, self.suc_b, self.sub_b)
        self.client.force_authenticate(self.user_a)
        res = self.client.get('/api/sales/ventas/')
        self.assertEqual(res.data['count'], 1)
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get('/api/sales/ventas/').data['count'], 2)

    def test_no_se_puede_borrar_ni_editar_ventas(self):
        self.vender(self.user_a, self.suc_a, self.sub_a)
        venta = Venta.objects.get()
        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.delete(f'/api/sales/ventas/{venta.id}/').status_code, 405)
        self.assertEqual(self.client.patch(f'/api/sales/ventas/{venta.id}/', {}, format='json').status_code, 405)

    def test_anular_devuelve_stock_y_descuenta_plata(self):
        self.vender(self.user_a, self.suc_a, self.sub_a, cantidad=4)
        venta = Venta.objects.get()
        self.stock_a.refresh_from_db()
        self.assertEqual(self.stock_a.cantidad, Decimal('6'))

        self.client.force_authenticate(self.admin)
        antes = self.client.get('/api/sales/balance/').data['total_ventas_kiosco']
        self.assertEqual(antes, 400.0)

        self.client.force_authenticate(self.user_a)
        res = self.client.post(f'/api/sales/ventas/{venta.id}/anular/')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['estado'], 'anulada')

        self.stock_a.refresh_from_db()
        self.assertEqual(self.stock_a.cantidad, Decimal('10'))

        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get('/api/sales/balance/').data['total_ventas_kiosco'], 0.0)

    def test_no_se_anula_dos_veces(self):
        self.vender(self.user_a, self.suc_a, self.sub_a)
        venta = Venta.objects.get()
        self.client.force_authenticate(self.user_a)
        self.assertEqual(self.client.post(f'/api/sales/ventas/{venta.id}/anular/').status_code, 200)
        self.assertEqual(self.client.post(f'/api/sales/ventas/{venta.id}/anular/').status_code, 400)
        self.stock_a.refresh_from_db()
        self.assertEqual(self.stock_a.cantidad, Decimal('10'))

    def test_sucursal_no_anula_ventas_ajenas(self):
        self.vender(self.user_b, self.suc_b, self.sub_b)
        venta = Venta.objects.get()
        self.client.force_authenticate(self.user_a)
        self.assertEqual(self.client.post(f'/api/sales/ventas/{venta.id}/anular/').status_code, 404)

    def test_anular_vuelve_al_lote_original(self):
        Stock.objects.filter(pk=self.stock_a.pk).update(lote='L1', fecha_ingreso='2026-01-01', cantidad=Decimal('2'))
        l2 = Stock.objects.create(producto=self.prod, sub_ubicacion=self.sub_a, cantidad=Decimal('5'),
                                  lote='L2', fecha_ingreso='2026-02-01')
        self.vender(self.user_a, self.suc_a, self.sub_a, cantidad=4)  # 2 de L1 + 2 de L2
        venta = Venta.objects.get()
        self.client.post(f'/api/sales/ventas/{venta.id}/anular/')
        self.stock_a.refresh_from_db()
        l2.refresh_from_db()
        self.assertEqual(self.stock_a.cantidad, Decimal('2'))
        self.assertEqual(l2.cantidad, Decimal('5'))


class PermisosTests(BaseSetup):
    def test_productos_requieren_login(self):
        self.assertEqual(self.client.get('/api/products/productos/').status_code, 401)
        self.assertEqual(self.client.get('/api/products/categorias/').status_code, 401)
        self.client.force_authenticate(self.user_a)
        self.assertEqual(self.client.get('/api/products/productos/').status_code, 200)

    def test_lista_de_usuarios_solo_admin_y_sin_passwords(self):
        self.client.force_authenticate(self.user_a)
        self.assertEqual(self.client.get('/api/users/').status_code, 403)
        self.client.force_authenticate(self.admin)
        res = self.client.get('/api/users/')
        self.assertEqual(res.status_code, 200)
        self.assertNotIn('password', res.data[0])


class PedidoTests(BaseSetup):
    def crear(self, user, destino, precio='1'):
        self.client.force_authenticate(user)
        return self.client.post('/api/inventory/pedidos/', {
            'destino': destino.id,
            'items': [{'producto': self.prod.id, 'cantidad': 5, 'precio_costo_momento': precio}],
        }, format='json')

    def test_sucursal_no_define_el_costo(self):
        res = self.crear(self.user_a, self.suc_a, precio='1')
        self.assertEqual(res.status_code, 201, res.data)
        item = PedidoItem.objects.get()
        self.assertEqual(item.precio_costo_momento, Decimal('60.00'))

    def test_sucursal_no_crea_pedidos_para_otra(self):
        self.assertEqual(self.crear(self.user_a, self.suc_b).status_code, 400)

    def test_admin_si_define_el_costo_y_recibir_lo_actualiza(self):
        res = self.crear(self.admin, self.suc_a, precio='75')
        self.assertEqual(res.status_code, 201, res.data)
        pedido = Pedido.objects.get()
        item = pedido.items.get()
        res = self.client.post(f'/api/inventory/pedidos/{pedido.id}/recibir/', {
            'items': [{'id': item.id, 'sub_ubicacion_destino': self.sub_a.id}],
        }, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.prod.refresh_from_db()
        self.assertEqual(self.prod.costo_compra, Decimal('75.00'))

    def test_traslado_entre_sucursales_no_cambia_costo(self):
        pedido = Pedido.objects.create(creado_por=self.admin, destino=self.suc_a, estado='aprobado')
        item = PedidoItem.objects.create(
            pedido=pedido, producto=self.prod, cantidad=2, precio_costo_momento=Decimal('999'),
            sub_ubicaciones_origen_detalle=[{'sub_ubicacion_id': self.sub_b.id, 'cantidad': 2}],
        )
        item.sub_ubicacion_destino = self.sub_a
        item.save()
        pedido.marcar_como_recibido()
        self.prod.refresh_from_db()
        self.assertEqual(self.prod.costo_compra, Decimal('60.00'))

    def test_pedido_aprobado_no_se_edita_ni_borra(self):
        pedido = Pedido.objects.create(creado_por=self.user_a, destino=self.suc_a, estado='aprobado')
        self.client.force_authenticate(self.user_a)
        self.assertEqual(self.client.put(f'/api/inventory/pedidos/{pedido.id}/', {
            'destino': self.suc_a.id, 'items': [],
        }, format='json').status_code, 400)
        self.assertEqual(self.client.delete(f'/api/inventory/pedidos/{pedido.id}/').status_code, 400)
        self.assertTrue(Pedido.objects.filter(pk=pedido.pk).exists())

    def test_borrador_si_se_borra(self):
        pedido = Pedido.objects.create(creado_por=self.user_a, destino=self.suc_a, estado='borrador')
        self.client.force_authenticate(self.user_a)
        self.assertEqual(self.client.delete(f'/api/inventory/pedidos/{pedido.id}/').status_code, 204)


class GastoOperativoTests(BaseSetup):
    def test_gasto_guarda_el_concepto_y_lo_devuelve_legible(self):
        self.client.force_authenticate(self.admin)
        res = self.client.post('/api/sales/gastos/', {
            'monto': '1500', 'fecha': '2026-11-24', 'concepto': 'sueldos', 'descripcion': 'Noviembre',
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data['concepto'], 'sueldos')
        self.assertEqual(res.data['concepto_display'], 'Sueldos y Honorarios')

    def test_concepto_invalido_se_rechaza_en_vez_de_perderse(self):
        self.client.force_authenticate(self.admin)
        res = self.client.post('/api/sales/gastos/', {
            'monto': '10', 'fecha': '2026-11-24', 'concepto': 'General',
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_solo_admin(self):
        self.client.force_authenticate(self.user_a)
        self.assertEqual(self.client.get('/api/sales/gastos/').status_code, 403)

    def test_balance_suma_gastos_operativos(self):
        self.client.force_authenticate(self.admin)
        self.client.post('/api/sales/gastos/', {'monto': '700', 'fecha': '2026-11-24', 'concepto': 'luz'}, format='json')
        data = self.client.get('/api/sales/balance/').data
        self.assertEqual(data['total_gastos_operativos'], 700.0)
        self.assertEqual(data['total_egresos'], 700.0)
