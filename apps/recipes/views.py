from decimal import Decimal
import random
import time
from datetime import date

from django.db import transaction
from django.db.models import Sum
from rest_framework.pagination import PageNumberPagination
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.inventory.models import Stock
from apps.locations.models import SubUbicacion
from apps.users.permissions import IsAdminUser

from .models import Fabricacion, FabricacionConsumo, Receta
from .permissions import IsAdminOrSucursalUser
from .serializers import FabricacionSerializer, FabricarSerializer, RecetaSerializer


class FabricacionPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50


class RecetaViewSet(viewsets.ModelViewSet):
    queryset = Receta.objects.all().select_related('producto_final').prefetch_related('insumos__producto_insumo')
    serializer_class = RecetaSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminUser()]
        if self.action in ['fabricar', 'fabricables']:
            return [IsAdminOrSucursalUser()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = super().get_queryset()
        activa = self.request.query_params.get('activa')
        if activa is not None:
            if activa.lower() in ['true', '1', 'yes']:
                qs = qs.filter(activa=True)
            elif activa.lower() in ['false', '0', 'no']:
                qs = qs.filter(activa=False)
        return qs.order_by('producto_final__nombre')

    @action(detail=False, methods=['get'])
    def fabricables(self, request):
        recetas = self.get_queryset().filter(activa=True)
        serializer = self.get_serializer(recetas, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def fabricar(self, request, pk=None):
        receta = self.get_object()
        if not receta.activa:
            return Response({'error': 'La receta está inactiva.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = FabricarSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        cantidad_producir = serializer.validated_data['cantidad_producir']
        sub_destino_id = serializer.validated_data['sub_ubicacion_destino']
        sub_origen_map = serializer.validated_data['sub_ubicaciones_origen']

        user = request.user
        sub_destino = SubUbicacion.objects.select_related('ubicacion').filter(id=sub_destino_id).first()
        if not sub_destino:
            return Response({'error': 'Sub-ubicación destino inválida.'}, status=status.HTTP_400_BAD_REQUEST)

        if user.rol == 'sucursal':
            if not user.sucursal_asignada:
                return Response({'error': 'El usuario sucursal no tiene sucursal asignada.'}, status=status.HTTP_400_BAD_REQUEST)
            if sub_destino.ubicacion_id != user.sucursal_asignada_id:
                return Response({'error': 'Solo podés fabricar en tu sucursal.'}, status=status.HTTP_403_FORBIDDEN)

        try:
            with transaction.atomic():
                fabricacion = Fabricacion.objects.create(
                    receta=receta,
                    ubicacion=sub_destino.ubicacion,
                    sub_ubicacion_destino=sub_destino,
                    cantidad_producida=cantidad_producir,
                    creado_por=user,
                )

                for receta_insumo in receta.insumos.select_related('producto_insumo').all():
                    required_qty = (Decimal(receta_insumo.cantidad_requerida) * Decimal(cantidad_producir)).quantize(Decimal('0.001'))
                    origen_id = sub_origen_map.get(str(receta_insumo.id)) or sub_origen_map.get(receta_insumo.id)
                    if not origen_id:
                        raise ValueError(f'Falta sub-ubicación origen para el insumo {receta_insumo.producto_insumo.nombre}.')

                    sub_origen = SubUbicacion.objects.select_related('ubicacion').filter(id=origen_id).first()
                    if not sub_origen:
                        raise ValueError(f'Sub-ubicación origen inválida para {receta_insumo.producto_insumo.nombre}.')

                    if user.rol == 'sucursal' and sub_origen.ubicacion_id != user.sucursal_asignada_id:
                        raise PermissionError('Solo podés consumir insumos de tu sucursal.')

                    stocks = Stock.objects.select_for_update().filter(
                        producto=receta_insumo.producto_insumo,
                        sub_ubicacion=sub_origen,
                        cantidad__gt=0,
                    ).order_by('fecha_ingreso', 'id')

                    total_disponible = stocks.aggregate(total=Sum('cantidad'))['total'] or Decimal('0.000')
                    if total_disponible < required_qty:
                        raise ValueError(
                            f'Stock insuficiente de {receta_insumo.producto_insumo.nombre}. Disponible: {total_disponible}, requerido: {required_qty}.'
                        )

                    restante = required_qty
                    for stock_item in stocks:
                        if restante <= 0:
                            break

                        consumir = min(Decimal(stock_item.cantidad), restante)
                        stock_item.cantidad = (Decimal(stock_item.cantidad) - consumir).quantize(Decimal('0.001'))
                        stock_item.save(update_fields=['cantidad', 'ultima_actualizacion'])

                        FabricacionConsumo.objects.create(
                            fabricacion=fabricacion,
                            receta_insumo=receta_insumo,
                            sub_ubicacion_origen=sub_origen,
                            lote=stock_item.lote,
                            cantidad_consumida=consumir,
                        )
                        restante -= consumir

                # Alta de stock del producto final
                if receta.producto_final.dias_caducidad:
                    timestamp = int(time.time() * 1000)
                    lote = f'FAB-{timestamp}-{random.randint(1000, 9999)}'
                    stock_final = Stock.objects.create(
                        producto=receta.producto_final,
                        sub_ubicacion=sub_destino,
                        cantidad=cantidad_producir,
                        lote=lote,
                        fecha_ingreso=date.today(),
                    )
                else:
                    stock_final, _ = Stock.objects.get_or_create(
                        producto=receta.producto_final,
                        sub_ubicacion=sub_destino,
                        lote=None,
                        defaults={'cantidad': Decimal('0.000')},
                    )
                    stock_final.cantidad = (Decimal(stock_final.cantidad) + Decimal(cantidad_producir)).quantize(Decimal('0.001'))
                    stock_final.save(update_fields=['cantidad', 'ultima_actualizacion'])

                response_data = FabricacionSerializer(fabricacion).data
                response_data['stock_generado_id'] = stock_final.id
                return Response(response_data, status=status.HTTP_201_CREATED)
        except PermissionError as e:
            return Response({'error': str(e)}, status=status.HTTP_403_FORBIDDEN)
        except ValueError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class FabricacionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = FabricacionSerializer
    permission_classes = [IsAdminOrSucursalUser]
    pagination_class = FabricacionPagination

    def get_queryset(self):
        qs = Fabricacion.objects.select_related(
            'receta',
            'receta__producto_final',
            'ubicacion',
            'sub_ubicacion_destino',
            'creado_por',
        ).prefetch_related(
            'consumos',
            'consumos__receta_insumo',
            'consumos__receta_insumo__producto_insumo',
            'consumos__sub_ubicacion_origen',
        ).order_by('-creado_en')

        user = self.request.user
        if user.rol == 'sucursal':
            if not user.sucursal_asignada_id:
                return Fabricacion.objects.none()
            qs = qs.filter(ubicacion_id=user.sucursal_asignada_id)
            return qs

        ubicacion = self.request.query_params.get('ubicacion')
        if ubicacion:
            qs = qs.filter(ubicacion_id=ubicacion)

        return qs
