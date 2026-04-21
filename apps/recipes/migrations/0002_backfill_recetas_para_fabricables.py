from django.db import migrations


def crear_recetas_para_fabricables(apps, schema_editor):
    Producto = apps.get_model('products', 'Producto')
    Receta = apps.get_model('recipes', 'Receta')

    for producto in Producto.objects.filter(es_fabricable=True):
        receta, created = Receta.objects.get_or_create(
            producto_final=producto,
            defaults={'activa': True, 'notas': ''},
        )
        if not created and not receta.activa:
            receta.activa = True
            receta.save(update_fields=['activa', 'actualizado_en'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0003_producto_es_fabricable'),
        ('recipes', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(crear_recetas_para_fabricables, noop_reverse),
    ]
