FROM python:3.9

RUN mkdir /code
WORKDIR /code

COPY requirements.txt /code/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /code/

CMD ["gunicorn", "FUExaminationSystem.wsgi:application", "--bind", "0.0.0.0:8000"]
