# API de Remoção de Fundo de Imagens

Esta API Flask permite remover o fundo de imagens utilizando a biblioteca `rembg`.

## Funcionalidades

- Remoção de fundo de imagens individuais
- Processamento em lote de múltiplas imagens
- Download de imagens processadas

## Requisitos

- Python 3.8+
- Dependências listadas no arquivo `requirements.txt`

## Instalação

1. Clone o repositório:
```bash
git clone https://github.com/seu-usuario/removedor-fundo-api.git
cd removedor-fundo-api
```

2. Instale as dependências:
```bash
pip install -r requirements.txt
```

3. Execute a aplicação:
```bash
python app.py
```

A API estará disponível em `http://localhost:5000`.

## Endpoints da API

### Verificação de Saúde

```
GET /health
```

Verifica se a API está funcionando corretamente.

### Remover Fundo de Imagem

```
POST /remove-background
```

Parâmetros do formulário:
- `file`: Arquivo de imagem a ser processado

Retorna:
- A imagem processada sem fundo (formato PNG)

### Processamento em Lote

```
POST /batch-remove
```

Parâmetros do formulário:
- `files`: Múltiplos arquivos de imagem a serem processados

Retorna:
- JSON com lista de IDs das imagens processadas para download posterior

### Download de Imagem Processada

```
GET /download/{file_id}
```

Parâmetros:
- `file_id`: ID da imagem processada

Retorna:
- A imagem processada sem fundo (formato PNG)

## Exemplos de Uso

### Utilizando cURL

**Remover fundo de uma imagem:**
```bash
curl -X POST -F "file=@caminho/para/imagem.jpg" http://localhost:5000/remove-background --output imagem_sem_fundo.png
```

**Processar múltiplas imagens:**
```bash
curl -X POST -F "files=@imagem1.jpg" -F "files=@imagem2.jpg" http://localhost:5000/batch-remove
```

**Baixar uma imagem processada:**
```bash
curl -X GET http://localhost:5000/download/{file_id} --output imagem_processada.png
```

### Utilizando Python Requests

```python
import requests

# Remover fundo de uma imagem
with open('imagem.jpg', 'rb') as f:
    response = requests.post(
        'http://localhost:5000/remove-background',
        files={'file': f}
    )
    
    if response.status_code == 200:
        # Salvar a imagem processada
        with open('imagem_sem_fundo.png', 'wb') as out:
            out.write(response.content)
    else:
        print(f"Erro: {response.json()}")
```

## Estrutura de Diretórios

- `app.py` - Arquivo principal da aplicação
- `uploads/` - Diretório para armazenar imagens originais
- `processed/` - Diretório para armazenar imagens processadas
- `requirements.txt` - Dependências do projeto

## Considerações sobre Produção

Para ambientes de produção, considere:

1. Usar um servidor WSGI como Gunicorn
2. Implementar autenticação para os endpoints
3. Adicionar limitação de taxa (rate limiting)
4. Configurar armazenamento em nuvem para imagens processadas
5. Definir tamanho máximo das imagens 