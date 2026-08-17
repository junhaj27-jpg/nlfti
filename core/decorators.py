from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from .models import user_role
def roles_required(*roles):
    def decorator(view):
        @login_required
        @wraps(view)
        def wrapped(request,*args,**kwargs):
            if user_role(request.user) not in roles: raise PermissionDenied
            return view(request,*args,**kwargs)
        return wrapped
    return decorator

