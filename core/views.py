from django.shortcuts import render
from django.contrib.auth.decorators import login_required

def dashboard(request):
    return render(request, 'core/dashboard.html', {
        'title': 'Painel de Gestão Fersie'
    })
