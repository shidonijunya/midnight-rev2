import json
import os
import re

import streamlit as st
from shared_backend import load_character, fetch_character, create_character_if_missing, save_character, patch_character, shared_enabled, upload_asset

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

[data-testid="stVerticalBlock"] { gap: .38rem; }
.block-container { padding-top: 1rem; padding-bottom: 1rem; }
.bar-container:empty { display: none; }
.bar-value { font-size: 1.1rem; margin: 0; }
.bar-bg { height: 10px; }
.info-box,.attr-box,.stat-highlight { padding: 5px 8px; }
.main-title { font-size: 1.55rem; }
.block-container { max-width: 1680px; padding-top: 3rem; }
.st-key-sheet-overview { background: #191b24; }
.stat-highlight { border:0; background:transparent; padding:0; text-align:left; }
.stat-highlight-label,.info-label,.bar-title { color:#bfc5d4; font-size:.73rem; letter-spacing:.045em; line-height:1.4; }
.stat-highlight-value,.info-value { color:#eef0f6; font-size:1.2rem; }
[data-testid="stVerticalBlock"] { gap:.6rem; }
[data-testid="stTabs"] [role="tablist"] { overflow-x:auto; gap:.8rem; }
.stMainBlockContainer.block-container { padding-top: 4.5rem; }
.st-key-sheet-overview { padding: 1rem; }
.st-key-sheet-secondary { margin-top:.85rem; padding-top:.65rem; border-top:1px solid #343844; }
.attr-mod { margin:0; text-align:center; line-height:1.2; padding:0 0 .45rem; }
[data-testid="stColumn"]:has(.attr-mod) [data-testid="stVerticalBlock"] { gap:.22rem; }
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

NUM_ARMAS = 12  # capacidade máxima; as 5 armas antigas continuam visíveis por padrão
NUM_INVENTARIO = 15

MODALIDADES = ["Normal", "Carregado", "Weapon Art"]

DICE_SIDES_OPTIONS = [4, 6, 8, 10, 12, 20, 100]

DEFESAS = {"Parry": "parry", "Rolagem": "rolagem", "Bloquear": "bloquear", "Pular": "pular", "Correr": "correr"}
PLAYER_ID = "jogador_1"
PLAYER_NAME = "Bondobo"

# ============================================================
# FÓRMULAS DO SISTEMA
# ============================================================

from game_rules import (
    modificador, bonus_nao_treinado, bonus_treinado,
    arredondar_para_cima, calc_hp_max, calc_mana_max,
    calc_estamina_max, calc_peso_max, formatar_peso,
)


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


def build_default_state() -> dict:
    """Constrói o dicionário completo de valores padrão da ficha."""

    state = {
        "nome_personagem": PLAYER_NAME,
        "nivel": 1,
        "fragmentos_essencia": 0,
        "weapon_slots_count": 5,
        "inventory_count": 8,
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

    return state


def all_persisted_keys(extra_keys=()):
    """Lista de todas as chaves de session_state que compõem a ficha."""

    keys = [
        "nome_personagem", "nivel", "fragmentos_essencia",
        "weapon_slots_count", "inventory_count", "requiem_atual",
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

    keys.extend(k for k in (*st.session_state.keys(), *extra_keys)
                if re.fullmatch(r"inv_\d+_(nome|qtd|desc)", str(k)))
    return keys


# ============================================================
# PERSISTÊNCIA (arquivo local + download/upload no navegador)
# ============================================================

def collect_state() -> dict:
    return {k: st.session_state[k] for k in all_persisted_keys() if k in st.session_state}


def apply_loaded_data(data: dict):
    """Aplica um dicionário carregado (arquivo local ou upload) ao session_state."""
    valid_keys = set(all_persisted_keys(data))
    for k, v in data.items():
        if k in valid_keys:
            st.session_state[k] = v


def init_session_state():

    if "ficha_inicializada" in st.session_state:
        return

    defaults = build_default_state()
    for k, v in defaults.items():
        st.session_state.setdefault(k, v)

    loaded = None
    if shared_enabled():
        result = fetch_character(PLAYER_ID)
        if result["status"] in ("error", "forbidden"):
            st.error("Não foi possível confirmar a ficha no Supabase. Por segurança, nenhuma ficha padrão será gravada.")
            st.stop()
        if result["status"] == "missing":
            # Create only if absent, never upsert defaults over another player's progress.
            if not create_character_if_missing(PLAYER_ID, defaults):
                st.error("Não foi possível criar o registro inicial da ficha.")
                st.stop()
            result = fetch_character(PLAYER_ID)
            if result["status"] != "found":
                st.error("Não foi possível confirmar os dados da ficha recém-criada.")
                st.stop()
        loaded = result["data"]
        if isinstance(loaded, dict):
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
    st.session_state["_last_synced_snapshot"] = collect_state()


# ============================================================
# CALLBACKS
# ============================================================

def resetar_estamina_callback():
    atributos = {a: st.session_state[attr_key(a)] for a in ATRIBUTOS}
    st.session_state["estamina_atual"] = calc_estamina_max(
        atributos["Fortitude"], atributos["Força"], atributos["Destreza"]
    )


# ============================================================
# RENDER: CABEÇALHO
# ============================================================

def render_header():

    col1, col2, col3, portrait = st.columns([2.3, 1, 1.6, .85], vertical_alignment="bottom")

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

    with portrait.popover("🖼️", help="Alterar retrato do personagem"):
        from image_manager import render_image_editor
        new_image_url = render_image_editor("portrait", PLAYER_ID,
                      st.session_state.get("imagem_url", ""), key=f"portrait_{PLAYER_ID}")
        if new_image_url != st.session_state.get("imagem_url"):
            st.session_state["imagem_url"] = new_image_url







def render_atributos():


    for index, nome in enumerate(ATRIBUTOS):
        if index % 4 == 0:
            cols = st.columns(4)
        with cols[index % 4]:
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


    # ---------------- Estamina ----------------
    with col_est:
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


    # ---------------- Mana ----------------
    with col_mana:
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

    with col2:
        st.markdown('<div class="info-label">🌘 Réquiem ao Umbral</div>', unsafe_allow_html=True)
        st.number_input(
            "Réquiem ao Umbral", min_value=0, step=1,
            key="requiem_atual", label_visibility="collapsed"
        )
        st.markdown(
            f'<div class="info-value">{st.session_state["requiem_atual"]} / 100</div>',
            unsafe_allow_html=True
        )


    with col3:
        classe_extra = "overweight" if sobrepeso else ""
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



# ============================================================
# RENDER: PERÍCIAS
# ============================================================

def render_pericias():


    mods = get_modificadores_dict()

    header = st.columns([2.4, 1.2, 1, 1.4], vertical_alignment="center")
    for c, txt in zip(header, ["Perícia", "Modificador", "Treinado", "Bônus"]):
        with c:
            st.markdown(f"**{txt}**")

    for pericia, attrs_pericia in PERICIAS.items():

        mod_pericia = max(mods[a] for a in attrs_pericia)

        treinado = st.session_state[pericia_key(pericia)]
        bonus = bonus_treinado(mod_pericia) if treinado else bonus_nao_treinado(mod_pericia)

        cols = st.columns([2.4, 1.2, 1, 1.4], vertical_alignment="center")

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

    st.number_input("Quantidade de armas", min_value=1, max_value=NUM_ARMAS,
                    step=1, key="weapon_slots_count",
                    help="Ao reduzir a quantidade, os dados dos slots ocultos são preservados.")
    for i in range(int(st.session_state["weapon_slots_count"])):

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


            st.text_input(f"Nome da arma {i + 1}", key=keys["nome"])

            st.markdown("**Ataque Padrão** — parâmetros manuais")

            st.markdown("**Ataque**")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.number_input("Dados teste", min_value=1, max_value=10, step=1, key=keys["test_dados"])
            with c2:
                st.selectbox("Lados teste", DICE_SIDES_OPTIONS, key=keys["test_lados"])
            with c3:
                st.number_input("Bônus atq.", step=1, key=keys["bonus_ataque"])
            st.markdown("**Dano**")
            c4, c5, c6 = st.columns(3)
            with c4:
                st.number_input("Dados dano", min_value=1, max_value=20, step=1, key=keys["dano_dados"])
            with c5:
                st.selectbox("Lados dano", DICE_SIDES_OPTIONS, key=keys["dano_lados"])
            with c6:
                st.number_input("Bônus dano", step=1, key=keys["bonus_dano"])
            with st.popover("Crítico e Weapon Art"):
                c7, c8 = st.columns(2)
                with c7:
                    st.number_input("Crítico mín.", min_value=1, max_value=100, step=1, key=keys["crit_min"])
                with c8:
                    st.number_input("Crítico ×", min_value=1, max_value=20, step=1, key=keys["crit_mult"])
                st.text_area("Descrição da Weapon Art", key=keys["wa_texto"], height=80)
                wc1, wc2 = st.columns(2)
                with wc1:
                    st.number_input("Estamina WA", min_value=0, step=1, key=keys["wa_estamina"])
                with wc2:
                    st.number_input("Mana WA", min_value=0, step=1, key=keys["wa_mana"])

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



def get_weapon_names():
    return [st.session_state[weapon_keys(i)["nome"]] or f"Arma {i + 1}" for i in range(int(st.session_state.get("weapon_slots_count", 5)))]


# ============================================================
# RENDER: ARMADURA
# ============================================================

def render_armadura():


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

def resize_inventory(expected, remove=False):
    state = st.session_state
    count = state.get("inventory_count", 8)
    if count != expected or (remove and count == 0):
        return
    changes = {"inventory_count": count - 1 if remove else count + 1}
    if remove:
        keys = inventory_keys(count - 1)
        changes.update({keys["nome"]: "", keys["qtd"]: 0, keys["desc"]: ""})
    if shared_enabled() and not patch_character(PLAYER_ID, changes):
        state["_inventory_error"] = True
        return
    state.update(changes)
    state.setdefault("_last_synced_snapshot", {}).update(changes)


def render_inventario():
    count = st.session_state.get("inventory_count", 8)
    with st.container(horizontal=True):
        st.button("Adicionar item", on_click=resize_inventory, args=(count,))
        with st.popover("Excluir último", disabled=count == 0):
            name = st.session_state.get(inventory_keys(count - 1)["nome"]) or f"Item {count}"
            st.write(f'Excluir o item {count} (“{name}”), a quantidade e a descrição?')
            st.button("Confirmar exclusão", key=f"delete_inventory_{count}",
                      on_click=resize_inventory, args=(count, True), type="primary")
    if st.session_state.pop("_inventory_error", False):
        st.error("Não foi possível salvar a alteração no inventário.")
    metade = (count + 1) // 2
    for col, faixa in zip(st.columns(2), (range(metade), range(metade, count))):
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

    overview, editor = st.columns([1, 1.35], gap="medium")
    with overview, st.container(border=True, key="sheet-overview"):
        render_header()
        render_barras()
        with st.container(key="sheet-secondary"):
            render_destaques()
    with editor:
        sections = {
            "Atributos": render_atributos, "Perícias": render_pericias,
            "Defesas": render_defesas, "Armas": render_armas,
            "Armadura": render_armadura, "Inventário": render_inventario,
        }
        for tab, render in zip(st.tabs(list(sections)), sections.values()):
            with tab, st.container(height=490):
                render()

    # Persist user edits after widgets, without changing their widget state.
    sync_shared_state(pull=False)


if __name__ == "__main__":
    main()
