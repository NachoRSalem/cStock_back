from rest_framework import viewsets
from apps.users.permissions import IsAdminUser
from .models import Ubicacion, SubUbicacion
from .serializers import UbicacionSerializer, SubUbicacionSerializer

class UbicacionViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet para ver las sucursales y sus heladeras. 
    Usamos ReadOnly porque el Admin las crea por el panel, 
    la App solo las consulta.
    """
    queryset = Ubicacion.objects.all()
    serializer_class = UbicacionSerializer

class SubUbicacionViewSet(viewsets.ModelViewSet):
    """
    CRUD completo de SubUbicaciones.
    Solo admins pueden crear/editar/eliminar.
    """
    queryset = SubUbicacion.objects.all().select_related('ubicacion')
    serializer_class = SubUbicacionSerializer
    permission_classes = [IsAdminUser]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        # Filtro opcional por ubicacion
        ubicacion_id = self.request.query_params.get('ubicacion')
        if ubicacion_id:
            queryset = queryset.filter(ubicacion_id=ubicacion_id)
        return queryset