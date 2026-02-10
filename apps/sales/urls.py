from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ReporteEconomicoView, VentaViewSet

router = DefaultRouter()
router.register(r'ventas', VentaViewSet)

urlpatterns = [
    path('', include(router.urls)),
    path('reporte-economico/', ReporteEconomicoView.as_view(), name='reporte-economico'),
]