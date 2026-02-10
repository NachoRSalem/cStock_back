from django.contrib import admin
from .models import Stock, Pedido, PedidoItem

# Esto permite cargar los productos dentro del Pedido
class PedidoItemInline(admin.TabularInline):
    model = PedidoItem
    extra = 1 # Cantidad de filas vacías que aparecen al principio
    fields = ('producto', 'cantidad', 'precio_costo_momento')

@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    editable_fields = ('estado',) # Solo el destino se puede editar después de creado
    list_display = ('id', 'destino', 'estado', 'creado_por', 'fecha_creacion')
    list_filter = ('estado', 'destino', 'fecha_creacion')
    search_fields = ('id', 'destino__nombre')
    inlines = [PedidoItemInline]
    
    # Podés hacer que algunos campos sean de solo lectura según el estado (opcional)
    # readonly_fields = ('fecha_creacion',)

@admin.register(Stock)
class StockAdmin(admin.ModelAdmin):
    list_display = ('producto', 'get_ubicacion', 'sub_ubicacion', 'cantidad', 'ultima_actualizacion')
    list_filter = ('sub_ubicacion__ubicacion', 'sub_ubicacion__tipo')
    search_fields = ('producto__nombre',)

    def get_ubicacion(self, obj):
        return obj.sub_ubicacion.ubicacion.nombre
    get_ubicacion.short_description = 'Sucursal/Almacén'