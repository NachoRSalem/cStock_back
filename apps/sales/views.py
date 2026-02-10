from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from django.db.models import Sum, F
from .models import Venta
from .serializers import VentaSerializer
from apps.locations.models import Ubicacion
from apps.inventory.models import PedidoItem
class VentaViewSet(viewsets.ModelViewSet):
    queryset = Venta.objects.all().order_by('-fecha')
    serializer_class = VentaSerializer

    def perform_create(self, serializer):
        # Al igual que en pedidos, nos aseguramos de asignar al usuario logueado
        # Si no tenés login, usá el usuario hardcodeado como hicimos antes
        from django.contrib.auth import get_user_model
        User = get_user_model()
        admin_user = User.objects.first()
        serializer.save(vendedor=admin_user)

class ReporteEconomicoView(APIView):
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