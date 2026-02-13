import io
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.users.permissions import IsAdminUser
from .models import PedidoItem
from .models import Pedido
from .serializers import PedidoSerializer
from django.http import FileResponse
from .utils import RemitoPDFGenerator 

class PedidoViewSet(viewsets.ModelViewSet):
    serializer_class = PedidoSerializer

    def get_queryset(self):
        user = self.request.user
        
        if user.is_superuser or user.rol == 'admin':
            return Pedido.objects.all()
        
        return Pedido.objects.filter(destino=user.sucursal_asignada)

    def perform_create(self, serializer):
        serializer.save(creado_por=self.request.user)

    @action(detail=True, methods=['post'])
    def enviar_a_revision(self, request, pk=None):
        """Pasa el pedido de Borrador a Pendiente de Aprobación."""
        pedido = self.get_object()
        if pedido.estado != 'borrador':
            return Response({'error': 'Solo pedidos en borrador pueden enviarse a revisión.'}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        pedido.estado = 'pendiente'
        pedido.save()
        return Response({'status': 'Pedido enviado a revisión del administrador.'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def aprobar(self, request, pk=None):
        """El Admin aprueba el pedido pendiente."""
        pedido = self.get_object()
        if pedido.estado != 'pendiente':
            return Response({'error': 'Solo pedidos pendientes pueden ser aprobados.'}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        pedido.estado = 'aprobado'
        pedido.save()
        return Response({'status': 'Pedido aprobado exitosamente.'})

    @action(detail=True, methods=['post'])
    def recibir(self, request, pk=None):
        """
        Endpoint: POST /api/inventory/pedidos/{id}/recibir/
        """
        pedido = self.get_object()
        
        items_data = request.data.get('items', [])
        
        try:
            for item_update in items_data:
                try:
                    item = PedidoItem.objects.get(id=item_update['id'], pedido=pedido)
                    item.sub_ubicacion_destino_id = item_update['sub_ubicacion_destino']
                    item.save()
                except PedidoItem.DoesNotExist:
                    return Response(
                        {'error': f"El item con id {item_update['id']} no pertenece al pedido {pedido.id}"},
                        status=status.HTTP_400_BAD_REQUEST
                    )
            
            pedido.marcar_como_recibido()
            return Response({'status': 'Pedido recibido y stock actualizado'}, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['get'])
    def descargar_pdf(self, request, pk=None):
        pedido = self.get_object()
        buffer = io.BytesIO()
        
        # Delegamos la responsabilidad del diseño a la clase utils
        reporte = RemitoPDFGenerator(buffer, pedido)
        reporte.generar()
        
        buffer.seek(0)
        return FileResponse(buffer, as_attachment=True, filename=f'remito_{pedido.id}.pdf')