from rest_framework import serializers
from .models import Ubicacion, SubUbicacion

class SubUbicacionSerializer(serializers.ModelSerializer):
    ubicacion_nombre = serializers.ReadOnlyField(source='ubicacion.nombre')
    
    class Meta:
        model = SubUbicacion
        fields = ['id', 'ubicacion', 'ubicacion_nombre', 'nombre', 'tipo']
        read_only_fields = ['ubicacion_nombre']

class UbicacionSerializer(serializers.ModelSerializer):
    # Esto anida las heladeras dentro de la sucursal en el JSON
    sub_ubicaciones = SubUbicacionSerializer(many=True, read_only=True)

    class Meta:
        model = Ubicacion
        fields = ['id', 'nombre', 'tipo', 'sub_ubicaciones']