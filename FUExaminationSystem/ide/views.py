from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import subprocess

@csrf_exempt
def run_code(request):
    if request.method == 'POST':
        code = request.POST.get('code', '')
        predefined_vars = request.session.get('predefined_vars', '')

        code_with_vars = f"{predefined_vars}\n{code}"

        try:
            result = subprocess.run(['python', '-c', code_with_vars], capture_output=True, text=True, timeout=10)
            output = result.stdout
            error = result.stderr
            return JsonResponse({'output': output, 'error': error})
        except subprocess.TimeoutExpired:
            return JsonResponse({'error': 'Execution timed out'}, status=408)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request'}, status=400)