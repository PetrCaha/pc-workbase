from .permissions import ROLE_ADMIN, ROLE_MANAGER, get_role_label, get_user_role


def user_capabilities(request):
    role = get_user_role(getattr(request, 'user', None))
    is_admin = role == ROLE_ADMIN
    is_manager = role == ROLE_MANAGER
    can_manage = is_admin or is_manager
    return {
        'app_role': role,
        'app_role_label': get_role_label(getattr(request, 'user', None)),
        'can_manage_users': is_admin,
        'can_manage_customers': can_manage,
        'can_edit_contacts': can_manage,
        'can_transfer_jobs': can_manage,
        'can_archive_records': can_manage,
        'can_delete_records': is_admin,
        'can_export_jobs': can_manage,
        'can_add_contacts': bool(role),
    }
