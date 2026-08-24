from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ReporteEconomicoView, VentaViewSet, DashboardView, IngresoViewSet, BalanceView

router = DefaultRouter()
router.register(r'ventas', VentaViewSet)
router.register(r'ingresos', IngresoViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('reporte-economico/', ReporteEconomicoView.as_view(), name='reporte-economico'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
    path('balance/', BalanceView.as_view(), name='balance'),
]