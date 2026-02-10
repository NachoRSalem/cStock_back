from rest_framework import serializers
from .models import Ubicacion, SubUbicacion

class SubUbicacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubUbicacion
        fields = ['id', 'nombre', 'tipo']

class UbicacionSerializer(serializers.ModelSerializer):
    # Esto anida las heladeras dentro de la sucursal en el JSON
    sub_ubicaciones = SubUbicacionSerializer(many=True, read_only=True)

    class Meta:
        model = Ubicacion
        fields = ['id', 'nombre', 'tipo', 'sub_ubicaciones']