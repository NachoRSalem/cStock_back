import io
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.db import transaction

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
        """
        El Admin aprueba el pedido pendiente.
        Body esperado:
        {
            "origen_tipo": "distribuidor" | "sucursal",
            "origen_sucursal": <id> (requerido si origen_tipo='sucursal'),
            "items": [
                {
                    "id": <pedido_item_id>,
                    "sub_ubicacion_origen": <sub_ubicacion_id del origen>
                },
                ...
            ]
        }
        """
        pedido = self.get_object()
        if pedido.estado != 'pendiente':
            return Response({'error': 'Solo pedidos pendientes pueden ser aprobados.'}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        origen_tipo = request.data.get('origen_tipo', 'distribuidor')
        origen_sucursal_id = request.data.get('origen_sucursal')
        items_data = request.data.get('items', [])
        
        try:
            with transaction.atomic():
                if origen_tipo == 'sucursal':
                    # Validar que se especificó la sucursal origen
                    if not origen_sucursal_id:
                        raise Exception("Debe especificar la sucursal de origen cuando origen_tipo='sucursal'")
                    
                    # Descontar stock de la sucursal origen
                    for item_data in items_data:
                        try:
                            item = PedidoItem.objects.get(id=item_data['id'], pedido=pedido)
                            sub_ubicacion_origen_id = item_data.get('sub_ubicacion_origen')
                            
                            if not sub_ubicacion_origen_id:
                                raise Exception(f"El producto {item.producto.nombre} no tiene sub_ubicación de origen especificada.")
                            
                            # Buscar el stock en la sucursal origen
                            try:
                                stock_origen = Stock.objects.get(
                                    producto=item.producto,
                                    sub_ubicacion_id=sub_ubicacion_origen_id
                                )
                                
                                if stock_origen.cantidad < item.cantidad:
                                    raise Exception(f"Stock insuficiente en la sucursal origen para {item.producto.nombre}. Disponible: {stock_origen.cantidad}, Requerido: {item.cantidad}")
                                
                                # Descontar del origen
                                stock_origen.cantidad -= item.cantidad
                                stock_origen.save()
                                
                                # Guardar la sub_ubicacion_origen en el item
                                item.sub_ubicacion_origen_id = sub_ubicacion_origen_id
                                item.save()
                                
                            except Stock.DoesNotExist:
                                raise Exception(f"No hay stock de {item.producto.nombre} en la sub-ubicación especificada de la sucursal origen.")
                        
                        except PedidoItem.DoesNotExist:
                            raise Exception(f"El item con id {item_data['id']} no pertenece al pedido {pedido.id}")
                
                pedido.estado = 'aprobado'
                pedido.origen_tipo = origen_tipo
                pedido.origen_sucursal_id = origen_sucursal_id if origen_tipo == 'sucursal' else None
                pedido.save()
                
            return Response({'status': 'Pedido aprobado exitosamente.'})
        
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def subir_pdf(self, request, pk=None):
        """Sube el PDF de la orden de compra al pedido."""
        pedido = self.get_object()
        
        if 'pdf' not in request.FILES:
            return Response({'error': 'No se proporcionó ningún archivo PDF.'}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        pdf_file = request.FILES['pdf']
        
        # Validar que sea PDF
        if not pdf_file.name.endswith('.pdf'):
            return Response({'error': 'El archivo debe ser un PDF.'}, 
                            status=status.HTTP_400_BAD_REQUEST)
        
        # Guardar el archivo
        pedido.pdf_archivo = pdf_file
        pedido.save()
        
        serializer = self.get_serializer(pedido, context={'request': request})
        return Response({
            'status': 'PDF subido exitosamente.',
            'pdf_url': serializer.data.get('pdf_url')
        })

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
    
    @action(detail=True, methods=['get'], permission_classes=[IsAdminUser])
    def disponibilidad_sucursales(self, request, pk=None):
        """
        Devuelve qué sucursales tienen stock disponible para cumplir este pedido.
        Retorna: [
            {
                "sucursal_id": int,
                "sucursal_nombre": str,
                "puede_completar": bool,
                "productos": [
                    {
                        "producto_id": int,
                        "producto_nombre": str,
                        "cantidad_requerida": int,
                        "cantidad_disponible": int,
                        "suficiente": bool
                    }
                ]
            }
        ]
        """
        from apps.locations.models import Ubicacion
        from django.db.models import Sum
        
        pedido = self.get_object()
        items = pedido.items.all()
        
        # Obtener todas las sucursales excepto el destino
        sucursales = Ubicacion.objects.exclude(id=pedido.destino.id)
        
        resultado = []
        
        for suc in sucursales:
            # Para cada sucursal, verificar si tiene stock de todos los productos requeridos
            productos_info = []
            puede_completar = True
            
            for item in items:
                # Sumar el stock disponible en todas las sub-ubicaciones de esta sucursal para este producto
                stock_total = Stock.objects.filter(
                    producto=item.producto,
                    sub_ubicacion__ubicacion=suc
                ).aggregate(total=Sum('cantidad'))['total'] or 0
                
                suficiente = stock_total >= item.cantidad
                if not suficiente:
                    puede_completar = False
                
                productos_info.append({
                    'producto_id': item.producto.id,
                    'producto_nombre': item.producto.nombre,
                    'cantidad_requerida': item.cantidad,
                    'cantidad_disponible': stock_total,
                    'suficiente': suficiente
                })
            
            resultado.append({
                'sucursal_id': suc.id,
                'sucursal_nombre': suc.nombre,
                'puede_completar': puede_completar,
                'productos': productos_info
            })
        
        return Response(resultado)

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