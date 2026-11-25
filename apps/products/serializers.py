from decimal import Decimal

from rest_framework import serializers

from . import units
from .models import Producto, Categoria

class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = ['id', 'nombre']

class ProductoSerializer(serializers.ModelSerializer):
    categoria_nombre = serializers.ReadOnlyField(source='categoria.nombre')

    def _sync_receta_fabricable(self, producto, es_fabricable):
        from apps.recipes.models import Receta

        try:
            receta = producto.receta
        except Receta.DoesNotExist:
            receta = None

        if es_fabricable:
            if receta:
                if not receta.activa:
                    receta.activa = True
                    receta.save(update_fields=['activa', 'actualizado_en'])
            else:
                Receta.objects.create(producto_final=producto, activa=True)
        elif receta and receta.activa:
            receta.activa = False
            receta.save(update_fields=['activa', 'actualizado_en'])
    
    class Meta:
        model = Producto
        fields = ['id', 'nombre', 'categoria', 'categoria_nombre', 'tipo_conservacion',
                  'precio_venta', 'costo_compra', 'es_fabricable', 'es_vianda', 'sku', 'dias_caducidad',
                  'unidad_medida', 'cantidad_envase', 'unidad_envase', 'precio_envase']
        read_only_fields = ['categoria_nombre']
        extra_kwargs = {
            # Se calculan / completan en validate() según el tipo de producto.
            'categoria': {'required': False},
            'tipo_conservacion': {'required': False},
            'costo_compra': {'required': False},
        }

    def _valor(self, attrs, campo, defecto=None):
        """Valor enviado o, en una edición parcial, el que ya tiene el producto."""
        if campo in attrs:
            return attrs[campo]
        if self.instance is not None:
            return getattr(self.instance, campo)
        return defecto

    def validate_unidad_medida(self, value):
        # Lista cerrada para valores nuevos. Un producto con una unidad anterior (pack, caja...) la conserva.
        actual = self.instance.unidad_medida if self.instance is not None else None
        if value not in units.UNIDADES and value != actual:
            raise serializers.ValidationError(f"Unidad inválida. Elegí una de: {', '.join(units.UNIDADES)}.")
        return value

    def validate(self, attrs):
        es_vianda = self._valor(attrs, 'es_vianda', False)
        es_fabricable = self._valor(attrs, 'es_fabricable', False)

        if es_vianda:
            if es_fabricable:
                raise serializers.ValidationError('Una vianda no puede ser fabricable.')
            # Vianda: sin costo, sin conservación/vencimiento/envase; solo precio de venta.
            if attrs.get('categoria') is None and (self.instance is None or self.instance.categoria_id is None):
                attrs['categoria'], _ = Categoria.objects.get_or_create(nombre='Vianda')
            attrs.update({
                'es_fabricable': False,
                'costo_compra': Decimal('0'),
                'tipo_conservacion': 'ambiente',
                'dias_caducidad': None,
                'unidad_medida': 'unidad',
                'cantidad_envase': None,
                'unidad_envase': None,
                'precio_envase': None,
            })
            return attrs

        if self._valor(attrs, 'categoria') is None:
            raise serializers.ValidationError({'categoria': 'Este campo es obligatorio.'})
        if not self._valor(attrs, 'tipo_conservacion'):
            raise serializers.ValidationError({'tipo_conservacion': 'Este campo es obligatorio.'})

        unidad = self._valor(attrs, 'unidad_medida', 'unidad') or 'unidad'
        cantidad_envase = self._valor(attrs, 'cantidad_envase')
        unidad_envase = self._valor(attrs, 'unidad_envase')
        precio_envase = self._valor(attrs, 'precio_envase')
        datos_envase = [cantidad_envase, unidad_envase, precio_envase]

        if any(v is not None for v in datos_envase):
            if any(v is None for v in datos_envase):
                raise serializers.ValidationError(
                    'Para calcular el precio normalizado completá cantidad, unidad y precio del envase.'
                )
            if cantidad_envase <= 0:
                raise serializers.ValidationError({'cantidad_envase': 'Debe ser mayor a 0.'})
            if precio_envase < 0:
                raise serializers.ValidationError({'precio_envase': 'No puede ser negativo.'})
            if unidad not in units.UNIDADES:
                raise serializers.ValidationError({
                    'unidad_medida': 'Para calcular el precio normalizado la unidad principal debe ser kg, g, l, ml o unidad.'
                })
            if not units.son_compatibles(unidad_envase, unidad):
                raise serializers.ValidationError({
                    'unidad_envase': f'No se puede comparar {unidad_envase} con {unidad}: son magnitudes distintas.'
                })
            # El costo por unidad principal lo calcula el servidor: única fuente de verdad.
            # Si los datos del envase no cambiaron se respeta el costo vigente (p. ej. el de la última compra).
            sin_cambios = self.instance is not None and (
                self.instance.cantidad_envase == cantidad_envase
                and self.instance.unidad_envase == unidad_envase
                and self.instance.precio_envase == precio_envase
                and self.instance.unidad_medida == unidad
            )
            if not sin_cambios:
                attrs['costo_compra'] = units.precio_normalizado(precio_envase, cantidad_envase, unidad_envase, unidad)
        elif self._valor(attrs, 'costo_compra') is None:
            raise serializers.ValidationError({'costo_compra': 'Este campo es obligatorio.'})

        return attrs

    def create(self, validated_data):
        es_fabricable = validated_data.get('es_fabricable', False)
        producto = super().create(validated_data)
        self._sync_receta_fabricable(producto, es_fabricable)
        return producto

    def update(self, instance, validated_data):
        es_fabricable = validated_data.get('es_fabricable', instance.es_fabricable)
        producto = super().update(instance, validated_data)
        self._sync_receta_fabricable(producto, es_fabricable)
        return producto
