"""
`migrate` de Django, pero esperando primero a la base.

En Railway este comando corre antes de cada publicación (pre-deploy). Si MySQL está
dormida, el primer intento de conexión falla y la publicación se cancela.
"""
from django.core.management.base import CommandError
from django.core.management.commands.migrate import Command as MigrateDeDjango

from core.db_wait import esperar_base

ESPERA_AL_PUBLICAR = 90  # segundos


class Command(MigrateDeDjango):
    def execute(self, *args, **options):
        # Antes de execute(): las comprobaciones de Django ya usan la base.
        if not esperar_base(ESPERA_AL_PUBLICAR):
            raise CommandError('La base de datos no respondió a tiempo.')
        return super().execute(*args, **options)
