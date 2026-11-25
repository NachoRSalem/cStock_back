from django.db import migrations


def borrar_stock_viandas(apps, schema_editor):
    """Las viandas ya no manejan stock: se eliminan los registros que quedaron de la producción diaria."""
    Stock = apps.get_model('inventory', 'Stock')
    Stock.objects.filter(producto__es_vianda=True).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0010_pedido_notas_recepcion_pedidoitem_cantidad_recibida'),
        ('products', '0006_unidades_envase_vianda'),
    ]

    operations = [
        migrations.RunPython(borrar_stock_viandas, migrations.RunPython.noop),
    ]
