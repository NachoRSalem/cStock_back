from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import get_user_model
from .serializers import MyTokenObtainPairSerializer

User = get_user_model()


class SwitchAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user

        if not user.cuenta_pareada:
            return Response(
                {'error': 'Esta cuenta no tiene una cuenta pareada'},
                status=status.HTTP_400_BAD_REQUEST
            )

        paired_user = user.cuenta_pareada

        serializer = MyTokenObtainPairSerializer(data={
            'username': paired_user.username,
            'password': 'switcheado'  # No importa, solo necesitamos el user
        })

        # Usamos el serializer para generar tokens sin password
        # El validate() de DRF necesita password, así que usamos get_token directamente
        refresh = RefreshToken.for_user(paired_user)

        # Agregar datos custom al token
        refresh['rol'] = paired_user.rol
        refresh['sucursal_id'] = paired_user.sucursal_asignada.id if paired_user.sucursal_asignada else None
        refresh['sucursal_nombre'] = paired_user.sucursal_asignada.nombre if paired_user.sucursal_asignada else None
        refresh['cuenta_pareada'] = paired_user.cuenta_pareada.username if paired_user.cuenta_pareada else None

        # Invalidar el token anterior del usuario actual
        # Obtenemos el refresh token del request para invalidarlo
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                try:
                    RefreshToken(refresh_token).blacklist()
                except:
                    pass  # Si no se puede blackliste, no importa
        except:
            pass

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'username': paired_user.username,
            'rol': paired_user.rol,
            'sucursal': paired_user.sucursal_asignada.id if paired_user.sucursal_asignada else None,
            'sucursal_detalle': {
                'id': paired_user.sucursal_asignada.id,
                'nombre': paired_user.sucursal_asignada.nombre,
                'tipo': paired_user.sucursal_asignada.tipo
            } if paired_user.sucursal_asignada else None,
            'cuenta_pareada': paired_user.cuenta_pareada.username if paired_user.cuenta_pareada else None,
        })


class CustomTokenRefreshView(APIView):
    permission_classes = []

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {'error': 'Refresh token requerido'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            refresh = RefreshToken(refresh_token)
            return Response({
                'access': str(refresh.access_token),
                'refresh': str(refresh),
            })
        except Exception as e:
            return Response(
                {'error': 'Token inválido o expirado'},
                status=status.HTTP_401_UNAUTHORIZED
            )