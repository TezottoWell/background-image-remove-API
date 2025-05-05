from flask import Flask, request, send_file, jsonify, render_template, url_for
import os
from rembg import remove
from PIL import Image
import io
import uuid
import logging

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Pasta para armazenar imagens processadas
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'

# Criar pastas se não existirem
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

@app.route('/')
def index():
    """Rota principal que renderiza a interface web"""
    return render_template('index.html')

@app.route('/health', methods=['GET'])
def health_check():
    """Endpoint para verificar se a API está funcionando"""
    return jsonify({"status": "ok"}), 200

@app.route('/remove-background', methods=['POST'])
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
    
    try:
        # Ler a imagem de entrada
        input_image = Image.open(file.stream)
        
        # Gerar um ID único para o arquivo
        file_id = str(uuid.uuid4())
        
        # Processar a imagem para remover o fundo
        logger.info(f"Processando imagem {file_id}")
        output_image = remove(input_image)
        
        # Preparar o buffer para enviar a imagem de volta
        img_byte_arr = io.BytesIO()
        output_image.save(img_byte_arr, format=input_image.format or 'PNG')
        img_byte_arr.seek(0)
        
        # Salvar as imagens (opcional)
        input_path = os.path.join(UPLOAD_FOLDER, f"{file_id}_input.png")
        output_path = os.path.join(PROCESSED_FOLDER, f"{file_id}_output.png")
        
        input_image.save(input_path)
        output_image.save(output_path)
        
        logger.info(f"Imagem processada com sucesso: {file_id}")
        
        # Retornar a imagem sem fundo
        return send_file(
            img_byte_arr,
            mimetype='image/png',
            as_attachment=True,
            download_name=f"no_bg_{file_id}.png"
        )
        
    except Exception as e:
        logger.error(f"Erro ao processar imagem: {str(e)}")
        return jsonify({"error": f"Erro ao processar imagem: {str(e)}"}), 500

@app.route('/batch-remove', methods=['POST'])
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
    
    processed_files = []
    
    try:
        for file in files:
            # Ler a imagem de entrada
            input_image = Image.open(file.stream)
            
            # Gerar um ID único para o arquivo
            file_id = str(uuid.uuid4())
            
            # Processar a imagem para remover o fundo
            logger.info(f"Processando imagem em lote: {file_id}")
            output_image = remove(input_image)
            
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
        
        logger.info(f"Processamento em lote concluído: {len(processed_files)} imagens")
        return jsonify({
            "status": "success", 
            "message": f"{len(processed_files)} imagens processadas",
            "files": processed_files
        }), 200
        
    except Exception as e:
        logger.error(f"Erro ao processar imagens em lote: {str(e)}")
        return jsonify({"error": f"Erro ao processar imagens: {str(e)}"}), 500

@app.route('/download/<file_id>', methods=['GET'])
def download_processed_image(file_id):
    """
    Faz o download de uma imagem processada pelo ID.
    
    Parâmetros esperados:
    - file_id: ID da imagem processada
    
    Retorna:
    - A imagem processada
    """
    try:
        # Verificar se o arquivo existe
        output_path = os.path.join(PROCESSED_FOLDER, f"{file_id}_output.png")
        
        if not os.path.exists(output_path):
            logger.error(f"Arquivo não encontrado: {file_id}")
            return jsonify({"error": "Arquivo não encontrado"}), 404
        
        logger.info(f"Enviando arquivo processado: {file_id}")
        return send_file(
            output_path,
            mimetype='image/png',
            as_attachment=True,
            download_name=f"no_bg_{file_id}.png"
        )
        
    except Exception as e:
        logger.error(f"Erro ao enviar arquivo: {str(e)}")
        return jsonify({"error": f"Erro ao enviar arquivo: {str(e)}"}), 500

if __name__ == '__main__':
    logger.info("Iniciando servidor de API para remoção de fundo de imagens")
    app.run(debug=True, host='0.0.0.0', port=5000) 