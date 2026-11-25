from django.db import transaction
from rest_framework import serializers
from apps.locations.models import SubUbicacion
from .models import Venta, VentaItem, Ingreso, GastoOperativo

class VentaItemSerializer(serializers.ModelSerializer):
    producto_nombre = serializers.ReadOnlyField(source='producto.nombre')
    cantidad = serializers.IntegerField(min_value=1)
    sub_ubicacion_origen = serializers.PrimaryKeyRelatedField(
        queryset=SubUbicacion.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = VentaItem
        fields = ['id', 'producto', 'producto_nombre', 'sub_ubicacion_origen', 'cantidad', 'precio_venta_momento']
        # El precio lo toma el servidor del producto; el cliente no lo puede definir.
        read_only_fields = ['precio_venta_momento']

class VentaSerializer(serializers.ModelSerializer):
    items = VentaItemSerializer(many=True)
    sucursal_nombre = serializers.ReadOnlyField(source='sucursal.nombre')
    vendedor_nombre = serializers.ReadOnlyField(source='vendedor.username')
    anulada_por_nombre = serializers.ReadOnlyField(source='anulada_por.username')

    class Meta:
        model = Venta
        fields = ['id', 'vendedor', 'vendedor_nombre', 'sucursal', 'sucursal_nombre', 'fecha', 'total', 'items',
                  'estado', 'anulada_en', 'anulada_por_nombre']
        read_only_fields = ['vendedor', 'vendedor_nombre', 'sucursal_nombre', 'total', 'fecha',
                            'estado', 'anulada_en', 'anulada_por_nombre']

    def validate(self, attrs):
        user = self.context['request'].user
        if not attrs.get('items'):
            raise serializers.ValidationError('La venta debe tener al menos un producto.')
        if user.rol != 'admin':
            if not user.sucursal_asignada_id:
                raise serializers.ValidationError('No tenés una sucursal asignada.')
            if attrs['sucursal'].id != user.sucursal_asignada_id:
                raise serializers.ValidationError('Solo podés registrar ventas de tu propia sucursal.')
        for item in attrs['items']:
            if item['producto'].es_vianda:
                item['sub_ubicacion_origen'] = None  # las viandas no salen de stock
                continue
            if item.get('sub_ubicacion_origen') is None:
                raise serializers.ValidationError(
                    f"Indicá de qué sub-ubicación sale {item['producto'].nombre}."
                )
            if item['sub_ubicacion_origen'].ubicacion_id != attrs['sucursal'].id:
                raise serializers.ValidationError(
                    'Todos los productos deben salir de sub-ubicaciones de la sucursal de la venta.'
                )
        return attrs

    def create(self, validated_data):
        # La creación real la delegamos al método procesar_venta del modelo.
        # Todo ocurre en una sola transacción: si falla el stock no queda nada guardado.
        items_data = validated_data.pop('items')
        try:
            with transaction.atomic():
                venta = Venta.objects.create(**validated_data)
                venta.procesar_venta(items_data)
        except Exception as e:
            raise serializers.ValidationError(str(e))
        return venta
    
class ReporteEconomicoSerializer(serializers.Serializer):
    sucursal_nombre = serializers.CharField()
    total_gastos = serializers.DecimalField(max_digits=12, decimal_places=2)
    total_ventas = serializers.DecimalField(max_digits=12, decimal_places=2)
    balance = serializers.DecimalField(max_digits=12, decimal_places=2)

class IngresoSerializer(serializers.ModelSerializer):
    registrado_por_nombre = serializers.ReadOnlyField(source='registrado_por.username')

    class Meta:
        model = Ingreso
        fields = ['id', 'monto', 'fecha', 'descripcion', 'tipo', 'medio_pago', 'registrado_por', 'registrado_por_nombre', 'creado_en']
        read_only_fields = ['registrado_por', 'registrado_por_nombre', 'creado_en']


class GastoOperativoSerializer(serializers.ModelSerializer):
    registrado_por_nombre = serializers.ReadOnlyField(source='registrado_por.username')
    sucursal_nombre = serializers.ReadOnlyField(source='sucursal.nombre')
    concepto_display = serializers.ReadOnlyField(source='get_concepto_display')

    class Meta:
        model = GastoOperativo
        fields = ['id', 'monto', 'fecha', 'concepto', 'concepto_display', 'descripcion', 'sucursal', 'sucursal_nombre', 'registrado_por', 'registrado_por_nombre', 'creado_en']
        read_only_fields = ['registrado_por', 'registrado_por_nombre', 'creado_en']