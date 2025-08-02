# --- Configuração do Flask ---
app = Flask(__name__)

# =================================================================================
# --- MÓDULO DE ANÁLISE (NOSSA INTELIGÊNCIA INTEGRADA) ---
# =================================================================================

def analisar_texto_completo(texto):
"""
   Executa todas as nossas regras de verificação no texto extraído.
@@ -34,7 +30,6 @@ def analisar_texto_completo(texto):
palavras_para_realcar = set()
texto_em_minusculo = texto.lower()

    # --- Regra 1: Nepotismo (com lista de exceções) ---
PALAVRAS_INSTITUCIONAIS = [
'campus', 'instituto', 'secretaria', 'prefeitura', 'comissao', 'diretoria', 
'coordenacao', 'avaliacao', 'servicos', 'companhia', 'programa', 'nacional', 
@@ -52,7 +47,6 @@ def analisar_texto_completo(texto):
erros_detectados.append(erro)
palavras_para_realcar.add(nome)

    # --- Regra 2: Datas Inválidas ---
datas = re.findall(r"\d{2}/\d{2}/\d{4}", texto)
for data in datas:
try:
@@ -61,20 +55,17 @@ def analisar_texto_completo(texto):
erros_detectados.append(f"Possível adulteração: A data '{data}' é inválida.")
except ValueError:
continue
    
    # --- Regra 3: Palavras-Chave Suspeitas ---
 
PALAVRAS_SUSPEITAS = ["dispensa de licitacao", "carater de urgencia", "pagamento retroativo", "inexigibilidade de licitacao"]
for palavra in PALAVRAS_SUSPEITAS:
if palavra in texto_em_minusculo:
erro = f"Alerta de Termo Sensível: A expressão '{palavra}' foi encontrada."
erros_detectados.append(erro)
palavras_para_realcar.add(palavra)

    # --- Regra 4: Análise Estrutural ---
if not re.search(r"(of[íi]cio|processo|portaria)\s+n[ºo]", texto_em_minusculo):
erros_detectados.append("Alerta Estrutural: Não foi encontrado um número de documento oficial (Ofício, Processo, etc.).")

    # --- Regra 5: Auditor de Dispensa de Licitação ---
LIMITE_DISPENSA_SERVICOS = 59906.02
if "dispensa de licitacao" in texto_em_minusculo:
valores_encontrados = re.findall(r"R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})", texto)
@@ -109,10 +100,6 @@ def enviar_alerta_discord(resultado):
except Exception as e:
print(f"Erro ao enviar notificação para o Discord: {e}")

# =================================================================================
# --- ROTAS DA APLICAÇÃO (SUA ESTRUTURA ORIGINAL) ---
# =================================================================================

@app.route('/', methods=['GET', 'POST'])
def index():
resultado_analise = None
@@ -138,7 +125,6 @@ def index():
except Exception as e:
erro_consulta = f"Erro ao consultar o banco de dados: {e}"

        # --- Ação de Cadastrar e Analisar Novo Documento ---
elif action == 'cadastrar':
if 'file' not in request.files or request.files['file'].filename == '':
erro_upload = "Nenhum arquivo selecionado para upload."
@@ -147,7 +133,6 @@ def index():
try:
file_bytes = file.read()

                    # 1. Extrai o texto via API
texto_extraido = requests.post(
"https://api.ocr.space/parse/image",
headers={'apikey': OCR_SPACE_API_KEY},
@@ -160,7 +145,7 @@ def index():

hash_sha256 = hashlib.sha256(texto_extraido.encode('utf-8')).hexdigest()

                    # 2. Verifica se a análise já existe no banco

data, count = supabase.table('analises').select('*').eq('hash_sha256', hash_sha256).execute()

if len(data[1]) > 0:
@@ -174,7 +159,7 @@ def index():
"texto_realcado": analise_salva['texto_extraido'] # Simplificação, poderia realçar aqui também
}
else:
                        # 3. Se for novo, executa nossa análise completa

analise = analisar_texto_completo(texto_extraido)

resultado_analise = {
@@ -184,21 +169,21 @@ def index():
"texto": texto_extraido
}

                        # 4. Realce de Evidências

texto_realcado = texto_extraido
for palavra in analise['palavras_realcar']:
texto_realcado = re.sub(f"({re.escape(palavra)})", r"<mark>\1</mark>", texto_realcado, flags=re.IGNORECASE)
resultado_analise['texto_realcado'] = texto_realcado

                        # 5. Salva a nova análise no Supabase

supabase.table('analises').insert({
'hash_sha256': hash_sha256,
'status': resultado_analise['status'],
'erros_detectados': resultado_analise['erros'],
'texto_extraido': texto_extraido
}).execute()

                        # 6. Se for suspeito, envia o alerta para o Discord

if resultado_analise['status'] == 'SUSPEITO':
enviar_alerta_discord(resultado_analise)
