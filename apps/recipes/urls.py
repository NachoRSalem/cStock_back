from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import FabricacionViewSet, RecetaViewSet

router = DefaultRouter()
router.register(r'recetas', RecetaViewSet, basename='receta')
router.register(r'fabricaciones', FabricacionViewSet, basename='fabricacion')

urlpatterns = [
    path('', include(router.urls)),
]
