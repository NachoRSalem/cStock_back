from rest_framework import viewsets
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Sum, F, Count, Avg, DecimalField
from django.db.models.functions import Coalesce
from datetime import date, timedelta
from decimal import Decimal
from collections import defaultdict

from apps.users.permissions import IsAdminUser
from .models import Venta, VentaItem
from .serializers import VentaSerializer
from apps.locations.models import Ubicacion
from apps.inventory.models import Stock, Pedido, PedidoItem
from apps.products.models import Producto
from apps.recipes.models import Fabricacion

class VentaPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100

class VentaViewSet(viewsets.ModelViewSet):
    queryset = Venta.objects.all()
    serializer_class = VentaSerializer
    pagination_class = VentaPagination

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
        sucursal_id = request.query_params.get('sucursal')
        fecha_desde = request.query_params.get('fecha_desde')
        fecha_hasta = request.query_params.get('fecha_hasta')

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
            gastos_qs = PedidoItem.objects.filter(
                pedido__destino=suc,
                pedido__estado='recibido',
                pedido__origen_tipo='distribuidor'
            )
            if fecha_desde:
                gastos_qs = gastos_qs.filter(pedido__fecha_creacion__gte=fecha_desde)
            if fecha_hasta:
                gastos_qs = gastos_qs.filter(pedido__fecha_creacion__lte=fecha_hasta)

            gastos = gastos_qs.aggregate(
                total=Sum(F('cantidad') * F('precio_costo_momento'))
            )['total'] or 0

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

            totales['total_gastos'] += float(gastos)
            totales['total_ventas'] += float(ingresos)
            totales['balance'] += float(balance)

        return Response({
            'por_sucursal': reporte,
            'totales': totales
        })


class DashboardView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        sucursal_id = request.query_params.get('sucursal')
        fecha_desde = request.query_params.get('fecha_desde')
        fecha_hasta = request.query_params.get('fecha_hasta')
        stock_minimo = int(request.query_params.get('stock_minimo', 5))

        hoy = date.today()

        # --- STOCK QUERIES ---
        stock_qs = Stock.objects.select_related(
            'producto', 'producto__categoria', 'sub_ubicacion', 'sub_ubicacion__ubicacion'
        )

        if sucursal_id:
            stock_qs = stock_qs.filter(sub_ubicacion__ubicacion_id=sucursal_id)

        # Stock total por ubicación
        stock_por_ubicacion = []
        ubicaciones = Ubicacion.objects.all()
        if sucursal_id:
            ubicaciones = ubicaciones.filter(id=sucursal_id)

        for ub in ubicaciones:
            subs = ub.sub_ubicaciones.all()
            for sub in subs:
                stocks_en_sub = stock_qs.filter(sub_ubicacion=sub)
                productos_count = stocks_en_sub.count()
                valor_total = sum(
                    float(s.cantidad) * float(s.producto.precio_venta)
                    for s in stocks_en_sub
                )
                if productos_count > 0:
                    stock_por_ubicacion.append({
                        'sucursal': ub.nombre,
                        'sucursal_id': ub.id,
                        'sub_ubicacion': sub.nombre,
                        'sub_ubicacion_id': sub.id,
                        'tipo': sub.tipo,
                        'productos_count': productos_count,
                        'valor_total': round(valor_total, 2)
                    })

        # KPIs de stock
        total_stock_value = sum(
            float(s.cantidad) * float(s.producto.precio_venta)
            for s in stock_qs
        )
        stock_items_count = stock_qs.count()

        # Stock bajo
        stock_bajo_data = []
        productos_con_stock = stock_qs.values('producto').annotate(
            total_cantidad=Sum('cantidad')
        ).filter(total_cantidad__lt=stock_minimo)

        productos_bajo_ids = [p['producto'] for p in productos_con_stock]
        productos_bajo = Producto.objects.filter(id__in=productos_bajo_ids).select_related('categoria')

        for prod in productos_bajo:
            stock_items = stock_qs.filter(producto=prod)
            total_cant = sum(float(s.cantidad) for s in stock_items)
            stock_bajo_data.append({
                'producto_id': prod.id,
                'producto_nombre': prod.nombre,
                'categoria': prod.categoria.nombre if prod.categoria else None,
                'cantidad_actual': round(total_cant, 3),
                'stock_minimo': stock_minimo
            })

        # Productos próximos a vencer
        productos_proximos_vencer = []
        seen = set()
        for s in stock_qs:
            fv = s.fecha_vencimiento
            if fv is None:
                continue
            dias = s.dias_para_vencer
            if dias is None or dias < 0:
                continue
            if dias > 30:
                continue
            key = (s.producto.id, s.lote, s.sub_ubicacion.id)
            if key in seen:
                continue
            seen.add(key)

            if dias <= 7:
                urgencia = 'critica' if dias <= 3 else 'alta'
            elif dias <= 15:
                urgencia = 'media'
            else:
                urgencia = 'baja'

            productos_proximos_vencer.append({
                'producto_id': s.producto.id,
                'producto_nombre': s.producto.nombre,
                'categoria': s.producto.categoria.nombre if s.producto.categoria else None,
                'sucursal': s.sub_ubicacion.ubicacion.nombre,
                'sub_ubicacion': s.sub_ubicacion.nombre,
                'lote': s.lote,
                'fecha_ingreso': str(s.fecha_ingreso) if s.fecha_ingreso else None,
                'fecha_vencimiento': str(fv) if fv else None,
                'dias_restantes': dias,
                'cantidad': float(s.cantidad),
                'urgencia': urgencia
            })

        productos_proximos_vencer.sort(key=lambda x: x['dias_restantes'])

        expiring_7 = len([x for x in productos_proximos_vencer if x['dias_restantes'] <= 7])
        expiring_15 = len([x for x in productos_proximos_vencer if x['dias_restantes'] <= 15])
        expiring_30 = len([x for x in productos_proximos_vencer if x['dias_restantes'] <= 30])

        # --- VENTAS QUERIES ---
        ventas_qs = Venta.objects.all()
        if sucursal_id:
            ventas_qs = ventas_qs.filter(sucursal_id=sucursal_id)
        if fecha_desde:
            ventas_qs = ventas_qs.filter(fecha__gte=fecha_desde)
        if fecha_hasta:
            ventas_qs = ventas_qs.filter(fecha__lte=fecha_hasta)

        total_ventas_periodo = float(ventas_qs.aggregate(total=Coalesce(Sum('total'), Decimal('0')))['total'] or 0)
        cantidad_ventas = ventas_qs.count()
        promedio_ticket = total_ventas_periodo / cantidad_ventas if cantidad_ventas > 0 else 0

        # Fetch all VentaItems for the filtered ventas
        venta_items = VentaItem.objects.filter(venta__in=ventas_qs).select_related('producto', 'producto__categoria')

        # Productos más vendidos - calculate in Python
        prod_stats = defaultdict(lambda: {'cantidad': 0, 'revenue': 0.0})
        for item in venta_items:
            key = (item.producto.nombre, item.producto.categoria.nombre if item.producto.categoria else None)
            prod_stats[key]['cantidad'] += item.cantidad
            prod_stats[key]['revenue'] += float(item.cantidad * item.precio_venta_momento)

        productos_mas_vendidos = sorted(
            [
                {
                    'producto_nombre': k[0],
                    'categoria': k[1],
                    'cantidad_vendida': v['cantidad'],
                    'revenue': round(v['revenue'], 2)
                }
                for k, v in prod_stats.items()
            ],
            key=lambda x: x['cantidad_vendida'],
            reverse=True
        )[:10]

        # Ventas por categoría - calculate in Python
        cat_stats = defaultdict(lambda: {'cantidad': 0, 'revenue': 0.0})
        for item in venta_items:
            cat = item.producto.categoria.nombre if item.producto.categoria else 'Sin categoría'
            cat_stats[cat]['cantidad'] += item.cantidad
            cat_stats[cat]['revenue'] += float(item.cantidad * item.precio_venta_momento)

        total_revenue_categoria = sum(v['revenue'] for v in cat_stats.values())
        ventas_por_categoria_data = sorted(
            [
                {
                    'categoria': k,
                    'cantidad': v['cantidad'],
                    'revenue': round(v['revenue'], 2),
                    'porcentaje': round((v['revenue'] / total_revenue_categoria * 100) if total_revenue_categoria > 0 else 0, 1)
                }
                for k, v in cat_stats.items()
            ],
            key=lambda x: x['revenue'],
            reverse=True
        )

        # Tendencia de ventas (diario)
        tendencia_data = []
        if fecha_desde and fecha_hasta:
            from django.db.models.functions import TruncDate
            ventas_diarias = (
                ventas_qs
                .annotate(fecha_date=TruncDate('fecha'))
                .values('fecha_date')
                .annotate(
                    total_ventas=Sum('total'),
                    cantidad_items=Sum('items__cantidad')
                )
                .order_by('fecha_date')
            )
            tendencia_data = [
                {
                    'fecha': str(v['fecha_date']),
                    'total_ventas': float(v['total_ventas'] or 0),
                    'cantidad_items': v['cantidad_items'] or 0,
                    'promedio_ticket': float(v['total_ventas'] or 0) / 1 if v['total_ventas'] else 0
                }
                for v in ventas_diarias
            ]

        # --- PEDIDOS ---
        pedidos_qs = Pedido.objects.all()
        if sucursal_id:
            pedidos_qs = pedidos_qs.filter(destino_id=sucursal_id)
        if fecha_desde:
            pedidos_qs = pedidos_qs.filter(fecha_creacion__gte=fecha_desde)
        if fecha_hasta:
            pedidos_qs = pedidos_qs.filter(fecha_creacion__lte=fecha_hasta)

        pedidos_estado = {
            'borrador': pedidos_qs.filter(estado='borrador').count(),
            'pendiente': pedidos_qs.filter(estado='pendiente').count(),
            'aprobado': pedidos_qs.filter(estado='aprobado').count(),
            'rechazado': pedidos_qs.filter(estado='rechazado').count(),
            'recibido': pedidos_qs.filter(estado='recibido').count(),
        }
        total_pedidos_recibidos = pedidos_qs.filter(estado='recibido').count()

        # --- FABRICACIONES ---
        fabricaciones_qs = Fabricacion.objects.all()
        if sucursal_id:
            fabricaciones_qs = fabricaciones_qs.filter(ubicacion_id=sucursal_id)
        if fecha_desde:
            fabricaciones_qs = fabricaciones_qs.filter(creado_en__gte=fecha_desde)
        if fecha_hasta:
            fabricaciones_qs = fabricaciones_qs.filter(creado_en__lte=fecha_hasta)

        fabricaciones_periodo = fabricaciones_qs.count()
        total_producido = sum(f.cantidad_producida for f in fabricaciones_qs)

        # Comparativa sucursales (stock value vs ventas)
        comparativa_sucursales = []
        for ub in ubicaciones:
            ub_stock_qs = stock_qs.filter(sub_ubicacion__ubicacion=ub)
            stock_value = sum(
                float(s.cantidad) * float(s.producto.precio_venta)
                for s in ub_stock_qs
            )
            ub_ventas = float(
                ventas_qs.filter(sucursal=ub).aggregate(
                    total=Coalesce(Sum('total'), Decimal('0'))
                )['total'] or 0
            )
            comparativa_sucursales.append({
                'sucursal': ub.nombre,
                'sucursal_id': ub.id,
                'stock_value': round(stock_value, 2),
                'ventas': round(ub_ventas, 2)
            })

        return Response({
            'kpis': {
                'total_stock_value': round(total_stock_value, 2),
                'stock_items_count': stock_items_count,
                'low_stock_count': len(productos_bajo_ids),
                'stock_minimo_configurado': stock_minimo,
                'expiring_7_days': expiring_7,
                'expiring_15_days': expiring_15,
                'expiring_30_days': expiring_30,
                'total_ventas_periodo': round(total_ventas_periodo, 2),
                'total_pedidos_recibidos': total_pedidos_recibidos,
                'fabricaciones_periodo': fabricaciones_periodo,
                'total_producido': total_producido,
                'promedio_ticket': round(promedio_ticket, 2),
                'cantidad_ventas': cantidad_ventas
            },
            'stock_por_ubicacion': stock_por_ubicacion,
            'productos_proximos_vencer': productos_proximos_vencer[:50],
            'productos_mas_vendidos': productos_mas_vendidos,
            'ventas_por_categoria': ventas_por_categoria_data,
            'ventas_tendencia': tendencia_data,
            'pedidos_estado': pedidos_estado,
            'top_productos_stock_bajo': stock_bajo_data[:20],
            'comparativa_sucursales': comparativa_sucursales
        })