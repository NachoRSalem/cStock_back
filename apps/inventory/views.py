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
        El Admin aprueba el pedido pendiente con origen mixto.
        Body esperado (nuevo formato):
        {
            "items": [
                {
                    "id": <pedido_item_id>,
                    "origen_tipo": "distribuidor" | "sucursal",
                    "origen_sucursal": <id> (solo si origen_tipo='sucursal'),
                    "sub_ubicaciones_origen": [...] (solo si origen_tipo='sucursal')
                },
                ...
            ]
        }
        """
        pedido = self.get_object()
        if pedido.estado != 'pendiente':
            return Response({'error': 'Solo pedidos pendientes pueden ser aprobados.'},
                            status=status.HTTP_400_BAD_REQUEST)

        items_data = request.data.get('items', [])

        # Compatibilidad con formato antiguo (origen_tipo a nivel de pedido)
        origen_tipo_legacy = request.data.get('origen_tipo')
        origen_sucursal_legacy = request.data.get('origen_sucursal')

        if origen_tipo_legacy and not any('origen_tipo' in item for item in items_data):
            # Formato antiguo: aplicar origen_tipo a todos los items
            for item_data in items_data:
                item_data['origen_tipo'] = origen_tipo_legacy
                if origen_tipo_legacy == 'sucursal':
                    item_data['origen_sucursal'] = origen_sucursal_legacy

        try:
            with transaction.atomic():
                # Contadores para determinar el origen_tipo del pedido
                items_distribuidor = []
                items_sucursal = []
                sucursales_origen_set = set()

                # Procesar cada item según su origen
                for item_data in items_data:
                    try:
                        item = PedidoItem.objects.get(id=item_data['id'], pedido=pedido)
                        origen_tipo_item = item_data.get('origen_tipo', 'distribuidor')

                        if origen_tipo_item == 'sucursal':
                            items_sucursal.append(item_data)
                            origen_sucursal_id = item_data.get('origen_sucursal')

                            if not origen_sucursal_id:
                                raise Exception(f"El producto {item.producto.nombre} marcado como 'sucursal' no tiene sucursal de origen especificada.")

                            sucursales_origen_set.add(origen_sucursal_id)

                            # Reutilizar lógica existente de descuento FIFO
                            sub_ubicaciones_origen = item_data.get('sub_ubicaciones_origen', [])

                            if not sub_ubicaciones_origen:
                                raise Exception(f"El producto {item.producto.nombre} no tiene sub-ubicaciones de origen especificadas.")

                            # Validar que la suma de cantidades coincide con la cantidad pedida
                            total_cantidad = sum(ub['cantidad'] for ub in sub_ubicaciones_origen)
                            if total_cantidad != item.cantidad:
                                raise Exception(f"La cantidad total asignada para {item.producto.nombre} ({total_cantidad}) no coincide con la cantidad pedida ({item.cantidad})")

                            # Procesar cada sub-ubicación y descontar stock usando FIFO
                            detalles_origen = []
                            for ub_data in sub_ubicaciones_origen:
                                sub_ubicacion_id = ub_data['sub_ubicacion']
                                cantidad_a_tomar = ub_data['cantidad']

                                # Obtener todos los lotes del producto en esta sub-ubicación
                                # Ordenar por fecha_ingreso (FIFO) - los sin fecha van al final
                                stocks_disponibles = Stock.objects.filter(
                                    producto=item.producto,
                                    sub_ubicacion_id=sub_ubicacion_id,
                                    cantidad__gt=0
                                ).order_by('fecha_ingreso', 'id')

                                if not stocks_disponibles.exists():
                                    raise Exception(f"No hay stock de {item.producto.nombre} en la sub-ubicación especificada de la sucursal origen.")

                                # Verificar que hay stock suficiente en total
                                total_disponible = sum(s.cantidad for s in stocks_disponibles)
                                if total_disponible < cantidad_a_tomar:
                                    raise Exception(f"Stock insuficiente en la sub-ubicación para {item.producto.nombre}. Disponible: {total_disponible}, Requerido: {cantidad_a_tomar}")

                                # Descontar de los lotes usando FIFO
                                cantidad_restante = cantidad_a_tomar
                                for stock_origen in stocks_disponibles:
                                    if cantidad_restante <= 0:
                                        break

                                    cantidad_a_descontar = min(stock_origen.cantidad, cantidad_restante)
                                    stock_origen.cantidad -= cantidad_a_descontar
                                    stock_origen.save()

                                    cantidad_restante -= cantidad_a_descontar

                                # Guardar detalle
                                detalles_origen.append({
                                    'sub_ubicacion_id': sub_ubicacion_id,
                                    'sub_ubicacion_nombre': stocks_disponibles.first().sub_ubicacion.nombre,
                                    'cantidad': cantidad_a_tomar
                                })

                            # Guardar los detalles en el item
                            item.sub_ubicaciones_origen_detalle = detalles_origen
                            if detalles_origen:
                                item.sub_ubicacion_origen_id = detalles_origen[0]['sub_ubicacion_id']
                            item.save()

                        elif origen_tipo_item == 'distribuidor':
                            items_distribuidor.append(item_data)
                            # No descontar stock, dejar sub_ubicaciones_origen_detalle vacío
                            item.sub_ubicaciones_origen_detalle = None
                            item.sub_ubicacion_origen = None
                            item.save()

                    except PedidoItem.DoesNotExist:
                        raise Exception(f"El item con id {item_data['id']} no pertenece al pedido {pedido.id}")

                # Determinar el origen_tipo del pedido
                if len(items_sucursal) == 0:
                    pedido.origen_tipo = 'distribuidor'
                    pedido.origen_sucursal = None
                elif len(items_distribuidor) == 0:
                    pedido.origen_tipo = 'sucursal'
                    # Usar la primera sucursal origen encontrada
                    pedido.origen_sucursal_id = list(sucursales_origen_set)[0] if sucursales_origen_set else None
                else:
                    pedido.origen_tipo = 'mixto'
                    # Para pedidos mixtos, guardar la primera sucursal origen
                    pedido.origen_sucursal_id = list(sucursales_origen_set)[0] if sucursales_origen_set else None

                pedido.estado = 'aprobado'
                pedido.save()

            return Response({
                'status': 'Pedido aprobado exitosamente.',
                'origen_tipo': pedido.origen_tipo
            })

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

class StockViewSet(viewsets.ModelViewSet):
    """
    Consulta de stock por ubicación.
    Usuarios de sucursal solo ven su stock.
    Admins ven todo el stock.
    Admins pueden crear y actualizar registros de stock.
    """
    serializer_class = StockSerializer
    
    def get_permissions(self):
        """
        Solo los admins pueden crear, actualizar o eliminar stock.
        Todos pueden listar (sujeto a filtros por rol en get_queryset).
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        return super().get_permissions()
    
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