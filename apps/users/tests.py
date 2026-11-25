from django.test import TestCase

# Create your tests here.
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase


class LoginTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('kiosco', password='clave-segura-1', rol='sucursal')

    def login(self, username, password='clave-segura-1'):
        return self.client.post('/api/token/', {'username': username, 'password': password}, format='json')

    def test_login_normal(self):
        self.assertEqual(self.login('kiosco').status_code, 200)

    def test_login_sin_distinguir_mayusculas_ni_espacios(self):
        self.assertEqual(self.login('Kiosco').status_code, 200)
        self.assertEqual(self.login(' KIOSCO ').status_code, 200)

    def test_contrasena_incorrecta_sigue_fallando(self):
        self.assertEqual(self.login('kiosco', 'otra').status_code, 401)
        self.assertEqual(self.login('Kiosco', 'otra').status_code, 401)

    def test_usuario_inexistente(self):
        self.assertEqual(self.login('nadie').status_code, 401)
