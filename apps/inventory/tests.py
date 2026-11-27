from decimal import Decimal
from unittest import mock

from django.db import OperationalError, connection
from django.test.utils import CaptureQueriesContext

from apps.inventory.models import Pedido, PedidoItem, Stock
from apps.sales.tests import BaseSetup


class PedidoBase(BaseSetup):
    def crear_pedido(self, estado='aprobado', cantidad=5, destino=None):
        pedido = Pedido.objects.create(creado_por=self.admin, destino=destino or self.suc_a, estado=estado)
        PedidoItem.objects.create(pedido=pedido, producto=self.prod, cantidad=cantidad, precio_costo_momento=50)
        return pedido


class ListadoYContadorTests(PedidoBase):
    def consultas_del_listado(self):
        with CaptureQueriesContext(connection) as consultas:
            self.assertEqual(self.client.get('/api/inventory/pedidos/').status_code, 200)
        return len(consultas)

    def test_el_listado_no_hace_mas_consultas_al_crecer(self):
        self.client.force_authenticate(self.admin)
        self.crear_pedido()
        con_uno = self.consultas_del_listado()
        for _ in range(10):
            self.crear_pedido()
        self.assertEqual(self.consultas_del_listado(), con_uno)

    def test_contador_segun_el_rol(self):
        self.crear_pedido('pendiente')
        self.crear_pedido('pendiente')
        self.crear_pedido('aprobado')
        self.crear_pedido('aprobado', destino=self.suc_b)

        self.client.force_authenticate(self.admin)
        self.assertEqual(self.client.get('/api/inventory/pedidos/contador/').data, {'cantidad': 2})
        self.client.force_authenticate(self.user_a)
        self.assertEqual(self.client.get('/api/inventory/pedidos/contador/').data, {'cantidad': 1})

    def test_contador_exige_sesion(self):
        self.assertEqual(self.client.get('/api/inventory/pedidos/contador/').status_code, 401)


class RecepcionYAprobacionTests(PedidoBase):
    def recibir(self, pedido, **extra):
        item = pedido.items.get()
        datos = {'id': item.id, 'sub_ubicacion_destino': self.sub_a.id}
        datos.update(extra)
        return self.client.post(f'/api/inventory/pedidos/{pedido.id}/recibir/', {'items': [datos]}, format='json')

    def stock_total(self, sub):
        return sum(s.cantidad for s in Stock.objects.filter(producto=self.prod, sub_ubicacion=sub))

    def test_recibir_usa_la_cantidad_recibida_y_no_se_puede_repetir(self):
        self.client.force_authenticate(self.admin)
        pedido = self.crear_pedido(cantidad=5)
        antes = self.stock_total(self.sub_a)
        self.assertEqual(self.recibir(pedido, cantidad_recibida=3).status_code, 200)
        self.assertEqual(self.stock_total(self.sub_a), antes + Decimal('3'))
        # Segundo intento: se rechaza y no cambia nada.
        self.assertEqual(self.recibir(pedido, cantidad_recibida=99).status_code, 400)
        self.assertEqual(self.stock_total(self.sub_a), antes + Decimal('3'))
        self.assertEqual(pedido.items.get().cantidad_recibida, Decimal('3'))

    def test_aprobar_traslado_que_vacia_el_stock_de_origen(self):
        self.client.force_authenticate(self.admin)
        disponible = int(self.stock_total(self.sub_a))
        pedido = self.crear_pedido('pendiente', cantidad=disponible, destino=self.suc_b)
        item = pedido.items.get()
        res = self.client.post(f'/api/inventory/pedidos/{pedido.id}/aprobar/', {'items': [{
            'id': item.id, 'origen_tipo': 'sucursal', 'origen_sucursal': self.suc_a.id,
            'sub_ubicaciones_origen': [{'sub_ubicacion': self.sub_a.id, 'cantidad': disponible}],
        }]}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(self.stock_total(self.sub_a), Decimal('0'))


class EsperaDeBaseTests(BaseSetup):
    LOGIN = {'username': 'nadie', 'password': 'x'}

    def test_reintenta_hasta_que_la_base_responde(self):
        fallas = [OperationalError(2002, "Can't connect to server")] * 2

        def conectar():
            # Falla dos veces (base despertando) y después responde siempre.
            if fallas:
                raise fallas.pop()

        with mock.patch('core.db_wait.time.sleep') as pausa, \
                mock.patch('core.db_wait.connection.ensure_connection', side_effect=conectar):
            res = self.client.post('/api/token/', self.LOGIN, format='json')
        self.assertEqual(res.status_code, 401)
        self.assertEqual(pausa.call_count, 2)

    def test_si_no_responde_devuelve_un_mensaje_claro(self):
        reloj = iter(range(0, 1000, 6))
        with mock.patch('core.db_wait.time.sleep'), \
                mock.patch('core.db_wait.time.monotonic', side_effect=lambda: next(reloj)), \
                mock.patch('core.db_wait.connection.ensure_connection',
                           side_effect=OperationalError(2002, 'sin conexión')), \
                self.assertLogs('core.db_wait', 'ERROR'):
            res = self.client.post('/api/token/', self.LOGIN, format='json')
        self.assertEqual(res.status_code, 503)
        self.assertIn('iniciando', res.json()['detail'])

    def test_otros_errores_de_la_base_no_se_reintentan(self):
        with mock.patch('core.db_wait.time.sleep') as pausa, \
                mock.patch('core.db_wait.connection.ensure_connection',
                           side_effect=OperationalError(1045, 'Access denied')):
            with self.assertRaises(OperationalError):
                self.client.post('/api/token/', self.LOGIN, format='json')
        pausa.assert_not_called()
