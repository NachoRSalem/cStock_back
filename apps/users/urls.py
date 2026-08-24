from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from .views import SwitchAccountView, CustomTokenRefreshView

urlpatterns = [
    path('switch/', SwitchAccountView.as_view(), name='switch_account'),
    path('refresh/', CustomTokenRefreshView.as_view(), name='token_refresh'),
]