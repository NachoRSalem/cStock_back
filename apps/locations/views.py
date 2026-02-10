from rest_framework import viewsets
from .models import Ubicacion
from .serializers import UbicacionSerializer

class UbicacionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para ver las sucursales y sus heladeras. 
    Usamos ReadOnly porque el Admin las crea por el panel, 
    la App solo las consulta.
    """
    queryset = Ubicacion.objects.all()
    serializer_class = UbicacionSerializer