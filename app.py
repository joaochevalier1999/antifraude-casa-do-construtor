import streamlit as st
import base64
import io
import html
import re
import os
import csv
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

from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Portal Antifraude & Crédito - Casa do Construtor",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização CSS Profissional
st.markdown("""
    <style>
    .stApp { background-color: #F8FAFC !important; color: #0F172A !important; }
    p, span, label, h1, h2, h3, h4, h5, h6, div, .stMarkdown { color: #0F172A !important; }
    div.stButton > button[kind="primary"] { 
        background-color: #003366 !important; color: #FFFFFF !important; 
        border-radius: 8px !important; border: 2px solid #003366 !important; 
        padding: 12px 24px !important; font-weight: bold !important; font-size: 16px !important;
        transition: all 0.3s !important; 
    }
    div.stButton > button[kind="primary"]:hover { 
        background-color: #FBC02D !important; color: #003366 !important; border: 2px solid #FBC02D !important; 
    }
    div[data-testid="stVerticalBlock"] > div[style*="border"] { 
        border-radius: 12px !important; background-color: #FFFFFF !important; 
        box-shadow: 0px 4px 12px rgba(0, 0, 0, 0.06) !important; border: 1px solid #CBD5E1 !important; padding: 22px !important; 
    }
    div[data-baseweb="select"] > div, div[data-baseweb="input"] > div, input, textarea {
        background-color: #FFFFFF !important; color: #0F172A !important;
        border: 1px solid #94A3B8 !important; border-radius: 6px !important;
    }
    div[data-baseweb="menu"] * { background-color: #FFFFFF !important; color: #0F172A !important; }
    div[role="radiogroup"] label p { color: #0F172A !important; font-weight: 600 !important; }
    button[data-baseweb="tab"] p, button[data-baseweb="tab"] div { color: #0F172A !important; font-weight: bold !important; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- USUÁRIOS ---
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

# --- AUTENTICAÇÃO GOOGLE CLOUD ---
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
            'https://www.googleapis.com/auth/drive'
        ]
        credenciais = service_account.Credentials.from_service_account_info(creds_json, scopes=escopos)
        req_auth = GoogleAuthRequest()
        credenciais.refresh(req_auth)
        token_acesso_valido = credenciais.token
    except Exception as e:
        erro_auth = f"Erro ao processar o JSON: {e}"

SPREADSHEET_ID = st.secrets.get("SPREADSHEET_ID", None)
DRIVE_FOLDER_ID = st.secrets.get("DRIVE_FOLDER_ID", None)
ARQUIVO_HISTORICO = "historico_analises.csv"
ARQUIVO_BLACKLIST = "blacklist_rede.csv"

# --- MÓDULOS DE INTEGRAÇÃO GOOGLE ---
def upload_para_google_drive(nome_arquivo, file_bytes, mime_type):
    if not DRIVE_FOLDER_ID or not token_acesso_valido:
        return False, "ID da pasta do Drive ou Token GCP não configurado."
    try:
        url = "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&supportsAllDrives=true"
        headers = {"Authorization": f"Bearer {token_acesso_valido}"}
        metadata = {"name": nome_arquivo, "parents": [DRIVE_FOLDER_ID.strip()]}
        files = {
            'data': ('metadata', json.dumps(metadata), 'application/json; charset=UTF-8'),
            'file': (nome_arquivo, file_bytes, mime_type)
        }
        res = requests.post(url, headers=headers, files=files)
        if res.status_code == 200:
            return True, "Enviado com sucesso."
        else:
            return False, f"Erro HTTP {res.status_code}: {res.text}"
    except Exception as e:
        return False, str(e)

def append_google_sheet(tab_name, row_values):
    if not SPREADSHEET_ID or not token_acesso_valido:
        return False, "ID da Planilha não configurado."
    try:
        tab_encoded = urllib.parse.quote(tab_name)
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/{tab_encoded}!A1:append?valueInputOption=USER_ENTERED"
        headers = {"Authorization": f"Bearer {token_acesso_valido}", "Content-Type": "application/json"}
        body = {"values": [row_values]}
        res = requests.post(url, headers=headers, json=body)
        return res.status_code == 200, res.text
    except Exception as e:
        return False, str(e)

def read_google_sheet(tab_name):
    if not SPREADSHEET_ID or not token_acesso_valido:
        return None
    try:
        tab_encoded = urllib.parse.quote(tab_name)
        url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/{tab_encoded}!A1:Z"
        headers = {"Authorization": f"Bearer {token_acesso_valido}"}
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            vals = res.json().get("values", [])
            if len(vals) > 1:
                header_idx = 0
                for i, r in enumerate(vals[:5]):
                    r_str = [str(x).upper() for x in r]
                    if any(k in r_str for k in ["CLIENTE", "CPF_CNPJ", "FILIAL", "DATA/HORA"]):
                        header_idx = i
                        break
                cols = [str(c).strip() for c in vals[header_idx]]
                num_cols = len(cols)
                rows_padded = []
                for r in vals[header_idx+1:]:
                    if not any(r): continue
                    padded = r + [''] * (num_cols - len(r)) if len(r) < num_cols else r[:num_cols]
                    rows_padded.append(padded)
                return pd.DataFrame(rows_padded, columns=cols)
    except Exception:
        pass
    return None

def obter_historico_completo():
    dfs = []
    df_sheets = read_google_sheet("Historico")
    if df_sheets is not None and not df_sheets.empty:
        dfs.append(df_sheets)
        
    if os.path.exists(ARQUIVO_HISTORICO):
        try:
            df_csv = pd.read_csv(ARQUIVO_HISTORICO, sep=";", on_bad_lines='skip', engine='python', dtype=str)
            if df_csv is not None and not df_csv.empty:
                dfs.append(df_csv)
        except Exception:
            pass
            
    if not dfs:
        return None
        
    df_total = pd.concat(dfs, ignore_index=True)
    column_mapping = {
        'CPF/CNPJ': 'CPF_CNPJ', 'CPF': 'CPF_CNPJ', 'CNPJ': 'CPF_CNPJ',
        'Status': 'Status Decisão', 'Status Decisao': 'Status Decisão',
        'Data': 'Data_Dia', 'Data Hora': 'Data/Hora', 'Data/Hora ': 'Data/Hora'
    }
    df_total.rename(columns=lambda x: column_mapping.get(str(x).strip(), str(x).strip()), inplace=True)
    df_total = df_total.loc[:, ~df_total.columns.str.contains('^Unnamed')]
    
    for col in df_total.columns:
        df_total[col] = df_total[col].astype(str).str.strip()
        
    subset_cols = [c for c in ['Data/Hora', 'CPF_CNPJ'] if c in df_total.columns]
    if subset_cols: df_total.drop_duplicates(subset=subset_cols, keep='first', inplace=True)
    else: df_total.drop_duplicates(inplace=True)
        
    return df_total

def atualizar_status_google_sheet(cpf_cnpj, novo_status, parecer_master):
    doc_busca = str(cpf_cnpj).strip()
    
    if os.path.exists(ARQUIVO_HISTORICO):
        try:
            df_local = pd.read_csv(ARQUIVO_HISTORICO, sep=";", on_bad_lines='skip', engine='python')
            if 'CPF_CNPJ' in df_local.columns:
                df_local['CPF_CNPJ'] = df_local['CPF_CNPJ'].astype(str).str.strip()
                mask = df_local['CPF_CNPJ'] == doc_busca
                if mask.any():
                    df_local.loc[mask, 'Status Decisão'] = novo_status
                    df_local.to_csv(ARQUIVO_HISTORICO, index=False, sep=";", encoding="utf-8-sig", quoting=csv.QUOTE_ALL)
        except Exception:
            pass

    if SPREADSHEET_ID and token_acesso_valido:
        try:
            df_sheets = read_google_sheet("Historico")
            if df_sheets is not None and not df_sheets.empty and 'CPF_CNPJ' in df_sheets.columns:
                df_sheets['CPF_CNPJ'] = df_sheets['CPF_CNPJ'].astype(str).str.strip()
                matches = df_sheets.index[df_sheets['CPF_CNPJ'] == doc_busca].tolist()
                if matches:
                    row_idx = matches[-1] + 2
                    url = f"https://sheets.googleapis.com/v4/spreadsheets/{SPREADSHEET_ID}/values/Historico!K{row_idx}?valueInputOption=USER_ENTERED"
                    headers = {"Authorization": f"Bearer {token_acesso_valido}", "Content-Type": "application/json"}
                    body = {"values": [[novo_status]]}
                    requests.put(url, headers=headers, json=body)
        except Exception:
            pass

def carregar_blacklist():
    df_sheets = read_google_sheet("Blacklist")
    if df_sheets is not None and not df_sheets.empty: return df_sheets
    if os.path.exists(ARQUIVO_HISTORICO):
        try:
            return pd.read_csv(ARQUIVO_BLACKLIST, sep=";", dtype=str, on_bad_lines='skip', engine='python')
        except Exception:
            pass
    return pd.DataFrame(columns=["Documento", "Nome_Razao", "Motivo_Alerta", "Data_Inclusao", "Cadastrado_Por"])

def salvar_blacklist_local(df):
    df.to_csv(ARQUIVO_BLACKLIST, index=False, sep=";", encoding="utf-8-sig", quoting=csv.QUOTE_ALL)

def salvar_no_historico(filial, atendente, cliente, doc_cliente, tipo_pessoa, equipamentos_str, valor_total, prazo, parecer_texto):
    data_hora_dt = datetime.now()
    parecer_up = str(parecer_texto).upper()
    
    if "[APROVADO COM RESTRIÇÃO]" in parecer_up or "RESTRIÇÃO" in parecer_up or "🟡" in parecer_up:
        status = "APROVADO COM RESTRIÇÃO"
    elif "[APROVADO]" in parecer_up or "🟢 APROVADO" in parecer_up:
        status = "APROVADO"
    elif "[REPROVADO]" in parecer_up or "🔴 REPROVADO" in parecer_up or "NEGADO" in parecer_up:
        status = "⏳ PENDENTE DE REAVALIAÇÃO MASTER"
    else:
        status = "ANALISADO"

    row_data = [
        data_hora_dt.strftime("%d/%m/%Y %H:%M:%S"),
        data_hora_dt.strftime("%d/%m/%Y"),
        filial, atendente, cliente, doc_cliente, tipo_pessoa,
        equipamentos_str, f"R$ {valor_total:,.2f}", prazo, status, parecer_texto
    ]

    append_google_sheet("Historico", row_data)

    novo_registro = pd.DataFrame([{
        "Data/Hora": row_data[0], "Data_Dia": row_data[1], "Filial": row_data[2], "Atendente": row_data[3],
        "Cliente": row_data[4], "CPF_CNPJ": row_data[5], "Tipo_Pessoa": row_data[6], "Equipamentos": row_data[7],
        "Valor Reposição Total (R$)": row_data[8], "Prazo": row_data[9], "Status Decisão": row_data[10], "Parecer_IA": row_data[11]
    }])
    if not os.path.exists(ARQUIVO_HISTORICO): 
        novo_registro.to_csv(ARQUIVO_HISTORICO, index=False, sep=";", encoding="utf-8-sig", quoting=csv.QUOTE_ALL)
    else: 
        novo_registro.to_csv(ARQUIVO_HISTORICO, mode='a', header=False, index=False, sep=";", encoding="utf-8-sig", quoting=csv.QUOTE_ALL)

# --- GERADOR DE PDF ---
def formatar_texto_para_reportlab(texto): 
    t = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', html.escape(str(texto)))
    t = re.sub(r'^#+\s+(.*)', r'<b>\1</b>', t) 
    return t

def gerar_pdf_parecer(nome_cliente, doc_cliente, tipo_pessoa, prazo, loja, equipamentos_str, valor_total, texto_parecer, chancela_master=None):
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
        [Paragraph("<b>Cliente / CPF-CNPJ:</b>", body_style), Paragraph(f"{html.escape(str(nome_cliente))} ({doc_cliente}) - {tipo_pessoa}", body_style)],
        [Paragraph("<b>Prazo Solicitado:</b>", body_style), Paragraph(str(prazo), body_style)],
        [Paragraph("<b>Filial / Equipamentos:</b>", body_style), Paragraph(f"{html.escape(str(loja))}<br/><b>Itens:</b> {html.escape(str(equipamentos_str))}<br/><b>Total Reposição:</b> {val_f}", body_style)],
    ], colWidths=[140, 380])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F2F4F8')), ('GRID', (0, 0), (-1, -1), 0.5, colors.gray)]))
    story.append(t)
    story.append(Spacer(1, 12))

    if chancela_master:
        story.append(Paragraph(f"<b>👑 AVALIAÇÃO DE CRÉDITO MASTER:</b> {html.escape(chancela_master)}", ParagraphStyle('Master', parent=body_style, textColor=colors.HexColor('#003366'), fontSize=11, leading=15)))
        story.append(Spacer(1, 10))

    for linha in str(texto_parecer).split('\n'):
        if linha.strip(): story.append(Paragraph(formatar_texto_para_reportlab(linha.strip()), body_style))
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# --- CATÁLOGO DE EQUIPAMENTOS ---
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
    "ROMPEDOR 31.3KG": 11260.0, "SERRA MADEIRA BATERIA": 6800.0, "SERRA MARMORE 180mm": 3070.0, "SERRA SABRE 18V BATERIA": 12000.0,
    "SERRA TICO-TICO": 980.0, "SOLDA ELETRICA": 2907.03, "SOPRADOR GASOLINA": 2010.0, "SOPRADOR TERMICO": 850.0,
    "TALHA ATE 03 TON": 800.0, "TRANSFORMADOR 7000W BIVOLT": 700.0, "TRANSPALET MANUAL ATE 02 TON": 2000.0,
    "TUPIA": 882.0, "VARREDEIRA MANUAL": 961.31, "VIBRADOR AF 35mm": 3000.0
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
    if token_acesso_valido and gcp_project_id: st.success(f"🟢 Nuvem Conectada!\n`{gcp_project_id}`")
    else: st.error("🔴 JSON GCP ausente nos Secrets.")
    if SPREADSHEET_ID: st.success("🟢 Google Sheets Ativo")
    if DRIVE_FOLDER_ID: st.success("🟢 Google Drive Restrito Ativo")

    st.markdown("---")
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state["logged_in"] = False
        st.rerun()

# ÁREA CENTRAL
st.title("🛡️ Central de Risco e Crédito")
st.caption("Validação inteligente de cadastros, esteira de crédito e reavaliação de risco.")

# NAVEGAÇÃO DE ABAS
if eh_master:
    aba_nova, aba_reaval, aba_black, aba_dash, aba_hist = st.tabs(["🚀 Nova Análise", "⚖️ Reavaliação Master", "🚨 Blacklist / Suspeitos", "📊 Dashboard Gerencial", "📋 Histórico Geral"])
else:
    aba_nova, aba_hist = st.tabs(["🚀 Nova Análise", "📋 Meu Histórico"])
    aba_reaval, aba_black, aba_dash = None, None, None

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
                st.warning("⚠️ **Regra de Crédito PF:** Pagamento faturado a prazo NÃO PERMITIDO. Somente Pagamento Antecipado.")
                forma_pagamento = st.selectbox("Condição de Pagamento Permitida", ["À Vista / Débito / Pix (Antecipado)"])
            else:
                forma_pagamento = st.selectbox("💳 Condição de Pagamento Solicitada", ["À Vista / Débito / Pix", "Boleto 7 dias", "Boleto 14 dias", "Boleto 21 dias", "Boleto 28 dias"])
                if subtipo_pj == "Empresa Padrão (LTDA/SA)":
                    st.info("📄 **Checklist Documental PJ:**\n- Contrato Social / Requerimento Empresarial\n- CNH do Solicitante com vínculo verificado")
                    referencias = st.text_area("📞 Feedback de Referências Comerciais", placeholder="Descreva os fornecedores consultados...")
                elif subtipo_pj in ["Condomínio", "MEI"]:
                    st.warning(f"📄 **Checklist Documental ({subtipo_pj}):**\n- Ata de eleição / Certificado MEI\n- CNH + Comprovante de Residência\n⚠️ **Limite:** Faturamento máximo de 7 dias.")

    with st.container(border=True):
        st.markdown("#### 2️⃣ Equipamento(s) Solicitado(s)")
        equipamentos_selecionados = st.multiselect("🔍 Selecione os equipamentos para a locação:", lista_opcoes_equipamentos)
        
        valor_total_reposicao = 0.0
        lista_nomes_finais = []
        
        if OPCAO_OUTRO_EQUIP in equipamentos_selecionados:
            st.markdown("---")
            st.markdown("##### ➕ Dados do Equipamento Manual")
            col_m1, col_m2 = st.columns(2)
            with col_m1: nome_manual = st.text_input("Nome do Equipamento Manual", value="EQUIPAMENTO ESPECIAL")
            with col_m2: valor_manual = st.number_input("Valor de Reposição Estimado (R$)", value=3000.0, step=500.0)
            
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
            with col_eq1: st.success(f"📦 **Itens Selecionados:** {len(equipamentos_selecionados)}")
            with col_eq2: st.success(f"💵 **Valor Total de Reposição:** R$ {valor_total_reposicao:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))

    with st.container(border=True):
        st.markdown("#### 📎 3️⃣ Documentação do Cliente (Upload)")
        documentos = st.file_uploader("Arraste PDFs ou fotos (CNH, Comprovante de Residência/CELESC, Contrato, Serasa/SPC)", accept_multiple_files=True)

    st.write("<br>", unsafe_allow_html=True)
    if st.button("🚀 INICIAR ANÁLISE DE RISCO E ESTEIRA DE CRÉDITO", type="primary", use_container_width=True):
        doc_limpo = re.sub(r'\D', '', doc_cliente)
        df_black = carregar_blacklist()
        black_match = df_black[df_black['Documento'].str.replace(r'\D', '', regex=True) == doc_limpo] if doc_limpo and not df_black.empty else pd.DataFrame()
        
        if not nome_cliente or not doc_cliente or not equipamentos_selecionados or not documentos:
            st.error("⚠️ Preencha Nome, CPF/CNPJ, Selecione ao menos 1 Equipamento e anexe os Documentos.")
        elif not black_match.empty:
            motivo = black_match.iloc[0]['Motivo_Alerta']
            origem = black_match.iloc[0]['Cadastrado_Por']
            st.error(f"🚨 **BLOQUEIO IMEDIATO DE SEGURANÇA (BLACK LIST DA REDE)!**\n\nEste documento **({doc_cliente})** consta na Lista Negra.\n\n**Motivo:** {motivo}\n**Registrado por:** {origem}")
            salvar_no_historico(loja, usr_info['nome'], nome_cliente, doc_cliente, tipo_cliente, ", ".join(lista_nomes_finais), valor_total_reposicao, forma_pagamento, f"🔴 REPROVADO - BLACKLIST: {motivo}")
        elif not token_acesso_valido or not gcp_project_id:
            st.error("❌ Erro de Autenticação na Nuvem. Verifique o painel lateral.")
        else:
            with st.spinner('A IA (Gemini 2.5 Flash) está analisando a documentação e registrando a operação...'):
                try:
                    payload_parts = []
                    data_hoje = datetime.now().strftime("%d/%m/%Y")
                    mes_atual = datetime.now().strftime("%B %Y")
                    
                    for doc in documentos:
                        file_bytes = doc.getvalue()
                        b64_data = base64.b64encode(file_bytes).decode("utf-8")
                        payload_parts.append({"inlineData": {"mimeType": doc.type, "data": b64_data}})

                        if DRIVE_FOLDER_ID:
                            sucesso_d, msg_d = upload_para_google_drive(f"{data_hoje.replace('/','-')}_{doc_limpo}_{doc.name}", file_bytes, doc.type)
                            if not sucesso_d:
                                st.warning(f"⚠️ **Aviso de Upload Drive no arquivo ({doc.name}):** {msg_d}")

                    equipamentos_str = ", ".join(lista_nomes_finais)

                    # PROMPT ENGINE 2.0 - MENTE DO ANALISTA IMPLACÁVEL
                    prompt = f"""
                    Você é um Analista Sênior de Crédito e Antifraude extremamente rigoroso da Casa do Construtor.
                    Sua missão é analisar os documentos anexados e emitir um parecer preciso, equilibrando segurança corporativa e aprovação comercial.
                    DATA DE HOJE PARA REFERÊNCIA DE VALIDADE: {data_hoje} ({mes_atual})

                    DADOS DA OPERAÇÃO:
                    - Cliente: {nome_cliente} (CPF/CNPJ: {doc_cliente})
                    - Natureza: {tipo_cliente} ({subtipo_pj if subtipo_pj else 'Pessoa Física'})
                    - Solicitante / Contato: {nome_solicitante} | {contato_solicitante}
                    - Equipamento(s): {equipamentos_str}
                    - Valor Total de Reposição Risco: R$ {valor_total_reposicao:,.2f}
                    - Condição Solicitada: {forma_pagamento}
                    
                    REGRA 0: DOCUMENTAÇÃO OBRIGATÓRIA (FALHA AUTOMÁTICA)
                    - Você DEVE obrigatoriamente verificar as imagens/PDFs anexados.
                    - Se o usuário enviou APENAS relatórios do Serasa/SPC/Consult Center e NÃO há nenhuma foto de Documento de Identidade (CNH ou RG com CPF) E nenhum Comprovante de Residência -> O PARECER DEVE SER IMEDIATAMENTE "🔴 REPROVADO". Motivo: Documentação incompleta (falta CNH e Comprovante). Não invente dados nem aprove sem ver a foto real do documento.

                    REGRA 1: VALIDAÇÃO DO COMPROVANTE DE RESIDÊNCIA (PF)
                    - O comprovante de residência deve ter no MÁXIMO 3 meses de emissão em relação a hoje ({mes_atual}). Faturas a vencer no próximo mês ou emitidas recentemente são 100% VÁLIDAS.
                    - Faturas de Cartão de Crédito são aceitas (respeitando a regra dos 3 meses).
                    - Titularidade: O comprovante deve estar no nome exato do cliente. EXCEÇÃO: Para equipamentos de baixo valor de risco, aceita-se no nome do Pai ou da Mãe (você deve conferir a filiação no RG/CNH anexado).
                    - Contratos de Locação (Aluguel): SÓ SÃO VÁLIDOS se estiverem registrados em cartório, com data atual, E acompanhados de uma conta de consumo no nome do proprietário do imóvel (locador).

                    REGRA 2: ANÁLISE DE RESTRIÇÕES E CRÉDITO (SPC/SERASA)
                    - O cliente NÃO precisa ter nome 100% limpo. Você deve analisar a ORIGEM da dívida.
                    - Restrições TOLERADAS (Aprove): Financiamento de Bancos Comerciais, Lojas de Varejo (ex: Havan, Renner), Telecomunicações (Claro, Vivo, Tim, Oi), Contas de consumo básicas atrasadas.
                    - Restrições GRAVES (Reprove imediatamente para faturamento): Dívidas com lojas de Materiais de Construção, Locadoras de Equipamentos, Dívidas de Aluguel/Imobiliárias, Cheques sem fundo repetitivos, ou Estelionato. Sinergia negativa com o nosso setor de atuação = Risco Alto.

                    REGRA 3: PRAZOS E CONDIÇÕES DE PAGAMENTO (INEGOCIÁVEL)
                    - Pessoa Física (PF): Pagamento EXCLUSIVAMENTE À Vista / PIX Antecipado. Boleto NUNCA é permitido para PF.
                    - Empresa (PJ) < 1 ano de abertura: Boleto no máximo 7 dias.
                    - MEI e Condomínio: Boleto no máximo 7 dias.
                    - Empresa Padrão (LTDA/SA) > 1 ano de abertura (sem restrições graves no setor): Pode aprovar para os prazos solicitados (7, 14, 21 ou 28 dias).

                    REGRA 4: DOCUMENTAÇÃO PJ
                    - Contratos Sociais e Requerimentos de Empresário NÃO possuem data de validade (são históricos).

                    REGRA 5: SINERGIA DAS 14 FASES DA OBRA E RISCO DE "LARANJA"
                    - Fases: 1.Canteiro | 2.Fundação | 3.Demolição | 4.Estrutura | 5.Alvenaria | 6.Cobertura | 7.Inst.Hidráulica | 8.Inst.Elétrica | 9.Piso Concreto | 10.Esquadrias | 11.Acabamento | 12.Pintura | 13.Jardinagem | 14.Limpeza.
                    - Analise os itens do pedido: {equipamentos_str}. Fazem sentido juntos na mesma fase da obra? 
                    - Pedidos completamente desconexos feitos por Pessoa Física (Ex: Betoneira + Aspirador + Furadeira Magnética) sugerem altíssimo risco de que o cliente seja um "Laranja" alugando para terceiros. Alerte o balcão.

                    FORMATO DA RESPOSTA OBRIGATÓRIO (Use títulos grandes com #):
                    Substitua o início com uma das opções exatas:
                    # 🟢 APROVADO
                    # 🟡 APROVADO COM RESTRIÇÃO
                    # 🔴 REPROVADO
                    
                    **Resumo da Decisão:** (Motivo direto e claro, citando se faltou documento ou qual foi a trava)
                    
                    **Auditoria Documental:** (Detalhe explicitamente se a foto da CNH estava legível, se o comprovante estava no nome correto, validade de 3 meses, etc.)
                    
                    **Análise de Restrições (Serasa/SPC):** (Quais dívidas o cliente possui? A dívida foi tolerada ou pertence ao setor de risco como material de construção?)
                    
                    **Análise de Sinergia dos Equipamentos:** (Comente se os equipamentos pertencem à mesma fase da obra)
                    
                    **⚠️ Alertas e Travas para o Balcão:** (Instruções rigorosas para o vendedor na hora da entrega)
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
                        
                        if DRIVE_FOLDER_ID:
                            upload_para_google_drive(f"PARECER_{data_hoje.replace('/','-')}_{doc_limpo}.pdf", pdf_bytes, "application/pdf")
                            
                        salvar_no_historico(loja, usr_info['nome'], nome_cliente, doc_cliente, tipo_cliente, equipamentos_str, valor_total_reposicao, forma_pagamento, texto_resultado)
                    else:
                        st.error(f"❌ Erro na API (Código {res.status_code}): {res.text}")

                except Exception as e:
                    st.error(f"Erro na execução da requisição: {e}")

    if 'resultado_parecer' in st.session_state and st.session_state['resultado_parecer']:
        st.success("✅ Avaliação Processada!")
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

# --- ABA 2: REAVALIAÇÃO MASTER ---
if eh_master and aba_reaval:
    with aba_reaval:
        st.markdown("### ⚖️ Painel de Reavaliação de Crédito (Master)")
        st.caption("Cadastros retidos pela IA para reavaliação da diretoria antes da decisão final.")
        
        df_hist_reaval = obter_historico_completo()

        if df_hist_reaval is not None and not df_hist_reaval.empty and 'Status Decisão' in df_hist_reaval.columns:
            pendentes = df_hist_reaval[df_hist_reaval['Status Decisão'].astype(str).str.contains("PENDENTE|REPROVADO", na=False, case=False)]
            
            if not pendentes.empty:
                st.warning(f"📌 **{len(pendentes)} Cadastros Aguardando Sua Decisão Final**")
                
                opcoes_pendentes = []
                for _, row in pendentes.iterrows():
                    row_dict = row.to_dict()
                    cli = row_dict.get('Cliente', 'Sem Nome')
                    doc = row_dict.get('CPF_CNPJ', 'N/A')
                    fil = row_dict.get('Filial', 'N/A')
                    opcoes_pendentes.append(f"{cli} | CPF-CNPJ: {doc} | Filial: {fil}")
                
                sel_cadastro = st.selectbox("🔍 Selecione o cadastro para reavaliar:", opcoes_pendentes)
                
                if sel_cadastro:
                    idx_sel = opcoes_pendentes.index(sel_cadastro)
                    dados_cliente = pendentes.iloc[idx_sel].to_dict()
                    
                    with st.container(border=True):
                        col_r1, col_r2 = st.columns(2)
                        with col_r1:
                            st.markdown(f"**👤 Cliente:** {dados_cliente.get('Cliente', 'N/A')}")
                            st.markdown(f"**📄 Documento:** {dados_cliente.get('CPF_CNPJ', 'N/A')}")
                            st.markdown(f"**🏢 Filial:** {dados_cliente.get('Filial', 'N/A')}")
                            st.markdown(f"**👤 Atendente:** {dados_cliente.get('Atendente', 'N/A')}")
                        with col_r2:
                            st.markdown(f"**📦 Equipamento(s):** {dados_cliente.get('Equipamentos', 'N/A')}")
                            st.markdown(f"**💵 Reposição Total:** {dados_cliente.get('Valor Reposição Total (R$)', 'N/A')}")
                            st.markdown(f"**💳 Prazo Solicitado:** {dados_cliente.get('Prazo', 'N/A')}")

                        if dados_cliente.get('Parecer_IA'):
                            with st.expander("🔍 Ver Justificativa Inicial da IA"):
                                st.markdown(dados_cliente['Parecer_IA'])

                        st.markdown("---")
                        st.markdown("#### ✍️ Decisão do Gestor Master")
                        
                        nova_decisao = st.radio("Selecione o Status Definitivo:", [
                            "🟢 APROVADO (Pelo Gestor Master)",
                            "🟡 APROVADO COM RESTRIÇÃO (Pelo Gestor Master)",
                            "🔴 MANTIDO REPROVADO"
                        ], horizontal=True)
                        
                        justificativa_master = st.text_area("Justificativa Comercial do Master (Ex: Cliente antigo / Garantia negociada):", placeholder="Descreva o motivo da aprovação/manutenção...")
                        
                        if st.button("💾 Confirmar Decisão e Notificar Filial", type="primary"):
                            if not justificativa_master:
                                st.error("⚠️ Digite a justificativa do gestor antes de confirmar.")
                            else:
                                novo_status_str = nova_decisao.split()[1]
                                if "RESTRIÇÃO" in nova_decisao: novo_status_str = "APROVADO COM RESTRIÇÃO"
                                
                                doc_alvo = dados_cliente.get('CPF_CNPJ', '')
                                atualizar_status_google_sheet(doc_alvo, f"🟢 {novo_status_str} (MASTER)", justificativa_master)
                                
                                parecer_original = dados_cliente.get('Parecer_IA', 'Parecer de IA reavaliado.')
                                pdf_master = gerar_pdf_parecer(
                                    dados_cliente.get('Cliente', 'N/A'), doc_alvo, 
                                    dados_cliente.get('Tipo_Pessoa', 'PJ/PF'), dados_cliente.get('Prazo', 'N/A'), 
                                    dados_cliente.get('Filial', 'N/A'), dados_cliente.get('Equipamentos', 'N/A'), 
                                    3000.0, parecer_original, 
                                    chancela_master=f"{nova_decisao} - Motivo: {justificativa_master}"
                                )
                                
                                if DRIVE_FOLDER_ID:
                                    doc_l = re.sub(r'\D', '', str(doc_alvo))
                                    upload_para_google_drive(f"PARECER_MASTER_{doc_l}.pdf", pdf_master, "application/pdf")

                                st.success("✅ Decisão Master registrada! O status foi atualizado para a filial.")
                                st.rerun()
            else:
                st.success("🎉 Nenhum cadastro pendente de reavaliação no momento!")
        else:
            st.info("Nenhum histórico disponível para reavaliação.")

# --- ABA 3: BLACKLIST DA REDE ---
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
                    append_google_sheet("Blacklist", [doc_block.strip(), nome_block.strip(), motivo_block.strip(), dt_hoje, usr_info['nome']])
                    
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
        if not df_black_atual.empty: st.dataframe(df_black_atual, use_container_width=True)
        else: st.info("Nenhum documento cadastrado na Blacklist até o momento.")

# --- ABA 4: DASHBOARD GERENCIAL & CUSTOS ---
if eh_master and aba_dash:
    with aba_dash:
        st.markdown("### 📊 Visão Geral, Indicadores e Custos de Consultas")
        
        df_hist = obter_historico_completo()
            
        if df_hist is not None and not df_hist.empty and 'Filial' in df_hist.columns:
            lojas_disponiveis = ["Todas as Lojas"] + sorted([str(x) for x in df_hist['Filial'].unique() if str(x) != 'nan' and str(x).strip() != ''])
            filtro_loja = st.selectbox("🎯 Filtrar Unidade:", lojas_disponiveis)
            
            if filtro_loja != "Todas as Lojas":
                df_hist = df_hist[df_hist['Filial'] == filtro_loja]
                
            total_analises = len(df_hist)
            col_status = 'Status Decisão' if 'Status Decisão' in df_hist.columns else None
            
            if col_status:
                status_series = df_hist[col_status].astype(str)
                restritos_mask = status_series.str.contains("RESTRIÇÃO|RESTRICAO", na=False, case=False)
                aprovados_mask = status_series.str.contains("APROVADO|🟢", na=False, case=False) & ~restritos_mask
                reprovados_mask = status_series.str.contains("REPROVADO|PENDENTE|NEGADO|🔴|⏳", na=False, case=False)
                
                aprovados = len(df_hist[aprovados_mask])
                restritos = len(df_hist[restritos_mask])
                reprovados = len(df_hist[reprovados_mask])
            else:
                aprovados, restritos, reprovados = 0, 0, 0
            
            st.markdown("#### 📌 Volume de Processamento")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("📌 Total de Cadastros", total_analises)
            col2.metric("✅ Aprovados", aprovados)
            col3.metric("🔴 Negados / Retidos", reprovados)
            col4.metric("🟡 Com Restrição", restritos)
            
            st.markdown("---")
            st.markdown("#### 💵 Controle Financeiro de Consultas e IA")
            
            if total_analises <= 500: custo_consult_center = total_analises * 1.00
            else: custo_consult_center = (500 * 1.00) + ((total_analises - 500) * 3.00)
                
            custo_spc = total_analises * 2.84
            custo_gemini_ia = total_analises * 0.03
            
            custo_total_acumulado = custo_consult_center + custo_spc + custo_gemini_ia
            custo_medio_por_cadastro = custo_total_acumulado / total_analises if total_analises > 0 else 0.0
            
            mc1, mc2, mc3, mc4, mc5 = st.columns(5)
            mc1.metric("🔍 Consult Center", f"R$ {custo_consult_center:,.2f}")
            mc2.metric("📋 SPC Brasil", f"R$ {custo_spc:,.2f}")
            mc3.metric("🤖 Gemini Vertex AI", f"R$ {custo_gemini_ia:,.2f}")
            mc4.metric("💰 Custo Total", f"R$ {custo_total_acumulado:,.2f}")
            mc5.metric("🎯 Média / Cadastro", f"R$ {custo_medio_por_cadastro:,.2f}")
            
            st.markdown("---")
            st.markdown("#### Volume de Análises por Data")
            if 'Data_Dia' in df_hist.columns:
                st.bar_chart(df_hist['Data_Dia'].value_counts().sort_index())
        else:
            st.info("Aguardando os primeiros cadastros para gerar o Dashboard.")

# --- ABA 5: HISTÓRICO GERAL ---
with aba_hist:
    st.markdown("### 📋 Registro Geral de Auditoria")
    df_hist_all = obter_historico_completo()
        
    if df_hist_all is not None and not df_hist_all.empty:
        if not eh_master and 'Filial' in df_hist_all.columns:
            df_hist_all = df_hist_all[df_hist_all['Filial'] == usr_info['filial']]
        st.dataframe(df_hist_all, use_container_width=True)
        if eh_master:
            st.download_button("📊 Exportar Dados (CSV)", df_hist_all.to_csv(index=False, sep=";").encode('utf-8-sig'), "Auditoria_Risco_CDC.csv", "text/csv")
    else:
        st.info("Nenhum registro encontrado no histórico.")
