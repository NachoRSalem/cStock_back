"""Unidades de medida y conversión para el precio normalizado."""
from decimal import Decimal, ROUND_HALF_UP

UNIDADES = ('kg', 'g', 'l', 'ml', 'unidad')

UNIDAD_CHOICES = (
    ('kg', 'Kilogramos (kg)'),
    ('g', 'Gramos (g)'),
    ('l', 'Litros (l)'),
    ('ml', 'Mililitros (ml)'),
    ('unidad', 'Unidad'),
)

# (dimensión, factor hacia la unidad base de esa dimensión: g, ml o unidad)
_INFO = {
    'kg': ('masa', Decimal('1000')),
    'g': ('masa', Decimal('1')),
    'l': ('volumen', Decimal('1000')),
    'ml': ('volumen', Decimal('1')),
    'unidad': ('conteo', Decimal('1')),
}


def dimension(unidad):
    return _INFO[unidad][0]


def son_compatibles(unidad_a, unidad_b):
    return dimension(unidad_a) == dimension(unidad_b)


def convertir(cantidad, desde, hacia):
    """Convierte `cantidad` de la unidad `desde` a la unidad `hacia` (misma dimensión)."""
    if not son_compatibles(desde, hacia):
        raise ValueError(f'No se puede convertir {desde} a {hacia}.')
    return Decimal(cantidad) * _INFO[desde][1] / _INFO[hacia][1]


def precio_normalizado(precio_envase, cantidad_envase, unidad_envase, unidad_principal):
    """
    Precio por unidad principal a partir de lo pagado por un envase.
    Ej.: $20.000 por un envase de 10 kg, unidad principal kg -> $2.000 el kg.
    """
    cantidad_en_principal = convertir(cantidad_envase, unidad_envase, unidad_principal)
    if cantidad_en_principal <= 0:
        raise ValueError('La cantidad del envase debe ser mayor a 0.')
    return (Decimal(precio_envase) / cantidad_en_principal).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
