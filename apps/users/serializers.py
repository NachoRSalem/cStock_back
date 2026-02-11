from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

class MyTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['rol'] = user.rol
        token['sucursal'] = user.sucursal_asignada
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data['rol'] = self.user.rol
        data['sucursal'] = self.user.sucursal_asignada
        data['username'] = self.user.username
        return data