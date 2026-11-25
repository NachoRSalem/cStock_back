from decimal import Decimal

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

from . import units
from .models import Categoria, Producto

User = get_user_model()


class UnidadesTests(APITestCase):
    def test_ejemplo_del_negocio(self):
        # 10 kg a $20.000 -> $2.000 el kg
        self.assertEqual(units.precio_normalizado('20000', '10', 'kg', 'kg'), Decimal('2000.00'))

    def test_conversion_entre_unidades_de_la_misma_magnitud(self):
        self.assertEqual(units.precio_normalizado('20000', '10000', 'g', 'kg'), Decimal('2000.00'))
        self.assertEqual(units.precio_normalizado('900', '1', 'l', 'ml'), Decimal('0.90'))
        self.assertEqual(units.precio_normalizado('500', '12', 'unidad', 'unidad'), Decimal('41.67'))

    def test_magnitudes_distintas_no_se_convierten(self):
        with self.assertRaises(ValueError):
            units.precio_normalizado('100', '1', 'l', 'kg')


class ProductoApiTests(APITestCase):
    def setUp(self):
        self.admin = User.objects.create_user('admin', password='x', rol='admin')
        self.sucursal = User.objects.create_user('suc', password='x', rol='sucursal')
        self.cat = Categoria.objects.create(nombre='Almacén')
        self.client.force_authenticate(self.admin)

    def payload(self, **extra):
        data = {
            'nombre': 'Harina', 'categoria': self.cat.id, 'tipo_conservacion': 'ambiente',
            'precio_venta': '3000', 'unidad_medida': 'kg',
        }
        data.update(extra)
        return data

    def test_costo_se_calcula_desde_el_envase(self):
        res = self.client.post('/api/products/productos/', self.payload(
            cantidad_envase='10', unidad_envase='kg', precio_envase='20000',
        ), format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(Decimal(res.data['costo_compra']), Decimal('2000.00'))

    def test_el_cliente_no_puede_forzar_el_costo_si_hay_envase(self):
        res = self.client.post('/api/products/productos/', self.payload(
            cantidad_envase='10', unidad_envase='kg', precio_envase='20000', costo_compra='1',
        ), format='json')
        self.assertEqual(Decimal(res.data['costo_compra']), Decimal('2000.00'))

    def test_unidad_incompatible_es_rechazada(self):
        res = self.client.post('/api/products/productos/', self.payload(
            cantidad_envase='1', unidad_envase='l', precio_envase='100',
        ), format='json')
        self.assertEqual(res.status_code, 400)

    def test_envase_incompleto_es_rechazado(self):
        res = self.client.post('/api/products/productos/', self.payload(cantidad_envase='10'), format='json')
        self.assertEqual(res.status_code, 400)

    def test_sin_envase_el_costo_es_obligatorio(self):
        self.assertEqual(self.client.post('/api/products/productos/', self.payload(), format='json').status_code, 400)
        res = self.client.post('/api/products/productos/', self.payload(costo_compra='50'), format='json')
        self.assertEqual(res.status_code, 201, res.data)

    def test_unidad_fuera_de_la_lista_es_rechazada(self):
        res = self.client.post(
            '/api/products/productos/', self.payload(unidad_medida='libras', costo_compra='5'), format='json'
        )
        self.assertEqual(res.status_code, 400)

    def test_editar_sin_cambiar_envase_respeta_el_costo_vigente(self):
        res = self.client.post('/api/products/productos/', self.payload(
            cantidad_envase='10', unidad_envase='kg', precio_envase='20000',
        ), format='json')
        pid = res.data['id']
        Producto.objects.filter(pk=pid).update(costo_compra=Decimal('2500'))  # costo de una compra posterior
        res = self.client.patch(f'/api/products/productos/{pid}/', {'precio_venta': '3500'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(Decimal(res.data['costo_compra']), Decimal('2500.00'))

    def test_vianda_solo_necesita_nombre_y_precio(self):
        res = self.client.post('/api/products/productos/', {
            'nombre': 'Milanesa con puré', 'precio_venta': '4500', 'es_vianda': True,
        }, format='json')
        self.assertEqual(res.status_code, 201, res.data)
        self.assertTrue(res.data['es_vianda'])
        self.assertEqual(Decimal(res.data['costo_compra']), Decimal('0'))
        self.assertEqual(res.data['categoria_nombre'], 'Vianda')

    def test_vianda_no_puede_ser_fabricable(self):
        res = self.client.post('/api/products/productos/', {
            'nombre': 'X', 'precio_venta': '1', 'es_vianda': True, 'es_fabricable': True,
        }, format='json')
        self.assertEqual(res.status_code, 400)

    def test_editar_precio_de_una_vianda(self):
        pid = self.client.post('/api/products/productos/', {
            'nombre': 'Tarta', 'precio_venta': '3000', 'es_vianda': True,
        }, format='json').data['id']
        res = self.client.patch(f'/api/products/productos/{pid}/', {'precio_venta': '3600'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(Decimal(res.data['precio_venta']), Decimal('3600'))
        self.assertTrue(res.data['es_vianda'])

    def test_solo_admin_edita_y_filtro_por_vianda(self):
        Producto.objects.create(nombre='V', categoria=self.cat, tipo_conservacion='ambiente',
                                precio_venta=1, costo_compra=0, es_vianda=True)
        Producto.objects.create(nombre='N', categoria=self.cat, tipo_conservacion='ambiente',
                                precio_venta=1, costo_compra=1)
        self.assertEqual(len(self.client.get('/api/products/productos/?es_vianda=true').data), 1)
        self.assertEqual(len(self.client.get('/api/products/productos/?es_vianda=false').data), 1)
        self.client.force_authenticate(self.sucursal)
        self.assertEqual(self.client.post('/api/products/productos/', {
            'nombre': 'Z', 'precio_venta': '1', 'es_vianda': True}, format='json').status_code, 403)

    def test_unidad_anterior_se_conserva_pero_no_se_puede_usar_en_productos_nuevos(self):
        # Productos cargados antes con unidades propias (pack, caja...) siguen funcionando.
        existente = Producto.objects.create(
            nombre='Gaseosa x pack', categoria=self.cat, tipo_conservacion='ambiente',
            precio_venta=Decimal('100'), costo_compra=Decimal('50'), unidad_medida='pack',
        )
        res = self.client.patch(f'/api/products/productos/{existente.id}/', {'precio_venta': '150'}, format='json')
        self.assertEqual(res.status_code, 200, res.data)
        self.assertEqual(res.data['unidad_medida'], 'pack')
        # En un producto nuevo (o al cambiarla) rige la lista cerrada.
        res = self.client.post('/api/products/productos/', self.payload(unidad_medida='pack', costo_compra='5'), format='json')
        self.assertEqual(res.status_code, 400)

    def test_precio_normalizado_exige_unidad_conocida(self):
        existente = Producto.objects.create(
            nombre='Caja de algo', categoria=self.cat, tipo_conservacion='ambiente',
            precio_venta=Decimal('100'), costo_compra=Decimal('50'), unidad_medida='caja',
        )
        res = self.client.patch(f'/api/products/productos/{existente.id}/', {
            'cantidad_envase': '10', 'unidad_envase': 'kg', 'precio_envase': '1000',
        }, format='json')
        self.assertEqual(res.status_code, 400)

