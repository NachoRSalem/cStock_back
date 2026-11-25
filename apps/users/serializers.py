from rest_framework import serializers
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['rol'] = user.rol
        token['sucursal_id'] = user.sucursal_asignada.id if user.sucursal_asignada else None
        token['sucursal_nombre'] = user.sucursal_asignada.nombre if user.sucursal_asignada else None
        token['cuenta_pareada'] = user.cuenta_pareada.username if user.cuenta_pareada else None
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['rol'] = self.user.rol
        data['sucursal'] = self.user.sucursal_asignada.id if self.user.sucursal_asignada else None
        data['sucursal_detalle'] = {
            'id': self.user.sucursal_asignada.id,
            'nombre': self.user.sucursal_asignada.nombre,
            'tipo': self.user.sucursal_asignada.tipo
        } if self.user.sucursal_asignada else None
        data['username'] = self.user.username
        data['cuenta_pareada'] = self.user.cuenta_pareada.username if self.user.cuenta_pareada else None
        return data


class UserListSerializer(serializers.ModelSerializer):
    sucursal_nombre = serializers.ReadOnlyField(source='sucursal_asignada.nombre')
    cuenta_pareada_username = serializers.ReadOnlyField(source='cuenta_pareada.username')

    class Meta:
        model = get_user_model()
        fields = ['id', 'username', 'rol', 'is_active', 'sucursal_asignada', 'sucursal_nombre', 'cuenta_pareada_username']
