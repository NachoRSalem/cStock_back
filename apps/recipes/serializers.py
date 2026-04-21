from decimal import Decimal

from rest_framework import serializers

from apps.locations.models import SubUbicacion

from .models import Fabricacion, FabricacionConsumo, Receta, RecetaInsumo


class RecetaInsumoSerializer(serializers.ModelSerializer):
    producto_insumo_nombre = serializers.ReadOnlyField(source='producto_insumo.nombre')

    class Meta:
        model = RecetaInsumo
        fields = ['id', 'producto_insumo', 'producto_insumo_nombre', 'cantidad_requerida']


class RecetaSerializer(serializers.ModelSerializer):
    producto_final_nombre = serializers.ReadOnlyField(source='producto_final.nombre')
    insumos = RecetaInsumoSerializer(many=True)

    class Meta:
        model = Receta
        fields = ['id', 'producto_final', 'producto_final_nombre', 'activa', 'notas', 'insumos', 'creado_en', 'actualizado_en']
        read_only_fields = ['creado_en', 'actualizado_en']

    def validate_insumos(self, value):
        if not value:
            raise serializers.ValidationError('La receta debe tener al menos un insumo.')
        for item in value:
            if Decimal(item['cantidad_requerida']) <= 0:
                raise serializers.ValidationError('Las cantidades de insumos deben ser mayores a 0.')
        return value

    def validate(self, attrs):
        producto_final = attrs.get('producto_final') or getattr(self.instance, 'producto_final', None)
        if producto_final and not producto_final.es_fabricable:
            raise serializers.ValidationError('El producto final debe estar marcado como fabricable.')
        insumos = attrs.get('insumos', [])
        for item in insumos:
            if producto_final and item['producto_insumo'] == producto_final:
                raise serializers.ValidationError('El producto final no puede ser insumo de su propia receta.')
        return attrs

    def create(self, validated_data):
        insumos_data = validated_data.pop('insumos', [])
        receta = Receta.objects.create(**validated_data)
        for item in insumos_data:
            RecetaInsumo.objects.create(receta=receta, **item)
        return receta

    def update(self, instance, validated_data):
        insumos_data = validated_data.pop('insumos', None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if insumos_data is not None:
            instance.insumos.all().delete()
            for item in insumos_data:
                RecetaInsumo.objects.create(receta=instance, **item)

        return instance


class FabricarSerializer(serializers.Serializer):
    cantidad_producir = serializers.IntegerField(min_value=1)
    sub_ubicacion_destino = serializers.IntegerField(min_value=1)
    sub_ubicaciones_origen = serializers.DictField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        help_text='Mapa {receta_insumo_id: sub_ubicacion_id}'
    )

    def validate_sub_ubicacion_destino(self, value):
        if not SubUbicacion.objects.filter(id=value).exists():
            raise serializers.ValidationError('Sub-ubicación destino inválida.')
        return value


class FabricacionConsumoSerializer(serializers.ModelSerializer):
    insumo_nombre = serializers.ReadOnlyField(source='receta_insumo.producto_insumo.nombre')
    sub_ubicacion_origen_nombre = serializers.ReadOnlyField(source='sub_ubicacion_origen.nombre')

    class Meta:
        model = FabricacionConsumo
        fields = ['id', 'insumo_nombre', 'sub_ubicacion_origen', 'sub_ubicacion_origen_nombre', 'lote', 'cantidad_consumida']


class FabricacionSerializer(serializers.ModelSerializer):
    producto_final_nombre = serializers.ReadOnlyField(source='receta.producto_final.nombre')
    ubicacion_nombre = serializers.ReadOnlyField(source='ubicacion.nombre')
    sub_ubicacion_destino_nombre = serializers.ReadOnlyField(source='sub_ubicacion_destino.nombre')
    consumos = FabricacionConsumoSerializer(many=True, read_only=True)
    consumos_resumen = serializers.SerializerMethodField()

    def get_consumos_resumen(self, obj):
        resumen = {}
        for consumo in obj.consumos.all():
            insumo_id = consumo.receta_insumo.producto_insumo_id
            insumo_nombre = consumo.receta_insumo.producto_insumo.nombre
            if insumo_id not in resumen:
                resumen[insumo_id] = {
                    'insumo_id': insumo_id,
                    'insumo_nombre': insumo_nombre,
                    'cantidad_total_consumida': Decimal('0.000'),
                }
            resumen[insumo_id]['cantidad_total_consumida'] += Decimal(consumo.cantidad_consumida)

        return [
            {
                'insumo_id': v['insumo_id'],
                'insumo_nombre': v['insumo_nombre'],
                'cantidad_total_consumida': v['cantidad_total_consumida'],
            }
            for v in resumen.values()
        ]

    class Meta:
        model = Fabricacion
        fields = [
            'id',
            'receta',
            'producto_final_nombre',
            'ubicacion',
            'ubicacion_nombre',
            'sub_ubicacion_destino',
            'sub_ubicacion_destino_nombre',
            'cantidad_producida',
            'creado_por',
            'creado_en',
            'consumos',
            'consumos_resumen',
        ]
        read_only_fields = ['creado_por', 'creado_en']
