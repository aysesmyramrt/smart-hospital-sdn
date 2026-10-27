FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1

# Sistem bağımlılıkları + OVS + ağ araçları
RUN apt-get update && apt-get install -y \
    git \
    python3 \
    python3-pip \
    python3-dev \
    openvswitch-switch \
    openvswitch-common \
    net-tools \
    iproute2 \
    iputils-ping \
    iperf3 \
    tcpdump \
    curl \
    help2man \
    socat \
    make \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Mininet — mnexec derle + Python paketi kur
RUN git clone https://github.com/mininet/mininet.git /mininet && \
    cd /mininet && git checkout 2.3.1b4 && \
    gcc -o mnexec mnexec.c && \
    install -v mnexec /usr/local/bin/ && \
    python3 setup.py install

# RYU SDN Controller (eventlet 0.30.2 gerekli - uyumluluk)
RUN pip3 install --upgrade pip && \
    pip3 install eventlet==0.30.2 ryu msgpack

WORKDIR /app
COPY . .
RUN chmod +x run.sh

CMD ["bash", "run.sh"]
