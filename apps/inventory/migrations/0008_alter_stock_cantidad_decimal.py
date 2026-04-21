# Generated manually to support decimal stock quantities

from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('inventory', '0007_alter_stock_unique_together_stock_fecha_ingreso_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='stock',
            name='cantidad',
            field=models.DecimalField(decimal_places=3, default=Decimal('0.000'), max_digits=12),
        ),
    ]
