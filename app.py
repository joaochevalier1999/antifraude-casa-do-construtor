import streamlit as st
import base64
import io
import html
import re
import os
import pandas as pd
from datetime import datetime
from google import genai
from google.genai import types

# Dependências para geração de PDF
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# --- CONFIGURAÇÃO DA PÁGINA E CSS CUSTOMIZADO ---
st.set_page_config(page_title="Portal Antifraude - Casa do Construtor", page_icon="🏗️", layout="wide", initial_sidebar_state="expanded")

# CSS para injetar a identidade visual da Casa do Construtor
st.markdown("""
    <style>
    /* Fundo da tela inteira */
    .stApp {
        background-color: #F4F6F9;
    }
    /* Títulos na cor Azul Marinho */
    h1, h2, h3 {
        color: #003366 !important;
        font-family: 'Arial', sans-serif;
    }
    /* Estilização do Botão Primário (Azul Marinho com Hover Amarelo) */
    div.stButton > button[kind="primary"] {
        background-color: #003366;
        color: #FFFFFF;
        border-radius: 8px;
        border: 2px solid #003366;
        padding: 10px 24px;
        font-weight: bold;
        transition: all 0.3s;
    }
    div.stButton > button[kind="primary"]:hover {
        background-color: #FBC02D;
        color: #003366;
        border: 2px solid #FBC02D;
    }
    /* Efeito de Card nas caixas de contêiner */
    div[data-testid="stVerticalBlock"] > div[style*="border"] {
        border-radius: 12px;
        background-color: #FFFFFF;
        box-shadow: 0px 4px 12px rgba(0, 0, 0, 0.05);
        border: 1px solid #E0E0E0;
        padding: 15px;
    }
    /* Ocultar marca do Streamlit */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
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

# --- TELA DE LOGIN (Estilo Portal) ---
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

# --- CHAVE DA API ---
if "GEMINI_API_KEY" in st.secrets:
    CHAVE_API = st.secrets["GEMINI_API_KEY"]
else:
    CHAVE_API = "AQ.Ab8RN6LJtRqJbejd1BORxjjCjfTb0iKyqEHCi8qQjMBwbRW8dA"

@st.cache_resource
def obter_cliente_genai(api_key: str):
    return genai.Client(api_key=api_key)

try:
    client = obter_cliente_genai(CHAVE_API)
except Exception as e:
    st.error(f"Erro de API: {e}")
    client = None

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

# --- PDF GENERATOR ---
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
        if linha.strip(): story.append(Paragraph(formatar_texto_para_reportlab(linha.strip()), body_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# --- CATÁLOGO COMPLETO DE EQUIPAMENTOS ---
RAW_CATALOGO = {
    "ACABADORA PA ACABAMENTO 36\"": 200.0,
    "ACABADORA ACV 36\" GASOLINA": 14000.0,
    "ACABADORA BFG 100 GASOLINA": 13500.0,
    "ACABADORA BUFFALO BFG 100 GASOLINA": 13500.0,
    "ACABADORA CSM AC36 GASOLINA": 11900.0,
    "ACABADORA CT36 5A GASOLINA": 14000.0,
    "ACABADORA CT36 5A GASOLINA (KIT PAS)": 300.0,
    "ACABADORA FINITI F36 GASOLINA": 10000.0,
    "ACABADORA HUSQVARNA BG375 GASOLINA": 13500.0,
    "ACABADORA MAC 36 GASOLINA": 13500.0,
    "ACABADORA MENEGOTTI MAC 36 GASOLINA": 13500.0,
    "ACABADORA MENEGOTTI TOL100 GASOLINA": 13500.0,
    "ACABADORA VIBROMAK ACV 36\" GASOLINA": 14000.0,
    "ACABADORA WACKER CT36-5A GASOLINA": 14000.0,
    "ACABADORA WACKER CT36-5A GASOLINA (KIT PAS)": 300.0,
    "APARADOR DUC353Z BATERIA": 2824.5,
    "APARADOR HUSQVARNA 122 HD60 GASOLINA": 1380.0,
    "APARADOR MAKITA DUC353Z BATERIA": 2824.5,
    "APARADOR MAKITA EH6000WG GASOLINA": 2721.02,
    "ASPIRADOR AL320 220V": 15000.0,
    "ASPIRADOR ARTLAV AL320 220V": 15000.0,
    "ASPIRADOR BOSCH GAS15PS 220V": 1900.0,
    "ASPIRADOR DEWALT DWV010 220V": 3200.0,
    "ASPIRADOR ELETROLUX GT3000 PRO 220V": 400.0,
    "ASPIRADOR HIDROPO 2KW 70L": 2000.0,
    "ASPIRADOR HILTI VC 40L-X 220V": 7500.0,
    "ASPIRADOR HILTI VC20-U 220V": 5500.0,
    "ASPIRADOR NT30/1 ME CLASSIC 220V": 2300.0,
    "ASPIRADOR NT65/2 ECO 220V": 4700.0,
    "ASPIRADOR NT90/2 220V": 3600.0,
    "ASPIRADOR SH 8000 220V": 2700.0,
    "ASPIRADOR VC 40L X 220V": 7500.0,
    "ASPIRADOR VC20 U 220V": 5500.0,
    "BANHEIRO 1.00X1.00X2.50M": 1600.0,
    "BARRA de LIGACAO 2.05M": 51.0,
    "BARRA LIGACAO 1.50M": 40.0,
    "BETONEIRA 200/300L": 3800.0,
    "BETONEIRA 400L INFINITY BIVOLT": 5700.0,
    "BETONEIRA BTA 400L": 4700.0,
    "BETONEIRA CS 400L GASOLINA": 5280.0,
    "BETONEIRA Prof. 250L 220V": 3800.0,
    "BICO TURBO HD585": 300.0,
    "BOMBA D'agua BFB 2\" 1500 220V": 1500.0,
    "BOMBA D'agua BSA 1100 2\" 220V": 1600.0,
    "BOMBA D'agua LKS 750P 220V": 395.09,
    "BOMBA D'agua MANGOTE 2\" 5.00M": 3000.0,
    "BOMBA D'agua MANGUEIRA 3\" 4.00M": 1000.0,
    "BOMBA D'agua PF1010 1\" 1/2 220V": 640.5,
    "BOMBA D'agua QDX 3\" 220V": 1239.0,
    "BOMBA D'agua RS 1100 220V": 2000.0,
    "BOMBA D'agua SPV1100F 3\" 220V": 2500.0,
    "BOMBA D'agua TW V1100 3\" 220V": 2500.0,
    "BOMBA D'agua XP 750 220V": 1300.0,
    "BOMBA Elet. AIRLESS 1.8HP D3.0X 220V": 5000.0,
    "BOMBA Elet. AIRLESS MMA370 220V": 2000.0,
    "BROCA ()": 300.0,
    "BROCA Hel. 300X800MM": 175.03,
    "CACAMBA P/GUINCHO 50L": 270.0,
    "CAMERA TERMICA C2": 5100.0,
    "CAMERA TERMICA C3 X WIFI": 5600.0,
    "CARRINHO de MAO de MAO": 200.0,
    "CARRINHO de MAO FORTE 60LTS": 480.0,
    "CARRINHO TRANSPORTE CILINDRO GAS": 300.0,
    "CHAVE ESMERILHADEIRA 4,5\"": 300.0,
    "CHAVE para MAKITAO": 300.0,
    "CHAVE SERRA MADEIRA": 300.0,
    "CHAVE TUPIA": 300.0,
    "CHAVES (CJO 2) para SERRA MARMORE 4,5\"": 300.0,
    "CLIMATIZADOR de AR BRYSA MB9000": 4200.0,
    "COMPACTADOR ate 72KG GASOLINA": 15550.0,
    "COMPACTADOR SRV550 GASOLINA": 18200.0,
    "COMPRESSOR AR DIRETO AIR PLUS 2.3 220V": 2000.0,
    "COMPRESSOR AR DIRETO G3 220V": 500.0,
    "COMPRESSOR AR DIRETO JET MASTER 110/220V": 600.0,
    "COMPRESSOR AR DIRETO Prof. 220V": 2000.0,
    "COMPRESSOR C/RESER 10SS/110L BIVOLT": 4100.0,
    "COMPRESSOR C/RESER 7.4BPI G2 28L BIVOLT": 850.0,
    "COMPRESSOR C/RESER CJ7.4/28L 110/220V": 2000.0,
    "COMPRESSOR C/RESER CSA 8.2/25 PRATIC 220V": 600.0,
    "COMPRESSOR C/RESER CSI 8.5/25 MONO 220V": 3000.0,
    "COMPRESSOR C/RESER CSL 10/100 220V": 3000.0,
    "COMPRESSOR C/RESER MC7.6/21L 2HP 220V": 850.0,
    "COMPRESSOR C/RESER RCH 200L 220V": 7000.0,
    "CONDUTOR de ENTULHO BOCA UP171": 270.0,
    "CONDUTOR de ENTULHO BOCAL UP171": 270.0,
    "CONDUTOR de ENTULHO DUTO COLETOR AZUL": 189.0,
    "CONDUTOR de ENTULHO DUTO COLETOR UP171": 252.35,
    "CONDUTOR de ENTULHO DUTO SIMPLES AZUL": 238.0,
    "CONDUTOR de ENTULHO DUTO SIMPLES RETO UP170": 250.0,
    "CONDUTOR de ENTULHO REFORCO": 160.0,
    "CONDUTOR de ENTULHO SUPORTE METALICO": 169.0,
    "CONDUTOR de ENTULHO SUPORTE METALICO FIXACAO UP43": 167.0,
    "CONDUTOR de ENTULHO SUPORTE METALICO LAJE": 82.6,
    "CONTAINER 2.00X2.10X3.00": 7500.0,
    "Cort. PISO/PORCELANATO ZAPP1250 220V": 6000.0,
    "CORTADORA BLOCO SAINT GOBAIN CM 41 220V": 6200.0,
    "CORTADORA de PAREDE BRIC35 220V": 5600.0,
    "CORTADORA de PAREDE DCH 300 X 220V": 12000.0,
    "CORTADORA GRAMA PLM4627N GASOLINA": 4515.0,
    "CORTADORA PISO BFG 350 GASOLINA": 4700.0,
    "CORTADORA PISO BFS 130 GASOLINA": 10000.0,
    "CORTADORA PISO CPV 460 GASOLINA": 12000.0,
    "CORTADORA PISO FS 400 GASOLINA": 9000.0,
    "CORTADORA PISO K4000 WET 220V": 5200.0,
    "CORTADORA PISO K760 GASOLINA": 4800.0,
    "CORTADORA PISO SAINT GOBAIN C13E GASOLINA": 10000.0,
    "CORTADORA PORTATIL K4000 WET 220V": 6000.0,
    "CORTADORA PORTATIL K760 GASOLINA": 12000.0,
    "DESEMPENADEIRA MDE 220V": 750.0,
    "DESENTUPIDORA TL 50 BIVOLT": 4176.0,
    "DETECTOR MATERIAIS DTECT 200": 3500.0,
    "DETECTOR MATERIAIS DTECT120": 1700.0,
    "DIAGONAL METALICA 2.12M": 70.0,
    "DIAGONAL X 2.28M": 80.0,
    "DISCO CONCRETO/ASFALTO 350 MM": 250.0,
    "ELEMENTO VERTICAL 0.90X2.00M": 158.86,
    "ELEMENTO VERTICAL C/ESC. 0.90X2.00M": 220.02,
    "ENCERADEIRA a 40 220V": 2900.0,
    "ENCERADEIRA CL400 220V": 2500.0,
    "ENGATE RAPIDO LAVADORA": 150.0,
    "ENGATE RAPIDO para LAVADORA": 250.0,
    "EQUIPTOS/ACESS. ADAPTADOR de BROCA": 140.0,
    "EQUIPTOS/ACESS. ADAPTADOR de BROCA Exten.perfur": 140.0,
    "EQUIPTOS/ACESS. BICO TURBO": 300.0,
    "EQUIPTOS/ACESS. BROCA": 300.0,
    "EQUIPTOS/ACESS. BROCA 8\" PERFURADOR de SOLO": 300.0,
    "EQUIPTOS/ACESS. BROCA PONTEIRA T3000": 300.0,
    "EQUIPTOS/ACESS. CACAMBA 50L": 270.0,
    "EQUIPTOS/ACESS. CARREGADOR KIT BATERIA": 810.0,
    "EQUIPTOS/ACESS. CARRINHO TROLLEY KV760": 3070.0,
    "EQUIPTOS/ACESS. CESTA 90L": 400.0,
    "EQUIPTOS/ACESS. CORTESIA CARRETEL": 300.0,
    "EQUIPTOS/ACESS. DETERGENTE": 300.0,
    "EQUIPTOS/ACESS. DISCO": 250.0,
    "EQUIPTOS/ACESS. DISCO FIBRA": 250.0,
    "EQUIPTOS/ACESS. DISCO FLOTACAO 36\"": 600.0,
    "EQUIPTOS/ACESS. DISCO POLI": 250.0,
    "EQUIPTOS/ACESS. DISCO SERRA 7": 250.0,
    "EQUIPTOS/ACESS. DIVERSOS BROCA": 300.0,
    "EQUIPTOS/ACESS. DIVERSOS BROCA 1/2": 300.0,
    "EQUIPTOS/ACESS. DIVERSOS BROCA 8\" PERFURADOR": 300.0,
    "EQUIPTOS/ACESS. DIVERSOS CORTESIA": 300.0,
    "EQUIPTOS/ACESS. DIVERSOS CORTESIA EXAUSTOR": 300.0,
    "EQUIPTOS/ACESS. DIVERSOS CORTESIA TRANSPORTE": 300.0,
    "EQUIPTOS/ACESS. DIVERSOS DISCO 24\"": 600.0,
    "EQUIPTOS/ACESS. DIVERSOS DISCO ESMER 9\"": 250.0,
    "EQUIPTOS/ACESS. DIVERSOS DISCO FLOTACAO 36\"": 600.0,
    "EQUIPTOS/ACESS. DIVERSOS DISCO SERRA 9": 250.0,
    "EQUIPTOS/ACESS. DIVERSOS LAMINA SERRA": 100.0,
    "EQUIPTOS/ACESS. DIVERSOS MANGUEIRA AP 20M": 300.0,
    "EQUIPTOS/ACESS. DIVERSOS MANGUEIRA FLEX 20M": 200.0,
    "EQUIPTOS/ACESS. DIVERSOS MANGUEIRA PRESSAO 20M": 400.0,
    "EQUIPTOS/ACESS. DIVERSOS MASCARA SOLDA": 250.0,
    "EQUIPTOS/ACESS. DIVERSOS PA": 200.0,
    "EQUIPTOS/ACESS. DIVERSOS PA SDSMAX": 200.0,
    "EQUIPTOS/ACESS. DIVERSOS PEDRA G100/120": 800.0,
    "EQUIPTOS/ACESS. DIVERSOS PONTEIRO": 150.0,
    "EQUIPTOS/ACESS. DIVERSOS PONTEIRO SDSMAX": 150.0,
    "EQUIPTOS/ACESS. DIVERSOS PONTEIRO SEXTAVADO": 150.0,
    "EQUIPTOS/ACESS. DIVERSOS SEGM DESBASTE": 500.0,
    "EQUIPTOS/ACESS. DIVERSOS SEGM DESBASTE G20 SETA": 500.0,
    "EQUIPTOS/ACESS. DIVERSOS SEGM DESBASTE GR100/120": 500.0,
    "EQUIPTOS/ACESS. DIVERSOS SEGM FRESAGEM DIAM G100": 450.0,
    "EQUIPTOS/ACESS. DIVERSOS TALHADEIRA": 150.0,
    "EQUIPTOS/ACESS. DIVERSOS TALHADEIRA SDSMAX": 150.0,
    "EQUIPTOS/ACESS. DIVERSOS TALHADEIRA SEXTAVADO": 150.0,
    "EQUIPTOS/ACESS. DIVERSOS TOCHA ELET 7018": 270.0,
    "EQUIPTOS/ACESS. MANGUEIRA 20M": 250.0,
    "EQUIPTOS/ACESS. MANGUEIRA AP 20M": 300.0,
    "EQUIPTOS/ACESS. PEDESTAL": 1500.0,
    "EQUIPTOS/ACESS. PODADOR KA HL": 500.0,
    "EQUIPTOS/ACESS. PONTEIRO": 150.0,
    "EQUIPTOS/ACESS. PONTEIRO SDSMAX": 150.0,
    "EQUIPTOS/ACESS. PONTEIRO SEXTAVADO": 850.0,
    "EQUIPTOS/ACESS. PONTEIRO TE HX SM 40": 700.0,
    "EQUIPTOS/ACESS. PONTEIRO TE SPX SM43": 630.0,
    "EQUIPTOS/ACESS. PROLONGADOR PERFURADOR": 350.0,
    "EQUIPTOS/ACESS. REBOLO de CORTE 25MM": 250.0,
    "EQUIPTOS/ACESS. SEGM DESBASTE": 500.0,
    "EQUIPTOS/ACESS. SEGM FRESAGEM DIAM G100": 450.0,
    "EQUIPTOS/ACESS. SEGM FRESAGEM DIAM G100 CORTE": 450.0,
    "EQUIPTOS/ACESS. TALHADEIRA": 900.0,
    "EQUIPTOS/ACESS. TALHADEIRA SDSMAX": 150.0,
    "EQUIPTOS/ACESS. TALHADEIRA SEXTAVADO": 850.0,
    "EQUIPTOS/ACESS. TALHADEIRA TE HX FM 40": 700.0,
    "EQUIPTOS/ACESS. TALHADEIRA TE SPX SM43": 630.0,
    "EQUIPTOS/ACESSORIOS TALHADEIRA SDSMAX": 150.0,
    "ESCADA ABRIR ALUMINIO 1.50 7D": 505.0,
    "ESCADA ABRIR FIBRA 4.80X8.40 28D": 1800.0,
    "ESCADA ABRIR FIBRA 5.00 16D": 2120.0,
    "ESCADA ABRIR MADEIRA 3.78 14D": 1550.0,
    "ESCADA EXTENSAO FIBRA 6.60X11.70 39D": 3000.0,
    "ESCADA EXTENSAO/ABRIR 09 DEG 2.70/4.72": 300.0,
    "ESCADA EXTENSAO/ABRIR 3.90X6.60 24D": 1380.0,
    "ESCADA EXTENSAO/ABRIR FIBRA 3.10X5.24 19D": 950.0,
    "ESCADA METALICA 1.00M": 170.0,
    "ESCORA METALICA de 2.0 a 3.1": 420.0,
    "ESMERILHADEIRA 4\" 1/2 G12SNDB": 500.0,
    "ESMERILHADEIRA 4\" 1/2 GWS 850 220V": 550.0,
    "ESMERILHADEIRA 5\" DGA504 BATERIA": 1150.0,
    "ESMERILHADEIRA 7\" GWS 26 180 220V": 1000.0,
    "ESQUADRILHADEIRA GCM 12 220V": 6230.67,
    "ESQUADRILHADEIRA LS1017L 220V": 3255.0,
    "EXAUSTOR EP50M42 220V": 1100.0,
    "EXTENSAO ELETRICA 30M": 400.0,
    "EXTENSAO ELETRICA 30M 3X6.00MM": 500.0,
    "EXTRATORA AEP150 220V": 3500.0,
    "EXTRATORA EP116 LAVACLEAN 220V": 3000.0,
    "EXTRATORA PUZZI 4/20 CLASSIC 220V": 2100.0,
    "FIXADOR BX 3 ME BATERIA": 6007.0,
    "FIXADOR BX 4 22 01 M3 BATERIA": 10050.0,
    "FIXADOR FA172N": 1200.0,
    "FRESADORA FN 1650 220V": 2240.0,
    "FURADEIRA 5/8\" DS5000 220V": 1365.0,
    "FURADEIRA IMP.1/2 HP2050H 220V": 1050.0,
    "FURADEIRA IMPACTO 1/2\" DW505 220V": 950.0,
    "FURADEIRA Imp. 1/2\" GSB20 2 RE 220V": 923.76,
    "FURADEIRA Imp. 5/8\" GSB30 2 220V": 2243.14,
    "FURADEIRA MAGNETICA GBM 50 2 220V": 5948.42,
    "GERADOR 13KVA BFGE13000 GASOLINA": 8140.0,
    "GERADOR 6 a 10 KW GASOLINA": 6000.0,
    "GERADOR 8KVA ES 8000 GASOLINA": 3000.0,
    "GUARDA CORPO C/PORTA 1.50M": 300.0,
    "GUARDA CORPO FRONTAL 1.00X2.05M": 250.0,
    "GUARDA CORPO S/PORTA 1.50M": 250.0,
    "GUARDA CORPO S/PORTA C/ENC. 1.00M": 200.0,
    "GUARDA CORPO S/PORTA C/ROD. 1.50M": 250.0,
    "GUINCHO de COLUNA 350KG 220V": 5730.0,
    "GUINCHO de COLUNA ACIMA 200KG 220V": 5200.0,
    "GUINCHO de COLUNA BALDE": 444.05,
    "GUINCHO de COLUNA ate 200KG 220V": 5200.0,
    "GUINCHO de ELEVACAO 500KG TRIFASICO": 12000.0,
    "INVERSORA FLAMA 221 220V": 995.0,
    "INVERSORA JOY 133 DV BIFASICO": 396.0,
    "INVERSORA KAB180 BIVOLT": 730.0,
    "INVERSORA MULTI MIG 160S 220V": 2000.0,
    "KIT PAS ACABADORA CT36 5A": 300.0,
    "LAVADORA AP 2500 PSI": 2700.0,
    "LAVADORA AP G2500 OH GASOLINA": 7500.0,
    "LAVADORA AP GHP 4 50 220V": 2500.0,
    "LAVADORA AP HD 10/25 MAXI TRIFASICA": 23000.0,
    "LAVADORA AP HD 585 PROFI S 220V": 2600.0,
    "LAVADORA AP HD 6/15 C 220V": 4000.0,
    "LAVADORA AP HD 6/15 CAGE PLUS 220V": 4000.0,
    "LAVADORA AP J12000 220V": 13000.0,
    "LAVADORA AP LPROFI 2000 220V": 4500.0,
    "LAVADORA/SECADORA 30/4C 220V": 7886.0,
    "LAVADORA/SECADORA BD50/50C 220V": 19000.0,
    "LIXADEIRA ANGULAR 7\" GWS 22U 220V": 900.0,
    "LIXADEIRA ANGULAR D28493": 800.0,
    "LIXADEIRA CINTA 9404 220V": 1995.0,
    "LIXADEIRA ORBITAL D26441 220V": 800.0,
    "LIXADEIRA ORBITAL GSS 10 SB 18V": 450.0,
    "LIXADEIRA OSCILANTE 1070.7 220V": 650.0,
    "LIXADEIRA OSCILANTE GSS 23 AE 220V": 650.0,
    "LIXADEIRA PAREDE GTR 550 220V": 1750.0,
    "LIXADEIRA PAREDE KUW45 220V": 1000.0,
    "LIXADEIRA ROTO 5 220V": 2200.0,
    "LIXADEIRA ROTO ORB GEX 40 150 220V": 1850.0,
    "LIXADEIRA ROTORBITAL BO6030 220V": 2700.0,
    "LIXADEIRA TETO DMJ700A 220V": 1600.0,
    "LIXADEIRA TETO LXB850 CS 220V": 2550.0,
    "LIXADEIRA de CINTA GBS 75AE 220V": 1850.0,
    "MANGOTE 35MM 5.00M": 1900.0,
    "MANGUEIRA 10M para BOMBA D'agua": 300.0,
    "MANGUEIRA JARDIM 10 METROS": 300.0,
    "MANGUEIRA P/DESENTUPIR": 300.02,
    "MANGUEIRA PISTOLA LAVADORA 50M": 300.0,
    "MAQUINA CORTAR BLOCO 6L": 2361.37,
    "MAQUINA CORTAR MASTER 125": 1300.0,
    "MAQUINA CORTAR PISO": 320.0,
    "MARTELETE 5.6KG GSH 5 220V": 3000.0,
    "MARTELETE 6.75KG TE DH12 220V": 1600.0,
    "MARTELETE 7.9KG TE700AVR 220V": 6770.0,
    "MARTELETE Perfurador\\romp 3.1KG TE 3 220V": 3000.0,
    "MARTELETE Perfurador\\romp 3.1KG TE 3 ML 220V": 3000.0,
    "MARTELETE Perfurador\\romp 6.8KG GBH 5 40D 220V": 5000.0,
    "MARTELETE Perfurador\\romp 6KG RT RH 32 220V": 1000.0,
    "MARTELETE Perfurador\\romp 8.9KG GBH 8 45 DV 220V": 7100.0,
    "MARTELETE Perfurador\\romp 9.5KG TE70 220V": 5100.0,
    "MEDIDOR LASER GLR300HV": 3860.0,
    "MEDIDOR LASER GRL 250HV": 4803.21,
    "MEDIDOR LASER PM4 M": 2198.83,
    "MISTURADOR MEL1200 220V": 515.0,
    "MISTURADOR MF 270L 220V": 10780.0,
    "MISTURADOR ML 1400": 269.0,
    "MORSA": 300.0,
    "MOTOBOMBA B4T 710L 2\" GASOLINA": 5000.0,
    "MOTOR 1.5CV 220V": 2350.0,
    "MOTOR 1.5CV Dup. Isol. 220V": 2242.38,
    "MOTOVIBRADOR 2.0CV Dup. Isol.": 2700.0,
    "MOTOVIBRADOR 5.5HP GASOLINA": 2000.0,
    "MOTOVIBRADOR MGK 5,5 GASOLINA": 2000.0,
    "MULTICORTADORA ELETRICA 220V": 600.0,
    "MULTICORTADORA GOP 30 28 220V": 1300.0,
    "NIVEL DW088K": 1242.4,
    "PAINEL METALICO 1.00X1.50M": 300.0,
    "PAINEL METALICO VK 85 GASOLINA": 7800.0,
    "PARAFUSADEIRA 6802 BV 220V": 1261.04,
    "PARAFUSADEIRA BATERIA DECKER 9.6V": 300.0,
    "PARAFUSADEIRA DHP481 18V BATERIA": 1995.0,
    "PARAFUSADEIRA GSB 18 VE EC BATERIA": 1308.33,
    "PARAFUSADEIRA GSR 18 V": 1143.35,
    "PARAFUSADEIRA/FURADEIRA 3/8\" PFV 1801 BATERIA": 460.88,
    "PARAFUSADEIRA/FURADEIRA DHP453SFX8 P BATERIA": 1134.0,
    "PARAFUSADEIRA/FURADEIRA GSB 18V 50 BATERIA": 975.18,
    "PARAFUSADEIRA/FURADEIRA HP333DWYE 220V": 850.5,
    "PARAFUSADEIRA/FURADEIRA SF 6H A22 BATERIA": 1665.0,
    "PAS (KIT com 4) para ACABADORA PISO": 300.0,
    "PEDESTAL P/GUINCHO PG400": 1430.0,
    "PERFIL REGUA ALUMINIO 1.80M": 1100.0,
    "PERFURADOR 541EA GASOLINA": 2100.0,
    "PERFURATRIZ DMS240 220V": 12631.9,
    "PINADOR AF506 PNEUMATICO": 619.5,
    "PISO METALICO 0.37X2.00M": 330.0,
    "PISTOLA PINTURA ALTA PRESSAO": 290.03,
    "PISTOLA PINTURA AR DIRETO": 250.0,
    "PISTOLA PINTURA MEDIA PRESSAO": 100.0,
    "PLACA VIBRATORIA CF2 GASOLINA": 8800.0,
    "PLACA VIBRATORIA REVERSIVEL CR3 GASOLINA": 24500.0,
    "PLACA VIBRATORIA VK 85 GASOLINA": 7800.0,
    "PLAINA GHO 26 82 220V": 1100.0,
    "PLAINA KP0800 220V": 756.0,
    "PLATAFORMA RETRATIL PORTATIL": 500.0,
    "PODADOR DUC353Z BATERIA": 2824.5,
    "PODADOR GALHO 525P5S GASOLINA": 3159.19,
    "PODADOR GALHO HSE 61 220V": 750.0,
    "POLICORTE GCO 1424 220V": 1400.0,
    "POLICORTE LW1400 220V": 1533.0,
    "POLITRIZ GPO 14 CE 220V": 950.0,
    "POLITRIZ de PISO FP 06 220V": 15500.0,
    "POLITRIZ de PISO PL30 220V": 14600.0,
    "POLITRIZ e LIXADEIRA DGH 130 220V": 3300.0,
    "POLITRIZ e LIXADEIRA SH 49SP 220V": 1800.0,
    "PONTEIRA ROMPEDOR 10KG": 150.0,
    "PONTEIRO ESPECIAL": 150.0,
    "PONTEIRO ROMPEDOR 16/30 KG": 150.0,
    "PONTEIRO ROMPEDOR 30KG": 150.0,
    "PROJETOR PAREDE CV 08": 650.0,
    "REGUA GR240": 493.24,
    "REGUA VIBRATORIA MCD4 3.0M GASOLINA": 3500.0,
    "REGUA VIBRATORIA RVVK 3 GASOLINA": 4820.39,
    "RETIFICADORA GGS 27 L 220V": 720.0,
    "ROCADEIRA 143 R II GASOLINA": 2429.19,
    "ROCADEIRA BFG 52S 2T GASOLINA": 856.32,
    "ROCADEIRA LATERAL ELETRICA 220V": 900.03,
    "ROCADEIRA RBC412U GASOLINA": 2382.48,
    "RODA METALICA C/ROLAMENTO POLIURETANO": 230.0,
    "RODA METALICA C/ROLAMENTO POLIURETANO FREIO": 230.0,
    "RODAPE 2.05M": 150.0,
    "ROMPEDOR 10KG TE DH 1027 220V": 2000.0,
    "ROMPEDOR 14.6KG TC DH 1600/1 220V": 1850.0,
    "ROMPEDOR 18.5KG GSH 16 28 220V": 7900.0,
    "ROMPEDOR 27KG 220V": 11700.0,
    "ROMPEDOR 29.9KG TE3000 AVR 220V": 23980.0,
    "ROMPEDOR 31.3 KG HM1812 220V": 11260.0,
    "ROMPEDOR Perfurador\\r 11.3KG HR5201 220V": 5600.0,
    "SAPATA AJUSTAVEL": 65.0,
    "SERRA COPO": 245.0,
    "SERRA COPO 100MM M14 DIAMANTADO": 250.0,
    "SERRA COPO KIT 12": 450.0,
    "SERRA MADEIRA 9\" 5902B 220V": 1510.0,
    "SERRA MADEIRA GKS 67 220V": 1000.0,
    "SERRA MADEIRA GKS 7 1/4 220V": 800.0,
    "SERRA MADEIRA SCW 22 a BATERIA": 6800.0,
    "SERRA MARMORE 180MM 4107R 220V": 3070.0,
    "SERRA MARMORE GDC 150 220V": 500.0,
    "SERRA SABRE GSA 164J 18V BATERIA": 1200.0,
    "SERRA SABRE JR 3051 TK 220V": 1150.0,
    "SERRA TICO TICO GTS 75E": 700.0,
    "SERRA TICO TICO JV0600K 220V": 980.0,
    "SERRA TICO TICO MST 80 220V": 270.0,
    "SOLDA ELETRICA BANTAM 250 220V": 1000.02,
    "SOLDA ELETRICA BR 425DC 220V": 2907.03,
    "SOLDA ELETRICA PRO3200 260A 220V": 410.0,
    "SOLDA ELETRICA SS 160 220V": 700.0,
    "SOLDA ELETRICA TT 250 BIVOLT": 485.0,
    "SOLDA ELETRICA VULCANO PRO 3200 220V": 570.0,
    "SOPRADOR BG 56 GASOLINA": 1500.0,
    "SOPRADOR BHX2500G GASOLINA": 2010.0,
    "SOPRADOR BS 470 GASOLINA": 850.0,
    "SOPRADOR TERMICO GHG 2063 220V": 850.0,
    "SOPRADOR TERMICO GHG 630 DCE 220V": 850.0,
    "SOPRADOR TERMICO HG5030K 220V": 410.0,
    "SOPRADOR TERMICO STL 2000 220V": 150.0,
    "TALHA TC 1000 5.00M": 670.0,
    "TALHA ate 03 ΤΟΝ": 800.0,
    "TALHADEIRA ESPECIAL": 150.0,
    "TALHADEIRA ESPECIAL LARGA (80MM)": 150.0,
    "TALHADEIRA ROMPEDOR 10KG": 150.0,
    "TALHADEIRA ROMPEDOR 16/30 KG": 150.0,
    "TRANSFORMADOR 7000W BIVOLT": 700.0,
    "TRANSFORMADOR ate 3000W 110/220V": 500.0,
    "TRANSPALLET MANUAL ate 02 TON": 2000.0,
    "TRIPE BT 150 HD": 292.16,
    "TRIPE BT160": 536.15,
    "TUPIA RP0900 220V": 882.0,
    "VARREDEIRA S4 TWIN MANUAL": 961.31,
    "VIBRADOR AF 35MM": 3000.0,
    "VIBRADOR AF MOTOR 220V": 3000.0,
    "VIBRADOR AR 35MM": 1500.0
}

CATALOGO_EQUIPAMENTOS = {" ".join(k.split()): v for k, v in RAW_CATALOGO.items()}
OPCAO_OUTRO = "➕ OUTRO EQUIPAMENTO (Manual)"
opcoes_equipamentos = sorted(list(CATALOGO_EQUIPAMENTOS.keys())) + [OPCAO_OUTRO]

# --- UI PRINCIPAL (PORTAL) ---
usr_info = st.session_state["usuario_atual"]
eh_master = usr_info["perfil"] == "master"

# BARRA LATERAL DE NAVEGAÇÃO (SIDEBAR)
with st.sidebar:
    st.image("https://casadoconstrutor.com.br/wp-content/uploads/2021/04/logo-casa-do-construtor.png", width=180)
    st.markdown("---")
    st.markdown(f"### 👤 {usr_info['nome']}")
    st.markdown(f"**📍 Unidade:** {usr_info['filial']}")
    st.markdown("---")
    if st.button("🚪 Sair do Sistema", use_container_width=True):
        st.session_state["logged_in"] = False
        st.rerun()
    st.markdown("<br><br><br><br><br><br>", unsafe_allow_html=True)
    st.caption("Powered by Google Gemini AI")

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
            loja = st.selectbox("🏢 Filial Responsável", ["087 - Blumenau", "213 - Indaial", "350 - Itapema", "250 - Balneário Camboriú", "284 - Jaraguá do Sul", "299 - Brusque", "360 - Blumenau 02", "503 - Timbó", "560 - Camboriú", "636 - Guaramirim", "695 - Tijucas", "733 - São Bento do Sul"]) if eh_master else usr_info["filial"]
            if not eh_master: st.text_input("🏢 Filial Responsável", value=loja, disabled=True)
            
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
                    referencias = st.text_area("📞 Feedback das Referências Comerciais", placeholder="Descreva aqui o que as empresas consultadas falaram sobre os hábitos de pagamento deste CNPJ...", help="Este campo é mandatório para aprovação de prazos maiores.")

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
        else:
            with st.spinner('A IA está processando as matrizes de risco, lendo documentos e cruzando bases...'):
                try:
                    payload = []
                    for doc in documentos:
                        b64 = base64.b64encode(doc.getvalue()).decode("utf-8")
                        payload.append({"type": "document" if "pdf" in doc.type else "image", "mime_type": doc.type, "data": b64})

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
                    - Verifique com o Google Search se a pessoa que pediu ({nome_solicitante}) tem o e-mail oficial da empresa ou consta no quadro societário (Contrato Social). Se for um terceiro desconhecido, emita um ALERTA VERMELHO exigindo "Pedido de Compra Oficial e Autorização".

                    FORMATO DA RESPOSTA:
                    - Status: [APROVADO], [APROVADO COM RESTRIÇÃO (ex: Prazo reduzido)] ou [REPROVADO].
                    - Quadro Resumo do Crédito (Tempo de Abertura, Situação Serasa, Resumo Referências).
                    - Parecer Detalhado (Por que aprovou? Por que reduziu o prazo? Por que bloqueou?).
                    - Destaque: Para Pessoa Física lembre expressamente que o pagamento é À Vista.
                    """

                    payload.append({"type": "text", "text": prompt})

                    interaction = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=payload,
                        config=types.GenerateContentConfig(
                            tools=[{"google_search": {}}],
                            temperature=0.1
                        )
                    )

                    st.session_state['resultado_parecer'] = interaction.text
                    st.session_state['nome_cliente_analisado'] = nome_cliente
                    
                    pdf = gerar_pdf_parecer(nome_cliente, tipo_cliente, forma_pagamento, loja, equip_nome, val_equip, interaction.text)
                    st.session_state['pdf_bytes'] = pdf

                    salvar_no_historico(loja, usr_info['nome'], nome_cliente, tipo_cliente, equip_nome, val_equip, forma_pagamento, interaction.text)

                except Exception as e:
                    st.error(f"Erro na IA: {e}")

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
