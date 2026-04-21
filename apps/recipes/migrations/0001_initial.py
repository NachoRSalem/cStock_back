# Generated manually for recipes app

from decimal import Decimal
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('locations', '0001_initial'),
        ('products', '0002_producto_dias_caducidad'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Receta',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('activa', models.BooleanField(default=True)),
                ('notas', models.TextField(blank=True, null=True)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('actualizado_en', models.DateTimeField(auto_now=True)),
                ('producto_final', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='receta', to='products.producto')),
            ],
            options={
                'ordering': ['producto_final__nombre'],
            },
        ),
        migrations.CreateModel(
            name='Fabricacion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cantidad_producida', models.DecimalField(decimal_places=3, max_digits=12)),
                ('creado_en', models.DateTimeField(auto_now_add=True)),
                ('creado_por', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL)),
                ('receta', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='fabricaciones', to='recipes.receta')),
                ('sub_ubicacion_destino', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='fabricaciones_destino', to='locations.sububicacion')),
                ('ubicacion', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='fabricaciones', to='locations.ubicacion')),
            ],
            options={
                'ordering': ['-creado_en'],
            },
        ),
        migrations.CreateModel(
            name='RecetaInsumo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cantidad_requerida', models.DecimalField(decimal_places=3, default=Decimal('0.000'), max_digits=12)),
                ('producto_insumo', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='es_insumo_de', to='products.producto')),
                ('receta', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='insumos', to='recipes.receta')),
            ],
            options={
                'ordering': ['producto_insumo__nombre'],
                'unique_together': {('receta', 'producto_insumo')},
            },
        ),
        migrations.CreateModel(
            name='FabricacionConsumo',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('lote', models.CharField(blank=True, max_length=100, null=True)),
                ('cantidad_consumida', models.DecimalField(decimal_places=3, max_digits=12)),
                ('fabricacion', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='consumos', to='recipes.fabricacion')),
                ('receta_insumo', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='recipes.recetainsumo')),
                ('sub_ubicacion_origen', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='locations.sububicacion')),
            ],
            options={
                'ordering': ['id'],
            },
        ),
    ]
