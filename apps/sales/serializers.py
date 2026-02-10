from rest_framework import serializers
from .models import Venta, VentaItem

class VentaItemSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.ReadOnlyField(source='producto.nombre')

    class Meta:
        model = VentaItem
        fields = ['id', 'producto', 'producto_nombre', 'sub_ubicacion_origen', 'cantidad', 'precio_venta_momento']

class VentaSerializer(serializers.ModelSerializer):
    items = VentaItemSerializer(many=True)

    class Meta:
        model = Venta
        fields = ['id', 'vendedor', 'sucursal', 'fecha', 'total', 'items']
        read_only_fields = ['vendedor', 'total', 'fecha']

    def create(self, validated_data):
        # La creación real la delegamos al método procesar_venta del modelo
        items_data = validated_data.pop('items')
        # Asignamos el vendedor desde el request context
        vendedor = self.context['request'].user
        
        venta = Venta.objects.create(**validated_data)
        try:
            venta.procesar_venta(items_data)
        except Exception as e:
            venta.delete() # Si falla el stock, borramos el registro de venta
            raise serializers.ValidationError(str(e))
            
        return venta
    
class ReporteEconomicoSerializer(serializers.Serializer):
    sucursal_nombre = serializers.CharField()
    total_gastos = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_ventas = serializers.DecimalField(max_digits=12, decimal_places=2)
    balance = serializers.DecimalField(max_digits=12, decimal_places=2)