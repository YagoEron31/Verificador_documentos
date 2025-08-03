import os
from flask import Flask, render_template, request, jsonify
# ... (suas outras importações como supabase, requests, etc.)

app = Flask(__name__)

# =================================================================================
# --- ROTAS PARA SERVIR AS PÁGINAS HTML ---
# =================================================================================

@app.route('/')
def home():
    """ Rota para a página inicial (landing page). """
    # CORREÇÃO: Usando o nome exato 'inicial.html'
    return render_template('inicial.html') 

@app.route('/login')
def login_page():
    """ Rota para exibir a página de login. """
    return render_template('login.html')

@app.route('/verificador', methods=['GET', 'POST'])
def verificador_page():
    """ Rota para a ferramenta de análise de documentos. """
    # CORREÇÃO: Usando o nome exato 'verificação.html'
    if request.method == 'GET':
        return render_template('verificação.html')
    
    # ... (Sua lógica de POST para análise que está no arquivo app.py anterior) ...
    
    # Exemplo de retorno em caso de POST bem-sucedido
    resultado_final = {"status": "SEGURO", "erros": [], "hash": "exemplo123", "texto": "Exemplo de texto"}
    return render_template('verificação.html', resultado=resultado_final)
    
@app.route('/transparencia')
def transparencia_page():
    """ Rota para o Portal de Transparência. """
    return render_template('transparencia.html')

# ... (outras rotas e lógicas como /faq, /signup, /handle_login permanecem aqui) ...

if __name__ == '__main__':
    app.run(debug=True)
