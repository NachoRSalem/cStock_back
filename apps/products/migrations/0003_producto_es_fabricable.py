# Generated manually to distinguish normal vs fabricable products

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('products', '0002_producto_dias_caducidad'),
    ]

    operations = [
        migrations.AddField(
            model_name='producto',
            name='es_fabricable',
            field=models.BooleanField(default=False, help_text='Indica si este producto se fabrica a partir de otros insumos'),
        ),
    ]
