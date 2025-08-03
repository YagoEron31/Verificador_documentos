import os
from flask import Flask, render_template, request
# ... (suas outras importações)

app = Flask(__name__)

# =================================================================================
# --- ROTAS PARA SERVIR AS PÁGINAS HTML ---
# =================================================================================

@app.route('/')
def home():
    """ Rota para a página inicial (landing page). """
    # Corrigido para o nome do seu arquivo
    return render_template('inicial.html') 

@app.route('/login')
def login_page():
    """ Rota para exibir a página de login. """
    return render_template('login.html')

@app.route('/cadastro')
def cadastro_page():
    """ Rota para exibir a página de cadastro. """
    return render_template('cadastro.html')

@app.route('/verificador', methods=['GET', 'POST'])
def verificador_page():
    """ Rota para a ferramenta de análise de documentos. """
    # Corrigido para o nome do seu arquivo
    if request.method == 'GET':
        return render_template('verificação.html')
    # ... (Sua lógica de POST para análise)
    return render_template('verificação.html')
    
@app.route('/transparencia')
def transparencia_page():
    """ Rota para o Portal de Transparência. """
    return render_template('transparencia.html')

@app.route('/faq')
def faq_page():
    """ Rota para a página de Perguntas Frequentes. """
    # Corrigido para o nome do seu arquivo
    return render_template('perguntas.html')

# =================================================================================
# --- ROTAS DE API E LÓGICA ---
# (Suas outras rotas e funções de análise permanecem aqui)
# =================================================================================

if __name__ == '__main__':
    app.run(debug=True)
