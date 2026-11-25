from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ConsumoCocinaViewSet

router = DefaultRouter()
router.register(r'consumos', ConsumoCocinaViewSet)

urlpatterns = [
    path('', include(router.urls)),
]
