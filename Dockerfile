FROM python:3.9-slim

WORKDIR /app

# Instalar dependências do sistema necessárias para a biblioteca rembg e onnxruntime
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Copiar arquivos de requisitos
COPY requirements.txt .

# Atualizar pip e instalar dependências
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY . .

# Criar diretórios para uploads e imagens processadas
RUN mkdir -p uploads processed logs

# Expor a porta onde a API será executada
EXPOSE 5000

# Aumentar o limite de memória para o processo
ENV GUNICORN_CMD_ARGS="--config=gunicorn_config.py"

# Comando para iniciar a aplicação usando gunicorn com configuração
CMD ["gunicorn", "app:app"] 