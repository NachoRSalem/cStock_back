# Generated manually to make production quantity integer

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('recipes', '0002_backfill_recetas_para_fabricables'),
    ]

    operations = [
        migrations.AlterField(
            model_name='fabricacion',
            name='cantidad_producida',
            field=models.PositiveIntegerField(),
        ),
    ]
