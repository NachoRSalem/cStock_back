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
    queryset = Venta.objects.all().order_by('-fecha')
    serializer_class = VentaSerializer

    def perform_create(self, serializer):
        serializer.save(vendedor=self.request.user)

class ReporteEconomicoView(APIView):
    permission_classes = [IsAdminUser]
    def get(self, request):
        reporte = []
        sucursales = Ubicacion.objects.all()

        for suc in sucursales:
            # 1. Sumar gastos de pedidos RECIBIDOS en esa sucursal
            gastos = PedidoItem.objects.filter(
                pedido__destino=suc, 
                pedido__estado='recibido'
            ).aggregate(
                total=Sum(F('cantidad') * F('precio_costo_momento'))
            )['total'] or 0

            # 2. Sumar ingresos de ventas en esa sucursal
            ingresos = Venta.objects.filter(sucursal=suc).aggregate(
                total=Sum('total')
            )['total'] or 0

            reporte.append({
                "sucursal_nombre": suc.nombre,
                "total_gastos": gastos,
                "total_ventas": ingresos,
                "balance": ingresos - gastos
            })

        return Response(reporte)