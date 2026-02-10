from django.contrib import admin
from .models import Ubicacion, SubUbicacion

@admin.register(Ubicacion)
class UbicacionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo')

@admin.register(SubUbicacion)
class SubUbicacionAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'ubicacion', 'tipo')
    list_filter = ('ubicacion', 'tipo')