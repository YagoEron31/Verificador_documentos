import os
from flask import Flask, render_template

app = Flask(__name__)

# Rota para a sua página inicial
@app.route('/')
def home():
    # Supondo que sua página inicial se chame 'inicial.html'
    return render_template('inicial.html')

# Rota que o botão "Transparência" vai chamar
@app.route('/transparencia')
def transparencia_page():
    # Esta rota vai carregar e exibir o seu arquivo 'transparencia.html'
    return render_template('transparencia.html')

# Adicione outras rotas simples se precisar
# @app.route('/login')
# def login_page():
#     return render_template('login.html')

# @app.route('/verificador')
# def verificador_page():
#     return render_template('verificação.html')

if __name__ == '__main__':
    app.run(debug=True)
