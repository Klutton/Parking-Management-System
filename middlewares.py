from functools import wraps
from sanic import response


def requires_auth():
    def decorator(f):
        @wraps(f)
        async def decorated_function(request, *args, **kwargs):
            userid = request.ctx.session.get('userid')
            if not userid:
                return response.redirect("/login")
            return await f(request, *args, **kwargs)

        return decorated_function

    return decorator


def before_login():
    def decorator(f):
        @wraps(f)
        async def func(request, *args, **kwargs):
            userid = request.ctx.session.get('userid')
            if userid is not None:
                return await response.redirect("/")
            return await f(request, *args, **kwargs)
        return func
    return decorator
