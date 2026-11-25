from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend


class CaseInsensitiveModelBackend(ModelBackend):
    """
    Permite iniciar sesión sin distinguir mayúsculas/minúsculas en el usuario.
    Los teclados de celular suelen poner la primera letra en mayúscula ("Kiosco" en vez de "kiosco"),
    lo que hacía fallar el primer intento de login.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        User = get_user_model()
        if username is None:
            username = kwargs.get(User.USERNAME_FIELD)
        if username is None or password is None:
            return None

        username = username.strip()
        candidatos = User._default_manager.filter(**{f'{User.USERNAME_FIELD}__iexact': username})
        # Si hay una coincidencia exacta se prefiere; si hay varias que difieren solo en mayúsculas, es ambiguo.
        usuario = candidatos.filter(**{User.USERNAME_FIELD: username}).first()
        if usuario is None and candidatos.count() == 1:
            usuario = candidatos.first()

        if usuario is None:
            # Misma demora que un login real para no revelar qué usuarios existen.
            User().set_password(password)
            return None
        if usuario.check_password(password) and self.user_can_authenticate(usuario):
            return usuario
        return None
