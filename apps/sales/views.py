from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum, F

from apps.users.permissions import IsAdminUser
from .models import Venta
from .serializers import VentaSerializer
from apps.locations.models import Ubicacion
from apps.inventory.models import PedidoItem

class VentaViewSet(viewsets.ModelViewSet):
    queryset = Venta.objects.all()
    serializer_class = VentaSerializer

    def get_queryset(self):
        qs = Venta.objects.select_related('sucursal', 'vendedor').prefetch_related('items__producto').order_by('-fecha')
        sucursal_id = self.request.query_params.get('sucursal')
        if sucursal_id:
            qs = qs.filter(sucursal_id=sucursal_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(vendedor=self.request.user)

class ReporteEconomicoView(APIView):
    permission_classes = [IsAdminUser]
    def get(self, request):
        # Filtros opcionales
        sucursal_id = request.query_params.get('sucursal')
        fecha_desde = request.query_params.get('fecha_desde')
        fecha_hasta = request.query_params.get('fecha_hasta')

        # Base queryset de sucursales
        sucursales_qs = Ubicacion.objects.all()
        if sucursal_id:
            sucursales_qs = sucursales_qs.filter(id=sucursal_id)

        reporte = []
        totales = {
            'total_gastos': 0,
            'total_ventas': 0,
            'balance': 0
        }

        for suc in sucursales_qs:
            # 1. Sumar gastos de pedidos RECIBIDOS en esa sucursal
            gastos_qs = PedidoItem.objects.filter(
                pedido__destino=suc, 
                pedido__estado='recibido'
            )
            if fecha_desde:
                gastos_qs = gastos_qs.filter(pedido__fecha_creacion__gte=fecha_desde)
            if fecha_hasta:
                gastos_qs = gastos_qs.filter(pedido__fecha_creacion__lte=fecha_hasta)
            
            gastos = gastos_qs.aggregate(
                total=Sum(F('cantidad') * F('precio_costo_momento'))
            )['total'] or 0

            # 2. Sumar ingresos de ventas en esa sucursal
            ventas_qs = Venta.objects.filter(sucursal=suc)
            if fecha_desde:
                ventas_qs = ventas_qs.filter(fecha__gte=fecha_desde)
            if fecha_hasta:
                ventas_qs = ventas_qs.filter(fecha__lte=fecha_hasta)
            
            ingresos = ventas_qs.aggregate(
                total=Sum('total')
            )['total'] or 0

            balance = ingresos - gastos

            reporte.append({
                "sucursal_id": suc.id,
                "sucursal_nombre": suc.nombre,
                "total_gastos": float(gastos),
                "total_ventas": float(ingresos),
                "balance": float(balance)
            })

            # Acumular totales
            totales['total_gastos'] += float(gastos)
            totales['total_ventas'] += float(ingresos)
            totales['balance'] += float(balance)

        return Response({
            'por_sucursal': reporte,
            'totales': totales
        })