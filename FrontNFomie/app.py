"""
Download de NFSe e XML — Front Streamlit (Sillion)
Encaminha período (data inicial/final) + email + CNPJ (opcional) para o backend
N8N via POST JSON. O backend retorna o relatório de extração por e-mail.

Arquitetura:
- app.py        → lógica Python (config, envio, widgets de input)
- styles/       → CSS (visual)
- templates/    → HTML estrutural (header, hero, footer, etc.)
"""

import re
from datetime import datetime, date
from pathlib import Path

import requests
import streamlit as st

# ============================================================
# Caminhos
# ============================================================
BASE_DIR = Path(__file__).parent
CSS_PATH = BASE_DIR / "styles" / "main.css"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

# ============================================================
# Recursos externos
# ============================================================
LOGO_EXTERNO = "https://www.sillion.com.br/wp-content/themes/sillion/images/logo-black-tm.svg"
LOGO_LOCAL_FILE = STATIC_DIR / "logo-sillion.svg"


def resolver_logo_url() -> str:
    """
    Retorna o caminho do logo:
    - Se houver `static/logo-sillion.svg`, usa a versão local (mais rápida e offline).
    - Caso contrário, cai para a URL externa do site da Sillion.
    Streamlit sanitiza o atributo `onerror` em HTML, então o fallback
    precisa ser feito no Python, não no navegador.
    """
    if LOGO_LOCAL_FILE.exists():
        return "app/static/logo-sillion.svg"
    return LOGO_EXTERNO

# ============================================================
# Config da página
# ============================================================
st.set_page_config(
    page_title="Sillion · Dawnload de NFSe e XML",
    page_icon="",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ============================================================
# Constantes
# ============================================================
# Apenas emails @sillion.com.br são aceitos (case-insensitive)
DOMINIO_PERMITIDO = "sillion.com.br"
EMAIL_REGEX = re.compile(
    rf"^[A-Za-z0-9._%+\-]+@{re.escape(DOMINIO_PERMITIDO)}$",
    re.IGNORECASE,
)

TIMEOUT_REQ = 120  # segundos

# Opções de empresa/fonte a serem extraídas
EMPRESAS_OPCOES = ["TOT", "VALE"]


# ============================================================
# Helpers de renderização (templates + CSS)
# ============================================================
def render_template(nome: str, **variaveis) -> str:
    """
    Lê um arquivo .html em templates/ e substitui placeholders no
    formato {{nome_da_variavel}} pelos valores passados.
    """
    caminho = TEMPLATES_DIR / f"{nome}.html"
    html = caminho.read_text(encoding="utf-8")
    for chave, valor in variaveis.items():
        html = html.replace(f"{{{{{chave}}}}}", str(valor))
    return html


def inject(html: str) -> None:
    """Injeta um trecho HTML na página."""
    st.markdown(html, unsafe_allow_html=True)


def carregar_css(caminho: Path) -> None:
    """Lê o arquivo CSS e injeta na página via st.markdown."""
    try:
        css = caminho.read_text(encoding="utf-8")
        inject(f"<style>{css}</style>")
    except FileNotFoundError:
        st.warning(f"Arquivo de estilos não encontrado: {caminho}")


# Carrega meta tags + CSS antes de qualquer conteúdo
inject(render_template("meta"))
carregar_css(CSS_PATH)


# ============================================================
# Configuração segura: URL do webhook
# ============================================================
try:
    WEBHOOK_URL = st.secrets["N8N_WEBHOOK_URL"]
except (KeyError, FileNotFoundError):
    WEBHOOK_URL = None


# ============================================================
# Helpers de negócio
# ============================================================
def email_valido(email: str) -> bool:
    return bool(EMAIL_REGEX.match(email.strip()))


def somente_digitos(valor: str) -> str:
    """Remove qualquer caractere que não seja dígito (útil para CNPJ)."""
    return re.sub(r"\D", "", valor or "")


def montar_payload(
    email: str,
    data_inicial: date,
    data_final: date,
    empresas: list,
    cnpj: str = "",
) -> dict:
    """
    Payload enviado ao backend N8N.
    - data_inicial / data_final: ISO 8601 (YYYY-MM-DD)
    - empresas: lista com uma ou mais entre EMPRESAS_OPCOES (ex.: ["TOT", "VALE"])
    - cnpj: apenas dígitos; string vazia quando não informado (opcional)
    """
    return {
        "email": email.strip(),
        "data_inicial": data_inicial.isoformat(),
        "data_final": data_final.isoformat(),
        "empresas": list(empresas),
        "cnpj": somente_digitos(cnpj),
    }


def enviar_para_n8n(url: str, payload: dict) -> requests.Response:
    return requests.post(
        url,
        json=payload,
        timeout=TIMEOUT_REQ,
        headers={"Content-Type": "application/json"},
    )


# ============================================================
# UI — Header + Hero (vindos dos templates HTML)
# ============================================================
inject(render_template("header", logo_url=resolver_logo_url()))
inject(render_template(
    "hero",
    titulo="Dawnload de NFSe e XML",
    subtitulo="Extração de arquivos PDF e XML de acordo com o período selecionado.",
))


# ============================================================
# Verificação de configuração
# ============================================================
if not WEBHOOK_URL:
    st.error(
        "⚠️ A URL do webhook N8N não foi configurada. "
        "Crie o arquivo `.streamlit/secrets.toml` com a chave `N8N_WEBHOOK_URL` "
        "ou configure-a no painel do Streamlit Community Cloud."
    )
    st.stop()


# ============================================================
# UI — Formulário (widgets Streamlit — precisam falar com Python)
# ============================================================
email = st.text_input(
    "Email corporativo",
    placeholder=f"usuario@{DOMINIO_PERMITIDO}",
    help=f"Apenas emails do domínio @{DOMINIO_PERMITIDO} são aceitos. "
         "O relatório processado será enviado para este endereço.",
)

cnpj = st.text_input(
    "CNPJ (opcional)",
    placeholder="00.000.000/0000-00",
    help="Filtre a extração por um CNPJ específico. "
         "Deixe em branco para considerar todos os CNPJs.",
)

st.markdown("**Período selecionado:**")
col_ini, col_fim = st.columns(2)
with col_ini:
    data_inicial = st.date_input(
        "Data inicial",
        value=None,
        format="DD/MM/YYYY",
    )
with col_fim:
    data_final = st.date_input(
        "Data final",
        value=None,
        format="DD/MM/YYYY",
    )

empresas = st.multiselect(
    "Empresas",
    options=EMPRESAS_OPCOES,
    default=[],
    placeholder="Selecione TOT, VALE ou ambas",
    help="Selecione uma ou as duas opções. Pelo menos uma é obrigatória.",
)

st.write("")
enviar = st.button("Download", type="primary", use_container_width=True)


# ============================================================
# Lógica de envio
# ============================================================
if enviar:
    erros = []

    if not email.strip():
        erros.append("Informe o email.")
    elif not email_valido(email):
        erros.append(
            f"Email inválido. Use um endereço corporativo @{DOMINIO_PERMITIDO} "
            "(ex: seu.nome@" + DOMINIO_PERMITIDO + ")."
        )

    if data_inicial is None:
        erros.append("Informe a data inicial.")
    if data_final is None:
        erros.append("Informe a data final.")
    if data_inicial and data_final and data_inicial > data_final:
        erros.append("A data inicial não pode ser posterior à data final.")

    if not empresas:
        erros.append("Selecione pelo menos uma empresa (TOT e/ou VALE).")

    # CNPJ é opcional — só valida se foi preenchido
    cnpj_digitos = somente_digitos(cnpj)
    if cnpj.strip() and len(cnpj_digitos) != 14:
        erros.append("CNPJ inválido. Deve conter 14 dígitos.")

    if erros:
        for e in erros:
            st.error(e)
    else:
        with st.spinner("Solicitando extração ao backend..."):
            try:
                payload = montar_payload(email, data_inicial, data_final, empresas, cnpj)
                resp = enviar_para_n8n(WEBHOOK_URL, payload)

                if 200 <= resp.status_code < 300:
                    @st.dialog("Solicitação enviada")
                    def confirmacao():
                        st.success("Solicitação enviada com sucesso!")
                        st.write(
                            f"O relatório com os arquivos PDF e XML será encaminhado "
                            f"para **{email.strip()}** assim que o backend concluir "
                            "a extração."
                        )
                        st.caption(
                            "Período: "
                            f"{data_inicial.strftime('%d/%m/%Y')} a "
                            f"{data_final.strftime('%d/%m/%Y')}"
                        )
                        st.caption(f"Empresas: {', '.join(empresas)}")
                        if cnpj_digitos:
                            st.caption(f"CNPJ: {cnpj.strip()}")
                        st.caption(
                            f"Enviado em {datetime.now().strftime('%d/%m/%Y às %H:%M:%S')}"
                        )
                        if st.button("OK", use_container_width=True):
                            st.rerun()

                    confirmacao()
                else:
                    st.error(f"O backend respondeu com status {resp.status_code}.")
                    with st.expander("Detalhes da resposta"):
                        st.code(resp.text or "(sem corpo)")
            except requests.exceptions.Timeout:
                st.error("Tempo de resposta excedido. Verifique se o N8N está acessível.")
            except requests.exceptions.ConnectionError:
                st.error("Falha de conexão. Verifique a URL do webhook.")
            except Exception as exc:
                st.error(f"Erro inesperado: {exc}")


# ============================================================
# UI — Footer (vindo do template HTML)
# ============================================================
inject(render_template("footer", ano=datetime.now().year))
