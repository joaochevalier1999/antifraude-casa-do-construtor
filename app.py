import streamlit as st
import base64
import io
import html
import re
import os
import pandas as pd
from datetime import datetime
from google import genai

# Dependências para geração de PDF profissional
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

# --- CONFIGURAÇÃO DA PÁGINA ---
st.set_page_config(page_title="Central de Cadastros - Casa do Construtor", page_icon="🏗️", layout="wide")

# --- CHAVE DA API (Leitura Segura via Secrets) ---
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
    st.error(f"Erro ao inicializar o cliente da API: {e}")
    client = None

# --- ARQUIVO DE HISTÓRICO DE AUDITORIA ---
ARQUIVO_HISTORICO = "historico_analises.csv"

def salvar_no_historico(filial, cliente, equipamento, valor, parecer_texto):
    data_hora = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    
    # Extrai o status principal ([APROVADO], [REPROVADO], etc) do texto do parecer
    status = "ANALISADO"
    if "[APROVADO COM RESTRIÇÃO]" in parecer_texto.upper():
        status = "APROVADO COM RESTRIÇÃO"
    elif "[APROVADO]" in parecer_texto.upper():
        status = "APROVADO"
    elif "[REPROVADO]" in parecer_texto.upper():
        status = "REPROVADO"

    novo_registro = pd.DataFrame([{
        "Data/Hora": data_hora,
        "Filial": filial,
        "Cliente": cliente,
        "Equipamento": equipamento,
        "Valor Reposição (R$)": valor,
        "Status Decisão": status
    }])

    if not os.path.exists(ARQUIVO_HISTORICO):
        novo_registro.to_csv(ARQUIVO_HISTORICO, index=False, sep=";", encoding="utf-8-sig")
    else:
        novo_registro.to_csv(ARQUIVO_HISTORICO, mode='a', header=False, index=False, sep=";", encoding="utf-8-sig")

# --- FUNÇÃO TRATADORA DE TEXTO PARA REPORTLAB ---
def formatar_texto_para_reportlab(texto):
    texto_escapado = html.escape(texto)
    texto_formatado = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', texto_escapado)
    return texto_formatado

# --- FUNÇÃO GERADORA DE PDF DO PARECER ---
def gerar_pdf_parecer(nome_cliente, loja, equipamento_nome, valor_equipamento, texto_parecer):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=letter, 
        rightMargin=36, 
        leftMargin=36, 
        topMargin=36, 
        bottomMargin=36
    )
    story = []
    styles = getSampleStyleSheet()

    titulo_style = ParagraphStyle('Titulo', parent=styles['Heading1'], fontSize=15, textColor=colors.HexColor('#003366'), spaceAfter=8)
    sub_style = ParagraphStyle('Sub', parent=styles['Normal'], fontSize=9, textColor=colors.gray, spaceAfter=15)
    body_style = ParagraphStyle('Body', parent=styles['Normal'], fontSize=10, leading=14, spaceAfter=6)

    story.append(Paragraph("<b>CASA DO CONSTRUTOR - PARECER TÉCNICO ANTIFRAUDE</b>", titulo_style))
    data_hora = datetime.now().strftime("%d/%m/%Y às %H:%M:%S")
    story.append(Paragraph(f"Relatório de Análise Interna | Emitido em: {data_hora}", sub_style))

    val_f = f"R$ {valor_equipamento:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
    dados_tabela = [
        [Paragraph("<b>Cliente:</b>", body_style), Paragraph(html.escape(nome_cliente), body_style)],
        [Paragraph("<b>Filial Responsável:</b>", body_style), Paragraph(html.escape(loja), body_style)],
        [Paragraph("<b>Equipamento Solicitado:</b>", body_style), Paragraph(html.escape(equipamento_nome), body_style)],
        [Paragraph("<b>Valor de Reposição:</b>", body_style), Paragraph(val_f, body_style)],
    ]
    t = Table(dados_tabela, colWidths=[140, 380])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F2F4F8')),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#D1D5DB')),
        ('PADDING', (0, 0), (-1, -1), 6),
    ]))
    story.append(t)
    story.append(Spacer(1, 15))

    story.append(Paragraph("<b>PARECER TÉCNICO E JUSTIFICATIVA:</b>", ParagraphStyle('Heading2', parent=styles['Heading2'], fontSize=12, textColor=colors.HexColor('#003366'))))
    story.append(Spacer(1, 6))

    for linha in texto_parecer.split('\n'):
        linha_limpa = linha.strip()
        if linha_limpa:
            linha_segura = formatar_texto_para_reportlab(linha_limpa)
            story.append(Paragraph(linha_segura, body_style))

    story.append(Spacer(1, 20))
    story.append(Paragraph("__________________________________________________________", body_style))
    story.append(Paragraph("<b>Validação Automatizada por Inteligência Artificial - Casa do Construtor</b>", sub_style))

    doc.build(story)
    buffer.seek(0)
    return buffer.getvalue()

# --- LISTA DE FILIAIS ---
LISTA_LOJAS = [
    "087 - Blumenau",
    "213 - Indaial",
    "250 - Balneário Camboriú",
    "284 - Jaraguá do Sul",
    "299 - Brusque",
    "350 - Itapema",
    "360 - Blumenau 02",
    "503 - Timbó",
    "560 - Camboriú",
    "636 - Guaramirim",
    "695 - Tijucas",
    "733 - São Bento do Sul"
]

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
OPCAO_OUTRO = "➕ OUTRO EQUIPAMENTO (Digitar manualmente)"
opcoes_equipamentos = sorted(list(CATALOGO_EQUIPAMENTOS.keys())) + [OPCAO_OUTRO]

# --- CABEÇALHO DO SITE ---
st.image("https://casadoconstrutor.com.br/wp-content/uploads/2021/04/logo-casa-do-construtor.png", width=220)
st.title("🛡️ Central de Análise Antifraude")

# Navegação por Abas (Nova Funcionalidade)
aba_analise, aba_historico = st.tabs(["🚀 Nova Análise Antifraude", "📊 Histórico & Auditoria"])

with aba_analise:
    st.caption(f"Sistema Interno de Validação | Catálogo: **{len(CATALOGO_EQUIPAMENTOS)} equipamentos**")

    # --- FORMULÁRIO DE ENTRADA REATIVO ---
    col1, col2 = st.columns(2)
    with col1:
        loja = st.selectbox("Filial Responsável", LISTA_LOJAS)
    with col2:
        nome_cliente = st.text_input("Nome Completo do Cliente")

    equipamento_selecionado = st.selectbox(
        "🔍 Buscar/Selecionar Equipamento Solicitado", 
        opcoes_equipamentos,
        index=None,
        placeholder="🔍 Digite para pesquisar ou escolha na lista...",
        key="equipamento_selectbox",
        help="Digite o nome para pesquisar. Caso não encontre, selecione a última opção (OUTRO EQUIPAMENTO)."
    )

    equipamento_nome = None
    valor_equipamento = 0.0

    if equipamento_selecionado == OPCAO_OUTRO:
        col_m1, col_m2 = st.columns(2)
        with col_m1:
            equipamento_nome = st.text_input("Nome do Equipamento (Manual)")
        with col_m2:
            valor_equipamento = st.number_input("Valor Estimado de Reposição (R$)", min_value=1.0, value=3000.0, step=500.0)

    elif equipamento_selecionado is not None:
        equipamento_nome = equipamento_selecionado
        valor_equipamento = CATALOGO_EQUIPAMENTOS.get(equipamento_selecionado, 0.0)
        
        val_f = f"R$ {valor_equipamento:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
        st.info(f"💵 **Valor de Reposição Cadastrado (Tabela Oficial):** {val_f}")

    st.markdown("### 📎 Anexos (Documentos / Selfie / Comprovante)")
    documentos = st.file_uploader(
        "Arraste fotos ou PDFs dos documentos do cliente (RG, CNH, Selfie, Comprovante de Residência)", 
        accept_multiple_files=True, 
        type=['png', 'jpg', 'jpeg', 'pdf']
    )

    submit = st.button("🚀 Iniciar Análise Antifraude", type="primary")

    # --- PROCESSAMENTO COM A IA ---
    if submit:
        if not nome_cliente or not equipamento_nome or not documentos:
            st.error("⚠️ Por favor, preencha o Nome do Cliente, escolha ou digite o Equipamento e anexe os Documentos!")
        elif client is None:
            st.error("❌ Falha na conexão com a API do Google.")
        else:
            with st.spinner('A IA está executando validação documental, biometria e análise de risco financeiro...'):
                try:
                    input_payload = []

                    for doc in documentos:
                        bytes_data = doc.getvalue()
                        b64_data = base64.b64encode(bytes_data).decode("utf-8")
                        mime_type = doc.type
                        media_type = "image" if mime_type.startswith("image/") else "document"
                        
                        input_payload.append({
                            "type": media_type,
                            "mime_type": mime_type,
                            "data": b64_data,
                        })

                    prompt = f"""
                    Você é o Analista de Crédito e Risco Sênior da Casa do Construtor.
                    
                    DADOS DO CADASTRO E DA OPERAÇÃO:
                    - Cliente Cadastrado: {nome_cliente}
                    - Filial: {loja}
                    - Equipamento Solicitado: {equipamento_nome}
                    - Valor de Reposição do Equipamento: R$ {valor_equipamento:,.2f}
                    
                    DIRETRIZES DE VALIDAÇÃO ANTIMODELOCAUTELA (RIGOROSO):
                    
                    1. CHECKLIST DOCUMENTAL E ESTRUTURAL (RG / CNH):
                       - Extraia e informe expressamente: Nome Completo no Documento, Número do CPF, Número do Documento e Órgão Emissor (ex: SSP/SC, DETRAN/SP).
                       - Avalie se o Órgão Emissor possui formato coerente para o estado de emissão.
                       - Verifique se o nome do cliente informado no formulário ({nome_cliente}) coincide 100% com o documento.
                       - Analise indícios de manipulação digital (fontes desproporcionais, cortes, rasuras, fundos colados).

                    2. BIOMETRIA FACIAL E PROVA DE VIDA:
                       - Compare os traços faciais entre a Selfie do cliente e a Foto do Documento (RG/CNH).
                       - Identifique se a selfie parece ser uma foto real da pessoa ou foto de foto/tela (reflexos, bordas de monitor, pixels).

                    3. COMPROVANTE DE ENDEREÇO:
                       - Verifique se o comprovante é recente, legível e se está no nome do cliente ou de parente direto.

                    4. ANÁLISE DE RISCO FINANCEIRO x PATRIMÔNIO:
                       - Relacione o nível de exigência documental ao valor de reposição do bem envolvido na locação (R$ {valor_equipamento:,.2f}). Equipamentos de alto valor de reposição exigem 100% de consistência.

                    FORMATO DO PARECER TÉCNICO:
                    - Status em destaque: [APROVADO], [APROVADO COM RESTRIÇÃO] ou [REPROVADO].
                    - Tabela/Resumo dos Dados Extraídos (Nome do Doc, CPF, Órgão Emissor, Status Biométrico).
                    - Justificativa técnica detalhada recomendando a liberação ou retenção da locação.
                    """

                    input_payload.append({"type": "text", "text": prompt})

                    interaction = client.interactions.create(
                        model="gemini-3.6-flash",
                        input=input_payload
                    )

                    texto_resultado = interaction.output_text
                    st.session_state['resultado_parecer'] = texto_resultado
                    st.session_state['nome_cliente_analisado'] = nome_cliente
                    
                    pdf_bytes = gerar_pdf_parecer(
                        nome_cliente=nome_cliente,
                        loja=loja,
                        equipamento_nome=equipamento_nome,
                        valor_equipamento=valor_equipamento,
                        texto_parecer=texto_resultado
                    )
                    st.session_state['pdf_bytes'] = pdf_bytes

                    # GRAVAÇÃO AUTOMÁTICA NO HISTÓRICO DE AUDITORIA
                    salvar_no_historico(
                        filial=loja,
                        cliente=nome_cliente,
                        equipamento=equipamento_nome,
                        valor=valor_equipamento,
                        parecer_texto=texto_resultado
                    )

                except Exception as e:
                    st.error(f"Erro no processamento da análise: {e}")

    # --- EXIBIÇÃO DO RESULTADO E DOWNLOAD DO PDF ---
    if 'resultado_parecer' in st.session_state and st.session_state['resultado_parecer']:
        st.success("Análise Concluída com Sucesso!")
        st.markdown("---")
        st.markdown(st.session_state['resultado_parecer'])

        st.markdown("### 📥 Documentação Oficial")
        nome_sanitizado = st.session_state.get('nome_cliente_analisado', 'Cliente').replace(' ', '_')
        st.download_button(
            label="📄 Baixar Parecer Técnico Antifraude (PDF)",
            data=st.session_state['pdf_bytes'],
            file_name=f"Parecer_Antifraude_{nome_sanitizado}.pdf",
            mime="application/pdf",
            type="primary"
        )

# --- ABA 2: HISTÓRICO & AUDITORIA ---
with aba_historico:
    st.subheader("📋 Registro de Análises Antifraude Realizadas")
    st.caption("Consolidado de consultas para controle de risco corporativo.")

    if os.path.exists(ARQUIVO_HISTORICO):
        df_hist = pd.read_csv(ARQUIVO_HISTORICO, sep=";", encoding="utf-8-sig")
        
        # Métricas Rápidas no Topo
        m1, m2, m3 = st.columns(3)
        m1.metric("Total de Análises", len(df_hist))
        m2.metric("Aprovados", len(df_hist[df_hist['Status Decisão'] == 'APROVADO']))
        m3.metric("Reprovados", len(df_hist[df_hist['Status Decisão'] == 'REPROVADO']))
        
        st.markdown("---")
        st.dataframe(df_hist, use_container_width=True)

        # Botão para exportar a planilha completa em CSV
        csv_bytes = df_hist.to_csv(index=False, sep=";", encoding="utf-8-sig").encode('utf-8-sig')
        st.download_button(
            label="📊 Baixar Planilha Geral de Auditoria (CSV)",
            data=csv_bytes,
            file_name=f"Auditoria_Antifraude_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
    else:
        st.info("Nenhuma análise foi gravada ainda. Execute uma validação na aba principal para inaugurar o histórico!")