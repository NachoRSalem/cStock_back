from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ConsumoCocinaViewSet, ProduccionViandaViewSet

router = DefaultRouter()
router.register(r'consumos', ConsumoCocinaViewSet)
router.register(r'producciones-vianda', ProduccionViandaViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
