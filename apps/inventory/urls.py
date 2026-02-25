from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PedidoViewSet, StockViewSet

router = DefaultRouter()
router.register(r'pedidos', PedidoViewSet, basename='pedido')
router.register(r'stock', StockViewSet, basename='stock')

urlpatterns = [
    path('', include(router.urls)),
]