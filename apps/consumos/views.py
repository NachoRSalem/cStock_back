from decimal import Decimal

from django.db.models import Sum
from rest_framework import status, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action

from apps.locations.models import SubUbicacion
from apps.products.models import Producto, Categoria
from apps.users.permissions import IsAdminUser

from .models import ConsumoCocina, ProduccionVianda
from .serializers import ConsumoCocinaSerializer, ProduccionViandaSerializer


class ConsumoPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


class ConsumoCocinaViewSet(viewsets.ModelViewSet):
    queryset = ConsumoCocina.objects.select_related(
        'ubicacion', 'registrado_por'
    ).prefetch_related(
        'items__producto', 'items__sub_ubicacion_origen'
    ).order_by('-fecha', '-creado_en')
    serializer_class = ConsumoCocinaSerializer
    pagination_class = ConsumoPagination

    def get_permissions(self):
        if self.action in ['destroy']:
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if user.rol == 'sucursal':
            if not user.sucursal_asignada_id:
                return ConsumoCocina.objects.none()
            qs = qs.filter(ubicacion_id=user.sucursal_asignada_id)
        else:
            ubicacion = self.request.query_params.get('ubicacion')
            if ubicacion:
                qs = qs.filter(ubicacion_id=ubicacion)

        fecha_desde = self.request.query_params.get('fecha_desde')
        fecha_hasta = self.request.query_params.get('fecha_hasta')
        if fecha_desde:
            qs = qs.filter(fecha__gte=fecha_desde)
        if fecha_hasta:
            qs = qs.filter(fecha__lte=fecha_hasta)

        return qs

    def create(self, request, *args, **kwargs):
        data = request.data
        ubicacion_id = data.get('ubicacion')
        fecha = data.get('fecha')
        items_raw = data.get('items', [])

        user = request.user

        if user.rol == 'sucursal':
            if not user.sucursal_asignada_id:
                return Response({'error': 'No tenés sucursal asignada.'}, status=status.HTTP_400_BAD_REQUEST)
            ubicacion_id = user.sucursal_asignada_id

        if not ubicacion_id or not fecha:
            return Response({'error': 'Faltan campos obligatorios: ubicacion, fecha.'}, status=status.HTTP_400_BAD_REQUEST)

        if not items_raw:
            return Response({'error': 'Debe incluir al menos un item.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            items_data = []
            for it in items_raw:
                producto = Producto.objects.filter(id=it['producto']).first()
                if not producto:
                    raise ValueError(f"Producto {it['producto']} no encontrado.")

                sub = SubUbicacion.objects.select_related('ubicacion').filter(id=it['sub_ubicacion_origen']).first()
                if not sub:
                    raise ValueError(f"Sub-ubicación {it['sub_ubicacion_origen']} no encontrada.")

                if user.rol == 'sucursal' and sub.ubicacion_id != user.sucursal_asignada_id:
                    raise PermissionError('Solo podés consumir stock de tu sucursal.')

                items_data.append({
                    'producto': producto,
                    'cantidad': Decimal(str(it['cantidad'])),
                    'sub_ubicacion_origen': sub,
                })

            consumo = ConsumoCocina.objects.create(
                ubicacion_id=ubicacion_id,
                fecha=fecha,
                registrado_por=user,
            )
            consumo.procesar_consumo(items_data)

            serializer = self.get_serializer(consumo)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except PermissionError as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class ProduccionViandaViewSet(viewsets.ModelViewSet):
    queryset = ProduccionVianda.objects.select_related(
        'ubicacion', 'sub_ubicacion_destino', 'registrado_por'
    ).prefetch_related(
        'items__producto'
    ).order_by('-fecha', '-creado_en')
    serializer_class = ProduccionViandaSerializer
    pagination_class = ConsumoPagination

    def get_permissions(self):
        if self.action in ['destroy']:
            return [IsAdminUser()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if user.rol == 'sucursal':
            if not user.sucursal_asignada_id:
                return ProduccionVianda.objects.none()
            qs = qs.filter(ubicacion_id=user.sucursal_asignada_id)
        else:
            ubicacion = self.request.query_params.get('ubicacion')
            if ubicacion:
                qs = qs.filter(ubicacion_id=ubicacion)

        fecha_desde = self.request.query_params.get('fecha_desde')
        fecha_hasta = self.request.query_params.get('fecha_hasta')
        if fecha_desde:
            qs = qs.filter(fecha__gte=fecha_desde)
        if fecha_hasta:
            qs = qs.filter(fecha__lte=fecha_hasta)

        return qs

    @action(detail=False, methods=['post'], url_path='crear-vianda-rapida')
    def crear_vianda_rapida(self, request):
        nombre = request.data.get('nombre', '').strip()
        precio_venta = request.data.get('precio_venta')

        if not nombre:
            return Response({'error': 'El nombre es obligatorio.'}, status=status.HTTP_400_BAD_REQUEST)
        if not precio_venta:
            return Response({'error': 'El precio de venta es obligatorio.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            precio_venta = Decimal(str(precio_venta))
        except Exception:
            return Response({'error': 'Precio de venta inválido.'}, status=status.HTTP_400_BAD_REQUEST)

        if precio_venta <= 0:
            return Response({'error': 'El precio de venta debe ser mayor a 0.'}, status=status.HTTP_400_BAD_REQUEST)

        categoria_vianda = Categoria.objects.filter(nombre__iexact='Vianda').first()
        if not categoria_vianda:
            return Response({'error': 'No existe la categoría "Vianda" en el sistema.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            producto = Producto.objects.create(
                nombre=nombre,
                categoria=categoria_vianda,
                tipo_conservacion='ambiente',
                precio_venta=precio_venta,
                costo_compra=Decimal('0'),
                es_fabricable=False,
            )
        except Exception as e:
            return Response({'error': f'Error creando producto: {str(e)}'}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            'id': producto.id,
            'nombre': producto.nombre,
            'precio_venta': str(producto.precio_venta),
            'categoria_nombre': producto.categoria.nombre,
        }, status=status.HTTP_201_CREATED)

    def create(self, request, *args, **kwargs):
        data = request.data
        ubicacion_id = data.get('ubicacion')
        sub_destino_id = data.get('sub_ubicacion_destino')
        fecha = data.get('fecha')
        items_raw = data.get('items', [])

        user = request.user

        if user.rol == 'sucursal':
            if not user.sucursal_asignada_id:
                return Response({'error': 'No tenés sucursal asignada.'}, status=status.HTTP_400_BAD_REQUEST)
            ubicacion_id = user.sucursal_asignada_id

        if not ubicacion_id or not sub_destino_id or not fecha:
            return Response({'error': 'Faltan campos obligatorios: ubicacion, sub_ubicacion_destino, fecha.'}, status=status.HTTP_400_BAD_REQUEST)

        if not items_raw:
            return Response({'error': 'Debe incluir al menos un item.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            sub_destino = SubUbicacion.objects.select_related('ubicacion').filter(id=sub_destino_id).first()
            if not sub_destino:
                raise ValueError(f"Sub-ubicación {sub_destino_id} no encontrada.")

            if int(sub_destino.ubicacion_id) != int(ubicacion_id):
                raise ValueError("La sub-ubicación destino no pertenece a la sucursal seleccionada.")

            if user.rol == 'sucursal' and sub_destino.ubicacion_id != user.sucursal_asignada_id:
                raise PermissionError('Solo podés registrar producción en tu sucursal.')

            items_data = []
            for it in items_raw:
                producto = Producto.objects.select_related('categoria').filter(id=it['producto']).first()
                if not producto:
                    raise ValueError(f"Producto {it['producto']} no encontrado.")
                if producto.categoria.nombre.lower() != 'vianda':
                    raise ValueError(f"El producto '{producto.nombre}' no es de categoría Vianda.")

                cantidad = int(it['cantidad'])
                if cantidad <= 0:
                    raise ValueError(f"La cantidad de {producto.nombre} debe ser mayor a 0.")

                items_data.append({
                    'producto': producto,
                    'cantidad': cantidad,
                })

            produccion = ProduccionVianda.objects.create(
                ubicacion_id=ubicacion_id,
                sub_ubicacion_destino=sub_destino,
                fecha=fecha,
                registrado_por=user,
            )
            produccion.procesar_produccion(items_data)

            serializer = self.get_serializer(produccion)
            return Response(serializer.data, status=status.HTTP_201_CREATED)

        except PermissionError as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
