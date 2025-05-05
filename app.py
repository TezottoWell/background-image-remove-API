from flask import Flask, request, send_file, jsonify, render_template, url_for, abort, make_response
import os
from rembg import remove
from PIL import Image
import io
import uuid
import logging
import time
import hashlib
import secrets
import functools
from werkzeug.middleware.proxy_fix import ProxyFix
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.utils import secure_filename
from logging.handlers import RotatingFileHandler
import json
from datetime import datetime
import pkg_resources

# Configuração inicial da remoção de fundo
rembg_version = pkg_resources.get_distribution("rembg").version
try:
    # A maioria das versões do rembg usa a função remove diretamente
    # sem necessidade de inicialização de sessão
    REMBG_SESSION = None
    logging.info(f"Rembg inicializado com sucesso (versão {rembg_version})")
except Exception as e:
    logging.error(f"Erro ao inicializar rembg: {str(e)}")
    REMBG_SESSION = None

# Função auxiliar para processamento de imagem
def process_image_remove_bg(input_image):
    """Função auxiliar para remover o fundo de uma imagem"""
    # Usar diretamente a função remove
    return remove(input_image)

# Configuração de logs de segurança
LOG_FOLDER = 'logs'
os.makedirs(LOG_FOLDER, exist_ok=True)

# Configurar logger principal
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Adicionar handler para arquivo com rotação
handler = RotatingFileHandler(
    os.path.join(LOG_FOLDER, 'app.log'),
    maxBytes=10485760,  # 10MB
    backupCount=10
)
handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
))
handler.setLevel(logging.INFO)
logger.addHandler(handler)

# Logger específico para eventos de segurança
security_logger = logging.getLogger('security')
security_logger.setLevel(logging.INFO)
security_handler = RotatingFileHandler(
    os.path.join(LOG_FOLDER, 'security.log'),
    maxBytes=10485760,
    backupCount=10
)
security_handler.setFormatter(logging.Formatter(
    '%(asctime)s %(levelname)s: %(message)s [ip: %(remote_addr)s]'
))
security_logger.addHandler(security_handler)

# Carregar configurações de um arquivo .env
from dotenv import load_dotenv
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', secrets.token_hex(32))
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # Limitar uploads a 16MB
app.config['UPLOAD_EXTENSIONS'] = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
app.config['API_KEYS'] = os.getenv('API_KEYS', '').split(',')

# Aplicar ProxyFix para garantir que os endereços IP corretos sejam registrados
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)

# Configurar limitador de taxa
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://",
)

# Pasta para armazenar imagens processadas
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'

# Criar pastas se não existirem
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

# Funções auxiliares de segurança
def validate_image(stream):
    """Valida se o arquivo é uma imagem real e não maliciosa"""
    try:
        # Em vez de usar imghdr, tentamos abrir a imagem com Pillow
        image = Image.open(stream)
        # Verificar se é um formato de imagem suportado
        format = image.format.lower() if image.format else None
        stream.seek(0)  # Resetar o ponteiro do stream
        if not format:
            return None
        return '.' + (format if format != 'jpeg' else 'jpg')
    except Exception:
        stream.seek(0)  # Resetar o ponteiro do stream em caso de erro
        return None

def log_security_event(event_type, details, level=logging.INFO):
    """Registra eventos de segurança com contexto"""
    extra = {
        'remote_addr': get_remote_address(),
        'event_type': event_type,
        'timestamp': datetime.utcnow().isoformat()
    }
    security_logger.log(level, f"{event_type}: {details}", extra=extra)

def require_api_key(view_function):
    """Decorador para exigir API key para endpoints sensíveis"""
    @functools.wraps(view_function)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key', '') or request.args.get('api_key', '')
        
        # Permitir acesso à interface web sem API key
        if request.path == '/' and request.method == 'GET':
            return view_function(*args, **kwargs)
            
        if not api_key:
            log_security_event('AUTH_FAILED', 'Tentativa de acesso sem API key')
            return jsonify({"error": "API key obrigatória"}), 401
            
        if app.config['API_KEYS'] and api_key not in app.config['API_KEYS']:
            log_security_event('AUTH_FAILED', f'API key inválida: {api_key[:5]}...')
            return jsonify({"error": "API key inválida"}), 403
            
        return view_function(*args, **kwargs)
    return decorated_function

# Middleware para adicionar cabeçalhos de segurança a todas as respostas
@app.after_request
def add_security_headers(response):
    """Adiciona cabeçalhos de segurança a todas as respostas HTTP"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self' 'unsafe-inline'"
    response.headers['Referrer-Policy'] = 'same-origin'
    response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    return response

@app.route('/')
def index():
    """Rota principal que renderiza a interface web"""
    return render_template('index.html')

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint para verificar se a API está funcionando"""
    return jsonify({"status": "ok"}), 200

@app.route('/remove-background', methods=['POST'])
@require_api_key
@limiter.limit("30 per minute")
def remove_background():
    """
    Remove o fundo de uma imagem enviada via POST.
    
    Parâmetros esperados:
    - file: arquivo de imagem
    
    Retorna:
    - A imagem processada sem fundo
    """
    if 'file' not in request.files:
        logger.error("Nenhum arquivo encontrado na requisição")
        return jsonify({"error": "Nenhum arquivo encontrado"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        logger.error("Nome de arquivo vazio")
        return jsonify({"error": "Nome de arquivo vazio"}), 400
    
    # Validar o nome do arquivo
    filename = secure_filename(file.filename)
    file_ext = os.path.splitext(filename)[1].lower()
    
    if file_ext not in app.config['UPLOAD_EXTENSIONS']:
        log_security_event('INVALID_FILE', f'Extensão de arquivo não permitida: {file_ext}')
        return jsonify({"error": "Formato de arquivo não permitido"}), 400
        
    # Verificar o conteúdo do arquivo para garantir que é realmente uma imagem
    if not validate_image(file.stream):
        log_security_event('INVALID_FILE', 'Arquivo não é uma imagem válida')
        return jsonify({"error": "Arquivo não é uma imagem válida"}), 400
    
    try:
        # Ler a imagem de entrada
        input_image = Image.open(file.stream)
        
        # Limitar o tamanho da imagem para processamento
        max_dimension = 3000  # Pixels
        if input_image.width > max_dimension or input_image.height > max_dimension:
            log_security_event('OVERSIZED_IMAGE', f'Imagem muito grande: {input_image.width}x{input_image.height}')
            return jsonify({"error": f"Imagem muito grande. Dimensão máxima permitida: {max_dimension}px"}), 400
        
        # Gerar um ID único para o arquivo
        file_id = str(uuid.uuid4())
        
        # Registrar a operação
        logger.info(f"Processando imagem {file_id} - IP: {get_remote_address()}")
        
        # Processar a imagem para remover o fundo
        start_time = time.time()
        output_image = process_image_remove_bg(input_image)
        processing_time = time.time() - start_time
        
        # Preparar o buffer para enviar a imagem de volta
        img_byte_arr = io.BytesIO()
        output_image.save(img_byte_arr, format=input_image.format or 'PNG')
        img_byte_arr.seek(0)
        
        # Salvar as imagens (opcional)
        input_path = os.path.join(UPLOAD_FOLDER, f"{file_id}_input.png")
        output_path = os.path.join(PROCESSED_FOLDER, f"{file_id}_output.png")
        
        input_image.save(input_path)
        output_image.save(output_path)
        
        logger.info(f"Imagem processada com sucesso: {file_id} em {processing_time:.2f}s")
        
        # Retornar a imagem sem fundo
        response = make_response(send_file(
            img_byte_arr,
            mimetype='image/png',
            as_attachment=True,
            download_name=f"no_bg_{file_id}.png"
        ))
        
        # Adicionar identificadores únicos no cabeçalho da resposta para rastreamento
        response.headers['X-Request-ID'] = file_id
        
        return response
        
    except Exception as e:
        logger.error(f"Erro ao processar imagem: {str(e)}")
        return jsonify({"error": f"Erro ao processar imagem: {str(e)}"}), 500

@app.route('/batch-remove', methods=['POST'])
@require_api_key
@limiter.limit("10 per minute")
def batch_remove_background():
    """
    Remove o fundo de múltiplas imagens enviadas via POST.
    
    Parâmetros esperados:
    - files: arquivos de imagem (múltiplos)
    
    Retorna:
    - IDs das imagens processadas para download posterior
    """
    if 'files' not in request.files:
        logger.error("Nenhum arquivo encontrado na requisição")
        return jsonify({"error": "Nenhum arquivo encontrado"}), 400
    
    files = request.files.getlist('files')
    
    if not files or files[0].filename == '':
        logger.error("Nenhum arquivo selecionado")
        return jsonify({"error": "Nenhum arquivo selecionado"}), 400
    
    # Limitar o número de arquivos por requisição
    max_files = 10
    if len(files) > max_files:
        log_security_event('BATCH_LIMIT_EXCEEDED', f'Tentativa de processamento em lote com {len(files)} arquivos')
        return jsonify({"error": f"Número máximo de arquivos por requisição: {max_files}"}), 400
    
    processed_files = []
    failed_files = []
    
    try:
        for file in files:
            # Validar o nome do arquivo
            filename = secure_filename(file.filename)
            file_ext = os.path.splitext(filename)[1].lower()
            
            if file_ext not in app.config['UPLOAD_EXTENSIONS']:
                failed_files.append({
                    "original_name": file.filename,
                    "error": "Formato de arquivo não permitido"
                })
                continue
                
            # Verificar se é uma imagem válida
            if not validate_image(file.stream):
                failed_files.append({
                    "original_name": file.filename,
                    "error": "Arquivo não é uma imagem válida"
                })
                continue
                
            try:
                # Ler a imagem de entrada
                input_image = Image.open(file.stream)
                
                # Limitar o tamanho da imagem
                max_dimension = 3000  # Pixels
                if input_image.width > max_dimension or input_image.height > max_dimension:
                    failed_files.append({
                        "original_name": file.filename,
                        "error": f"Imagem muito grande. Dimensão máxima permitida: {max_dimension}px"
                    })
                    continue
                
                # Gerar um ID único para o arquivo
                file_id = str(uuid.uuid4())
                
                # Processar a imagem para remover o fundo
                logger.info(f"Processando imagem em lote: {file_id}")
                output_image = process_image_remove_bg(input_image)
                
                # Salvar as imagens
                input_path = os.path.join(UPLOAD_FOLDER, f"{file_id}_input.png")
                output_path = os.path.join(PROCESSED_FOLDER, f"{file_id}_output.png")
                
                input_image.save(input_path)
                output_image.save(output_path)
                
                processed_files.append({
                    "file_id": file_id,
                    "original_name": file.filename,
                    "output_path": output_path
                })
            except Exception as e:
                failed_files.append({
                    "original_name": file.filename,
                    "error": str(e)
                })
        
        logger.info(f"Processamento em lote concluído: {len(processed_files)} imagens processadas, {len(failed_files)} falhas")
        
        # Incluir as falhas no resultado
        response_data = {
            "status": "success" if not failed_files else "partial_success", 
            "message": f"{len(processed_files)} imagens processadas, {len(failed_files)} falhas",
            "files": processed_files
        }
        
        if failed_files:
            response_data["failed_files"] = failed_files
        
        return jsonify(response_data), 200
        
    except Exception as e:
        logger.error(f"Erro ao processar imagens em lote: {str(e)}")
        return jsonify({"error": f"Erro ao processar imagens: {str(e)}"}), 500

@app.route('/download/<file_id>', methods=['GET'])
@require_api_key
@limiter.limit("60 per minute")
def download_processed_image(file_id):
    """
    Faz o download de uma imagem processada pelo ID.
    
    Parâmetros esperados:
    - file_id: ID da imagem processada
    
    Retorna:
    - A imagem processada
    """
    try:
        # Sanitizar o ID de entrada para evitar path traversal
        if not file_id or not all(c.isalnum() or c == '-' for c in file_id):
            log_security_event('INVALID_FILE_ID', f'ID de arquivo inválido: {file_id}')
            return jsonify({"error": "ID de arquivo inválido"}), 400
            
        # Verificar se o arquivo existe
        output_path = os.path.join(PROCESSED_FOLDER, f"{file_id}_output.png")
        
        if not os.path.exists(output_path):
            logger.error(f"Arquivo não encontrado: {file_id}")
            return jsonify({"error": "Arquivo não encontrado"}), 404
        
        logger.info(f"Enviando arquivo processado: {file_id}")
        
        # Verificar o tempo de criação do arquivo - opcionalmente poderia expirar arquivos antigos
        file_age = time.time() - os.path.getctime(output_path)
        if file_age > 86400 * 7:  # 7 dias
            logger.warning(f"Arquivo com mais de 7 dias: {file_id}")
        
        return send_file(
            output_path,
            mimetype='image/png',
            as_attachment=True,
            download_name=f"no_bg_{file_id}.png"
        )
        
    except Exception as e:
        logger.error(f"Erro ao enviar arquivo: {str(e)}")
        return jsonify({"error": f"Erro ao enviar arquivo: {str(e)}"}), 500

# Tratamento de erros
@app.errorhandler(404)
def page_not_found(e):
    return jsonify({"error": "Página não encontrada"}), 404

@app.errorhandler(405)
def method_not_allowed(e):
    return jsonify({"error": "Método não permitido"}), 405

@app.errorhandler(413)
def request_entity_too_large(e):
    log_security_event('OVERSIZED_REQUEST', 'Tentativa de upload de arquivo grande demais')
    return jsonify({"error": f"Arquivo muito grande. Tamanho máximo: {app.config['MAX_CONTENT_LENGTH'] // (1024 * 1024)}MB"}), 413

@app.errorhandler(400)
def bad_request(e):
    return jsonify({"error": "Requisição inválida"}), 400

@app.errorhandler(500)
def internal_server_error(e):
    logger.error(f"Erro interno do servidor: {str(e)}")
    return jsonify({"error": "Erro interno do servidor"}), 500

if __name__ == '__main__':
    logger.info("Iniciando servidor de API para remoção de fundo de imagens")
    app.run(debug=False, host='0.0.0.0', port=5000) 