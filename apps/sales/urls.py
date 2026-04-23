from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ReporteEconomicoView, VentaViewSet, DashboardView

router = DefaultRouter()
router.register(r'ventas', VentaViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('reporte-economico/', ReporteEconomicoView.as_view(), name='reporte-economico'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
]