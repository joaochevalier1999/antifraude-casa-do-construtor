import streamlit as st
import base64
import io
import html
import re
import os
import requests
import pandas as pd
import json
from datetime import datetime

# Tratamento para garantir que a biblioteca do google-auth foi instalada
try:
    from google.oauth2 import service_account
    from google.auth.transport.requests import Request as GoogleAuthRequest
    GOOGLE_AUTH_INSTALLED = True
except ImportError:
    GOOGLE_AUTH_INSTALLED = False

# Dependências para geração de PDF
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(
    page_title="Portal Antifraude - Casa do Construtor",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
    <style>
    .stApp { background-color: #F4F6F9; }
    h1, h2, h3 { color: #003366 !important; font-family: 'Arial', sans-serif; }
    div.stButton > button[kind="primary"] { background-color: #003366; color: #FFFFFF; border-radius: 8px; border: 2px solid #003366; padding: 10px 24px; font-weight: bold; transition: all 0.3s; }
    div.stButton > button[kind="primary"]:hover { background-color: #FBC02D; color: #003366; border: 2px solid #FBC02D; }
    div[data-testid="stVerticalBlock"] > div[style*="border"] { border-radius: 12px; background-color: #FFFFFF; box-shadow: 0px 4px 12px rgba(0, 0, 0, 0.05); border: 1px solid #E0E0E0; padding: 15px; }
    #MainMenu {visibility: hidden;} footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# --- USUÁRIOS ---
USUARIOS = {
    "master": {"senha": "master2026", "nome": "Gestor Geral Master", "filial": "Todas", "perfil": "master"},
    "087_blumenau": {"senha": "cc087", "nome": "Atendente Blumenau", "filial": "087 - Blumenau", "perfil": "user"}
}

if "logged_in" not in st.session_state: 
    st.session_state["logged_in"] = False
if "usuario_atual" not in st.session_state: 
    st.session_state["usuario_atual"] = None

# --- TELA DE LOGIN ---
if not st.session_state["logged_in"]:
    st.write("<br><br><br>", unsafe_allow_html=True)
    col_l1, col_l2, col_l3 = st.columns([1, 1.5, 1])
    with col_l2:
        with st.container(border=True):
            st.image("https://casadoconstrutor.com.br/wp-content/uploads/2021/04/logo-casa-do-construtor.png", width=300)
            st.markdown("### 🔐 Acesso Restrito Corporativo")
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

# --- AUTENTICAÇÃO VIA CONTA DE SERVIÇO (VERTEX AI) ---
token_acesso_valido = None
gcp_project_id = None
erro_auth = None

if GOOGLE_AUTH_INSTALLED and "GCP_CREDENTIALS" in st.secrets:
    try:
        creds_json = json.loads(st.secrets["GCP_CREDENTIALS"])
        gcp_project_id = creds_json.get("project_id")
        
        # ESCOPO OFICIAL DO VERTEX AI / GOOGLE CLOUD PLATFORM
        escopos = ['https://www.googleapis.com/auth/cloud-platform']
        credenciais = service_account.Credentials.from_service_account_info(creds_json, scopes=escopos)
        
        req_auth = GoogleAuthRequest()
        credenciais.refresh(req_auth)
        token_acesso_valido = credenciais.token
    except Exception as e:
        erro_auth = f"Erro ao processar o JSON: {e}"

# --- BARRA LATERAL ---
usr_info = st.session_state["usuario_atual"]
eh_master = usr_info["perfil"] == "master"

with st.sidebar:
    st.image("https://casadoconstrutor.com.br/wp-content/uploads/2021/04/logo-casa-do-construtor.png", width=180)
    st.markdown("---")
    st.markdown(f"### 👤 {usr_info['nome']}")
    st.markdown(f"**📍 Unidade:** {usr_info['filial']}")
    st.markdown("---")
    
    st.markdown("🔍 **Status da Conexão AI**")
    if not GOOGLE_AUTH_INSTALLED:
        st.error("🔴 Falta adicionar `google-auth` no requirements.txt do GitHub!")
    elif token_acesso_valido and gcp_project_id:
        st.success(f"🟢 Vertex AI Conectado!\nProjeto: `{gcp_project_id}`")
    else:
        st.error("🔴 JSON de Serviço não configurado nos Secrets.")
        if erro_auth: st.caption(erro_auth)

    st.markdown("---")
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state["logged_in"] = False
        st.rerun()

ARQUIVO_HISTORICO = "historico_analises.csv"
def salvar_no_historico(filial, atendente, cliente, tipo_pessoa, equipamento, valor, prazo, parecer_texto):
    data_hora_dt = datetime.now()
    status = "ANALISADO"
    if "[APROVADO COM RESTRIÇÃO]" in parecer_texto.upper(): status = "APROVADO COM RESTRIÇÃO"
    elif "[APROVADO]" in parecer_texto.upper(): status = "APROVADO"
    elif "[REPROVADO]" in parecer_texto.upper(): status = "REPROVADO"

    novo_registro = pd.DataFrame([{
        "Data/Hora": data_hora_dt.strftime("%d/%m/%Y %H:%M:%S"), "Data_Dia": data_hora_dt.strftime("%d/%m/%Y"),
        "Filial": filial, "Atendente": atendente, "Cliente": cliente, "Tipo_Pessoa": tipo_pessoa,
        "Equipamento": equipamento, "Valor Reposição (R$)": valor, "Prazo": prazo, "Status Decisão": status
    }])
    if not os.path.exists(ARQUIVO_HISTORICO): novo_registro.to_csv(ARQUIVO_HISTORICO, index=False, sep=";", encoding="utf-8-sig")
    else: novo_registro.to_csv(ARQUIVO_HISTORICO, mode='a', header=False, index=False, sep=";", encoding="utf-8-sig")

# --- GERADOR DE PDF ---
def formatar_texto_para_reportlab(texto): return re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', html.escape(texto))

def gerar_pdf_parecer(nome_cliente, tipo_pessoa, prazo, loja, equipamento_nome, valor_equipamento, texto_parecer):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=36, leftMargin=36, topMargin=36, bottomMargin=36)
    story, styles = [], getSampleStyleSheet()
    titulo_style = ParagraphStyle('Titulo', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#003366'))
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=10, leading=14)

    story.append(Paragraph("<b>CASA DO CONSTRUTOR - PARECER TÉCNICO ANTIFRAUDE</b>", titulo_style))
    story.append(Paragraph(f"Emitido em: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}", styles['Normal']))
    story.append(Spacer(1, 10))

    val_f = f"R$ {valor_equipamento:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    t = Table([
        [Paragraph("<b>Cliente:</b>", body_style), Paragraph(f"{html.escape(nome_cliente)} ({tipo_pessoa})", body_style)],
        [Paragraph("<b>Prazo Solicitado:</b>", body_style), Paragraph(prazo, body_style)],
        [Paragraph("<b>Filial/Equipamento:</b>", body_style), Paragraph(f"{html.escape(loja)} | {html.escape(equipamento_nome)} ({val_f})", body_style)],
    ], colWidths=[140, 380])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F2F4F8')), ('GRID', (0, 0), (-1, -1), 0.5, colors.gray)]))
    story.append(t)
    story.append(Spacer(1, 15))

    for linha in texto_parecer.split('\n'):
        if linha.strip(): story.append(Paragraph(formatar_texto_para_reportlab(linha.strip()), body_style))
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

CATALOGO_EQUIPAMENTOS = {"BETONEIRA 400L BIVOLT": 5700.0, "COMPACTADOR A GASOLINA": 15550.0}
OPCAO_OUTRO = "➕ OUTRO EQUIPAMENTO (Manual)"
opcoes_equipamentos = sorted(list(CATALOGO_EQUIPAMENTOS.keys())) + [OPCAO_OUTRO]

# ÁREA CENTRAL
st.title("🛡️ Central de Risco e Crédito")
st.markdown("Bem-vindo ao portal unificado de validação de locações.")

abas = st.tabs(["🚀 Nova Análise", "📊 Dashboard Executivo", "📋 Histórico Geral"] if eh_master else ["🚀 Nova Análise", "📋 Meu Histórico"])

with abas[0]:
    with st.container(border=True):
        st.markdown("### 1️⃣ Dados do Cliente e Operação")
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            loja = st.selectbox("🏢 Filial Responsável", ["087 - Blumenau", "Todas"]) if eh_master else usr_info["filial"]
            if not eh_master: st.text_input("🏢 Filial Responsável", value=loja, disabled=True)
            tipo_cliente = st.radio("👤 Tipo de Cadastro", ["Pessoa Física (PF)", "Pessoa Jurídica (PJ)"], horizontal=True)
            nome_cliente = st.text_input("Nome Completo ou Razão Social")
            subtipo_pj, nome_solicitante, contato_solicitante = None, None, None
            if tipo_cliente == "Pessoa Jurídica (PJ)":
                subtipo_pj = st.selectbox("🏢 Natureza Jurídica", ["Empresa Padrão (LTDA/SA)", "Condomínio", "MEI"])
                col_pj1, col_pj2 = st.columns(2)
                with col_pj1: nome_solicitante = st.text_input("Quem está solicitando?")
                with col_pj2: contato_solicitante = st.text_input("E-mail ou WhatsApp")

        with col_a2:
            referencias = ""
            if tipo_cliente == "Pessoa Física (PF)":
                forma_pagamento = st.selectbox("Condição de Pagamento Permitida", ["À Vista / Débito / Pix (Antecipado)"])
            else:
                forma_pagamento = st.selectbox("💳 Condição de Pagamento", ["À Vista / Débito / Pix", "Boleto 7 dias", "Boleto 28 dias"])
                if "Boleto" in forma_pagamento: referencias = st.text_area("📞 Feedback das Referências Comerciais")

    with st.container(border=True):
        st.markdown("### 2️⃣ Equipamento")
        equip_sel = st.selectbox("🔍 Buscar Equipamento", opcoes_equipamentos, index=None)
        equip_nome = equip_sel
        val_equip = CATALOGO_EQUIPAMENTOS.get(equip_sel, 0.0) if equip_sel != OPCAO_OUTRO else 0.0
        if equip_sel == OPCAO_OUTRO:
            ce1, ce2 = st.columns(2)
            with ce1: equip_nome = st.text_input("Nome (Manual)")
            with ce2: val_equip = st.number_input("Valor Reposição (R$)", value=3000.0)
        elif equip_sel:
            st.success(f"💵 Valor Oficial: **R$ {val_equip:,.2f}**")

    with st.container(border=True):
        st.markdown("### 📎 3️⃣ Documentação Base")
        documentos = st.file_uploader("Arraste PDFs e Imagens", accept_multiple_files=True)

    st.write("<br>", unsafe_allow_html=True)
    if st.button("🚀 INICIAR ANÁLISE DE RISCO", type="primary", use_container_width=True):
        if not nome_cliente or not equip_nome or not documentos:
            st.error("⚠️ Preencha Cliente, Equipamento e Anexos.")
        elif not token_acesso_valido or not gcp_project_id:
            st.error("❌ Erro de Autenticação Vertex AI. Verifique o painel na barra lateral.")
        else:
            with st.spinner('A IA está processando as matrizes e documentos via Vertex AI...'):
                try:
                    payload_parts = []
                    for doc in documentos:
                        b64_data = base64.b64encode(doc.getvalue()).decode("utf-8")
                        payload_parts.append({"inline_data": {"mime_type": doc.type, "data": b64_data}})

                    prompt = f"""
                    Analista Master de Risco. 
                    Cliente: {nome_cliente} | Natureza: {tipo_cliente}
                    Equipamento: {equip_nome} (R$ {val_equip:,.2f})
                    Condição: {forma_pagamento} | Referências: {referencias if referencias else 'Nenhuma'}
                    
                    REGRAS: 
                    1. PF sempre À vista. 
                    2. MEI/Condomínio: Boleto máx 7 dias.
                    3. Empresa < 1 ano: Boleto máx 7 dias. Restrição no setor = REPROVADO.
                    Formato: Resumo, Status ([APROVADO], [APROVADO COM RESTRIÇÃO], [REPROVADO]), e Parecer.
                    """
                    payload_parts.append({"text": prompt})

                    # URL VERTEX AI COM O NOME OFICIAL DA VERSÃO
                    url_api = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{gcp_project_id}/locations/us-central1/publishers/google/models/gemini-1.5-flash-001:generateContent"
                    
                    headers_api = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {token_acesso_valido}"
                    }
                    data_api = {"contents": [{"parts": payload_parts}], "generationConfig": {"temperature": 0.1}}

                    # Chamada corrigida
                    res = requests.post(url_api, json=data_api, headers=headers_api)

                    if res.status_code == 200:
                        texto_resultado = res.json()['candidates'][0]['content']['parts'][0]['text']
                        st.session_state['resultado_parecer'] = texto_resultado
                        pdf = gerar_pdf_parecer(nome_cliente, tipo_cliente, forma_pagamento, loja, equip_nome, val_equip, texto_resultado)
                        st.session_state['pdf_bytes'] = pdf
                        salvar_no_historico(loja, usr_info['nome'], nome_cliente, tipo_cliente, equip_nome, val_equip, forma_pagamento, texto_resultado)
                    else:
                        st.error(f"❌ Erro na API (Código {res.status_code}): {res.text}")

                except Exception as e:
                    st.error(f"Erro na execução da requisição: {e}")

    if 'resultado_parecer' in st.session_state and st.session_state['resultado_parecer']:
        st.success("✅ Avaliação Finalizada!")
        st.markdown(st.session_state['resultado_parecer'])
        st.download_button("📄 Baixar Relatório PDF", data=st.session_state['pdf_bytes'], file_name="Relatorio.pdf", mime="application/pdf", type="primary")
