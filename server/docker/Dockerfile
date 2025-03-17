FROM ubuntu:20.04

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    unzip \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y libgl1
RUN apt update

WORKDIR /app

COPY ./main.zip /app
COPY ./requirements.txt /app
RUN unzip main.zip
RUN pip3 install --no-cache-dir -r /app/requirements.txt

CMD ["python3", "storage.py"]
