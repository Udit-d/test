FROM python:3.10

WORKDIR /hello

RUN apt update -y

COPY . /hello

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 5000

CMD ["flask", "run", "--host=0.0.0.0"]





