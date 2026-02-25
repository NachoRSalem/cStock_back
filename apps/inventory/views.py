import io
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.users.permissions import IsAdminUser
from .models import PedidoItem, Stock
from .models import Pedido
from .serializers import PedidoSerializer, StockSerializer
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
        user = self.request.user
        # Admin: auto-aprobar pedido (no necesita revisión)
        if user.rol == 'admin':
            serializer.save(creado_por=user, estado='aprobado')
        else:
            # Sucursal: queda en borrador para enviar a revisión
            serializer.save(creado_por=user, estado='borrador')

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

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def rechazar(self, request, pk=None):
        """El Admin rechaza el pedido pendiente."""
        pedido = self.get_object()
        if pedido.estado != 'pendiente':
            return Response({'error': 'Solo pedidos pendientes pueden ser rechazados.'}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        pedido.estado = 'rechazado'
        pedido.save()
        return Response({'status': 'Pedido rechazado.'})

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

class StockViewSet(viewsets.ReadOnlyModelViewSet):
    """
    Consulta de stock por ubicación.
    Usuarios de sucursal solo ven su stock.
    Admins ven todo el stock.
    """
    serializer_class = StockSerializer
    
    def get_queryset(self):
        user = self.request.user
        queryset = Stock.objects.all().select_related(
            'producto', 'producto__categoria', 
            'sub_ubicacion', 'sub_ubicacion__ubicacion'
        )
        
        # Filtrar por rol
        if user.rol == 'sucursal' and user.sucursal_asignada:
            queryset = queryset.filter(sub_ubicacion__ubicacion=user.sucursal_asignada)
        
        # Filtros opcionales por query params
        ubicacion = self.request.query_params.get('ubicacion')
        if ubicacion:
            # Intentar filtrar por ID si es numérico, sino por nombre
            if ubicacion.isdigit():
                queryset = queryset.filter(sub_ubicacion__ubicacion_id=ubicacion)
            else:
                queryset = queryset.filter(sub_ubicacion__ubicacion__nombre=ubicacion)
        
        sub_ubicacion_id = self.request.query_params.get('sub_ubicacion')
        if sub_ubicacion_id:
            queryset = queryset.filter(sub_ubicacion_id=sub_ubicacion_id)
        
        producto_id = self.request.query_params.get('producto')
        if producto_id:
            queryset = queryset.filter(producto_id=producto_id)
        
        # Filtro para mostrar solo items con stock
        solo_con_stock = self.request.query_params.get('solo_con_stock')
        if solo_con_stock and solo_con_stock.lower() in ['true', '1', 'yes']:
            queryset = queryset.filter(cantidad__gt=0)
        
        return queryset