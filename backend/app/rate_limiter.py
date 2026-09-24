from slowapi import Limiter
from slowapi.util import get_remote_address

def _user_or_ip_key_func(request):
    return get_remote_address(request)

limiter = Limiter(key_func=_user_or_ip_key_func)
