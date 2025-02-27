FROM FROM ubuntu:20.04

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-dev \
    unzip \
    && rm -rf /var/lib/apt/lists/*

RUN apt-get update && apt-get install -y libgl1
RUN apt update

WORKDIR /app

# Copy and unzip the main application
COPY ./main.zip /app
COPY ./requirements.txt /app
RUN unzip main.zip
RUN pip3 install --no-cache-dir --break-system-packages -r /app/requirements.txt

# Copy the 'entrypoint.sh' script and make it executable
# Set the entrypoint script
CMD ["python3", "fetch_data.py"]

