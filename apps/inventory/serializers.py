from rest_framework import serializers
from .models import Pedido, PedidoItem, Stock
from apps.locations.serializers import UbicacionSerializer

class PedidoItemSerializer(serializers.ModelSerializer):
    
    producto_nombre = serializers.ReadOnlyField(source='producto.nombre')

    class Meta:
        model = PedidoItem
        fields = ['id', 'producto', 'producto_nombre', 'cantidad', 'precio_costo_momento', 'sub_ubicacion_destino']

class PedidoSerializer(serializers.ModelSerializer):
    items = PedidoItemSerializer(many=True) 
    destino_nombre = serializers.ReadOnlyField(source='destino.nombre')

    class Meta:
        model = Pedido
        fields = ['id', 'creado_por', 'destino', 'destino_nombre', 'estado', 'fecha_creacion', 'items']
        read_only_fields = ['creado_por', 'estado']

    def create(self, validated_data):
       
        items_data = validated_data.pop('items')
        pedido = Pedido.objects.create(**validated_data)
        for item_data in items_data:
            PedidoItem.objects.create(pedido=pedido, **item_data)
        return pedido