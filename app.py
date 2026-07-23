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
    
    /* Customização do título da resposta da IA */
    .resultado-titulo { font-size: 32px !important; font-weight: 900 !important; margin-bottom: 20px; text-align: center; }
    .resultado-aprovado { color: #2E7D32 !important; }
    .resultado-reprovado { color: #C62828 !important; }
    .resultado-restricao { color: #F57F17 !important; }
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
        st.error("🔴 Falta `google-auth` no requirements.txt!")
    elif token_acesso_valido and gcp_project_id:
        st.success(f"🟢 Nuvem Autenticada!\n`{gcp_project_id}`")
    else:
        st.error("🔴 JSON de Serviço ausente nos Secrets.")
        if erro_auth: st.caption(erro_auth)

    st.markdown("---")
    if st.button("🚪 Sair", use_container_width=True):
        st.session_state["logged_in"] = False
        st.rerun()

ARQUIVO_HISTORICO = "historico_analises.csv"
def salvar_no_historico(filial, atendente, cliente, tipo_pessoa, equipamento, valor, prazo, parecer_texto):
    data_hora_dt = datetime.now()
    status = "ANALISADO"
    parecer_up = parecer_texto.upper()
    if "[APROVADO COM RESTRIÇÃO]" in parecer_up or "RESTRIÇÃO" in parecer_up: status = "APROVADO COM RESTRIÇÃO"
    elif "[APROVADO]" in parecer_up or "🟢 APROVADO" in parecer_up: status = "APROVADO"
    elif "[REPROVADO]" in parecer_up or "🔴 REPROVADO" in parecer_up or "NEGADO" in parecer_up: status = "REPROVADO"

    novo_registro = pd.DataFrame([{
        "Data/Hora": data_hora_dt.strftime("%d/%m/%Y %H:%M:%S"), "Data_Dia": data_hora_dt.strftime("%d/%m/%Y"),
        "Filial": filial, "Atendente": atendente, "Cliente": cliente, "Tipo_Pessoa": tipo_pessoa,
        "Equipamento": equipamento, "Valor Reposição (R$)": valor, "Prazo": prazo, "Status Decisão": status
    }])
    if not os.path.exists(ARQUIVO_HISTORICO): novo_registro.to_csv(ARQUIVO_HISTORICO, index=False, sep=";", encoding="utf-8-sig")
    else: novo_registro.to_csv(ARQUIVO_HISTORICO, mode='a', header=False, index=False, sep=";", encoding="utf-8-sig")

# --- GERADOR DE PDF ---
def formatar_texto_para_reportlab(texto): 
    # Transforma # e ** do Markdown em tags HTML seguras para o PDF
    t = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', html.escape(texto))
    t = re.sub(r'^#+\s+(.*)', r'<b>\1</b>', t) 
    return t

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

# --- CATÁLOGO DE EQUIPAMENTOS ---
RAW_CATALOGO = {
    "ACABADORA PA ACABAMENTO 36\"": 200.0, "ACABADORA ACV 36\" GASOLINA": 14000.0, "ACABADORA BFG 100 GASOLINA": 13500.0,
    "ACABADORA BUFFALO BFG 100 GASOLINA": 13500.0, "ACABADORA CSM AC36 GASOLINA": 11900.0, "ACABADORA CT36 5A GASOLINA": 14000.0,
    "BETONEIRA 400L INFINITY BIVOLT": 5700.0, "COMPACTADOR ate 72KG GASOLINA": 15550.0, "GERADOR 13KVA BFGE13000 GASOLINA": 8140.0,
    "GUINCHO de COLUNA 350KG 220V": 5730.0, "LAVADORA AP HD 585 PROFI S 220V": 2600.0, "ROMPEDOR 29.9KG TE3000 AVR 220V": 23980.0
}
CATALOGO_EQUIPAMENTOS = {" ".join(k.split()): v for k, v in RAW_CATALOGO.items()}
OPCAO_OUTRO = "➕ OUTRO EQUIPAMENTO (Manual)"
opcoes_equipamentos = sorted(list(CATALOGO_EQUIPAMENTOS.keys())) + [OPCAO_OUTRO]

# ÁREA CENTRAL
st.title("🛡️ Central de Risco e Crédito")
st.markdown("Bem-vindo ao portal unificado de validação de locações.")

abas = st.tabs(["🚀 Nova Análise", "📊 Dashboard Gerencial", "📋 Histórico Geral"] if eh_master else ["🚀 Nova Análise", "📋 Meu Histórico"])

# --- ABA 1: NOVA ANÁLISE ---
with abas[0]:
    with st.container(border=True):
        st.markdown("### 1️⃣ Dados do Cliente e Operação")
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            loja = st.selectbox("🏢 Filial Responsável", [
                "087 - Blumenau", "213 - Indaial", "350 - Itapema", "250 - Balneário Camboriú",
                "284 - Jaraguá do Sul", "299 - Brusque", "360 - Blumenau 02", "503 - Timbó",
                "560 - Camboriú", "636 - Guaramirim", "695 - Tijucas", "733 - São Bento do Sul", "Todas"
            ]) if eh_master else usr_info["filial"]
            if not eh_master: st.text_input("🏢 Filial Responsável", value=loja, disabled=True)
            
            tipo_cliente = st.radio("👤 Tipo de Cadastro", ["Pessoa Física (PF)", "Pessoa Jurídica (PJ)"], horizontal=True)
            nome_cliente = st.text_input("Nome Completo ou Razão Social")
            subtipo_pj, nome_solicitante, contato_solicitante = None, None, None
            
            if tipo_cliente == "Pessoa Jurídica (PJ)":
                subtipo_pj = st.selectbox("🏢 Natureza Jurídica", ["Empresa Padrão (LTDA/SA)", "Condomínio", "MEI"])
                col_pj1, col_pj2 = st.columns(2)
                with col_pj1: nome_solicitante = st.text_input("Quem está solicitando no balcão/WhatsApp?" if subtipo_pj != "Condomínio" else "Nome do Síndico Responsável")
                with col_pj2: contato_solicitante = st.text_input("E-mail corporativo ou WhatsApp")

        with col_a2:
            referencias = ""
            if tipo_cliente == "Pessoa Física (PF)":
                st.warning("⚠️ **Atenção:** Pagamento a prazo não permitido para Pessoa Física.")
                forma_pagamento = st.selectbox("Condição de Pagamento Permitida", ["À Vista / Débito / Pix (Antecipado)"])
            else:
                # LISTA DE BOLETOS ATUALIZADA
                forma_pagamento = st.selectbox("💳 Condição de Pagamento Solicitada", ["À Vista / Débito / Pix", "Boleto 7 dias", "Boleto 14 dias", "Boleto 21 dias", "Boleto 28 dias"])
                
                # REGRAS DINÂMICAS DE DOCUMENTAÇÃO NA TELA
                if subtipo_pj == "Empresa Padrão (LTDA/SA)":
                    st.info("📄 **Checklist Documental Obrigatório:**\n- Contrato Social Atualizado.\n- CNH ou RG de quem está solicitando.")
                    referencias = st.text_area("📞 Feedback das Referências Comerciais (Opcional, mas ajuda na aprovação)", placeholder="O que os fornecedores disseram sobre o histórico deste CNPJ?")
                elif subtipo_pj == "Condomínio":
                    st.warning("📄 **Checklist Documental Obrigatório:**\n- Ata atualizada de eleição do Síndico.\n- Contato direto do Síndico.\n\n⚠️ **Regra Rígida:** Máximo de 7 dias no boleto.")
                    if "Boleto" in forma_pagamento: referencias = st.text_area("📞 Referências do Condomínio (Opcional)")
                elif subtipo_pj == "MEI":
                    st.warning("📄 **Checklist Documental Obrigatório:**\n- Cartão CNPJ ou Certificado de MEI.\n- CNH do Titular.\n- Comprovante de Residência.\n\n⚠️ **Regra Rígida:** Máximo de 7 dias no boleto.")
                    if "Boleto" in forma_pagamento: referencias = st.text_area("📞 Referências do MEI (Opcional)")

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
            st.success(f"💵 Valor Oficial de Risco: **R$ {val_equip:,.2f}**")

    with st.container(border=True):
        st.markdown("### 📎 3️⃣ Documentação Base")
        documentos = st.file_uploader("Arraste PDFs, Fotos (CNH, Contrato Social, Serasa)", accept_multiple_files=True)

    st.write("<br>", unsafe_allow_html=True)
    if st.button("🚀 INICIAR ANÁLISE DE RISCO", type="primary", use_container_width=True):
        if not nome_cliente or not equip_nome or not documentos:
            st.error("⚠️ Preencha Cliente, Equipamento e anexe os Documentos listados acima.")
        elif not token_acesso_valido or not gcp_project_id:
            st.error("❌ Erro de Autenticação na Nuvem. Verifique o painel na barra lateral.")
        else:
            with st.spinner('A IA (Gemini 2.5 Flash) está processando os documentos com máxima segurança...'):
                try:
                    payload_parts = []
                    for doc in documentos:
                        b64_data = base64.b64encode(doc.getvalue()).decode("utf-8")
                        payload_parts.append({
                            "inlineData": {
                                "mimeType": doc.type,
                                "data": b64_data
                            }
                        })

                    # PROMPT MELHORADO PARA GARANTIR LAYOUT E REGRAS DE FRAUDE
                    prompt = f"""
                    Você é o Analista Master de Risco Financeiro e Fraude da Casa do Construtor.
                    
                    DADOS DA OPERAÇÃO:
                    - Cliente: {nome_cliente}
                    - Natureza: {tipo_cliente} ({subtipo_pj if subtipo_pj else 'Pessoa Física'})
                    - Solicitante e Contato: {nome_solicitante} | {contato_solicitante}
                    - Equipamento: {equip_nome} (R$ {val_equip:,.2f})
                    - Condição Solicitada: {forma_pagamento}
                    - Referências: {referencias if referencias else 'Nenhuma informada'}
                    
                    REGRAS INEGOCIÁVEIS: 
                    1. Pessoa Física (PF): Somente pagamento À vista.
                    2. MEI e Condomínio: Boleto máximo 7 dias. Acima disso = REPROVADO (ou aprovado apenas se baixar para 7 dias).
                    3. Empresa < 1 ano: Boleto máximo 7 dias. Restrição no Serasa no setor da construção = REPROVADO.
                    
                    FORMATO OBRIGATÓRIO DE SAÍDA (Use blocos visualmente claros):
                    
                    Comece a resposta COM UMA DAS 3 FRASES EXATAS EM LETRAS GIGANTES (Markdown #):
                    # 🟢 APROVADO
                    # 🟡 APROVADO COM RESTRIÇÃO
                    # 🔴 REPROVADO
                    
                    Logo abaixo, crie as seguintes seções (usando ** negrito e marcadores):
                    **Resumo da Decisão:** (Por que tomou essa decisão de forma direta).
                    
                    **Justificativa Técnica:** (Detalhe o que encontrou de bom/ruim nos documentos e consultas).
                    
                    **⚠️ Alerta Obrigatório Antifraude:** (Instrua o atendente: "Ligue para o telefone fixo registrado no site oficial ou Cartão CNPJ da empresa para confirmar se {nome_solicitante} realmente trabalha lá e tem autorização para locar equipamentos.")
                    """
                    payload_parts.append({"text": prompt})

                    # MODELO GEMINI 2.5 FLASH VIA VERTEX AI
                    url_api = f"https://us-central1-aiplatform.googleapis.com/v1/projects/{gcp_project_id}/locations/us-central1/publishers/google/models/gemini-2.5-flash:generateContent"
                    headers_api = {
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {token_acesso_valido}"
                    }
                    data_api = {
                        "contents": [{"role": "user", "parts": payload_parts}], 
                        "generationConfig": {"temperature": 0.1}
                    }

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
        
        # Envelopa o resultado em um visual limpo e grande
        st.markdown("<hr>", unsafe_allow_html=True)
        st.markdown(st.session_state['resultado_parecer'], unsafe_allow_html=True)
        st.markdown("<hr>", unsafe_allow_html=True)
        
        st.download_button("📄 Baixar Relatório PDF", data=st.session_state['pdf_bytes'], file_name=f"Parecer_{nome_cliente.replace(' ', '_')}.pdf", mime="application/pdf", type="primary")


# --- ABA 2: DASHBOARD GERENCIAL (Aprimorado) ---
with abas[1]:
    if eh_master:
        st.markdown("### 📊 Visão Geral da Rede")
        if os.path.exists(ARQUIVO_HISTORICO):
            df = pd.read_csv(ARQUIVO_HISTORICO, sep=";")
            
            # Filtro por loja dinâmico
            lojas_disponiveis = ["Todas as Lojas"] + sorted(list(df['Filial'].dropna().unique()))
            filtro_loja = st.selectbox("🎯 Filtrar Resultados por Unidade:", lojas_disponiveis)
            
            if filtro_loja != "Todas as Lojas":
                df = df[df['Filial'] == filtro_loja]
                
            total_analises = len(df)
            aprovados = len(df[df['Status Decisão'] == 'APROVADO'])
            reprovados = len(df[df['Status Decisão'] == 'REPROVADO'])
            restritos = len(df[df['Status Decisão'] == 'APROVADO COM RESTRIÇÃO'])
            
            # Grid de Métricas
            st.write("<br>", unsafe_allow_html=True)
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("📌 Total de Cadastros", total_analises)
            col2.metric("✅ Aprovados", aprovados)
            col3.metric("🔴 Negados", reprovados)
            col4.metric("🟡 Com Restrição", restritos)
            
            st.markdown("---")
            st.markdown("#### Volume de Operações Recentes")
            st.bar_chart(df['Data_Dia'].value_counts().sort_index())
            
        else:
            st.info("Aguardando as primeiras análises para gerar o Dashboard...")
    else:
        st.markdown("### 📋 Log de Operações da Unidade")
        if os.path.exists(ARQUIVO_HISTORICO):
            df = pd.read_csv(ARQUIVO_HISTORICO, sep=";")
            st.dataframe(df[df['Filial'] == usr_info['filial']], use_container_width=True)


# --- ABA 3: HISTÓRICO MASTER ---
if eh_master and len(abas) > 2:
    with abas[2]:
        st.markdown("### 📋 Tabela Geral de Auditoria")
        if os.path.exists(ARQUIVO_HISTORICO):
            df = pd.read_csv(ARQUIVO_HISTORICO, sep=";")
            st.dataframe(df.sort_values(by="Data/Hora", ascending=False), use_container_width=True)
            st.download_button("📊 Exportar Banco de Dados", df.to_csv(index=False, sep=";").encode('utf-8-sig'), "Auditoria_Risco_CDC.csv", "text/csv")
