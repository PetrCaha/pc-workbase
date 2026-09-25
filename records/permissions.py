from functools import wraps

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied


ROLE_ADMIN = 'admin'
ROLE_MANAGER = 'manager'
ROLE_MEMBER = 'member'

ROLE_CHOICES = [
    (ROLE_ADMIN, 'Administrátor'),
    (ROLE_MANAGER, 'Správce'),
    (ROLE_MEMBER, 'Člen'),
]

GROUP_NAMES = {
    ROLE_ADMIN: 'Administrátor',
    ROLE_MANAGER: 'Správce',
    ROLE_MEMBER: 'Člen',
}


def ensure_role_groups():
    return {role: Group.objects.get_or_create(name=name)[0] for role, name in GROUP_NAMES.items()}


def set_user_role(user, role):
    if role not in GROUP_NAMES:
        raise ValueError('Neplatná role uživatele.')
    groups = ensure_role_groups()
    user.groups.remove(*groups.values())
    user.groups.add(groups[role])
    if not user.is_superuser and user.is_staff:
        user.is_staff = False
        user.save(update_fields=['is_staff'])
    if hasattr(user, '_zakazkovnik_role'):
        delattr(user, '_zakazkovnik_role')


def get_user_role(user):
    if not user or not user.is_authenticated:
        return None
    if user.is_superuser:
        return ROLE_ADMIN
    cached = getattr(user, '_zakazkovnik_role', None)
    if cached:
        return cached
    names = set(user.groups.values_list('name', flat=True))
    for role in (ROLE_ADMIN, ROLE_MANAGER, ROLE_MEMBER):
        if GROUP_NAMES[role] in names:
            user._zakazkovnik_role = role
            return role
    role = ROLE_ADMIN if user.is_superuser or user.is_staff else ROLE_MEMBER
    user._zakazkovnik_role = role
    return role


def get_role_label(user):
    from django.utils.translation import gettext as _
    role = get_user_role(user)
    return {ROLE_ADMIN: _('Majitel'), ROLE_MANAGER: _('Vedoucí'), ROLE_MEMBER: _('Pracovník')}.get(role, '—')


def has_role(user, *roles):
    return get_user_role(user) in roles


def roles_required(*roles):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not has_role(request.user, *roles):
                raise PermissionDenied('Pro tuto akci nemáte oprávnění.')
            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
