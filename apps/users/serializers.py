from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['rol'] = user.rol
        token['sucursal_id'] = user.sucursal_asignada.id if user.sucursal_asignada else None
        token['sucursal_nombre'] = user.sucursal_asignada.nombre if user.sucursal_asignada else None
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['rol'] = self.user.rol
        # Mantener compatibilidad: sucursal como string (nombre)
        data['sucursal'] = self.user.sucursal_asignada.nombre if self.user.sucursal_asignada else None
        # Objeto completo disponible si lo necesitas
        data['sucursal_detalle'] = {
            'id': self.user.sucursal_asignada.id,
            'nombre': self.user.sucursal_asignada.nombre,
            'tipo': self.user.sucursal_asignada.tipo
        } if self.user.sucursal_asignada else None
        data['username'] = self.user.username
        return data