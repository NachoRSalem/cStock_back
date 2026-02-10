from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import Pedido
from .serializers import PedidoSerializer

class PedidoViewSet(viewsets.ModelViewSet):
    queryset = Pedido.objects.all()
    serializer_class = PedidoSerializer

    def perform_create(self, serializer):
        serializer.save(creado_por=self.request.user)

    """def perform_create(self, serializer):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admin_user = User.objects.first()
        serializer.save(creado_por=admin_user)"""

    @action(detail=True, methods=['post'])
    def recibir(self, request, pk=None):
        """
        Endpoint: POST /api/inventory/pedidos/{id}/recibir/
        """
        pedido = self.get_object()
        
        # 1. Actualizamos las sub-ubicaciones enviadas desde el Frontend (React)
        # El body debe ser: {"items": [{"id": 1, "sub_ubicacion_destino": 5}, ...]}
        items_data = request.data.get('items', [])
        for item_update in items_data:
            from .models import PedidoItem
            item = PedidoItem.objects.get(id=item_update['id'], pedido=pedido)
            item.sub_ubicacion_destino_id = item_update['sub_ubicacion_destino']
            item.save()

        # 2. Ejecutamos la lógica de negocio que definimos en el modelo
        try:
            pedido.marcar_como_recibido()
            return Response({'status': 'Pedido recibido y stock actualizado'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)