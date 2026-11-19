import json
import math
import os

import streamlit as st
from shared_backend import load_character, save_character, patch_character, shared_enabled, upload_asset

# ============================================================
# CONFIGURAÇÃO DA PÁGINA
# ============================================================

st.set_page_config(
    page_title="Bondobo — Midnight Sun",
    page_icon="🌒",
    layout="wide",
    initial_sidebar_state="expanded",
)
from auth_unified import require_role
require_role("jogador_3", "mestre")


DATA_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "ficha_midnightsun_dados.json",
)

# ============================================================
# CSS
# ============================================================

st.markdown("""
<style>

.block-container {
    padding-top: 1.5rem;
    padding-bottom: 3rem;
    max-width: 1300px;
}

.main-title {
    text-align: center;
    font-size: 2.1rem;
    font-weight: 800;
    margin-bottom: 0.1rem;
}

.subtitle {
    text-align: center;
    color: #999;
    margin-bottom: 1.2rem;
}

.section-title {
    font-size: 1.3rem;
    font-weight: 800;
    letter-spacing: 1px;
    text-transform: uppercase;
    margin-top: 1.6rem;
    margin-bottom: 0.6rem;
    padding-bottom: 4px;
    border-bottom: 2px solid #444;
}

.attr-box {
    border: 1px solid #333;
    border-radius: 12px;
    padding: 10px 6px 12px 6px;
    text-align: center;
    background: rgba(255,255,255,0.025);
}

.attr-name {
    font-size: 0.78rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #ccc;
    margin-bottom: 2px;
}

.attr-mod {
    font-size: 1.4rem;
    font-weight: 800;
    margin-top: 4px;
    color: #ff5252;
}

.bar-container {
    border: 1px solid #333;
    border-radius: 14px;
    padding: 14px 22px 18px 22px;
    margin: 6px 0 10px 0;
    background: rgba(255,255,255,0.025);
}

.bar-title {
    font-size: 0.95rem;
    font-weight: 800;
    letter-spacing: 2px;
    text-transform: uppercase;
    color: #ddd;
    margin-bottom: 6px;
}

.bar-value {
    font-size: 1.5rem;
    font-weight: 800;
    margin-bottom: 8px;
}

.bar-bg {
    width: 100%;
    height: 20px;
    background: #262626;
    border-radius: 12px;
    overflow: hidden;
    border: 1px solid #444;
}

.bar-fill-hp { height: 100%; background: #d32f2f; border-radius: 12px; transition: width 0.3s ease; }
.bar-fill-mana { height: 100%; background: #2979ff; border-radius: 12px; transition: width 0.3s ease; }
.bar-fill-estamina { height: 100%; background: #43a047; border-radius: 12px; transition: width 0.3s ease; }

.stat-highlight {
    border: 2px solid #c62828;
    border-radius: 12px;
    padding: 10px 14px;
    text-align: center;
    background: rgba(180, 20, 20, 0.08);
}

.stat-highlight-label {
    color: #ff5252;
    font-size: 0.8rem;
    font-weight: 800;
    letter-spacing: 1px;
    text-transform: uppercase;
}

.stat-highlight-value {
    color: #ff5252;
    font-size: 1.9rem;
    font-weight: 800;
    margin-top: 2px;
}

.info-box {
    border: 1px solid #333;
    border-radius: 12px;
    padding: 10px 14px;
    text-align: center;
    background: rgba(255,255,255,0.025);
}

.info-label {
    font-size: 0.8rem;
    font-weight: 800;
    letter-spacing: 1px;
    text-transform: uppercase;
    color: #ccc;
}

.info-value {
    font-size: 1.5rem;
    font-weight: 800;
    margin-top: 2px;
}

.overweight {
    color: #ff5252 !important;
}

.warning-box {
    border: 1px solid #ff5252;
    border-radius: 8px;
    padding: 6px 10px;
    margin-top: 6px;
    background: rgba(255, 82, 82, 0.08);
    color: #ff5252;
    font-weight: 700;
    text-align: center;
    font-size: 0.85rem;
}

.levelup-box {
    border: 1px solid #4caf50;
    border-radius: 8px;
    padding: 8px 14px;
    margin-top: 8px;
    background: rgba(76, 175, 80, 0.08);
    color: #66bb6a;
    font-weight: 700;
    text-align: center;
}

.weapon-card {
    border: 1px solid #333;
    border-radius: 12px;
    padding: 14px 18px;
    margin-bottom: 14px;
    background: rgba(255,255,255,0.02);
}

.attack-line {
    font-family: "Courier New", monospace;
    font-size: 1.0rem;
    padding: 6px 10px;
    border-radius: 8px;
    background: rgba(255,255,255,0.04);
    margin: 4px 0;
}

.pericia-row {
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 4px;
    border-bottom: 1px solid #2a2a2a;
}

.small-caption {
    color: #888;
    font-size: 0.8rem;
}

</style>
""", unsafe_allow_html=True)


# ============================================================
# CONSTANTES DO SISTEMA
# ============================================================

ATRIBUTOS = [
    "Força", "Destreza", "Constituição",
    "Inteligência", "Sabedoria", "Carisma", "Fortitude"
]

PERICIAS = {
    "Malandragem": ["Destreza", "Carisma"],
    "Herbalismo": ["Inteligência", "Sabedoria"],
    "Aura": ["Carisma"],
    "Mente": ["Sabedoria"],
    "Conhecimento": ["Inteligência", "Sabedoria"],
    "Instinto": ["Destreza"],
    "Fibra": ["Força", "Destreza"],
}

ARMOR_SLOTS = ["Peitoral", "Capacete", "Braçadeiras", "Botas"]

NUM_ARMAS = 5
NUM_INVENTARIO = 15
NUM_ACOES_TURNO = 10

MODALIDADES = ["Normal", "Carregado", "Weapon Art"]

DICE_SIDES_OPTIONS = [4, 6, 8, 10, 12, 20, 100]

DEFESAS = {"Parry": "parry", "Rolagem": "rolagem", "Bloquear": "bloquear", "Pular": "pular", "Correr": "correr"}
PLAYER_ID = "jogador_3"
PLAYER_NAME = "Bondobo"

# Tabela de Fragmentos de Essência necessários para cada nível (1 a 99)
XP_TABLE = {
    1: 255, 2: 319, 3: 399, 4: 470, 5: 550, 6: 667, 7: 834, 8: 1003, 9: 1201,
    10: 1382, 11: 1589, 12: 1827, 13: 2101, 14: 2416, 15: 2593, 16: 2853,
    17: 3281, 18: 3773, 19: 4338, 20: 4772, 21: 5249, 22: 5774, 23: 6352,
    24: 6987, 25: 7686, 26: 8454, 27: 9130, 28: 9861, 29: 10649, 30: 11501,
    31: 12421, 32: 13415, 33: 14488, 34: 15647, 35: 16899, 36: 18251,
    37: 19711, 38: 21288, 39: 22991, 40: 24830, 41: 25823, 42: 26856,
    43: 27930, 44: 29048, 45: 30210, 46: 31418, 47: 32675, 48: 33328,
    49: 33995, 50: 34675, 51: 35368, 52: 36075, 53: 36797, 54: 37533,
    55: 38283, 56: 39049, 57: 39830, 58: 40627, 59: 41439, 60: 42268,
    61: 43113, 62: 43976, 63: 44855, 64: 45752, 65: 46667, 66: 47600,
    67: 48552, 68: 49524, 69: 50514, 70: 51524, 71: 52555, 72: 53606,
    73: 54678, 74: 55771, 75: 56887, 76: 58025, 77: 59185, 78: 60369,
    79: 61576, 80: 62808, 81: 64064, 82: 65345, 83: 66652, 84: 67985,
    85: 69345, 86: 70732, 87: 72146, 88: 73589, 89: 75061, 90: 76562,
    91: 78093, 92: 79655, 93: 81248, 94: 82873, 95: 84531, 96: 86221,
    97: 87946, 98: 89705, 99: 91499,
}


# ============================================================
# FÓRMULAS DO SISTEMA
# ============================================================

def modificador(valor: int) -> int:
    """floor((atributo - 10) / 2) — usada para todos os atributos."""
    return (valor - 10) // 2


def bonus_nao_treinado(mod: int) -> int:
    """Metade do modificador, arredondado para baixo (funciona p/ negativos)."""
    return mod // 2


def bonus_treinado(mod: int) -> int:
    """
    Bônus de perícia treinada.
    Reconstruída a partir da tabela fornecida (mod + bônus não treinado + 1),
    que reproduz fielmente os valores 0 a 7 informados.
    """
    return mod + (mod // 2) + 1


def arredondar_para_cima(valor: float) -> int:
    return math.ceil(round(valor, 6))


def calc_hp_max(constituicao: int, fortitude: int):
    hp_const = 50 + (constituicao - 10) * 6
    hp_fort = (fortitude - 10) * 2
    return hp_const + hp_fort, hp_const, hp_fort


def calc_mana_max(carisma: int, sabedoria: int, inteligencia: int) -> int:
    valor = (carisma * 1.7) + (sabedoria * 1.7) + (inteligencia * 2.3)
    return arredondar_para_cima(valor)


def calc_estamina_max(fortitude: int, forca: int, destreza: int) -> int:
    valor = (fortitude * 4.6) + (forca * 1.2) + (destreza * 1.2)
    return arredondar_para_cima(valor)


def calc_peso_max(fortitude: int, constituicao: int) -> float:
    valor = (fortitude * 1) + (constituicao * 0.4)
    return round(valor, 2)


def formatar_peso(valor: float) -> str:
    if float(valor).is_integer():
        return f"{int(valor)}"
    texto = f"{valor:.2f}".rstrip("0").rstrip(".")
    return texto


# ============================================================
# ESTADO PADRÃO / CHAVES DA FICHA
# ============================================================

def attr_key(nome):
    return f"attr_{nome}"


def armor_keys(i):
    return {
        "nome": f"armor_{i}_nome",
        "peso": f"armor_{i}_peso",
        "rd": f"armor_{i}_rd",
    }


def pericia_key(nome):
    return f"pericia_{nome}"


def weapon_keys(i):
    return {
        "nome": f"arma_{i}_nome",
        "test_dados": f"arma_{i}_test_dados",
        "test_lados": f"arma_{i}_test_lados",
        "bonus_ataque": f"arma_{i}_bonus_ataque",
        "dano_dados": f"arma_{i}_dano_dados",
        "dano_lados": f"arma_{i}_dano_lados",
        "bonus_dano": f"arma_{i}_bonus_dano",
        "crit_min": f"arma_{i}_crit_min",
        "crit_mult": f"arma_{i}_crit_mult",
        "custo_estamina": f"arma_{i}_custo_estamina",
        "wa_texto": f"arma_{i}_wa_texto",
        "wa_estamina": f"arma_{i}_wa_estamina",
        "wa_mana": f"arma_{i}_wa_mana",
    }


def inventory_keys(i):
    return {
        "nome": f"inv_{i}_nome",
        "qtd": f"inv_{i}_qtd",
        "desc": f"inv_{i}_desc",
    }


def turn_keys(i):
    return {
        "arma": f"turno_{i}_arma",
        "modalidade": f"turno_{i}_modalidade",
    }


def build_default_state() -> dict:
    """Constrói o dicionário completo de valores padrão da ficha."""

    state = {
        "nome_personagem": PLAYER_NAME,
        "nivel": 1,
        "fragmentos_essencia": 0,
        "pontos_atributo": 0,
        "requiem_atual": 0,
        "hp_atual": None,
        "mana_atual": None,
        "estamina_atual": None,
        "imagem_url": "",
        "token_url": "",
    }

    for a in ATRIBUTOS:
        state[attr_key(a)] = 10

    for i in range(NUM_ARMOR := len(ARMOR_SLOTS)):
        keys = armor_keys(i)
        state[keys["nome"]] = ""
        state[keys["peso"]] = 0.0
        state[keys["rd"]] = 0

    for p in PERICIAS:
        state[pericia_key(p)] = False

    for defesa in DEFESAS.values():
        state[f"defesa_{defesa}_bonus"] = 0
        state[f"defesa_{defesa}_custo"] = 0

    for i in range(NUM_ARMAS):
        keys = weapon_keys(i)
        state[keys["nome"]] = f"Arma {i + 1}"
        state[keys["test_dados"]] = 1
        state[keys["test_lados"]] = 20
        state[keys["bonus_ataque"]] = 0
        state[keys["dano_dados"]] = 1
        state[keys["dano_lados"]] = 6
        state[keys["bonus_dano"]] = 0
        state[keys["crit_min"]] = 20
        state[keys["crit_mult"]] = 2
        state[keys["custo_estamina"]] = 0
        state[keys["wa_texto"]] = ""
        state[keys["wa_estamina"]] = 0
        state[keys["wa_mana"]] = 0

    for i in range(NUM_INVENTARIO):
        keys = inventory_keys(i)
        state[keys["nome"]] = ""
        state[keys["qtd"]] = 0
        state[keys["desc"]] = ""

    for i in range(NUM_ACOES_TURNO):
        keys = turn_keys(i)
        state[keys["arma"]] = "Nenhuma"
        state[keys["modalidade"]] = "Normal"

    return state


def all_persisted_keys():
    """Lista de todas as chaves de session_state que compõem a ficha."""

    keys = [
        "nome_personagem", "nivel", "fragmentos_essencia",
        "pontos_atributo", "requiem_atual",
        "hp_atual", "mana_atual", "estamina_atual", "imagem_url", "token_url",
    ]

    for a in ATRIBUTOS:
        keys.append(attr_key(a))

    for i in range(len(ARMOR_SLOTS)):
        keys.extend(armor_keys(i).values())

    for p in PERICIAS:
        keys.append(pericia_key(p))

    for defesa in DEFESAS.values():
        keys.extend([f"defesa_{defesa}_bonus", f"defesa_{defesa}_custo"])

    for i in range(NUM_ARMAS):
        keys.extend(weapon_keys(i).values())

    for i in range(NUM_INVENTARIO):
        keys.extend(inventory_keys(i).values())

    for i in range(NUM_ACOES_TURNO):
        keys.extend(turn_keys(i).values())

    return keys


# ============================================================
# PERSISTÊNCIA (arquivo local + download/upload no navegador)
# ============================================================

def load_from_disk():
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
    return None


def save_to_disk(data: dict):
    try:
        tmp_file = DATA_FILE + ".tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, DATA_FILE)
    except OSError:
        # Em ambientes hospedados sem escrita em disco, ignora silenciosamente.
        # O jogador ainda pode usar Baixar/Carregar Ficha (.json).
        pass


def collect_state() -> dict:
    return {k: st.session_state[k] for k in all_persisted_keys() if k in st.session_state}


def apply_loaded_data(data: dict):
    """Aplica um dicionário carregado (arquivo local ou upload) ao session_state."""
    valid_keys = set(all_persisted_keys())
    for k, v in data.items():
        if k in valid_keys:
            st.session_state[k] = v


def init_session_state():

    if "ficha_inicializada" in st.session_state:
        return

    defaults = build_default_state()
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

    loaded = load_character(PLAYER_ID) if shared_enabled() else None
    if loaded:
        apply_loaded_data(loaded)

    # HP / Mana / Estamina atuais começam no máximo, se ainda não definidos
    atributos = {a: st.session_state[attr_key(a)] for a in ATRIBUTOS}

    if st.session_state.get("hp_atual") is None:
        hp_max, _, _ = calc_hp_max(atributos["Constituição"], atributos["Fortitude"])
        st.session_state["hp_atual"] = hp_max

    if st.session_state.get("mana_atual") is None:
        st.session_state["mana_atual"] = calc_mana_max(
            atributos["Carisma"], atributos["Sabedoria"], atributos["Inteligência"]
        )

    if st.session_state.get("estamina_atual") is None:
        st.session_state["estamina_atual"] = calc_estamina_max(
            atributos["Fortitude"], atributos["Força"], atributos["Destreza"]
        )

    st.session_state["ficha_inicializada"] = True
    if shared_enabled() and not loaded:
        save_character(PLAYER_ID, collect_state())
    st.session_state["_last_synced_snapshot"] = collect_state()


# ============================================================
# CALLBACKS
# ============================================================

def resetar_estamina_callback():
    atributos = {a: st.session_state[attr_key(a)] for a in ATRIBUTOS}
    st.session_state["estamina_atual"] = calc_estamina_max(
        atributos["Fortitude"], atributos["Força"], atributos["Destreza"]
    )


def aplicar_ponto_atributo_callback(atributo_escolhido):
    if st.session_state["pontos_atributo"] > 0:
        st.session_state[attr_key(atributo_escolhido)] += 1
        st.session_state["pontos_atributo"] -= 1


def carregar_upload_callback():
    arquivo = st.session_state.get("uploader_ficha")
    if arquivo is None:
        return
    try:
        data = json.loads(arquivo.getvalue().decode("utf-8"))
        apply_loaded_data(data)
        st.session_state["_upload_ok"] = True
    except (json.JSONDecodeError, UnicodeDecodeError):
        st.session_state["_upload_ok"] = False


# ============================================================
# RENDER: CABEÇALHO
# ============================================================

def render_header():

    st.markdown(
        '<div class="main-title">🌒 Sol da Meia-Noite</div>',
        unsafe_allow_html=True
    )
    col1, col2, col3 = st.columns([2.5, 1, 1.5])

    with col1:
        st.text_input("Nome do personagem", key="nome_personagem")

    with col2:
        st.number_input(
            "Nível", min_value=1, max_value=99, step=1, key="nivel"
        )

    with col3:
        st.number_input(
            "Fragmentos de Essência", min_value=0, step=1, key="fragmentos_essencia"
        )

    from image_manager import render_image_editor
    new_image_url = render_image_editor("portrait", PLAYER_ID,
                  st.session_state.get("imagem_url", ""), key=f"portrait_{PLAYER_ID}")
    if new_image_url != st.session_state.get("imagem_url"):
        st.session_state["imagem_url"] = new_image_url
    with st.expander("🎯 Token do mapa (PNG transparente)", expanded=False):
        new_token = render_image_editor("token", PLAYER_ID,
                       st.session_state.get("token_url", ""), key=f"token_{PLAYER_ID}")
        if new_token != st.session_state.get("token_url"):
            st.session_state["token_url"] = new_token





# ============================================================
# RENDER: ATRIBUTOS
# ============================================================

def render_atributos():

    with st.expander("Atributos", expanded=False):
        st.markdown('<div class="section-title">Atributos</div>', unsafe_allow_html=True)

        cols = st.columns(7)

        for col, nome in zip(cols, ATRIBUTOS):
            with col:
                st.markdown(f'<div class="attr-name">{nome}</div>', unsafe_allow_html=True)
                st.number_input(
                    nome, min_value=1, max_value=100, step=1,
                    key=attr_key(nome), label_visibility="collapsed"
                )
                mod = modificador(st.session_state[attr_key(nome)])
                sinal = "+" if mod >= 0 else ""
                st.markdown(
                    f'<div class="attr-mod">{sinal}{mod}</div>',
                    unsafe_allow_html=True
                )


def get_atributos_dict():
    return {a: st.session_state[attr_key(a)] for a in ATRIBUTOS}


def get_modificadores_dict():
    return {a: modificador(v) for a, v in get_atributos_dict().items()}


# ============================================================
# RENDER: BARRAS (HP / ESTAMINA / MANA)
# ============================================================

def sincronizar_recursos_compartilhados():
    """Banco prevalece em polling; mudanças locais são salvas por callback.
    
    Nunca reenvie um snapshot antigo a partir do fragment.
    """
    if not shared_enabled() or not st.session_state.get("ficha_inicializada"):
        return
    remote = load_character(PLAYER_ID)
    if not remote:
        return
    for key in ("hp_atual", "mana_atual", "estamina_atual"):
        if remote.get(key) is not None:
            st.session_state[key] = remote[key]
    st.session_state["_resource_snapshot"] = {key: st.session_state.get(key) for key in ("hp_atual", "mana_atual", "estamina_atual")}


def persist_resource(field):
    if not shared_enabled():
        return
    value = st.session_state.get(field)
    if patch_character(PLAYER_ID, {field: value}):
        snapshot = dict(st.session_state.get("_last_synced_snapshot", {}))
        snapshot[field] = value
        st.session_state["_last_synced_snapshot"] = snapshot


@st.fragment(run_every="5s")
def render_barras():

    sincronizar_recursos_compartilhados()
    atributos = get_atributos_dict()

    hp_max, hp_const, hp_fort = calc_hp_max(atributos["Constituição"], atributos["Fortitude"])
    mana_max = calc_mana_max(atributos["Carisma"], atributos["Sabedoria"], atributos["Inteligência"])
    estamina_max = calc_estamina_max(atributos["Fortitude"], atributos["Força"], atributos["Destreza"])

    col_hp, col_est, col_mana = st.columns(3)

    # ---------------- HP ----------------
    with col_hp:
        st.markdown('<div class="bar-container">', unsafe_allow_html=True)
        st.markdown('<div class="bar-title">❤️ Pontos de Vida</div>', unsafe_allow_html=True)

        st.number_input(
            "HP atual", min_value=0, step=1,
            key="hp_atual", label_visibility="collapsed", on_change=persist_resource, args=("hp_atual",)
        )

        pct = (st.session_state["hp_atual"] / hp_max * 100) if hp_max else 0
        pct = max(0, min(100, pct))

        st.markdown(
            f"""
            <div class="bar-value">{st.session_state['hp_atual']} / {hp_max}</div>
            <div class="bar-bg"><div class="bar-fill-hp" style="width:{pct}%;"></div></div>
            """,
            unsafe_allow_html=True
        )
        st.caption(f"HP (Constituição): {hp_const} · HP (Fortitude): {hp_fort}")
        st.markdown('</div>', unsafe_allow_html=True)

    # ---------------- Estamina ----------------
    with col_est:
        st.markdown('<div class="bar-container">', unsafe_allow_html=True)
        st.markdown('<div class="bar-title">🟢 Estamina</div>', unsafe_allow_html=True)

        st.number_input(
            "Estamina atual", min_value=0, step=1,
            key="estamina_atual", label_visibility="collapsed", on_change=persist_resource, args=("estamina_atual",)
        )

        pct_est = (st.session_state["estamina_atual"] / estamina_max * 100) if estamina_max else 0
        pct_est = max(0, min(100, pct_est))

        st.markdown(
            f"""
            <div class="bar-value">{st.session_state['estamina_atual']} / {estamina_max}</div>
            <div class="bar-bg"><div class="bar-fill-estamina" style="width:{pct_est}%;"></div></div>
            """,
            unsafe_allow_html=True
        )
        st.markdown('</div>', unsafe_allow_html=True)

    # ---------------- Mana ----------------
    with col_mana:
        st.markdown('<div class="bar-container">', unsafe_allow_html=True)
        st.markdown('<div class="bar-title">🔵 Mana</div>', unsafe_allow_html=True)

        st.number_input(
            "Mana atual", min_value=0, step=1,
            key="mana_atual", label_visibility="collapsed", on_change=persist_resource, args=("mana_atual",)
        )

        pct_mana = (st.session_state["mana_atual"] / mana_max * 100) if mana_max else 0
        pct_mana = max(0, min(100, pct_mana))

        st.markdown(
            f"""
            <div class="bar-value">{st.session_state['mana_atual']} / {mana_max}</div>
            <div class="bar-bg"><div class="bar-fill-mana" style="width:{pct_mana}%;"></div></div>
            """,
            unsafe_allow_html=True
        )
        st.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# RENDER: RESISTÊNCIA A DANO / RÉQUIEM / EQUIP LOAD
# ============================================================

def render_destaques():

    atributos = get_atributos_dict()

    rd_total = sum(int(st.session_state[armor_keys(i)["rd"]] or 0) for i in range(len(ARMOR_SLOTS)))
    peso_atual = sum(float(st.session_state[armor_keys(i)["peso"]] or 0) for i in range(len(ARMOR_SLOTS)))
    peso_max = calc_peso_max(atributos["Fortitude"], atributos["Constituição"])
    sobrepeso = peso_atual > peso_max

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown(
            f"""
            <div class="stat-highlight">
                <div class="stat-highlight-label">🛡️ Resistência a Dano</div>
                <div class="stat-highlight-value">{rd_total}</div>
            </div>
            """,
            unsafe_allow_html=True
        )
        st.caption("Soma do RD de Peitoral, Capacete, Braçadeiras e Botas.")

    with col2:
        st.markdown('<div class="info-box">', unsafe_allow_html=True)
        st.markdown('<div class="info-label">🌘 Réquiem ao Umbral</div>', unsafe_allow_html=True)
        st.number_input(
            "Réquiem ao Umbral", min_value=0, step=1,
            key="requiem_atual", label_visibility="collapsed"
        )
        st.markdown(
            f'<div class="info-value">{st.session_state["requiem_atual"]} / 100</div>',
            unsafe_allow_html=True
        )
        st.markdown('</div>', unsafe_allow_html=True)

    with col3:
        classe_extra = "overweight" if sobrepeso else ""
        st.markdown('<div class="info-box">', unsafe_allow_html=True)
        st.markdown('<div class="info-label">🎒 Equip Load</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="info-value {classe_extra}">'
            f'{formatar_peso(peso_atual)} / {formatar_peso(peso_max)}</div>',
            unsafe_allow_html=True
        )
        if sobrepeso:
            st.markdown(
                '<div class="warning-box">⚠️ SOBREPESO</div>',
                unsafe_allow_html=True
            )
        st.markdown('</div>', unsafe_allow_html=True)


# ============================================================
# RENDER: PERÍCIAS
# ============================================================

def render_pericias():

    with st.expander("Perícias", expanded=False):
        st.markdown('<div class="section-title">Perícias</div>', unsafe_allow_html=True)

        mods = get_modificadores_dict()

        header = st.columns([2.4, 1.2, 1, 1.4])
        for c, txt in zip(header, ["Perícia", "Modificador", "Treinado", "Bônus"]):
            with c:
                st.markdown(f"**{txt}**")

        for pericia, attrs_pericia in PERICIAS.items():

            mod_pericia = max(mods[a] for a in attrs_pericia)

            treinado = st.session_state[pericia_key(pericia)]
            bonus = bonus_treinado(mod_pericia) if treinado else bonus_nao_treinado(mod_pericia)

            cols = st.columns([2.4, 1.2, 1, 1.4])

            with cols[0]:
                st.write(f"**{pericia}** ({'/'.join(a[:3] for a in attrs_pericia)})")

            with cols[1]:
                sinal = "+" if mod_pericia >= 0 else ""
                st.write(f"{sinal}{mod_pericia}")

            with cols[2]:
                st.checkbox(
                    "Treinado", key=pericia_key(pericia), label_visibility="collapsed"
                )

            with cols[3]:
                sinal_b = "+" if bonus >= 0 else ""
                st.write(f"**{sinal_b}{bonus}**")


    # ============================================================
    # RENDER: DEFESAS
    # ============================================================

def render_defesas():
    with st.expander("Defesas e movimentação", expanded=False):
        for nome, chave in DEFESAS.items():
            c1, c2, c3 = st.columns([2, 1, 1])
            with c1:
                st.write(f"**{nome}** — rolagem 1d20 + bônus")
            with c2:
                st.number_input(f"Bônus {nome}", step=1, key=f"defesa_{chave}_bonus")
            with c3:
                st.number_input(f"Custo estamina {nome}", min_value=0, step=1, key=f"defesa_{chave}_custo")


# ============================================================
# RENDER: ARMAS
# ============================================================

def render_armas():

    with st.expander("Armas", expanded=False):
        st.markdown('<div class="section-title">Armas</div>', unsafe_allow_html=True)

        for i in range(NUM_ARMAS):

            keys = weapon_keys(i)

            with st.popover(f"Importar JSON — arma {i + 1}"):
                pasted = st.text_area("JSON da arma", key=f"weapon_json_{i}", height=130,
                    placeholder='{"nome":"Espada","test_dados":1,"test_lados":20,"bonus_ataque":5,"dano_dados":2,"dano_lados":6}')
                if st.button("Aplicar JSON", key=f"apply_weapon_json_{i}"):
                    try:
                        payload = json.loads(pasted)
                        if not isinstance(payload, dict):
                            raise ValueError("Esperado um objeto JSON.")
                        updates = {}
                        defaults = build_default_state()
                        for field, statekey in keys.items():
                            if field not in payload:
                                continue
                            value = payload[field]
                            if statekey in defaults and isinstance(defaults[statekey], int):
                                if isinstance(value, bool):
                                    raise ValueError(f"Campo inválido: {field}")
                                value = int(value)
                            elif not isinstance(value, str):
                                value = str(value)
                            if field in ("test_lados", "dano_lados") and value not in DICE_SIDES_OPTIONS:
                                raise ValueError(f"Dado inválido para {field}")
                            if field in ("test_dados", "dano_dados", "crit_min", "crit_mult") and value < 1:
                                raise ValueError(f"Valor inválido para {field}")
                            updates[statekey] = value
                        if not updates:
                            raise ValueError("Nenhum campo reconhecido.")
                        st.session_state.update(updates)
                        st.success("Arma importada. Os campos continuam editáveis.")
                        st.rerun()
                    except (ValueError, TypeError, json.JSONDecodeError) as exc:
                        st.error(f"JSON inválido: {exc}")

            with st.container():
                st.markdown('<div class="weapon-card">', unsafe_allow_html=True)

                st.text_input(f"Nome da arma {i + 1}", key=keys["nome"])

                st.markdown("**Ataque Padrão** — parâmetros manuais")

                c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(8)

                with c1:
                    st.number_input("Dados teste", min_value=1, max_value=10, step=1, key=keys["test_dados"])
                with c2:
                    st.selectbox("Lados teste", DICE_SIDES_OPTIONS, key=keys["test_lados"])
                with c3:
                    st.number_input("Bônus atq.", step=1, key=keys["bonus_ataque"])
                with c4:
                    st.number_input("Dados dano", min_value=1, max_value=20, step=1, key=keys["dano_dados"])
                with c5:
                    st.selectbox("Lados dano", DICE_SIDES_OPTIONS, key=keys["dano_lados"])
                with c6:
                    st.number_input("Bônus dano", step=1, key=keys["bonus_dano"])
                with c7:
                    st.number_input("Crít. mín.", min_value=1, max_value=100, step=1, key=keys["crit_min"])
                with c8:
                    st.number_input("Crít. x", min_value=1, max_value=20, step=1, key=keys["crit_mult"])

                st.number_input(
                    "Custo de estamina (ataque padrão)", min_value=0, step=1, key=keys["custo_estamina"]
                )

                # ---------- Linhas formatadas ----------
                td, tl = st.session_state[keys["test_dados"]], st.session_state[keys["test_lados"]]
                ba = st.session_state[keys["bonus_ataque"]]
                dd, dl = st.session_state[keys["dano_dados"]], st.session_state[keys["dano_lados"]]
                bd = st.session_state[keys["bonus_dano"]]
                cmin = st.session_state[keys["crit_min"]]
                cmult = st.session_state[keys["crit_mult"]]
                custo = st.session_state[keys["custo_estamina"]]

                linha_normal = (
                    f"{td}d{tl}{'+' if ba >= 0 else ''}{ba}  /  "
                    f"{dd}d{dl}{'+' if bd >= 0 else ''}{bd}  /  "
                    f"{cmin}-{tl} x{cmult}  /  Est: {custo}"
                )

                custo_carregado = custo * 2
                dd_carregado = dd * 3

                linha_carregada = (
                    f"{td}d{tl}{'+' if ba >= 0 else ''}{ba}  /  "
                    f"{dd_carregado}d{dl}{'+' if bd >= 0 else ''}{bd}  /  "
                    f"{cmin}-{tl} x{cmult}  /  Est: {custo_carregado}"
                )

                st.markdown(
                    f'<div class="attack-line">🗡️ <b>Ataque Padrão</b> &nbsp; {linha_normal}</div>',
                    unsafe_allow_html=True
                )
                st.markdown(
                    f'<div class="attack-line">💥 <b>Ataque Carregado</b> &nbsp; {linha_carregada}'
                    f'<br><span class="small-caption">Dano ×3 dados (bônus não é triplicado) · Estamina ×2</span></div>',
                    unsafe_allow_html=True
                )

                st.markdown("**Weapon Art**")
                wc1, wc2, wc3 = st.columns([3, 1, 1])
                with wc1:
                    st.text_area(
                        "Descrição da Weapon Art", key=keys["wa_texto"], height=80,
                        label_visibility="collapsed"
                    )
                with wc2:
                    st.number_input("Estamina", min_value=0, step=1, key=keys["wa_estamina"])
                with wc3:
                    st.number_input("Mana", min_value=0, step=1, key=keys["wa_mana"])

                st.markdown('</div>', unsafe_allow_html=True)


def get_weapon_names():
    return [st.session_state[weapon_keys(i)["nome"]] or f"Arma {i + 1}" for i in range(NUM_ARMAS)]


# ============================================================
# RENDER: ARMADURA
# ============================================================

def render_armadura():

    with st.expander("Armaduras", expanded=False):
        st.markdown('<div class="section-title">Armadura</div>', unsafe_allow_html=True)

        header = st.columns([1.4, 2.4, 1.2, 1.2])
        for c, txt in zip(header, ["Tipo", "Nome do Item", "Peso", "RD"]):
            with c:
                st.markdown(f"**{txt}**")

        for i, tipo in enumerate(ARMOR_SLOTS):

            keys = armor_keys(i)
            cols = st.columns([1.4, 2.4, 1.2, 1.2])

            with cols[0]:
                st.write(f"**{tipo}**")
            with cols[1]:
                st.text_input(f"Nome {tipo}", key=keys["nome"], label_visibility="collapsed")
            with cols[2]:
                st.number_input(
                    f"Peso {tipo}", min_value=0.0, step=0.1, format="%.1f",
                    key=keys["peso"], label_visibility="collapsed"
                )
            with cols[3]:
                st.number_input(
                    f"RD {tipo}", min_value=0, step=1,
                    key=keys["rd"], label_visibility="collapsed"
                )


    # ============================================================
    # RENDER: INVENTÁRIO
    # ============================================================

def render_inventario():

    with st.expander("Inventário", expanded=False):
        st.markdown('<div class="section-title">Inventário</div>', unsafe_allow_html=True)

        col_a, col_b = st.columns(2)
        metade = (NUM_INVENTARIO + 1) // 2

        for idx_col, (col, faixa) in enumerate(
            zip([col_a, col_b], [range(0, metade), range(metade, NUM_INVENTARIO)])
        ):
            with col:
                for i in faixa:
                    keys = inventory_keys(i)

                    c1, c2 = st.columns([3, 1])
                    with c1:
                        st.text_input(
                            f"Item {i + 1}", key=keys["nome"],
                            placeholder=f"Item {i + 1}", label_visibility="collapsed"
                        )
                    with c2:
                        st.number_input(
                            f"Qtd {i + 1}", min_value=0, step=1,
                            key=keys["qtd"], label_visibility="collapsed"
                        )

                    titulo = st.session_state[keys["nome"]] or f"Item {i + 1}"
                    with st.expander(f"📝 Descrição — {titulo}"):
                        st.text_area(
                            f"Descrição {i + 1}", key=keys["desc"], height=70,
                            label_visibility="collapsed"
                        )


    # ============================================================
    # RENDER: PLANEJADOR DE AÇÕES DO TURNO
    # ============================================================

def render_planejador_turno():

    with st.expander("Planejador de ações do turno", expanded=False):
        st.markdown('<div class="section-title">Planejador de Ações do Turno</div>', unsafe_allow_html=True)
        st.caption(
            "Ferramenta apenas de planejamento — não aplica dano nem desconta estamina automaticamente."
        )

        nomes_armas = ["Nenhuma"] + get_weapon_names()
        custo_planejado_total = 0

        for i in range(NUM_ACOES_TURNO):

            keys = turn_keys(i)
            cols = st.columns([0.4, 2.4, 1.6, 1.4])

            with cols[0]:
                st.write(f"**{i + 1}.**")

            with cols[1]:
                if st.session_state[keys["arma"]] not in nomes_armas:
                    st.session_state[keys["arma"]] = "Nenhuma"
                arma_escolhida = st.selectbox(
                    f"Arma ação {i + 1}", nomes_armas,
                    key=keys["arma"], label_visibility="collapsed"
                )

            with cols[2]:
                modalidade = st.selectbox(
                    f"Modalidade ação {i + 1}", MODALIDADES,
                    key=keys["modalidade"], label_visibility="collapsed"
                )

            custo_acao = 0
            if arma_escolhida != "Nenhuma":
                idx_arma = nomes_armas.index(arma_escolhida) - 1
                wkeys = weapon_keys(idx_arma)
                custo_base = st.session_state[wkeys["custo_estamina"]]

                if modalidade == "Normal":
                    custo_acao = custo_base
                elif modalidade == "Carregado":
                    custo_acao = custo_base * 2
                else:  # Weapon Art
                    custo_acao = st.session_state[wkeys["wa_estamina"]]

            with cols[3]:
                st.write(f"Est: **{custo_acao}**")

            custo_planejado_total += custo_acao

        atributos = get_atributos_dict()
        estamina_max = calc_estamina_max(atributos["Fortitude"], atributos["Força"], atributos["Destreza"])

        excede = custo_planejado_total > estamina_max
        classe = "overweight" if excede else ""

        st.markdown(
            f'<div class="info-box"><div class="info-label">Estamina planejada</div>'
            f'<div class="info-value {classe}">{custo_planejado_total} / {estamina_max}</div></div>',
            unsafe_allow_html=True
        )
        if excede:
            st.caption("⚠️ O total planejado ultrapassa a estamina máxima (apenas informativo).")


    # ============================================================
    # SIDEBAR: PERSISTÊNCIA
    # ============================================================



def sync_shared_state(pull=True):
    """Only patch changed fields; never send an old copy of all resources."""
    if not shared_enabled() or not st.session_state.get("ficha_inicializada"):
        return
    current = collect_state()
    snapshot = st.session_state.get("_last_synced_snapshot", {})
    resources = {"hp_atual", "mana_atual", "estamina_atual"}
    changed = {key: value for key, value in current.items()
               if key not in resources and snapshot.get(key) != value}
    if changed:
        if patch_character(PLAYER_ID, changed):
            latest = dict(snapshot)
            latest.update(changed)
            st.session_state["_last_synced_snapshot"] = latest
        return
    if pull:
        remote = load_character(PLAYER_ID)
        if remote:
            apply_loaded_data(remote)
            st.session_state["_last_synced_snapshot"] = collect_state()


# ============================================================
# APP PRINCIPAL
# ============================================================

def main():

    init_session_state()
    sync_shared_state()

    render_header()
    render_atributos()
    render_barras()
    render_destaques()
    render_pericias()
    render_defesas()
    render_armas()
    render_armadura()
    render_inventario()

    # Persist user edits after widgets, without changing their widget state.
    sync_shared_state(pull=False)


if __name__ == "__main__":
    main()
