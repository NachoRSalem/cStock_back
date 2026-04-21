from django.contrib import admin

from .models import Fabricacion, FabricacionConsumo, Receta, RecetaInsumo


class RecetaInsumoInline(admin.TabularInline):
    model = RecetaInsumo
    extra = 1


@admin.register(Receta)
class RecetaAdmin(admin.ModelAdmin):
    list_display = ('producto_final', 'activa', 'actualizado_en')
    list_filter = ('activa',)
    search_fields = ('producto_final__nombre',)
    inlines = [RecetaInsumoInline]


class FabricacionConsumoInline(admin.TabularInline):
    model = FabricacionConsumo
    extra = 0
    readonly_fields = ('receta_insumo', 'sub_ubicacion_origen', 'lote', 'cantidad_consumida')
    can_delete = False


@admin.register(Fabricacion)
class FabricacionAdmin(admin.ModelAdmin):
    list_display = ('id', 'receta', 'ubicacion', 'cantidad_producida', 'creado_por', 'creado_en')
    list_filter = ('ubicacion', 'creado_en')
    search_fields = ('receta__producto_final__nombre',)
    inlines = [FabricacionConsumoInline]
