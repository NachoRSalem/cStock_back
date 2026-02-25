from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import UbicacionViewSet, SubUbicacionViewSet

router = DefaultRouter()
router.register(r'sucursales', UbicacionViewSet)
router.register(r'sub-ubicaciones', SubUbicacionViewSet)

urlpatterns = [
    path('', include(router.urls)),
]