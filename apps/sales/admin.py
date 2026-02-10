from django.contrib import admin
from .models import Venta, VentaItem

# Register your models here.
class VentaItemInline(admin.TabularInline):
    model = VentaItem
    extra = 1
    fields = ('producto', 'sub_ubicacion_origen', 'cantidad', 'precio_venta_momento')

@admin.register(Venta)
class VentaAdmin(admin.ModelAdmin):
    list_display = ('id', 'fecha', 'vendedor', 'sucursal', 'total')
    list_filter = ('fecha', 'sucursal')
    search_fields = ('vendedor__username',)
    inlines = [VentaItemInline]
