import streamlit as st
import base64
import io
import html
import re
import os
import requests
import pandas as pd
from datetime import datetime

# Dependências para geração de PDF
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# --- CONFIGURAÇÃO DA PÁGINA E CSS CUSTOMIZADO ---
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
    div.stButton > button[kind="primary"] {
        background-color: #003366; color: #FFFFFF; border-radius: 8px;
        border: 2px solid #003366; padding: 10px 24px; font-weight: bold; transition: all 0.3s;
    }
    div.stButton > button[kind="primary"]:hover { background-color: #FBC02D; color: #003366; border: 2px solid #FBC02D; }
    div[data-testid="stVerticalBlock"] > div[style*="border"] {
        border-radius: 12px; background-color: #FFFFFF; box-shadow: 0px 4px 12px rgba(0, 0, 0, 0.05);
        border: 1px solid #E0E0E0; padding: 15px;
    }
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
            st.markdown("Portal exclusivo para análise de risco e antifraude.")
            with st.form("form_login"):
                usuario_input = st.text_input("Usuário da Unidade")
                senha_input = st.text_input("Senha", type="password")
                btn_entrar = st.form_submit_button("Entrar no Portal", type="primary", use_container_width=True)
                if btn_entrar:
                    user_clean = usuario_input.strip().lower()
                    if user_clean in USUARIOS and USUARIOS[user_clean]["senha"] == senha_input:
                        st.session_state["logged_in"] = True
                        st.session_state["usuario_atual"] = USUARIOS[user_clean]
                        st.rerun()
                    else:
                        st.error("❌ Credenciais inválidas. Tente novamente.")
    st.stop()

# --- CARREGAMENTO SEGURO DA CHAVE DA API ---
CHAVE_API = ""
if "GEMINI_API_KEY" in st.secrets and st.secrets["GEMINI_API_KEY"]:
    CHAVE_API = str(st.secrets["GEMINI_API_KEY"]).strip()
elif os.getenv("GEMINI_API_KEY"):
    CHAVE_API = str(os.getenv("GEMINI_API_KEY")).strip()

# BARRA LATERAL DE NAVEGAÇÃO
usr_info = st.session_state["usuario_atual"]
eh_master = usr_info["perfil"] == "master"

with st.sidebar:
    st.image("https://casadoconstrutor.com.br/wp-content/uploads/2021/04/logo-casa-do-construtor.png", width=180)
    st.markdown("---")
    st.markdown(f"### 👤 {usr_info['nome']}")
    st.markdown(f"**📍 Unidade:** {usr_info['filial']}")
    st.markdown("---")
    
    if CHAVE_API:
        st.success("🟢 API Key Conectada")
    else:
        st.warning("⚠️ Chave não configurada no Secrets")
        chave_manual = st.text_input("Cole sua chave aqui se necessário:", type="password")
        if chave_manual.strip():
            CHAVE_API = chave_manual.strip()

    st.markdown("---")
    if st.button("🚪 Sair do Sistema", use_container_width=True):
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
        "Data/Hora": data_hora_dt.strftime("%d/%m/%Y %H:%M:%S"),
        "Data_Dia": data_hora_dt.strftime("%d/%m/%Y"),
        "Filial": filial,
        "Atendente": atendente,
        "Cliente": cliente,
        "Tipo_Pessoa": tipo_pessoa,
        "Equipamento": equipamento,
        "Valor Reposição (R$)": valor,
        "Prazo": prazo,
        "Status Decisão": status
    }])
    if not os.path.exists(ARQUIVO_HISTORICO): 
        novo_registro.to_csv(ARQUIVO_HISTORICO, index=False, sep=";", encoding="utf-8-sig")
    else: 
        novo_registro.to_csv(ARQUIVO_HISTORICO, mode='a', header=False, index=False, sep=";", encoding="utf-8-sig")

# --- GERADOR DE PDF ---
def formatar_texto_para_reportlab(texto):
    return re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', html.escape(texto))

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
    dados_tabela = [
        [Paragraph("<b>Cliente:</b>", body_style), Paragraph(f"{html.escape(nome_cliente)} ({tipo_pessoa})", body_style)],
        [Paragraph("<b>Prazo Solicitado:</b>", body_style), Paragraph(prazo, body_style)],
        [Paragraph("<b>Filial/Equipamento:</b>", body_style), Paragraph(f"{html.escape(loja)} | {html.escape(equipamento_nome)} ({val_f})", body_style)],
    ]
    t = Table(dados_tabela, colWidths=[140, 380])
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F2F4F8')), ('GRID', (0, 0), (-1, -1), 0.5, colors.gray)]))
    story.append(t)
    story.append(Spacer(1, 15))

    for linha in texto_parecer.split('\n'):
        if linha.strip(): 
            story.append(Paragraph(formatar_texto_para_reportlab(linha.strip()), body_style))
    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# --- CATÁLOGO COMPLETO DE EQUIPAMENTOS ---
RAW_CATALOGO = {
    "ACABADORA PA ACABAMENTO 36\"": 200.0, "ACABADORA ACV 36\" GASOLINA": 14000.0, "ACABADORA BFG 100 GASOLINA": 13500.0,
    "ACABADORA BUFFALO BFG 100 GASOLINA": 13500.0, "ACABADORA CSM AC36 GASOLINA": 11900.0, "ACABADORA CT36 5A GASOLINA": 14000.0,
    "ACABADORA CT36 5A GASOLINA (KIT PAS)": 300.0, "ACABADORA FINITI F36 GASOLINA": 10000.0, "ACABADORA HUSQVARNA BG375 GASOLINA": 13500.0,
    "ACABADORA MAC 36 GASOLINA": 13500.0, "ACABADORA MENEGOTTI MAC 36 GASOLINA": 13500.0, "ACABADORA MENEGOTTI TOL100 GASOLINA": 13500.0,
    "ACABADORA VIBROMAK ACV 36\" GASOLINA": 14000.0, "ACABADORA WACKER CT36-5A GASOLINA": 14000.0, "ACABADORA WACKER CT36-5A GASOLINA (KIT PAS)": 300.0,
    "APARADOR DUC353Z BATERIA": 2824.5, "APARADOR HUSQVARNA 122 HD60 GASOLINA": 1380.0, "APARADOR MAKITA DUC353Z BATERIA": 2824.5,
    "APARADOR MAKITA EH6000WG GASOLINA": 2721.02, "ASPIRADOR AL320 220V": 15000.0, "ASPIRADOR ARTLAV AL320 220V": 15000.0,
    "ASPIRADOR BOSCH GAS15PS 220V": 1900.0, "ASPIRADOR DEWALT DWV010 220V": 3200.0, "ASPIRADOR ELETROLUX GT3000 PRO 220V": 400.0,
    "ASPIRADOR HIDROPO 2KW 70L": 2000.0, "ASPIRADOR HILTI VC 40L-X 220V": 7500.0, "ASPIRADOR HILTI VC20-U 220V": 5500.0,
    "ASPIRADOR NT30/1 ME CLASSIC 220V": 2300.0, "ASPIRADOR NT65/2 ECO 220V": 4700.0, "ASPIRADOR NT90/2 220V": 3600.0,
    "ASPIRADOR SH 8000 220V": 2700.0, "ASPIRADOR VC 40L X 220V": 7500.0, "ASPIRADOR VC20 U 220V": 5500.0,
    "BANHEIRO 1.00X1.00X2.50M": 1600.0, "BARRA de LIGACAO 2.05M": 51.0, "BARRA LIGACAO 1.50M": 40.0, "BETONEIRA 200/300L": 3800.0,
    "BETONEIRA 400L INFINITY BIVOLT": 5700.0, "BETONEIRA BTA 400L": 4700.0, "BETONEIRA CS 400L GASOLINA": 5280.0,
    "BETONEIRA Prof. 250L 220V": 3800.0, "BICO TURBO HD585": 300.0, "BOMBA D'agua BFB 2\" 1500 220V": 1500.0, "BOMBA D'agua BSA 1100 2\" 220V": 1600.0,
    "COMPACTADOR ate 72KG GASOLINA": 15550.0, "COMPRESSOR AR DIRETO AIR PLUS 2.3 220V": 2000.0, "CONTAINER 2.00X2.10X3.00": 7500.0,
    "GERADOR 13KVA BFGE13000 GASOLINA": 8140.0, "GUINCHO de COLUNA 350KG 220V": 5730.0, "LAVADORA AP HD 585 PROFI S 220V": 2600.0,
    "MARTELETE 7.9KG TE700AVR 220V": 6770.0, "PLACA VIBRATORIA REVERSIVEL CR3 GASOLINA": 24500.0, "ROMPEDOR 29.9KG TE3000 AVR 220V": 23980.0
}

CATALOGO_EQUIPAMENTOS = {" ".join(k.split()): v for k, v in RAW_CATALOGO.items()}
OPCAO_OUTRO = "➕ OUTRO EQUIPAMENTO (Manual)"
opcoes_equipamentos = sorted(list(CATALOGO_EQUIPAMENTOS.keys())) + [OPCAO_OUTRO]

# ÁREA CENTRAL
st.title("🛡️ Central de Risco e Crédito")
st.markdown("Bem-vindo ao portal unificado de validação de locações.")

abas = st.tabs(["🚀 Nova Análise", "📊 Dashboard Executivo", "📋 Histórico Geral"] if eh_master else ["🚀 Nova Análise", "📋 Meu Histórico"])

# --- ABA 1: FORMULÁRIO ---
with abas[0]:
    with st.container(border=True):
        st.markdown("### 1️⃣ Dados do Cliente e Operação")
        col_a1, col_a2 = st.columns(2)
        
        with col_a1:
            loja = st.selectbox("🏢 Filial Responsável", [
                "087 - Blumenau", "213 - Indaial", "350 - Itapema", "250 - Balneário Camboriú",
                "284 - Jaraguá do Sul", "299 - Brusque", "360 - Blumenau 02", "503 - Timbó",
                "560 - Camboriú", "636 - Guaramirim", "695 - Tijucas", "733 - São Bento do Sul"
            ]) if eh_master else usr_info["filial"]
            
            if not eh_master: 
                st.text_input("🏢 Filial Responsável", value=loja, disabled=True)
            
            tipo_cliente = st.radio("👤 Tipo de Cadastro", ["Pessoa Física (PF)", "Pessoa Jurídica (PJ)"], horizontal=True)
            nome_cliente = st.text_input("Nome Completo ou Razão Social" if tipo_cliente == "Pessoa Jurídica (PJ)" else "Nome Completo do Cliente")
            
            subtipo_pj, nome_solicitante, contato_solicitante = None, None, None
            if tipo_cliente == "Pessoa Jurídica (PJ)":
                subtipo_pj = st.selectbox("🏢 Natureza Jurídica", ["Empresa Padrão (LTDA/SA)", "Condomínio", "MEI"])
                col_pj1, col_pj2 = st.columns(2)
                with col_pj1:
                    nome_solicitante = st.text_input("Quem está solicitando no balcão/WhatsApp?" if subtipo_pj != "Condomínio" else "Nome do Síndico Responsável")
                with col_pj2:
                    contato_solicitante = st.text_input("E-mail corporativo ou WhatsApp")
                
                if subtipo_pj == "Empresa Padrão (LTDA/SA)":
                    st.info("📌 **Documentação:** Contrato Social + Doc do Sócio + Relatório Serasa.")
                elif subtipo_pj == "Condomínio":
                    st.warning("🏢 **Regra:** Ata de Eleição + Doc do Síndico (assinatura obrigatória).")
                elif subtipo_pj == "MEI":
                    st.info("🏪 **Regra MEI:** Cartão CNPJ/CCMEI + Doc Titular + Comprovante de Endereço + Serasa.")

        with col_a2:
            referencias = ""
            if tipo_cliente == "Pessoa Física (PF)":
                st.warning("⚠️ **Atenção:** Pagamento à vista (Débito/Pix) é obrigatório para Pessoa Física.")
                forma_pagamento = st.selectbox("Condição de Pagamento Permitida", ["À Vista / Débito / Pix (Antecipado)"])
            else:
                forma_pagamento = st.selectbox("💳 Condição de Pagamento Solicitada", ["À Vista / Débito / Pix", "Boleto 7 dias", "Boleto 14 dias", "Boleto 21 dias", "Boleto 28 dias"])
                if "Boleto" in forma_pagamento:
                    referencias = st.text_area("📞 Feedback das Referências Comerciais", placeholder="Descreva aqui o que as empresas consultadas falaram sobre os hábitos de pagamento deste CNPJ...")

    with st.container(border=True):
        st.markdown("### 2️⃣ Equipamento")
        equip_sel = st.selectbox("🔍 Buscar Equipamento (Digite para pesquisar)", opcoes_equipamentos, index=None)
        equip_nome = equip_sel
        val_equip = CATALOGO_EQUIPAMENTOS.get(equip_sel, 0.0) if equip_sel != OPCAO_OUTRO else 0.0
        
        if equip_sel == OPCAO_OUTRO:
            ce1, ce2 = st.columns(2)
            with ce1: equip_nome = st.text_input("Nome do Equipamento (Manual)")
            with ce2: val_equip = st.number_input("Valor de Reposição Base (R$)", value=3000.0)
        elif equip_sel:
            st.success(f"💵 Valor Oficial de Risco da Máquina: **R$ {val_equip:,.2f}**")

    with st.container(border=True):
        st.markdown("### 📎 3️⃣ Documentação Base")
        documentos = st.file_uploader("Arraste PDFs, CNH, Contrato Social, Serasa/Consult Center", accept_multiple_files=True, type=['png', 'jpg', 'jpeg', 'pdf'])

    st.write("<br>", unsafe_allow_html=True)
    if st.button("🚀 INICIAR ANÁLISE DE RISCO", type="primary", use_container_width=True):
        if not nome_cliente or not equip_nome or not documentos:
            st.error("⚠️ Por favor, preencha as 3 etapas (Cliente, Equipamento e Anexos) antes de iniciar.")
        elif not CHAVE_API or len(CHAVE_API) < 5:
            st.error("❌ Por favor, configure a chave de API nos Secrets do Streamlit ou na barra lateral para continuar.")
        else:
            with st.spinner('A IA está processando as matrizes de risco, lendo documentos e cruzando bases...'):
                try:
                    payload_parts = []
                    for doc in documentos:
                        b64_data = base64.b64encode(doc.getvalue()).decode("utf-8")
                        payload_parts.append({
                            "inline_data": {
                                "mime_type": doc.type,
                                "data": b64_data
                            }
                        })

                    prompt = f"""
                    Você é o Analista Master de Risco Financeiro e Fraude da Casa do Construtor.
                    
                    DADOS DA OPERAÇÃO:
                    - Cliente: {nome_cliente}
                    - Natureza: {tipo_cliente} ({subtipo_pj if subtipo_pj else 'Pessoa Física'})
                    - Quem solicitou (Contato): {nome_solicitante} | {contato_solicitante}
                    - Equipamento: {equip_nome} (Valor: R$ {val_equip:,.2f})
                    - Condição Solicitada: {forma_pagamento}
                    - Referências: {referencias if referencias else 'Nenhuma informada'}

                    =========================================
                    📜 MATRIZ ESTRITA DE POLÍTICA DE CRÉDITO
                    =========================================
                    Siga RIGOROSAMENTE estas regras para aprovar, rebaixar prazo ou reprovar o cadastro:

                    REGRA 1 - PESSOA FÍSICA (PF):
                    - Pagamento deve ser estritamente À Vista / Antecipado. Destaque essa regra no seu parecer.

                    REGRA 2 - PESSOA JURÍDICA (MEI e CONDOMÍNIOS):
                    - Condomínios: Prazo máximo permitido é 7 dias (boleto). O Síndico atual DEVE assinar o contrato (veja na Ata).
                    - MEI: Prazo máximo permitido é 7 dias. Não conceda prazos maiores sob nenhuma hipótese.

                    REGRA 3 - PESSOA JURÍDICA (Empresa Padrão LTDA/SA):
                    A aprovação de boletos DEPENDE dos dados extraídos do Serasa e Referências:
                    A) Idade da Empresa: Se a empresa tem menos de 1 ano de abertura, O PRAZO MÁXIMO DEVE SER CORTADO PARA 7 DIAS.
                    B) Referências Comerciais: Se as referências forem ausentes, o prazo DEVE SER REDUZIDO para À Vista ou 7 dias.
                    C) Restrições SPC/Serasa: 
                       - Protestos ou dívidas VINCULADOS AO SETOR DA CONSTRUÇÃO/LOCAÇÃO: [REPROVADO] (Alto risco de perda do equipamento).
                       - Dívidas em outros setores > R$ 1.000: [APROVADO COM RESTRIÇÃO], cortando o pagamento SOMENTE PARA À VISTA.
                       - Ficha Totalmente Limpa + Boas Referências: Você pode [APROVAR] o prazo solicitado.

                    DIRETRIZES DE FRAUDE (TERCEIROS NA PJ):
                    - Analise se a pessoa que pediu ({nome_solicitante}) tem o e-mail oficial da empresa ou consta no quadro societário (Contrato Social). Se for um terceiro desconhecido, emita um ALERTA VERMELHO exigindo "Pedido de Compra Oficial e Autorização".

                    FORMATO DA RESPOSTA:
                    - Status: [APROVADO], [APROVADO COM RESTRIÇÃO (ex: Prazo reduzido)] ou [REPROVADO].
                    - Quadro Resumo do Crédito (Tempo de Abertura, Situação Serasa, Resumo Referências).
                    - Parecer Detalhado (Por que aprovou? Por que reduziu o prazo? Por que bloqueou?).
                    - Destaque: Para Pessoa Física lembre expressamente que o pagamento é À Vista.
                    """

                    payload_parts.append({"text": prompt})

                    url_api = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
                    headers_api = {
                        "Content-Type": "application/json",
                        "x-goog-api-key": CHAVE_API
                    }
                    data_api = {
                        "contents": [{
                            "parts": payload_parts
                        }],
                        "generationConfig": {
                            "temperature": 0.1
                        }
                    }

                    res = requests.post(url_api, json=data_api, headers=headers_api)

                    if res.status_code == 200:
                        res_json = res.json()
                        texto_resultado = res_json['candidates'][0]['content']['parts'][0]['text']
                        
                        st.session_state['resultado_parecer'] = texto_resultado
                        st.session_state['nome_cliente_analisado'] = nome_cliente
                        
                        pdf = gerar_pdf_parecer(nome_cliente, tipo_cliente, forma_pagamento, loja, equip_nome, val_equip, texto_resultado)
                        st.session_state['pdf_bytes'] = pdf

                        salvar_no_historico(loja, usr_info['nome'], nome_cliente, tipo_cliente, equip_nome, val_equip, forma_pagamento, texto_resultado)
                    else:
                        st.error(f"❌ Erro na API (Código {res.status_code}): {res.text}")

                except Exception as e:
                    st.error(f"Erro na execução da análise: {e}")

    if 'resultado_parecer' in st.session_state and st.session_state['resultado_parecer']:
        st.success("✅ Avaliação Finalizada!")
        st.markdown(st.session_state['resultado_parecer'])
        st.download_button("📄 Baixar Relatório Oficial (PDF)", data=st.session_state['pdf_bytes'], file_name=f"Relatorio_{nome_cliente.replace(' ', '_')}.pdf", mime="application/pdf", type="primary")

# --- ABA 2 & 3: DASHBOARD E HISTÓRICO ---
with abas[1]:
    if eh_master:
        st.markdown("### 📈 Visão Consolidada de Risco (Rede)")
        if os.path.exists(ARQUIVO_HISTORICO):
            df = pd.read_csv(ARQUIVO_HISTORICO, sep=";")
            df_hoje = df[df['Data_Dia'] == datetime.now().strftime("%d/%m/%Y")] if 'Data_Dia' in df.columns else df
            
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Análises Hoje", len(df_hoje))
            m2.metric("Demandas PJ", len(df[df['Tipo_Pessoa'].str.contains('PJ', na=False)]))
            m3.metric("Aprovações Limpas", len(df[df['Status Decisão'] == 'APROVADO']))
            m4.metric("Barrados/Reprovados", len(df[df['Status Decisão'] == 'REPROVADO']))
            
            st.markdown("#### Volume Operacional por Filial")
            st.bar_chart(df['Filial'].value_counts())
        else: st.info("Aguardando os primeiros dados operacionais...")
    else:
        st.markdown("### 📋 Log de Operações da Unidade")
        if os.path.exists(ARQUIVO_HISTORICO):
            df = pd.read_csv(ARQUIVO_HISTORICO, sep=";")
            st.dataframe(df[df['Filial'] == usr_info['filial']], use_container_width=True)

if eh_master and len(abas) > 2:
    with abas[2]:
        st.markdown("### 📋 Tabela Geral de Auditoria")
        if os.path.exists(ARQUIVO_HISTORICO):
            df = pd.read_csv(ARQUIVO_HISTORICO, sep=";")
            st.dataframe(df, use_container_width=True)
            st.download_button("📊 Exportar para Excel/CSV", df.to_csv(index=False, sep=";").encode('utf-8-sig'), "Auditoria_Risco_CDC.csv", "text/csv")
