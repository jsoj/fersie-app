import re
from django.shortcuts import redirect
from django.conf import settings

class RequireLoginMiddleware:
    """
    Middleware global que protege 100% das rotas do app.fersie.com com login e senha.
    Qualquer requisição não autenticada é redirecionada para a tela de login.
    Apenas URLs essenciais de autenticação e assets estáticos são isentas.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt_patterns = [
            re.compile(r'^/login/'),
            re.compile(r'^/logout/'),
            re.compile(r'^/admin/login/'),
            re.compile(r'^/static/'),
            re.compile(r'^/media/'),
            re.compile(r'^/favicon\.ico$'),
        ]

    def __call__(self, request):
        if not request.user.is_authenticated:
            path = request.path_info
            if not any(pattern.match(path) for pattern in self.exempt_patterns):
                full_path = request.get_full_path()
                return redirect(f"{settings.LOGIN_URL}?next={full_path}")

        return self.get_response(request)
