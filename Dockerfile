FROM python:3.9-slim

WORKDIR /app

# Instalar dependências do sistema necessárias para a biblioteca rembg
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Copiar arquivos de requisitos
COPY requirements.txt .

# Instalar dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copiar código da aplicação
COPY . .

# Criar diretórios para uploads e imagens processadas
RUN mkdir -p uploads processed

# Expor a porta onde a API será executada
EXPOSE 5000

# Comando para iniciar a aplicação usando gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"] 