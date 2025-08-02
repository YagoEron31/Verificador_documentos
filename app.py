import os
import re
import hashlib
from flask import Flask, request, render_template
import requests # Usaremos para enviar a notificação
import json

# --- Configuração da API ---
OCR_SPACE_API_KEY = 'SUA_CHAVE_DE_API_AQUI' 
# --- Carregando a URL do Webhook do Ambiente Render ---
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK_URL')

# --- Configuração do Aplicativo ---
app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# --- Função para Enviar Notificação ao Discord ---
def enviar_alerta_discord(resultado):
    if not DISCORD_WEBHOOK_URL:
        print("URL do Webhook do Discord não configurada.")
        return

    # Formata a mensagem para o Discord
    embed = {
        "title": f"🚨 Alerta: Documento Suspeito Detectado!",
        "color": 15158332, # Cor vermelha
        "fields": [
            {"name": "Status", "value": resultado['status'], "inline": True},
            {"name": "Hash do Conteúdo", "value": f"`{resultado['hash']}`", "inline": True},
            {"name": "Inconsistências Encontradas", "value": "\n".join([f"- {erro}" for erro in resultado['erros']])}
        ],
        "footer": {"text": "Análise concluída pelo Verificador Inteligente."}
    }
    
    data = {
        "content": "Um novo documento suspeito requer atenção imediata!",
        "embeds": [embed]
    }
    
    try:
        response = requests.post(DISCORD_WEBHOOK_URL, data=json.dumps(data), headers={"Content-Type": "application/json"})
        response.raise_for_status()
    except Exception as e:
        print(f"Erro ao enviar notificação para o Discord: {e}")

# --- Rota Principal da Aplicação ---
@app.route('/', methods=['GET', 'POST'])
def index():
    resultado_analise = None
    if request.method == 'POST':
        # ... (todo o código de upload e verificação de hash de arquivo continua o mesmo)
        
        # --- Lógica de Análise de Conteúdo e Notificação ---
        try:
            # ... (código de extração de texto com a API OCR.space) ...
            
            # ... (todas as nossas regras de verificação que já tínhamos) ...
            erros_detectados = []

            # Se forem encontradas inconsistências...
            if erros_detectados:
                status = "SUSPEITO"
                resultado_analise = { "status": status, "erros": erros_detectados, "hash": "..." } # Preenche com dados reais
                
                # CHAMA A FUNÇÃO DE NOTIFICAÇÃO
                enviar_alerta_discord(resultado_analise)
            else:
                status = "SEGURO"
                resultado_analise = { "status": status, "erros": [], "hash": "..." }

            # (O restante do código para mostrar o resultado na tela continua igual)

        except Exception as e:
            # ...
        finally:
            # ...

    return render_template('index.html', resultado=resultado_analise)

if __name__ == '__main__':
    app.run(debug=True)
