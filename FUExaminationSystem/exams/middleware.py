import subprocess

class CheckExamSubmissionsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.run_management_command()

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def run_management_command(self):
        try:
            subprocess.call(['python', 'manage.py', 'check_exam_submissions'])
        except Exception as e:
            print(f'Error running management command: {str(e)}')
