from django.shortcuts import render
from django.template import loader
from django.http import HttpResponseNotFound, HttpResponseServerError

def custom_400(request, exception=None):
    return render(request, 'errors/400.html', status=400)

def custom_401(request, exception=None):
    return render(request, 'errors/401.html', status=401)

def custom_403(request, exception=None):
    return render(request, 'errors/403.html', status=403)

def custom_404(request, exception=None):
    try:
        template = loader.get_template('errors/404.html')
        return HttpResponseNotFound(template.render({}, request))
    except:
        return HttpResponseNotFound('<h1>Sayfa Bulunamadı</h1>')

def custom_408(request, exception=None):
    return render(request, 'errors/408.html', status=408)

def custom_429(request, exception=None):
    return render(request, 'errors/429.html', status=429)

def custom_500(request, *args, **kwargs):
    try:
        template = loader.get_template('errors/500.html')
        return HttpResponseServerError(template.render({}, request))
    except:
        return HttpResponseServerError('<h1>Sunucu Hatası</h1>')

def custom_502(request, *args, **kwargs):
    return render(request, 'errors/502.html', status=502)