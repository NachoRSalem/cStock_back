from rest_framework import serializers
from .models import Pedido, PedidoItem, Stock
from apps.locations.serializers import UbicacionSerializer

class StockSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.ReadOnlyField(source='producto.nombre')
    producto_tipo_conservacion = serializers.ReadOnlyField(source='producto.tipo_conservacion')
    sub_ubicacion_nombre = serializers.ReadOnlyField(source='sub_ubicacion.nombre')
    sub_ubicacion_tipo = serializers.ReadOnlyField(source='sub_ubicacion.tipo')
    ubicacion_nombre = serializers.ReadOnlyField(source='sub_ubicacion.ubicacion.nombre')
    ubicacion_id = serializers.ReadOnlyField(source='sub_ubicacion.ubicacion.id')
    
    class Meta:
        model = Stock
        fields = ['id', 'producto', 'producto_nombre', 'producto_tipo_conservacion',
                  'sub_ubicacion', 'sub_ubicacion_nombre', 'sub_ubicacion_tipo',
                  'ubicacion_id', 'ubicacion_nombre', 'cantidad', 'ultima_actualizacion']
        read_only_fields = ['ultima_actualizacion']

class PedidoItemSerializer(serializers.ModelSerializer):
    
    producto_nombre = serializers.ReadOnlyField(source='producto.nombre')

    class Meta:
        model = PedidoItem
        fields = ['id', 'producto', 'producto_nombre', 'cantidad', 'precio_costo_momento', 'sub_ubicacion_destino', 'sub_ubicacion_origen']

class PedidoSerializer(serializers.ModelSerializer):
    items = PedidoItemSerializer(many=True) 
    destino_nombre = serializers.ReadOnlyField(source='destino.nombre')
    pdf_url = serializers.SerializerMethodField()

    class Meta:
        model = Pedido
        fields = ['id', 'creado_por', 'destino', 'destino_nombre', 'estado', 'fecha_creacion', 'items', 'pdf_archivo', 'pdf_url', 'provisto_desde_almacen']
        read_only_fields = ['creado_por', 'estado', 'pdf_archivo', 'pdf_url', 'provisto_desde_almacen']
    
    def get_pdf_url(self, obj):
        if obj.pdf_archivo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.pdf_archivo.url)
        return None

    def create(self, validated_data):
       
        items_data = validated_data.pop('items')
        pedido = Pedido.objects.create(**validated_data)
        for item_data in items_data:
            PedidoItem.objects.create(pedido=pedido, **item_data)
        return pedido
    
    def update(self, instance, validated_data):
        # Extraer los items anidados si existen
        items_data = validated_data.pop('items', None)
        
        # Actualizar los campos del pedido
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        
        # Si se enviaron items, reemplazar los existentes
        if items_data is not None:
            # Eliminar los items existentes
            instance.items.all().delete()
            
            # Crear los nuevos items
            for item_data in items_data:
                PedidoItem.objects.create(pedido=instance, **item_data)
        
        return instance