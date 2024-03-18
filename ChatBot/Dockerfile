FROM python:3.8-slim

WORKDIR /chatapp

RUN apt-get update && apt-get install -y build-essential

COPY . /chatapp

RUN pip install -r requirements.txt

ENV FLASK_APP=app.py

EXPOSE 5000

#COPY .env /chatapp

CMD ["flask", "run", "--host=0.0.0.0"]