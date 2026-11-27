"""
En producción los servicios se duermen cuando no se usan. Al despertar, el back puede
estar listo antes que MySQL: sin esto, la primera petición (normalmente el login) daba error 500.

Solo se reintenta la apertura de la conexión, antes de ejecutar la vista, así que
nunca se repite una operación.
"""
import logging
import time

from django.db import OperationalError, connection
from django.http import JsonResponse

logger = logging.getLogger(__name__)

# Errores de MySQL que significan "todavía no pude conectarme".
ERRORES_DE_CONEXION = {2002, 2003, 2013}
ESPERA_MAXIMA = 20  # segundos
PAUSA = 1  # segundos entre intentos

MENSAJE = 'El sistema se está iniciando. Esperá unos segundos y volvé a intentar.'


class EsperarBaseDeDatosMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.method != 'OPTIONS' and request.path.startswith(('/api/', '/admin/')):
            if not self._conectar():
                return JsonResponse({'detail': MENSAJE}, status=503, headers={'Retry-After': '5'})
        return self.get_response(request)

    def _conectar(self):
        limite = time.monotonic() + ESPERA_MAXIMA
        while True:
            try:
                connection.ensure_connection()
                return True
            except OperationalError as error:
                codigo = error.args[0] if error.args else None
                if codigo not in ERRORES_DE_CONEXION:
                    raise
                if time.monotonic() + PAUSA >= limite:
                    logger.error('La base de datos no respondió a tiempo: %s', error)
                    return False
                time.sleep(PAUSA)
