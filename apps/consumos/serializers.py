from rest_framework import serializers
from .models import ConsumoCocina, ConsumoCocinaItem, ProduccionVianda, ProduccionViandaItem


class ConsumoCocinaItemSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.ReadOnlyField(source='producto.nombre')
    sub_ubicacion_origen_nombre = serializers.ReadOnlyField(source='sub_ubicacion_origen.nombre')

    class Meta:
        model = ConsumoCocinaItem
        fields = [
            'id', 'producto', 'producto_nombre', 'cantidad',
            'sub_ubicacion_origen', 'sub_ubicacion_origen_nombre',
            'costo_unitario_momento'
        ]


class ConsumoCocinaSerializer(serializers.ModelSerializer):
    items = ConsumoCocinaItemSerializer(many=True, read_only=True)
    ubicacion_nombre = serializers.ReadOnlyField(source='ubicacion.nombre')
    registrado_por_nombre = serializers.ReadOnlyField(source='registrado_por.username')

    class Meta:
        model = ConsumoCocina
        fields = [
            'id', 'ubicacion', 'ubicacion_nombre', 'fecha',
            'registrado_por', 'registrado_por_nombre',
            'creado_en', 'total_costo', 'items'
        ]
        read_only_fields = ['registrado_por', 'registrado_por_nombre', 'creado_en', 'total_costo']


class ProduccionViandaItemSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.ReadOnlyField(source='producto.nombre')

    class Meta:
        model = ProduccionViandaItem
        fields = ['id', 'producto', 'producto_nombre', 'cantidad', 'precio_venta_momento']


class ProduccionViandaSerializer(serializers.ModelSerializer):
    items = ProduccionViandaItemSerializer(many=True, read_only=True)
    ubicacion_nombre = serializers.ReadOnlyField(source='ubicacion.nombre')
    sub_ubicacion_destino_nombre = serializers.ReadOnlyField(source='sub_ubicacion_destino.nombre')
    registrado_por_nombre = serializers.ReadOnlyField(source='registrado_por.username')

    class Meta:
        model = ProduccionVianda
        fields = [
            'id', 'ubicacion', 'ubicacion_nombre',
            'sub_ubicacion_destino', 'sub_ubicacion_destino_nombre',
            'fecha', 'registrado_por', 'registrado_por_nombre',
            'creado_en', 'items'
        ]
        read_only_fields = ['registrado_por', 'registrado_por_nombre', 'creado_en']
