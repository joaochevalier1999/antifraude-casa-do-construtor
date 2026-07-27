import streamlit as st
import base64
import io
import html
import re
import os
import requests
import pandas as pd
import json
import urllib.parse
from datetime import datetime

# Tratamento para biblioteca google-auth
try:
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request as GoogleAuthRequest
    GOOGLE_AUTH_INSTALLED = True
except ImportError:
    GOOGLE_AUTH_INSTALLED = False

# Dependências ReportLab para PDF
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# --- CONFIGURAÇÃO DA PÁGINA (PRODUÇÃO) ---
st.set_page_config(
    page_title="Portal Antifraude & Crédito - Casa do Construtor",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ESTILIZAÇÃO CSS PROFISSIONAL (ALTO CONTRASTE E UNIFORMIZAÇÃO) ---
st.markdown("""
    <style>
    /* Forçar fundo claro e leitura limpa em qualquer modo do navegador */
    .stApp { 
        background-color: #F8FAFC !important; 
        color: #0F172A !important; 
    }
    
    p, span, label, h1, h2, h3, h4, h5, h6, div, .stMarkdown { 
        color: #0F172A !important; 
    }

    /* Botão Principal - Azul Casa do Construtor com hover Amarelo */
    div.stButton > button[kind="primary"] { 
        background-color: #003366 !important; 
        color: #FFFFFF !important; 
        border-radius: 8px !important; 
        border: 2px solid #003366 !important; 
        padding: 12px 24px !important; 
        font-weight: bold !important; 
        font-size: 16px !important;
        transition: all 0.3s !important; 
    }
    div.stButton > button[kind="primary"]:hover { 
        background-color: #FBC02D !important; 
        color: #003366 !important; 
        border: 2px solid #FBC02D !important; 
    }

    /* Contêineres / Cards de Seção */
    div[data-testid="stVerticalBlock"] > div[style*="border"] { 
        border-radius: 12px !important; 
        background-color: #FFFFFF !important; 
        box-shadow: 0px 4px 12px rgba(0, 0, 0, 0.06) !important; 
        border: 1px solid #CBD5E1 !important; 
        padding: 22px !important; 
    }

    /* Campos de Entrada de Texto, Data e Selectbox */
    div[data-baseweb="select"] > div, 
    div[data-baseweb="input"] > div, 
    input, textarea {
        background-color: #FFFFFF !important;
        color: #0F172A !important;
        border: 1px solid #94A3B8 !important;
        border-radius: 6px !important;
    }

    div[data-baseweb="menu"] * {
        background-color: #FFFFFF !important;
        color: #0F172A !important;
    }

    /* Banners e Modificadores de Interface */
    div[role="radiogroup"] label p { color: #0F172A !important; font-weight: 600 !important; }
    button[data-baseweb="tab"] p, button[data-baseweb="tab"] div { color: #0F172A !important; font-weight: bold !important; }

    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- BANCO DE USUÁRIOS E SENHAS ---
USUARIOS = {
    "master": {"senha": "master2026", "nome": "Gestor Geral Master", "filial": "Todas", "perfil": "master"},
    "087_blumenau": {"senha": "cc087", "nome": "Atendente Blumenau", "filial": "087 - Blumenau", "perfil": "user"},
    "213_indaial": {"senha": "cc213", "nome": "Atendente Indaial", "filial": "213 - Indaial", "perfil": "user"},
    "250_bc": {"senha": "cc250", "nome": "Atendente Balneário Camboriú", "filial": "250 - Balneário Camboriú", "perfil": "user"},
    "284_jaragua": {"senha": "cc284", "nome": "Atendente Jaraguá do Sul", "filial": "284 - Jaraguá do Sul", "perfil": "user"},
    "299_brusque": {"senha": "cc299", "nome": "Atendente Brusque", "filial": "299 - Brusque", "perfil": "user"},
    "350_itapema": {"senha": "cc350", "nome": "Atendente Itapema", "filial": "350 - Itapema", "perfil": "user"},
    "360_blumenau2": {"senha": "cc360", "nome": "Atendente Blumenau 02", "filial": "360 - Blumenau 02", "perfil": "user"},
    "503_timbo": {"senha": "cc503", "nome": "Atendente Timbó", "filial": "503 - Timbó", "perfil": "user"},
    "560_camboriu": {"senha": "cc560", "nome": "Atendente Camboriú", "filial": "560 - Camboriú", "perfil": "user"},
    "636_guaramirim": {"senha": "cc636", "nome": "Atendente Guaramirim", "filial": "636 - Guaramirim", "perfil": "user"},
    "695_tijucas": {"senha": "cc695", "nome": "Atendente Tijucas", "filial": "695 - Tijucas", "perfil": "user"},
    "733_sao_bento": {"senha": "cc733", "nome": "Atendente São Bento", "filial": "733 - São Bento do Sul", "perfil": "user"},
}

if "logged_in" not in st.session_state: st.session_state["logged_in"] = False
if "usuario_atual" not in st.session_state: st.session_state["usuario_atual"] = None

# --- TELA DE LOGIN ---
if not st.session_state["logged_in"]:
    st.write("<br><br><br>", unsafe_allow_html=True)
    col_l1, col_l2, col_l3 = st.columns([1, 1.5, 1])
    with col_l2:
        with st.container(border=True):
            st.image("https://casadoconstrutor.com.br/wp-content/uploads/2021/04/logo-casa-do-construtor.png", width=300)
            st.markdown("### 🔐 Central Restrita de Análise de Risco")
            with st.form("form_login"):
                usuario_input = st.text_input("Usuário da Unidade")
                senha_input = st.text_input("Senha", type="password")
                if st.form_submit_button("Entrar no Portal", type="primary", use_container_width=True):
                    user_clean = usuario_input.strip().lower()
                    if user_clean in USUARIOS and USUARIOS[user_clean]["senha"] == senha_input:
                        st.session_state["logged_in"] = True
                        st.session_state["usuario_atual"] = USUARIOS[user_clean]
                        st.rerun()
                    else:
                        st.error("❌ Credenciais inválidas.")
    st.stop()

# --- AUTENTICAÇÃO GOOGLE CLOUD (VERTEX AI + SHEETS + STORAGE) ---
token_acesso_valido = None
gcp_project_id = None
erro_auth = None

if GOOGLE_AUTH_INSTALLED and "GCP_CREDENTIALS" in st.secrets:
    try:
        creds_json = json.loads(st.secrets["GCP_CREDENTIALS"])
        gcp_project_id = creds_json.get("project_id")
        
        escopos = [
            'https://www.googleapis.com/auth/cloud-platform',
            'https://www.googleapis.com/auth/spreadsheets',
            'https://www.googleapis.com/auth/devstorage.full_control'
        ]
        credenciais = service_account.Credentials.from_service_account_info(creds_json, scopes=escopos)
        req_auth = GoogleAuthRequest()
        credenciais.refresh(req_auth)
        token_acesso_valido = credenciais.token
    except Exception as e:
        erro_auth = f"Erro ao processar o JSON: {e}"

# --- CONFIGURAÇÕES DE PERSISTÊNCIA (SECRETS) ---
SPREADSHEET_ID = st.secrets.get("SPREADSHEET_ID", None)
GCS_BUCKET_NAME = st.secrets.get("GCS_BUCKET_NAME", None)
if GCS_BUCKET_NAME and "nome-do-seu-bucket" in GCS_BUCKET_NAME:
    GCS_BUCKET_NAME = None

ARQUIVO_HISTORICO = "historico_analises.csv"
ARQUIVO_BLACKLIST = "blacklist_rede.csv"

# --- FUNÇÕES REST API GOOGLE SHEETS E STORAGE ---
def append_google_sheet(tab_name, row_values):
    """Grava uma nova linha na Planilha do Google via REST API v4."""
    if not SPREADSHEET_ID or not token_acesso_valido:
        return False, "ID da Planilha ou Token não configurado."
    try:
        tab_encoded = urllib.parse.quote(tab_name)
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/{tab_encoded}!A1:append?valueInputOption=USER_ENTERED"
        headers = {"Authorization": f"Bearer {token_acesso_valido}", "Content-Type": "application/json"}
        body = {"values": [row_values]}
        res = requests.post(url, headers=headers, json=body)
        if res.status_code == 200:
            return True, "Sucesso"
        else:
            return False, f"HTTP {res.status_code}: {res.text}"
    except Exception as e:
        return False, str(e)

def read_google_sheet(tab_name):
    """Lê os dados de uma aba da Planilha do Google via REST API."""
    if not SPREADSHEET_ID or not token_acesso_valido:
        return None
    try:
        tab_encoded = urllib.parse.quote(tab_name)
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/{tab_encoded}!A1:Z5000"
        headers = {"Authorization": f"Bearer {token_acesso_valido}"}
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            vals = res.json().get("values", [])
            if len(vals) > 1:
                return pd.DataFrame(vals[1:], columns=vals[0])
    except Exception:
        pass
    return None

def upload_to_gcs(object_name, file_bytes, mime_type):
    """Envia arquivos para o Google Cloud Storage via REST API."""
    if not GCS_BUCKET_NAME or not token_acesso_valido:
        return False, "Bucket GCS não configurado."
    try:
        obj_encoded = urllib.parse.quote(object_name)
        url = f"https://storage.googleapis.com/upload/storage/v1/b/{GCS_BUCKET_NAME}/o?uploadType=media&name={obj_encoded}"
        headers = {"Authorization": f"Bearer {token_acesso_valido}", "Content-Type": mime_type}
        res = requests.post(url, headers=headers, data=file_bytes)
        return res.status_code == 200, res.text
    except Exception as e:
        return False, str(e)

def carregar_blacklist():
    df_sheets = read_google_sheet("Blacklist")
    if df_sheets is not None and not df_sheets.empty:
        return df_sheets
    if os.path.exists(ARQUIVO_BLACKLIST):
        return pd.read_csv(ARQUIVO_BLACKLIST, sep=";", dtype=str)
    return pd.DataFrame(columns=["Documento", "Nome_Razao", "Motivo_Alerta", "Data_Inclusao", "Cadastrado_Por"])

def salvar_blacklist_local(df):
    df.to_csv(ARQUIVO_BLACKLIST, index=False, sep=";", encoding="utf-8-sig")

def salvar_no_historico(filial, atendente, cliente, doc_cliente, tipo_pessoa, equipamentos_str, valor_total, prazo, parecer_texto):
    data_hora_dt = datetime.now()
    status = "ANALISADO"
    parecer_up = parecer_texto.upper()
    if "[APROVADO COM RESTRIÇÃO]" in parecer_up or "RESTRIÇÃO" in parecer_up or "🟡" in parecer_up: 
        status = "APROVADO COM RESTRIÇÃO"
    elif "[APROVADO]" in parecer_up or "🟢 APROVADO" in parecer_up: 
        status = "APROVADO"
    elif "[REPROVADO]" in parecer_up or "🔴 REPROVADO" in parecer_up or "NEGADO" in parecer_up: 
        status = "REPROVADO"

    row_data = [
        data_hora_dt.strftime("%d/%m/%Y %H:%M:%S"),
        data_hora_dt.strftime("%d/%m/%Y"),
        filial, atendente, cliente, doc_cliente, tipo_pessoa,
        equipamentos_str, f"R$ {valor_total:,.2f}", prazo, status
    ]

    # Gravação na nuvem (Google Sheets)
    sucesso_sheets, msg_sheets = append_google_sheet("Historico", row_data)
    if SPREADSHEET_ID and not sucesso_sheets:
        st.warning(f"⚠️ **Aviso de Sincronização Google Sheets:** O registro foi gravado localmente, pois a planilha retornou: ({msg_sheets}).")

    # Gravação no arquivo CSV local como backup
    novo_registro = pd.DataFrame([{
        "Data/Hora": row_data[0], "Data_Dia": row_data[1], "Filial": row_data[2], "Atendente": row_data[3],
        "Cliente": row_data[4], "CPF_CNPJ": row_data[5], "Tipo_Pessoa": row_data[6], "Equipamentos": row_data[7],
        "Valor Reposição Total (R$)": row_data[8], "Prazo": row_data[9], "Status Decisão": row_data[10]
    }])
    if not os.path.exists(ARQUIVO_HISTORICO): 
        novo_registro.to_csv(ARQUIVO_HISTORICO, index=False, sep=";", encoding="utf-8-sig")
    else: 
        novo_registro.to_csv(ARQUIVO_HISTORICO, mode='a', header=False, index=False, sep=";", encoding="utf-8-sig")

# --- GERADOR DE PDF ---
def formatar_texto_para_reportlab(texto): 
    t = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', html.escape(texto))
    t = re.sub(r'^#+\s+(.*)', r'<b>\1</b>', t) 
    return t

def gerar_pdf_parecer(nome_cliente, doc_cliente, tipo_pessoa, prazo, loja, equipamentos_str, valor_total, texto_parecer):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story, styles = [], getSampleStyleSheet()
    titulo_style = ParagraphStyle('Titulo', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#003366'))
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=10, leading=14)

    story.append(Paragraph("<b>CASA DO CONSTRUTOR - PARECER TÉCNICO ANTIFRAUDE</b>", titulo_style))
    story.append(Paragraph(f"Emitido em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", styles['Normal']))
    story.append(Spacer(1, 10))

    val_f = f"R$ {valor_total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    
    t = Table([
        [Paragraph("<b>Cliente / CPF-CNPJ:</b>", body_style), Paragraph(f"{html.escape(nome_cliente)} ({doc_cliente}) - {tipo_pessoa}", body_style)],
        [Paragraph("<b>Prazo Solicitado:</b>", body_style), Paragraph(prazo, body_style)],
        [Paragraph("<b>Filial / Equipamentos:</b>", body_style), Paragraph(f"{html.escape(loja)}<br/><b>Itens:</b> {html.escape(equipamentos_str)}<br/><b>Total Reposição:</b> {val_f}", body_style)],
    ], colWidths=[140, 380])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F2F4F8')), ('GRID', (0, 0), (-1, -1), 0.5, colors.gray)]))
    story.append(t)
    story.append(Spacer(1, 15))

    for linha in texto_parecer.split('\n'):
        if linha.strip(): story.append(Paragraph(formatar_texto_para_reportlab(linha.strip()), body_style))
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# --- CATÁLOGO DE EQUIPAMENTOS COMPLETO ---
CATALOGO_EQUIPAMENTOS = {
    "ACABADORA GASOLINA": 14000.0, "ANDAIME": 15000.0, "APARADOR BATERIA": 2824.50, "ASPIRADOR": 15000.0,
    "BARRA DE LIGACAO 2.05m": 51.0, "BETONEIRA 120/150L": 2280.0, "BETONEIRA 200/300L": 3800.0,
    "BETONEIRA 400L BIVOLT": 5700.0, "BOMBA D'AGUA 3\"": 2500.0, "BOMBA D'AGUA MANGOTE 2\" 5.00m": 3000.0,
    "BOMBA ELETRICA AIRLESS": 5000.0, "CACAMBA PARA GUINCHO 50L": 270.0, "CAMERA TERMICA WIFI": 5600.0,
    "CARRINHO DE MAO 60L": 480.0, "CLIMATIZADOR DE AR": 4200.0, "COMPACTADOR GASOLINA": 18200.0,
    "COMPRESSOR AR DIRETO": 2000.0, "COMPRESSOR COM RESERVATORIO 200L": 7000.0, "CONDUTOR DE ENTULHO": 2500.0,
    "CONTAINER 2.00x2.10x3.00": 7500.0, "CORTADORA DE BLOCO": 6200.0, "CORTADORA DE GRAMA GASOLINA": 4515.0,
    "CORTADORA DE PAREDE": 12000.0, "CORTADORA DE PISO GASOLINA": 12000.0, "CORTADORA PORTATIL GASOLINA": 12000.0,
    "DESEMPENADEIRA": 750.0, "DESENTUPIDORA BIVOLT": 4176.0, "DETECTOR DE MATERIAIS": 3500.0,
    "ENCERADEIRA": 2900.0, "ESCADA ABRIR FIBRA 5.00 16D": 2120.0, "ESCADA EXTENSAO FIBRA 6.60X11.70 39D": 3000.0,
    "ESCADA EXTENSAO/ABRIR 3.90X6.60 24D": 1380.0, "ESCORA METALICA": 20000.0, "ESMERILHADEIRA 4 1/2\"": 550.0,
    "ESMERILHADEIRA 5\" BATERIA": 1150.0, "ESMERILHADEIRA 7\"": 1000.0, "ESMERILHADEIRA 9\"": 1000.0,
    "ESQUADRILHADEIRA": 6230.67, "EXAUSTOR": 1100.0, "EXTENSAO ELETRICA 30m 3x6.00mm": 500.0, "EXTRATORA": 3500.0,
    "FIXADOR BATERIA": 10050.0, "FRESADORA": 2240.0, "FURADEIRA MAGNETICA": 5948.42, "GERADOR 13KVA GASOLINA": 8140.0,
    "GUINCHO DE COLUNA 350KG": 5730.0, "GUINCHO DE ELEVACAO 500KG TRIFASICO": 12000.0, "INVERSORA MULTI-MIG": 2000.0,
    "LAVADORA ALTA PRESSAO TRIFASICA": 23000.0, "LAVADORA/SECADORA": 19000.0, "LIXADEIRA ANGULAR 7\"": 900.0,
    "LIXADEIRA DE CINTA": 1995.0, "LIXADEIRA DE PAREDE": 1750.0, "LIXADEIRA DE TETO": 2550.0,
    "LIXADEIRA ROTO 5\"": 2200.0, "LIXADEIRA ROTO ORBITAL": 1850.0, "LIXADEIRA ROTORBITAL": 2700.0,
    "MANGOTE 35mm 5.00m": 1900.0, "MANGUEIRA PARA DESENTUPIR": 300.02, "MAQUINA CORTAR BLOCO": 2361.37,
    "MARTELETE 2KG": 950.0, "MARTELETE 5KG": 4680.0, "MARTELETE 7.9KG": 6770.0, "MARTELETE PERFURADOR/ROMPEDOR 3.1KG": 3000.0,
    "MARTELETE PERFURADOR/ROMPEDOR 6KG": 4520.0, "MARTELETE PERFURADOR/ROMPEDOR 9.5KG": 5100.0,
    "MEDIDOR LASER": 10000.0, "MISTURADOR 270L": 500.0, "MORSA": 300.0, "MOTOBOMBA 2\" GASOLINA": 5000.0,
    "MOTOVIBRADOR 2.0CV": 2700.0, "MULTICORTADORA": 1300.0, "PARAFUSADEIRA 18V BATERIA": 1995.0,
    "PEDESTAL PARA GUINCHO": 1430.0, "PERFIL REGUA ALUMINIO 1.80m": 1100.0, "PERFURADOR GASOLINA": 2100.0,
    "PERFURATRIZ": 12631.90, "PINADOR PNEUMATICO": 619.50, "PISTOLA PINTURA ALTA PRESSAO": 290.03,
    "PLACA VIBRATORIA REVERSIVEL GASOLINA": 12000.0, "PLAINA": 1100.0, "PODADOR DE GALHO GASOLINA": 3159.19,
    "POLICORTE": 1533.0, "POLITRIZ DE PISO": 15500.0, "POLITRIZ E LIXADEIRA": 3300.0, "REGUA": 493.24,
    "REGUA VIBRATORIA GASOLINA": 4820.39, "RETIFICADORA": 720.0, "RISCADEIRA": 6000.0, "ROCADEIRA GASOLINA": 2429.19,
    "ROMPEDOR 10KG": 5600.0, "ROMPEDOR 11.8KG": 9150.0, "ROMPEDOR 14.5KG": 11440.0, "ROMPEDOR 16KG": 7900.0,
    "ROMPEDOR 17.3KG": 4100.0, "ROMPEDOR 18.5KG": 7900.0, "ROMPEDOR 27KG": 11700.0, "ROMPEDOR 29.9KG": 23980.0,
    "ROMPEDOR 31.3KG": 11260.0, "SERRA MADEIRA BATERIA": 6800.0, "SERRA MARMORE 180mm": 3070.0,
    "SERRA SABRE 18V BATERIA": 12000.0, "SERRA TICO-TICO": 980.0, "SOLDA ELETRICA": 2907.03, "SOPRADOR GASOLINA": 2010.0,
    "SOPRADOR TERMICO": 850.0, "TALHA ATE 03 TON": 800.0, "TRANSFORMADOR 7000W BIVOLT": 700.0,
    "TRANSPALET MANUAL ATE 02 TON": 2000.0, "TUPIA": 882.0, "VARREDEIRA MANUAL": 961.31, "VIBRADOR AF 35mm": 3000.0
}

OPCAO_OUTRO_EQUIP = "➕ OUTRO EQUIPAMENTO (Manual)"
lista_opcoes_equipamentos = sorted(list(CATALOGO_EQUIPAMENTOS.keys())) + [OPCAO_OUTRO_EQUIP]

# --- BARRA LATERAL ---
usr_info = st.session_state["usuario_atual"]
eh_master = usr_info["perfil"] == "master"

with st.sidebar:
    st.image("https://casadoconstrutor.com.br/wp-content/uploads/2021/04/logo-casa-do-construtor.png", width=180)
    st.markdown(f"### 👤 {usr_info['nome']}")
    st.markdown(f"**📍 Unidade:** {usr_info['filial']}")
    st.markdown("---")
    
    st.markdown("🔍 **Status do Sistema**")
    if token_acesso_valido and gcp_project_id:
        st.success(f"🟢 Nuvem Conectada!\n`{gcp_project_id}`")
    else:
        st.error("🔴 JSON GCP ausente nos Secrets.")

    if SPREADSHEET_ID:
        st.success("🟢 Google Sheets Ativo")
    else:
        st.caption("🟡 Sheets não configurado nas Secrets.")

    if GCS_BUCKET_NAME:
        st.success("🟢 Storage de Fotos Ativo")
    else:
        st.caption("🟡 GCS não configurado.")

    st.markdown("---")
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state["logged_in"] = False
        st.rerun()

# ÁREA CENTRAL
st.title("🛡️ Central de Risco e Crédito")
st.caption("Validação de cadastros, análise de risco documental e sinergia de obra.")

# NAVEGAÇÃO DE ABAS ISOLADA
if eh_master:
    aba_nova, aba_black, aba_dash, aba_hist = st.tabs(["🚀 Nova Análise", "🚨 Blacklist / Suspeitos", "📊 Dashboard Gerencial", "📋 Histórico Geral"])
else:
    aba_nova, aba_hist = st.tabs(["🚀 Nova Análise", "📋 Meu Histórico"])
    aba_black, aba_dash = None, None

# --- ABA 1: NOVA ANÁLISE ---
with aba_nova:
    with st.container(border=True):
        st.markdown("#### 1️⃣ Identificação do Cliente e Operação")
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            loja = st.selectbox("🏢 Filial Responsável", [
                "087 - Blumenau", "213 - Indaial", "350 - Itapema", "250 - Balneário Camboriú",
                "284 - Jaraguá do Sul", "299 - Brusque", "360 - Blumenau 02", "503 - Timbó",
                "560 - Camboriú", "636 - Guaramirim", "695 - Tijucas", "733 - São Bento do Sul", "Todas"
            ]) if eh_master else usr_info["filial"]
            if not eh_master: st.text_input("🏢 Filial Responsável", value=loja, disabled=True)
            
            tipo_cliente = st.radio("👤 Tipo de Cadastro", ["Pessoa Física (PF)", "Pessoa Jurídica (PJ)"], horizontal=True)
            nome_cliente = st.text_input("Nome Completo ou Razão Social", placeholder="Ex: João da Silva / Empresa X LTDA")
            doc_cliente = st.text_input("CPF ou CNPJ do Cliente", placeholder="Apenas números").strip()
            
            subtipo_pj, nome_solicitante, contato_solicitante = None, None, None
            if tipo_cliente == "Pessoa Jurídica (PJ)":
                subtipo_pj = st.selectbox("🏢 Natureza Jurídica", ["Empresa Padrão (LTDA/SA)", "Condomínio", "MEI"])
                col_pj1, col_pj2 = st.columns(2)
                with col_pj1: nome_solicitante = st.text_input("Nome do Solicitante / Síndico")
                with col_pj2: contato_solicitante = st.text_input("E-mail corporativo / WhatsApp")

        with col_a2:
            referencias = ""
            if tipo_cliente == "Pessoa Física (PF)":
                st.warning("⚠️ **Atenção:** Pagamento faturado a prazo NÃO É PERMITIDO para Pessoa Física.")
                forma_pagamento = st.selectbox("Condição de Pagamento Permitida", ["À Vista / Débito / Pix (Antecipado)"])
            else:
                forma_pagamento = st.selectbox("💳 Condição de Pagamento Solicitada", ["À Vista / Débito / Pix", "Boleto 7 dias", "Boleto 14 dias", "Boleto 21 dias", "Boleto 28 dias"])
                
                if subtipo_pj == "Empresa Padrão (LTDA/SA)":
                    st.info("📄 **Checklist Documental:**\n- Contrato Social Atualizado\n- CNH do solicitante")
                    referencias = st.text_area("📞 Feedback de Referências Comerciais", placeholder="Descreva o retorno das referências...")
                elif subtipo_pj in ["Condomínio", "MEI"]:
                    st.warning(f"📄 **Checklist Documental ({subtipo_pj}):**\n- Ata de eleição / Certificado MEI\n- CNH + Comprovante de Residência\n⚠️ **Limite:** Máximo 7 dias no boleto.")
                    if "Boleto" in forma_pagamento: referencias = st.text_area("📞 Referências Comerciais")

    with st.container(border=True):
        st.markdown("#### 2️⃣ Equipamento(s) Solicitado(s)")
        equipamentos_selecionados = st.multiselect("🔍 Selecione os equipamentos para a locação:", lista_opcoes_equipamentos)
        
        valor_total_reposicao = 0.0
        lista_nomes_finais = []
        
        # TRATAMENTO PARA OUTRO EQUIPAMENTO MANUAL
        if OPCAO_OUTRO_EQUIP in equipamentos_selecionados:
            st.markdown("---")
            st.markdown("##### ➕ Dados do Equipamento Manual (Não encontrado no catálogo)")
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                nome_manual = st.text_input("Nome do Equipamento Manual", value="EQUIPAMENTO ESPECIAL")
            with col_m2:
                valor_manual = st.number_input("Valor de Reposição Estimado (R$)", value=3000.0, step=500.0)
            
            for eq in equipamentos_selecionados:
                if eq == OPCAO_OUTRO_EQUIP:
                    valor_total_reposicao += valor_manual
                    lista_nomes_finais.append(f"{nome_manual.strip()} (Manual - R$ {valor_manual:,.2f})")
                else:
                    valor_total_reposicao += CATALOGO_EQUIPAMENTOS[eq]
                    lista_nomes_finais.append(eq)
        else:
            for eq in equipamentos_selecionados:
                valor_total_reposicao += CATALOGO_EQUIPAMENTOS[eq]
                lista_nomes_finais.append(eq)

        if equipamentos_selecionados:
            col_eq1, col_eq2 = st.columns(2)
            with col_eq1:
                st.success(f"📦 **Itens Selecionados:** {len(equipamentos_selecionados)}")
            with col_eq2:
                st.success(f"💵 **Valor Total de Reposição:** R$ {valor_total_reposicao:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))

    with st.container(border=True):
        st.markdown("#### 📎 3️⃣ Documentação do Cliente (Upload)")
        documentos = st.file_uploader("Arraste PDFs ou fotos (CNH, Comprovante de Residência/CELESC, Contrato, Serasa)", accept_multiple_files=True)

    st.write("<br>", unsafe_allow_html=True)
    if st.button("🚀 INICIAR ANÁLISE DE RISCO E SINERGIA", type="primary", use_container_width=True):
        doc_limpo = re.sub(r'\D', '', doc_cliente)
        df_black = carregar_blacklist()
        
        black_match = df_black[df_black['Documento'].str.replace(r'\D', '', regex=True) == doc_limpo] if doc_limpo and not df_black.empty else pd.DataFrame()
        
        if not nome_cliente or not doc_cliente or not equipamentos_selecionados or not documentos:
            st.error("⚠️ Preencha Nome, CPF/CNPJ, Selecione ao menos 1 Equipamento e anexe os Documentos.")
        elif not black_match.empty:
            motivo = black_match.iloc[0]['Motivo_Alerta']
            origem = black_match.iloc[0]['Cadastrado_Por']
            st.error(f"🚨 **BLOQUEIO IMEDIATO DE SEGURANÇA (BLACK LIST DA REDE)!**\n\nEste documento **({doc_cliente})** está na lista negra da Casa do Construtor.\n\n**Motivo:** {motivo}\n**Registrado por:** {origem}")
            salvar_no_historico(loja, usr_info['nome'], nome_cliente, doc_cliente, tipo_cliente, ", ".join(lista_nomes_finais), valor_total_reposicao, forma_pagamento, f"🔴 REPROVADO - BLACKLIST: {motivo}")
        elif not token_acesso_valido or not gcp_project_id:
            st.error("❌ Erro de Autenticação na Nuvem. Verifique o painel lateral.")
        else:
            with st.spinner('A IA (Gemini 2.5 Flash) está processando os documentos e analisando a operação...'):
                try:
                    payload_parts = []
                    data_hoje = datetime.now().strftime("%Y-%m-%d")
                    
                    for doc in documentos:
                        file_bytes = doc.getvalue()
                        b64_data = base64.b64encode(file_bytes).decode("utf-8")
                        payload_parts.append({"inlineData": {"mimeType": doc.type, "data": b64_data}})

                        if GCS_BUCKET_NAME:
                            upload_to_gcs(f"analises/{data_hoje}/{doc_limpo}/{doc.name}", file_bytes, doc.type)

                    equipamentos_str = ", ".join(lista_nomes_finais)

                    prompt = f"""
                    Você é o Analista Master de Risco Financeiro, Fraude e Engenharia da Casa do Construtor.
                    
                    DADOS DA OPERAÇÃO:
                    - Cliente: {nome_cliente} (CPF/CNPJ: {doc_cliente})
                    - Natureza: {tipo_cliente} ({subtipo_pj if subtipo_pj else 'Pessoa Física'})
                    - Solicitante / Contato: {nome_solicitante} | {contato_solicitante}
                    - Equipamento(s): {equipamentos_str}
                    - Valor Total de Reposição Risco: R$ {valor_total_reposicao:,.2f}
                    - Condição Solicitada: {forma_pagamento}
                    - Feedback Referências: {referencias if referencias else 'Nenhuma informada'}
                    
                    DIRETRIZES TÉCNICAS E REGRAS INEGOCIÁVEIS:
                    1. DATA DE VENCIMENTO DE COMPROVANTES: Faturas de energia/água (ex: CELESC) ou serviços com data de vencimento em MÊS FUTURO mas emitidas recentemente SÃO TOTALMENTE VÁLIDAS. NÃO classifique como documento vencido ou fraude faturas que vencerão no próximo mês!
                    
                    2. ANÁLISE DE SINERGIA DAS 14 FASES DA OBRA (CASA DO CONSTRUTOR):
                       Verifique se os equipamentos solicitados fazem sentido na mesma fase de trabalho:
                       - Fases: 1.Canteiro | 2.Fundação | 3.Demolição | 4.Estrutura | 5.Alvenaria | 6.Cobertura | 7.Inst.Hidráulica | 8.Inst.Elétrica | 9.Piso Concreto | 10.Esquadrias | 11.Acabamento | 12.Pintura | 13.Jardinagem | 14.Limpeza.
                       - ALERTA DE SINERGIA: Se o cliente pedir itens completamente desconexos sem explicação plausível (Ex: Betoneira + Riscadeira + Aspirador na mesma locação para PF), ALERTE SOBRE ALTO RISCO DE ESTELIONATO/LARANJA.
                    
                    3. REGRAS DE CRÉDITO:
                       - Pessoa Física (PF): Somente pagamento À vista.
                       - MEI e Condomínio: Boleto máximo 7 dias.
                       - Empresa < 1 ano: Boleto máximo 7 dias. Restrição no Serasa no setor da construção = REPROVADO.
                    
                    4. CHECAGEM DE SEGURANÇA PJ:
                       - Para PJ APROVADA: Exigir expressamente no parecer que o vendedor LIGUE PARA O NÚMERO FIXO DA EMPRESA REGISTRADO NO GOOGLE / CARTÃO CNPJ ou exija Ordem de Compra (PO) oriunda de e-mail corporativo.

                    FORMATO DA RESPOSTA (Use marcadores visuais e títulos grandes #):
                    
                    Substitua o início com uma das opções exatas:
                    # 🟢 APROVADO
                    # 🟡 APROVADO COM RESTRIÇÃO
                    # 🔴 REPROVADO
                    
                    **Resumo da Decisão:** (Motivo direto e claro)
                    
                    **Justificativa Técnica e Documental:** (Detalhe análise de CPF/CNPJ, comprovantes e dívidas)
                    
                    **Análise de Sinergia dos Equipamentos:** (Comente a coerência com a fase da obra)
                    
                    **⚠️ Alerta de Segurança e Validação Antifraude:** (Orientações obrigatórias para a entrega no balcão)
                    """
                    payload_parts.append({"text": prompt})

                    url_api = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{gcp_project_id}/locations/us-central1/publishers/google/models/gemini-2.5-flash:generateContent"
                    headers_api = {"Content-Type": "application/json", "Authorization": f"Bearer {token_acesso_valido}"}
                    data_api = {"contents": [{"role": "user", "parts": payload_parts}], "generationConfig": {"temperature": 0.1}}

                    res = requests.post(url_api, json=data_api, headers=headers_api)

                    if res.status_code == 200:
                        texto_resultado = res.json()['candidates'][0]['content']['parts'][0]['text']
                        st.session_state['resultado_parecer'] = texto_resultado
                        
                        pdf_bytes = gerar_pdf_parecer(nome_cliente, doc_cliente, tipo_cliente, forma_pagamento, loja, equipamentos_str, valor_total_reposicao, texto_resultado)
                        st.session_state['pdf_bytes'] = pdf_bytes
                        
                        if GCS_BUCKET_NAME:
                            upload_to_gcs(f"analises/{data_hoje}/{doc_limpo}/Parecer_CDC.pdf", pdf_bytes, "application/pdf")
                            
                        salvar_no_historico(loja, usr_info['nome'], nome_cliente, doc_cliente, tipo_cliente, equipamentos_str, valor_total_reposicao, forma_pagamento, texto_resultado)
                    else:
                        st.error(f"❌ Erro na API (Código {res.status_code}): {res.text}")

                except Exception as e:
                    st.error(f"Erro na execução da requisição: {e}")

    # EXIBIÇÃO DO PARECER FORMATADO
    if 'resultado_parecer' in st.session_state and st.session_state['resultado_parecer']:
        st.success("✅ Avaliação Finalizada!")
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown(st.session_state['resultado_parecer'], unsafe_allow_html=True)
        st.markdown("<hr>", unsafe_allow_html=True)
        
        if 'pdf_bytes' in st.session_state and st.session_state['pdf_bytes']:
            st.download_button(
                "📄 Baixar Relatório PDF do Parecer", 
                data=st.session_state['pdf_bytes'], 
                file_name=f"Parecer_CDC_{doc_cliente if doc_cliente else 'Analise'}.pdf", 
                mime="application/pdf", 
                type="primary"
            )

# --- ABA 2: BLACKLIST DA REDE ---
if eh_master and aba_black:
    with aba_black:
        st.markdown("### 🚨 Cadastro de Documentos Suspeitos (Blacklist da Rede)")
        st.caption("Cadastre CPFs/CNPJs para bloquear instantaneamente em todas as 12 lojas.")
        
        with st.container(border=True):
            st.markdown("#### ➕ Incluir Novo Suspeito")
            col_b1, col_b2, col_b3 = st.columns([1.5, 2, 2])
            with col_b1: doc_block = st.text_input("CPF ou CNPJ Suspeito")
            with col_b2: nome_block = st.text_input("Nome / Razão Social do Suspeito")
            with col_b3: motivo_block = st.text_input("Motivo do Alerta (Ex: Golpe em locadoras)")
            
            if st.button("🚨 Cadastrar na Lista Negra", type="primary"):
                if not doc_block or not motivo_block:
                    st.error("⚠️ Preencha o CPF/CNPJ e o Motivo do alerta.")
                else:
                    dt_hoje = datetime.now().strftime("%d/%m/%Y")
                    df_b = carregar_blacklist()
                    
                    sucesso_b_sheet, msg_b = append_google_sheet("Blacklist", [doc_block.strip(), nome_block.strip(), motivo_block.strip(), dt_hoje, usr_info['nome']])
                    if SPREADSHEET_ID and not sucesso_b_sheet:
                        st.warning(f"⚠️ **Aviso Sheets:** Não foi possível salvar na aba 'Blacklist' da planilha ({msg_b}).")

                    novo_suspeito = pd.DataFrame([{
                        "Documento": doc_block.strip(), "Nome_Razao": nome_block.strip(),
                        "Motivo_Alerta": motivo_block.strip(), "Data_Inclusao": dt_hoje,
                        "Cadastrado_Por": usr_info['nome']
                    }])
                    df_b = pd.concat([df_b, novo_suspeito], ignore_index=True)
                    salvar_blacklist_local(df_b)
                    st.success(f"✅ Documento {doc_block} adicionado à Blacklist!")
                    st.rerun()

        st.markdown("---")
        st.markdown("#### 📋 Suspeitos Cadastrados na Rede")
        df_black_atual = carregar_blacklist()
        if not df_black_atual.empty:
            st.dataframe(df_black_atual, use_container_width=True)
        else:
            st.info("Nenhum documento cadastrado na Blacklist até o momento.")

# --- ABA 3: DASHBOARD GERENCIAL ---
if eh_master and aba_dash:
    with aba_dash:
        st.markdown("### 📊 Visão Geral e Indicadores da Rede")
        
        df_hist = read_google_sheet("Historico")
        if df_hist is None and os.path.exists(ARQUIVO_HISTORICO):
            df_hist = pd.read_csv(ARQUIVO_HISTORICO, sep=";")
            
        if df_hist is not None and not df_hist.empty:
            lojas_disponiveis = ["Todas as Lojas"] + sorted(list(df_hist['Filial'].dropna().unique()))
            filtro_loja = st.selectbox("🎯 Filtrar Unidade:", lojas_disponiveis)
            
            if filtro_loja != "Todas as Lojas":
                df_hist = df_hist[df_hist['Filial'] == filtro_loja]
                
            total_analises = len(df_hist)
            aprovados = len(df_hist[df_hist['Status Decisão'] == 'APROVADO'])
            reprovados = len(df_hist[df_hist['Status Decisão'] == 'REPROVADO'])
            restritos = len(df_hist[df_hist['Status Decisão'] == 'APROVADO COM RESTRIÇÃO'])
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("📌 Total de Cadastros", total_analises)
            col2.metric("✅ Aprovados", aprovados)
            col3.metric("🔴 Negados", reprovados)
            col4.metric("🟡 Com Restrição", restritos)
            
            st.markdown("---")
            st.markdown("#### Volume de Análises por Data")
            if 'Data_Dia' in df_hist.columns:
                st.bar_chart(df_hist['Data_Dia'].value_counts().sort_index())
        else:
            st.info("Aguardando primeiras análises para montar o Dashboard...")

# --- ABA 4: HISTÓRICO GERAL ---
with aba_hist:
    st.markdown("### 📋 Registro Geral de Auditoria")
    df_hist_all = read_google_sheet("Historico")
    if df_hist_all is None and os.path.exists(ARQUIVO_HISTORICO):
        df_hist_all = pd.read_csv(ARQUIVO_HISTORICO, sep=";")
        
    if df_hist_all is not None and not df_hist_all.empty:
        if not eh_master:
            df_hist_all = df_hist_all[df_hist_all['Filial'] == usr_info['filial']]
        st.dataframe(df_hist_all, use_container_width=True)
        if eh_master:
            st.download_button("📊 Exportar Dados (CSV)", df_hist_all.to_csv(index=False, sep=";").encode('utf-8-sig'), "Auditoria_Risco_CDC.csv", "text/csv")
    else:
        st.info("Nenhum registro encontrado no histórico.")
