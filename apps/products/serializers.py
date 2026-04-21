from rest_framework import serializers
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
                  'precio_venta', 'costo_compra', 'es_fabricable', 'sku', 'dias_caducidad']
        read_only_fields = ['categoria_nombre']

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
