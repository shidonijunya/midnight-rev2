"""Painel da mesa: ficha à esquerda; rolador 3D e chat à direita."""
import html
import inspect
import math
import re
import secrets
import uuid
from datetime import datetime, timezone

import streamlit as st

from shared_backend import (shared_enabled, load_character, save_character, patch_character, load_app_state, save_app_state, upload_asset,
                            publish_roll, send_chat_message, get_chat_messages, clean_author,
                            config_value)
import dice3d

st.set_page_config(page_title="Painel da Mesa", page_icon="🎲", layout="wide")
from auth_unified import require_role
require_role()


st.markdown("""
<style>
.stApp {background:#101116;color:#ececf1}
header[data-testid="stHeader"] {background:transparent;height:2rem}
.block-container {max-width:1800px;padding-top:2.2rem;padding-bottom:1rem;padding-left:1rem;padding-right:1rem}
h4, h5 {margin:.1rem 0 .35rem 0 !important;padding:0 !important;font-size:.95rem !important;letter-spacing:.04em;text-transform:uppercase;color:#b8bacb}
[data-testid="stForm"] {border:none;padding:0}
[data-testid="stVerticalBlock"] {gap:.55rem}
.card {background:#191b23;border:1px solid #30323d;border-radius:12px;padding:10px 12px}
.who {display:flex;align-items:center;gap:10px}
.who img {width:54px;height:54px;border-radius:50%;object-fit:cover;border:2px solid #3b3e4d}
.who .nm {font-weight:800;font-size:1.05rem;line-height:1.15}
.who .sub {font-size:.75rem;color:#a1a4b3}
.res {display:grid;grid-template-columns:44px 1fr 66px;align-items:center;gap:8px;margin:5px 0}
.res .rl {font-size:.72rem;color:#b8bacb;text-transform:uppercase;letter-spacing:.05em}
.res .rb {height:8px;background:#2b2d38;border-radius:6px;overflow:hidden}
.res .rb i {display:block;height:100%;border-radius:6px}
.res .rv {font-size:.8rem;font-weight:700;text-align:right;font-variant-numeric:tabular-nums}
.attrs {display:grid;grid-template-columns:repeat(4,1fr);gap:5px;margin-top:6px}
.attr {background:#1f212b;border:1px solid #2f3240;border-radius:8px;padding:3px 4px;text-align:center}
.attr .an {font-size:.62rem;color:#9a9db0;letter-spacing:.06em}
.attr .av {font-size:1rem;font-weight:800;line-height:1.1}
.attr .am {font-size:.68rem;color:#8fd0a8}
.mini {display:grid;grid-template-columns:90px 1fr;gap:6px;align-items:center;font-size:.74rem;margin:4px 0}
.mini .bars div {height:5px;background:#2b2d38;border-radius:4px;margin:2px 0;overflow:hidden}
.mini .bars i {display:block;height:100%}
.chat-card {background:#1a1d27;border:1px solid #363948;border-left:3px solid #9c7bff;border-radius:8px;padding:6px 9px;margin:0 0 6px 0;font-size:.86rem}
.chat-card.dice {border-left-color:#5488ff;background:#152238}.chat-card.attack {border-left-color:#ef4250;background:#321821;box-shadow:inset 0 0 16px #6f1f2633}.chat-card.defense {border-left-color:#45bd83;background:#142b24}
.boss-name{text-align:center;font-family:Georgia,serif;font-size:1.6rem;font-weight:900;letter-spacing:.1em;color:#efc9aa;text-shadow:0 2px 12px #a4453f}
.boss-bar{height:18px;border-radius:12px;background:#292025;overflow:hidden;border:1px solid #5c2930}.boss-bar div{height:100%;background:linear-gradient(90deg,#731522,#ed3444);transition:width .4s}
.boss-empty{min-height:180px;border:1px solid #282b34;border-radius:14px;background:#121318}
div[data-testid="stButton"] button[kind="primary"] {background:#971f2d;border-color:#971f2d;color:white}
.chat-head {display:flex;justify-content:space-between;font-size:.72rem;color:#9a9db0;margin-bottom:2px}
.chat-head b {color:#d7d9e6}
.chat-title {font-weight:800;font-size:.9rem;margin-bottom:2px}
.result-card {background:#191b23;border:1px solid #30323d;border-radius:10px;padding:8px 12px;font-size:.88rem;line-height:1.45}
.result-card.warn {border-color:#e0a02f}
.muted {font-size:.78rem;color:#a1a4b3}
</style>
""", unsafe_allow_html=True)

PLAYER_IDS = ["jogador_1", "jogador_2", "jogador_3"]
PLAYER_LABELS = {"jogador_1": "Kuro", "jogador_2": "Andrias", "jogador_3": "Bondobo"}
DICE_SIDES = [4, 6, 8, 10, 12, 20, 100]
DEFENSES = [("Parry", "parry"), ("Rolagem", "rolagem"), ("Bloquear", "bloquear"), ("Pular", "pular"), ("Correr", "correr")]
ATTR_ABBR = [("Força", "FOR"), ("Destreza", "DES"), ("Constituição", "CON"), ("Inteligência", "INT"),
             ("Sabedoria", "SAB"), ("Carisma", "CAR"), ("Fortitude", "FRT")]
NUM_WEAPONS = 5
# `use_container_width` está obsoleto nas versões novas do Streamlit; usa `width="stretch"` quando existir.
try:
    _HAS_WIDTH = "width" in inspect.signature(st.button).parameters
except (TypeError, ValueError):
    _HAS_WIDTH = False
STRETCH = {"width": "stretch"} if _HAS_WIDTH else {"use_container_width": True}
MAX_QTY = 1000
RNG = secrets.SystemRandom()
ss = st.session_state


# ----------------------------------------------------------------- regras / utilidades
def num(value, default=0):
    """Converte para int sem levantar exceção (None, '', texto e float viram valores seguros)."""
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def signed(n):
    return f"+{n}" if n >= 0 else str(n)


def attr_value(data, name):
    v = data.get(f"attr_{name}")
    return num(v, 10) if v is not None else 10


def attr_mod(value):
    """Mesma fórmula da ficha: floor((valor - 1) / 2) - 5."""
    return (value - 10) // 2


def _ceil(x):
    return math.ceil(round(x, 6))


def maxima(data):
    """Máximos de HP, mana e estamina — mesmas fórmulas das fichas."""
    f, d, c, i, s, cha, fort = (attr_value(data, n) for n, _ in ATTR_ABBR)
    hp = 50 + (c - 10) * 6 + (fort - 10) * 2
    mana = _ceil(cha * 1.7 + s * 1.7 + i * 2.3)
    stamina = _ceil(fort * 4.6 + f * 1.2 + d * 1.2)
    return max(0, hp), max(0, mana), max(0, stamina)


def resources(data):
    """(hp, hp_max, mana, mana_max, estamina, estamina_max) com valores sempre dentro dos limites."""
    hpmax, manamax, stmax = maxima(data)

    def cur(key, mx):
        v = data.get(key)
        return max(0, num(v, mx) if v is not None else mx)

    return (cur("hp_atual", hpmax), hpmax, cur("mana_atual", manamax), manamax,
            cur("estamina_atual", stmax), stmax)


def rd_total(data):
    return sum(num(data.get(f"armor_{i}_rd"), 0) for i in range(4))


def roll_dice(qty, sides):
    return [RNG.randint(1, sides) for _ in range(qty)]


def char_name(data, pid):
    return str((data or {}).get("nome_personagem") or "").strip() or PLAYER_LABELS.get(pid, "Jogador")


def fresh(pid):
    return load_character(pid) or {}


def fmt(text):
    """Escapa HTML e converte **negrito** e quebras de linha."""
    safe = html.escape(str(text))
    safe = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", safe)
    return safe.replace("\n", "<br>")


def show_html(html_str, height):
    """Render HTML inside a Streamlit component, not as an iframe URL."""
    import streamlit.components.v1 as components
    components.html(html_str, height=height, scrolling=False)


def effective_name():
    """Nome de exibição: o que o usuário digitou; senão o personagem selecionado."""
    typed = clean_author(ss.get("display_name"), default="")
    if typed:
        return typed
    pid = ss.get("sel_player")
    return (ss.get("_char_names") or {}).get(pid) or "Jogador"


def set_result(**kw):
    kw.setdefault("id", uuid.uuid4().hex)
    ss["last_result"] = kw


def set_error(*lines):
    set_result(kind="error", caption="", groups=[], totals=[], warn=True, published=True, lines=list(lines))


# ----------------------------------------------------------------- callbacks (executam uma única vez por clique)
def cb_roll(sides=None, expression=None):
    """Roll fixed die or safe NdM+K syntax without evaluating arbitrary code."""
    if expression is not None:
        matched = re.fullmatch(r"\s*(\d{1,3})d(4|6|8|10|12|20|100)\s*([+-]\s*\d{1,4})?\s*", expression, re.I)
        if not matched:
            set_error("Digite uma expressão como 2d20+7, 1d8 ou 3d6-2.")
            return
        qty, sides = int(matched.group(1)), int(matched.group(2))
        bonus = int((matched.group(3) or "0").replace(" ", ""))
    else:
        qty = max(1, min(MAX_QTY, num(ss.get("dice_qty"), 1)))
        sides = sides or num(ss.get("dice_sides"), 20)
        bonus = num(ss.get("dice_bonus"), 0)
    if qty < 1 or qty > MAX_QTY or sides not in DICE_SIDES:
        set_error("Quantidade ou tipo de dado inválido.")
        return
    who = effective_name()
    results = roll_dice(qty, sides)
    total = sum(results) + bonus
    label = f"{qty}d{sides}{signed(bonus) if bonus else ''}"
    shown = results[:20]
    details = f"Rolagem: {label}\nDados: {shown}{' …' if len(results) > 20 else ''}\nTotal: **{total}**"
    payload = {"title": f"{who} — {label}", "details": details,
               "dice": {"sides": sides, "qty": qty, "bonus": bonus, "total": total, "results": results[:40]}}
    ok = publish_roll("dice", payload, who, notify=False)
    set_result(kind="dice", caption=f"{who} — {label}",
               groups=[{"label": "", "sides": sides, "values": results}],
               totals=[{"label": "Total", "value": total}],
               lines=[details], published=ok)


def cb_send_chat():
    ok, err = send_chat_message(effective_name(), ss.get("chat_msg", ""))
    if ok:
        ss["chat_msg"] = ""           # só limpa depois do sucesso confirmado
        ss["chat_feedback"] = None
    else:
        ss["chat_feedback"] = {"level": "warning" if "Escreva" in (err or "") else "error", "text": err}


def cb_save_resources(pid, field, widget_key):
    """Persist only the edited resource, merging with a fresh record."""
    data = fresh(pid)
    if not data:
        ss["notice"] = {"level": "error", "text": "Ficha não encontrada."}
        return
    data[field] = max(0, num(ss.get(widget_key)))
    if patch_character(pid, {field: data[field]}):
        ss[f"resource_snapshot_{pid}_{field}"] = data[field]
    else:
        ss["notice"] = {"level": "error", "text": "Erro ao salvar recurso."}


def cb_reset_stamina(pid):
    data = fresh(pid)
    if not data:
        ss["notice"] = {"level": "error", "text": "Essa ficha ainda não tem dados salvos."}
        return
    data["estamina_atual"] = maxima(data)[2]
    if patch_character(pid, {"estamina_atual": data["estamina_atual"]}):
        publish_roll("text", {"text": f"{char_name(data, pid)} recuperou toda a estamina."}, "Sistema", notify=False)
        ss["notice"] = {"level": "success", "text": "Estamina restaurada."}
    else:
        ss["notice"] = {"level": "error", "text": "Não foi possível salvar a estamina no Supabase."}


def cb_defense(pid, key, label):
    data = fresh(pid)
    if not data:
        set_error("Essa ficha ainda não tem dados salvos.")
        return
    _, _, _, _, st_cur, st_max = resources(data)
    bonus = num(data.get(f"defesa_{key}_bonus"), 0)
    cost = num(data.get(f"defesa_{key}_custo"), 0)
    name = char_name(data, pid)
    if st_cur < cost:
        set_error(f"Estamina insuficiente para **{label}**: custo {cost}, disponível {st_cur}.")
        return
    roll = roll_dice(1, 20)
    total = roll[0] + bonus
    data["estamina_atual"] = st_cur - cost
    if not patch_character(pid, {"estamina_atual": data["estamina_atual"]}):
        set_error("Não foi possível salvar a estamina; a defesa não foi registrada.")
        return
    details = (f"{label}: 1d20 ({roll[0]}) {signed(bonus)} = **{total}**\n"
               f"Estamina: -{cost} · restante {data['estamina_atual']}/{st_max}")
    ok = publish_roll("defense", {"title": f"{name} — {label}", "details": details,
                                  "dice": {"sides": 20, "qty": 1, "bonus": bonus, "total": total, "results": roll}},
                      effective_name(), notify=False)
    set_result(kind="defense", caption=f"{name} — {label}",
               groups=[{"label": label, "sides": 20, "values": roll}],
               totals=[{"label": "Total", "value": total}],
               lines=details.split("\n"), published=ok)


def missing_weapon_fields(data, wk):
    needed = ["test_dados", "test_lados", "dano_dados", "dano_lados"]
    return [n for n in needed if data.get(wk + n) in (None, "")]


def cb_attack(pid, slot=0):
    data = fresh(pid)
    if not data:
        set_error("Essa ficha ainda não tem dados salvos. Salve a ficha no app do jogador primeiro.")
        return
    widx = ss.get(f"atk_weapon_{pid}_{slot}")
    modality = ss.get(f"atk_mod_{pid}_{slot}", "Normal")
    if widx is None:
        set_error("Nenhuma arma configurada. Preencha o **nome da arma** na ficha do jogador.")
        return
    wk = f"arma_{widx}_"
    wname = str(data.get(wk + "nome") or f"Arma {widx + 1}")
    name = char_name(data, pid)
    who = effective_name()
    _, _, mana_cur, _, st_cur, st_max = resources(data)

    if modality == "Weapon Art":
        est, mana = num(data.get(wk + "wa_estamina"), 0), num(data.get(wk + "wa_mana"), 0)
        if st_cur < est or mana_cur < mana:
            set_error(f"Recursos insuficientes para a Weapon Art. Estamina: {st_cur}/{est}; mana: {mana_cur}/{mana}.")
            return
        data["estamina_atual"], data["mana_atual"] = st_cur - est, mana_cur - mana
        if not patch_character(pid, {"estamina_atual": data["estamina_atual"], "mana_atual": data["mana_atual"]}):
            set_error("Não foi possível salvar os recursos; a ação não foi registrada.")
            return
        desc = str(data.get(wk + "wa_texto") or "").strip() or "Sem descrição cadastrada."
        details = (f"Weapon Art selecionada.\nDescrição: {desc}\nCusto: -{est} estamina e -{mana} mana.\n"
                   "Rolagem e efeito: manuais (a ficha não define fórmula para Weapon Art).")
        ok = publish_roll("attack", {"title": f"{name} — {wname} / Weapon Art", "details": details}, who, notify=False)
        set_result(kind="attack", caption=f"{name} — {wname} / Weapon Art", groups=[], totals=[],
                   lines=details.split("\n"), published=ok)
        return

    missing = missing_weapon_fields(data, wk)
    if missing:
        set_error(f"A arma **{wname}** está sem configuração: {', '.join(missing)}. "
                  "Abra a ficha do jogador, preencha o ataque padrão da arma e salve.")
        return
    td, tl = max(1, num(data.get(wk + "test_dados"), 1)), num(data.get(wk + "test_lados"), 20)
    dd, dl = max(1, num(data.get(wk + "dano_dados"), 1)), num(data.get(wk + "dano_lados"), 6)
    ba, bd = num(data.get(wk + "bonus_ataque"), 0), num(data.get(wk + "bonus_dano"), 0)
    critmin = num(data.get(wk + "crit_min"), 20)
    critmult = max(1, num(data.get(wk + "crit_mult"), 2))
    if tl not in DICE_SIDES or dl not in DICE_SIDES:
        set_error(f"A arma **{wname}** usa um tipo de dado inválido (d{tl} / d{dl}). Corrija na ficha.")
        return
    cost = num(data.get(wk + "custo_estamina"), 0)
    if modality == "Carregado":
        cost *= 2
        dd *= 3                         # regra da ficha: dano x3 dados, bônus não triplica; estamina x2
    if st_cur < cost:
        set_error(f"Estamina insuficiente: custo {cost}, disponível {st_cur}.")
        return
    test = roll_dice(td, tl)
    attack_total = sum(test) + ba
    dmg_rolls = roll_dice(dd, dl)
    base_damage = sum(dmg_rolls) + bd
    crit = any(v >= critmin for v in test)
    damage = base_damage * critmult if crit else base_damage
    data["estamina_atual"] = st_cur - cost
    if not patch_character(pid, {"estamina_atual": data["estamina_atual"]}):
        set_error("Não foi possível salvar a estamina; o ataque não foi registrado.")
        return
    dmg_line = f"Dano: {dmg_rolls} {signed(bd)} = **{base_damage}**"
    if crit:
        dmg_line += f" × {critmult} = **{damage}** (CRÍTICO)"
    details = (f"Tipo: {modality}\nTeste: {test} {signed(ba)} = **{attack_total}**\n{dmg_line}\n"
               f"Estamina: -{cost} · restante {data['estamina_atual']}/{st_max}\n"
               "Dano não é aplicado automaticamente ao alvo.")
    payload = {"title": f"{name} — {wname}", "details": details,
               "dice": {"attack": {"sides": tl, "results": test, "bonus": ba, "total": attack_total},
                        "damage": {"sides": dl, "results": dmg_rolls, "bonus": bd, "total": damage, "crit": crit}}}
    ok = publish_roll("attack", payload, who, notify=False)
    set_result(kind="attack", caption=f"{name} — {wname} ({modality})",
               groups=[{"label": "Teste", "sides": tl, "values": test}, {"label": "Dano", "sides": dl, "values": dmg_rolls}],
               totals=[{"label": "Teste", "value": attack_total},
                       {"label": "Dano" + (f" ×{critmult}" if crit else ""), "value": damage}],
               lines=details.split("\n"), published=ok, note="CRÍTICO!" if crit else None)


# ----------------------------------------------------------------- componentes visuais
def bar_html(label, current, maximum, color):
    pct = (current / maximum * 100) if maximum else 0
    return (f'<div class="res"><span class="rl">{label}</span>'
            f'<div class="rb"><i style="width:{pct:.1f}%;background:{color}"></i></div>'
            f'<span class="rv">{current}/{maximum}</span></div>')


def render_status(pid):
    """Cabeçalho do personagem, barras compactas e atributos (somente leitura)."""
    data = fresh(pid)
    if not data:
        st.warning("Essa ficha ainda não tem dados salvos. Abra o app da ficha e salve os dados.")
        return
    hp, hpmax, mana, manamax, stam, stmax = resources(data)
    img = data.get("imagem_url")
    img_html = f'<img src="{html.escape(str(img), quote=True)}" alt="">' if img else ""
    level = data.get("nivel")
    sub = f"Nível {html.escape(str(level))} · " if level not in (None, "") else ""
    attrs = "".join(
        f'<div class="attr"><div class="an">{ab}</div><div class="av">{attr_value(data, n)}</div>'
        f'<div class="am">{signed(attr_mod(attr_value(data, n)))}</div></div>' for n, ab in ATTR_ABBR)
    st.markdown(
        f'<div class="card"><div class="who">{img_html}<div><div class="nm">{html.escape(char_name(data, pid))}</div>'
        f'<div class="sub">{sub}RD total {rd_total(data)}</div></div></div>'
        f'{bar_html("HP", hp, hpmax, "#d83342")}{bar_html("Mana", mana, manamax, "#5488ff")}'
        f'{bar_html("Est.", stam, stmax, "#45bd83")}<div class="attrs">{attrs}</div></div>',
        unsafe_allow_html=True)


def render_party():
    rows = []
    for pid in PLAYER_IDS:
        d = fresh(pid)
        if not d:
            rows.append(f'<div class="mini"><span>{PLAYER_LABELS[pid]}</span><span class="muted">sem dados</span></div>')
            continue
        hp, hpmax, mana, manamax, stam, stmax = resources(d)

        def pc(a, b):
            return (a / b * 100) if b else 0

        rows.append(
            f'<div class="mini"><span><b>{html.escape(char_name(d, pid))}</b></span><div class="bars">'
            f'<div><i style="width:{pc(hp, hpmax):.0f}%;background:#d83342"></i></div>'
            f'<div><i style="width:{pc(mana, manamax):.0f}%;background:#5488ff"></i></div>'
            f'<div><i style="width:{pc(stam, stmax):.0f}%;background:#45bd83"></i></div></div></div>')
    st.markdown('<div class="card">' + "".join(rows) + "</div>", unsafe_allow_html=True)


_fragment = getattr(st, "fragment", None)


def _live(seconds):
    """Atualiza só o trecho a cada N segundos (sem rerun da página inteira)."""
    def deco(fn):
        if _fragment is None:
            return fn
        try:
            return _fragment(run_every=seconds)(fn)
        except TypeError:
            return fn
    return deco


@_live(6)
def live_character(pid):
    render_status(pid)



def format_time(created_at):
    try:
        dt = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        try:
            from zoneinfo import ZoneInfo
            dt = dt.astimezone(ZoneInfo(str(config_value("PANEL_TIMEZONE", "America/Sao_Paulo"))))
        except Exception:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime("%H:%M")
    except Exception:
        return ""


def message_html(msg):
    typ = msg.get("message_type", "text")
    data = msg.get("data") or {}
    who = html.escape(str(msg.get("author") or "Mesa"))
    when = format_time(msg.get("created_at"))
    if typ == "image":
        url = html.escape(str(data.get("url") or ""), quote=True)
        return f'<div class="chat-card"><div class="chat-head"><b>{who}</b><span>{when}</span></div><img src="{url}" style="max-width:100%;max-height:280px;object-fit:contain;border-radius:8px"></div>'
    if typ == "text":
        return (f'<div class="chat-card"><div class="chat-head"><b>{who}</b><span>{when}</span></div>'
                f'{fmt(data.get("text", ""))}</div>')
    if typ in ("dice", "attack", "defense"):
        title = html.escape(str(data.get("title", typ.title())))
        return (f'<div class="chat-card {typ}"><div class="chat-head"><b>{who}</b><span>{typ.upper()} · {when}</span></div>'
                f'<div class="chat-title">{title}</div>{fmt(data.get("details", ""))}</div>')
    return f'<div class="chat-card"><div class="chat-head"><b>{who}</b><span>{when}</span></div>{fmt(data)}</div>'


@_live(4)
def chat_history():
    messages = get_chat_messages(60)
    with st.container(height=440, border=True):
        if not messages:
            st.caption("As mensagens e rolagens compartilhadas aparecerão aqui.")
        else:
            st.markdown("".join(message_html(m) for m in reversed(messages)), unsafe_allow_html=True)


def render_result():
    res = ss.get("last_result")
    if res and res.get("groups"):
        spec = dice3d.build_spec(res["id"], res.get("caption", ""), res["groups"],
                                 totals=res.get("totals"), note=res.get("note"))
    elif res:
        spec = None
    else:
        spec = dice3d.idle_spec()
    if spec:
        show_html(dice3d.stage_html(spec, height=250), 252)
    if res:
        cls = "result-card warn" if res.get("warn") or res.get("published") is False else "result-card"
        body = "<br>".join(fmt(line) for line in res.get("lines", []))
        extra = ""
        if res.get("published") is False:
            extra = ('<br><span class="muted">⚠ O resultado foi calculado, mas não foi registrado '
                     'no chat compartilhado (verifique o Supabase).</span>')
        st.markdown(f'<div class="{cls}">{body}{extra}</div>', unsafe_allow_html=True)


def render_notice():
    n = ss.pop("notice", None)
    if n:
        getattr(st, n.get("level", "info"), st.info)(n["text"])


# ----------------------------------------------------------------- colunas
def left_column(pid, chars):
    data = chars.get(pid) or {}
    st.markdown("#### Personagem")
    if ss.get("_midnight_role") not in PLAYER_IDS:
        st.selectbox("Personagem", PLAYER_IDS, key="sel_player", label_visibility="collapsed",
                     format_func=lambda p: f"{PLAYER_LABELS[p]} — {char_name(chars.get(p), p)}")
    else:
        ss["sel_player"] = ss["_midnight_role"]
    render_notice()
    live_character(pid)
    if not data:
        return
    st.markdown("##### Recursos")
    cols = st.columns(3)
    for col, (field, label) in zip(cols, (("hp_atual", "HP"), ("mana_atual", "Mana"), ("estamina_atual", "Estamina"))):
        key = f"resource_{pid}_{field}"
        current = max(0, num(data.get(field), 0))
        if ss.get(f"resource_snapshot_{pid}_{field}") != current:
            ss[key] = current
            ss[f"resource_snapshot_{pid}_{field}"] = current
        col.number_input(label, min_value=0, step=1, key=key,
            on_change=cb_save_resources, args=(pid, field, key))
    if st.button("Resetar estamina", key=f"reset_st_{pid}"):
        cb_reset_stamina(pid)
        st.rerun()
    st.markdown("##### Ataques")
    weapons = [(i, str(data.get(f"arma_{i}_nome") or f"Arma {i+1}")) for i in range(NUM_WEAPONS)]
    for slot in range(5):
        c1, c2, c3 = st.columns([4, 3, 1], vertical_alignment="bottom")
        c1.selectbox("Arma", [i for i, _ in weapons],
                     key=f"atk_weapon_{pid}_{slot}", format_func=lambda i: dict(weapons)[i],
                     label_visibility="collapsed")
        c2.selectbox("Tipo", ["Normal", "Carregado", "Weapon Art"],
                     key=f"atk_mod_{pid}_{slot}", label_visibility="collapsed")
        c3.button("⬡", key=f"atk_run_{pid}_{slot}", type="primary",
                  help="Rolar ataque", on_click=cb_attack, args=(pid, slot), **STRETCH)


@_live(1)
def scene_panel():
    display = load_app_state("table_display", {}) or {}
    st.markdown("#### Cena")
    if ss.get("_midnight_role") not in PLAYER_IDS:
        from image_manager import render_image_editor
        image_url = render_image_editor(
            "scene", "table", display.get("scene_image_url", ""),
            key="panel_scene")
        if image_url and image_url != display.get("scene_image_url"):
            display["scene_image_url"] = image_url
            display["show_scene"] = True
            config = load_app_state("boss_config", {}) or {}
            boss_display = dict(config.get("display", {}) or {})
            boss_display["scene_image_url"] = image_url
            config["display"] = boss_display
            if save_app_state("table_display", display):
                save_app_state("boss_config", config)
                st.success("Cena publicada.")
    elif display.get("scene_image_url") and display.get("show_scene", True):
        st.image(display["scene_image_url"], use_container_width=True)
    else:
        st.markdown('<div class="boss-empty"></div>', unsafe_allow_html=True)


@_live(1)
def boss_panel():
    display = load_app_state("table_display", {}) or {}
    st.markdown("#### Chefe")
    if str(display.get("mode", "Chefe")).lower() in ("chefe", "boss") and display.get("boss_name"):
        if display.get("boss_image_url"):
            st.image(display["boss_image_url"], **STRETCH)
        name = html.escape(str(display["boss_name"]))
        st.markdown(f'<div class="boss-name">{name}</div>', unsafe_allow_html=True)
        hp, hpmax = max(0, num(display.get("boss_hp"))), max(1, num(display.get("boss_max_hp"), 1))
        st.markdown(f'<div class="boss-bar"><div style="width:{min(100, hp / hpmax * 100):.2f}%"></div></div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="boss-empty"></div>', unsafe_allow_html=True)


SKILL_ATTRIBUTES = {
    "Malandragem": ["Destreza", "Carisma"],
    "Herbalismo": ["Inteligência", "Sabedoria"],
    "Aura": ["Carisma"],
    "Mente": ["Sabedoria"],
    "Conhecimento": ["Inteligência", "Sabedoria"],
    "Instinto": ["Destreza"],
    "Fibra": ["Força", "Destreza"],
}


def cb_skill(pid, skill):
    data = fresh(pid)
    if not data or skill not in SKILL_ATTRIBUTES:
        return
    mod = max(attr_mod(attr_value(data, name)) for name in SKILL_ATTRIBUTES[skill])
    trained = bool(data.get(f"pericia_{skill}"))
    bonus = mod + (mod // 2) + 1 if trained else mod // 2
    value = roll_dice(1, 20)[0]
    total = value + bonus
    details = f"Perícia: {skill}\nTeste: 1d20 ({value}) {signed(bonus)} = **{total}**"
    ok = publish_roll("dice", {"title": f"{char_name(data,pid)} — {skill}",
                  "details": details, "dice": {"sides": 20, "results": [value], "total": total}},
                  effective_name(), notify=False)
    set_result(kind="dice", caption=skill,
               groups=[{"label": skill, "sides": 20, "values": [value]}],
               totals=[{"label": "Total", "value": total}], lines=[details], published=ok)


def render_defenses_and_skills(pid, data):
    dcol, scol = st.columns(2)
    with dcol:
        st.markdown("##### Defesas")
        for label, key in DEFENSES:
            st.button(label, key=f"def_{pid}_{key}", **STRETCH,
                      on_click=cb_defense, args=(pid, key, label))
    with scol:
        st.markdown("##### Perícias")
        for skill in SKILL_ATTRIBUTES:
            st.button(skill, key=f"skill_{pid}_{skill}", **STRETCH,
                      on_click=cb_skill, args=(pid, skill))



def render_grid():
    st.markdown("#### Mapa tático 20 × 20")
    zoom = st.slider("Zoom", min_value=14, max_value=40, value=23, key="grid_zoom")
    # Local browser interaction for positioning preconfigured tokens, with Ctrl+drag ruler.
    grid_html = tactical_grid_html(zoom=zoom)
    show_html(grid_html, 490)


def tactical_grid_html(zoom=23):
    """Shared 20x20 tactical map using the EXISTING app_state table.

    The legacy deployment already has public anon RLS. Only its public anon key
    is passed to the browser; never pass the service-role secret to JavaScript.
    Future protected deployments should use a server-authorized component.
    """
    import json
    from shared_backend import auth_configured
    api_url = str(config_value("SUPABASE_URL") or "").rstrip("/")
    anon_key = str(config_value("SUPABASE_ANON_KEY") or "")
    if auth_configured():
        anon_key = ""  # Never expose unrestricted public writes in password mode.
    markup = r"""<!doctype html><html lang="pt-BR"><head><meta charset="UTF-8"><style>
      html,body{margin:0;background:#11141c;color:#e9e9ed;font:12px system-ui}
      #toolbar{display:flex;gap:6px;align-items:center;padding:6px;flex-wrap:wrap}
      #status{font-size:11px;color:#9298ab;margin-left:auto}
      #board{height:430px;overflow:auto;background:#141827;border:1px solid #32394a;border-radius:8px}
      canvas{display:block;touch-action:none;cursor:crosshair}
      select,button{background:#292e3a;color:#fff;border:1px solid #525b70;padding:6px;border-radius:6px}
      #distance{padding:5px;color:#d8bc74}
      </style></head><body>
      <div id="toolbar"><select id="preset">
       <option value="Kuro|🗡️">Kuro</option>
       <option value="Andrias|🛡️">Andrias</option>
       <option value="Bondobo|🧙">Bondobo</option>
       <option value="Chefe|🐉">Chefe</option>
       <option value="Inimigo|👹">Inimigo</option>
       </select><button id="clear">Limpar mapa</button><span id="status">Conectando…</span></div>
      <div id="board"><canvas id="board_canvas"></canvas></div>
      <div id="distance">Clique para colocar · Arraste para mover · Ctrl+arraste para medir · Botão direito para excluir.</div>
      <script>
      const API=__API__, ANON=__ANON__, CELL=__CELL__, COUNT=20, WIDTH=CELL*COUNT;
      const canvas=document.querySelector('#board_canvas'),ctx=canvas.getContext('2d');
      canvas.width=WIDTH;canvas.height=WIDTH;
      const status=document.querySelector('#status'),distance=document.querySelector('#distance');
      const preset=document.querySelector('#preset'), remote=Boolean(API && ANON);
      const URL=API+'/rest/v1/app_state?on_conflict=key';
      const headers={'apikey':ANON,'Authorization':'Bearer '+ANON,'Content-Type':'application/json'};
      let tokens=[],interaction=null,lastWrite=0,loading=false;
      try{const initial=JSON.parse(localStorage.getItem('midnight_grid_20')||'[]');
          if(Array.isArray(initial))tokens=initial;}catch(e){}
      const point=e=>{const box=canvas.getBoundingClientRect();
        const x=(e.clientX-box.left)*canvas.width/box.width,y=(e.clientY-box.top)*canvas.height/box.height;
        return [Math.max(0,Math.min(19,Math.floor(x/CELL))),
                Math.max(0,Math.min(19,Math.floor(y/CELL)))];};
      const selected=(xy)=>tokens.find(t=>t.x===xy[0]&&t.y===xy[1]);
      const saveLocal=()=>localStorage.setItem('midnight_grid_20',JSON.stringify(tokens));
      function draw(){
        ctx.fillStyle='#171c2b';ctx.fillRect(0,0,WIDTH,WIDTH);
        ctx.strokeStyle='#354159';ctx.lineWidth=1;
        for(let i=0;i<=20;i++){ctx.beginPath();
          ctx.moveTo(i*CELL+.5,0);ctx.lineTo(i*CELL+.5,WIDTH);
          ctx.moveTo(0,i*CELL+.5);ctx.lineTo(WIDTH,i*CELL+.5);ctx.stroke();}
        ctx.font=Math.round(CELL*.70)+'px serif';ctx.textAlign='center';
        ctx.textBaseline='middle';
        for(const t of tokens){
          ctx.fillStyle='#272a36';ctx.beginPath();
          ctx.arc((t.x+.5)*CELL,(t.y+.5)*CELL,CELL*.44,0,Math.PI*2);ctx.fill();
          ctx.fillText(t.emoji,(t.x+.5)*CELL,(t.y+.52)*CELL);
        }
        if(interaction && interaction.mode==='measure'){
          const a=interaction.start,b=interaction.end||a;
          ctx.strokeStyle='#f2d077';ctx.lineWidth=3;ctx.beginPath();
          ctx.moveTo((a[0]+.5)*CELL,(a[1]+.5)*CELL);
          ctx.lineTo((b[0]+.5)*CELL,(b[1]+.5)*CELL);ctx.stroke();
          const dist=Math.hypot(b[0]-a[0],b[1]-a[1]);
          distance.textContent='Distância: '+dist.toFixed(2)+' quadrados';
        }
      }
      async function readRemote(){
        if(!remote || loading || interaction || Date.now()-lastWrite<1400)return;
        loading=true;
        try{
          const query=API+'/rest/v1/app_state?key=eq.battle_grid&select=data';
          const response=await fetch(query,{headers:{apikey:ANON,Authorization:'Bearer '+ANON}});
          if(!response.ok)throw Error('HTTP '+response.status);
          const rows=await response.json(),next=(rows[0]&&rows[0].data&&rows[0].data.tokens)||[];
          if(Array.isArray(next)){
            tokens=next.filter(t=>Number.isInteger(t.x)&&Number.isInteger(t.y)&&
                       t.x>=0&&t.x<20&&t.y>=0&&t.y<20).slice(0,100);
            saveLocal();draw();
          }
          status.textContent='● Mapa compartilhado';
        }catch(e){status.textContent='⚠ Sem sincronização';}
        finally{loading=false;}
      }
      async function persist(){
        saveLocal();draw();lastWrite=Date.now();
        if(!remote){status.textContent='Mapa local';return;}
        try{
          const response=await fetch(URL,{method:'POST',headers:{...headers,
              Prefer:'resolution=merge-duplicates'},body:JSON.stringify({
              key:'battle_grid',data:{tokens},updated_at:new Date().toISOString()})});
          if(!response.ok)throw Error('HTTP '+response.status);
          status.textContent='● Salvo para todos';
        }catch(e){status.textContent='⚠ Falha ao salvar mapa';}
      }
      canvas.addEventListener('pointerdown',e=>{
        const xy=point(e);
        if(e.ctrlKey){interaction={mode:'measure',start:xy,end:xy};}
        else{const target=selected(xy);
          if(target){interaction={mode:'move',id:target.id};}
          else{const [name,emoji]=preset.value.split('|');
             const id=(name==='Inimigo')?'enemy-'+Date.now()+'-'+Math.random():name;
             const old=tokens.find(t=>t.id===id);
             if(old){old.x=xy[0];old.y=xy[1];}
             else tokens.push({id,name,emoji,x:xy[0],y:xy[1]});
             interaction={mode:'place'};
          }
        }
        canvas.setPointerCapture(e.pointerId);draw();
      });
      canvas.addEventListener('pointermove',e=>{
        if(!interaction)return;const xy=point(e);
        if(interaction.mode==='measure')interaction.end=xy;
        if(interaction.mode==='move'){const t=tokens.find(t=>t.id===interaction.id);
             if(t){t.x=xy[0];t.y=xy[1];}}
        draw();
      });
      canvas.addEventListener('pointerup',async e=>{
        if(!interaction)return;
        const mode=interaction.mode;interaction=null;draw();
        if(mode!=='measure')await persist();
        else distance.textContent='Ctrl+arraste para medir outra distância.';
      });
      canvas.addEventListener('contextmenu',e=>{
        e.preventDefault();const xy=point(e);
        tokens=tokens.filter(t=>!(t.x===xy[0]&&t.y===xy[1]));persist();
      });
      document.querySelector('#clear').addEventListener('click',()=>{
        if(confirm('Remover todos os tokens do mapa?')){tokens=[];persist();}
      });
      draw();if(remote){readRemote();setInterval(readRemote,1100);}else status.textContent='Mapa local';
      </script></body></html>"""
    return (markup.replace("__API__", json.dumps(api_url))
                  .replace("__ANON__", json.dumps(anon_key))
                  .replace("__CELL__", str(max(14, min(40, int(zoom))))))


def right_column(pid, chars):
    st.markdown("#### Rolador de dados")
    st.text_input("Nome na mesa", key="display_name",
                  placeholder=char_name(chars.get(pid), pid))
    q, bonus = st.columns(2)
    q.number_input("Quantidade", min_value=1, max_value=MAX_QTY, key="dice_qty")
    bonus.number_input("Bônus", key="dice_bonus")
    dice_cols = st.columns(7)
    icons = {4: "▲", 6: "■", 8: "◆", 10: "⬟", 12: "⬢", 20: "⬡", 100: "◈"}
    for col, sides in zip(dice_cols, DICE_SIDES):
        col.button(f"{icons[sides]} d{sides}", key=f"dice_quick_{sides}",
                   on_click=cb_roll, args=(sides,), **STRETCH)
    with st.popover("??  Expressão personalizada", use_container_width=True):
        expression = st.text_input("Rolagem", key="custom_roll", placeholder="2d20+7")
        if st.button("Rolar expressão", key="run_custom", type="primary"):
            cb_roll(expression=expression)
    shared_animation()


def chat_composer():
    st.markdown("#### Enviar mensagem")
    try:
        sent = st.chat_input("Mensagem, imagem ou GIF (Enter para enviar)",
                             accept_file="multiple",
                             file_type=["png", "jpeg", "jpg", "webp", "gif"],
                             key="rich_chat_input")
    except TypeError:
        sent = st.chat_input("Digite mensagem e pressione Enter", key="rich_chat_fallback")
    if sent:
        body = sent if isinstance(sent, str) else sent.text
        files = [] if isinstance(sent, str) else list(sent.files or [])
        if body:
            send_chat_message(effective_name(), body)
        from chat_media import upload_chat_file
        for item in files:
            try:
                url = upload_chat_file(item)
                if url:
                    publish_roll("image", {"url": url, "name": item.name},
                                 effective_name(), notify=False)
                else:
                    st.error("Não foi possível enviar a imagem.")
            except ValueError as exc:
                st.error(str(exc))


@_live(1)
def shared_animation():
    """Every connected panel fetches recent rolls for a shared dice stage."""
    messages = get_chat_messages(20)
    rolls = [m for m in messages if m.get("message_type") in ("dice", "attack", "defense")]
    if rolls:
        latest = rolls[-1]
        data = latest.get("data") or {}
        die = data.get("dice", {})
        if "sides" in die and die.get("results"):
            spec = dice3d.build_spec(str(latest["id"]), str(data.get("title") or ""),
                [{"label": "", "sides": die["sides"], "values": die["results"]}],
                totals=[{"label": "Total", "value": die.get("total", 0)}])
            show_html(dice3d.stage_html(spec, height=240), 245)
            return
        if die.get("attack"):
            attack, damage = die["attack"], die.get("damage", {})
            groups = [{"label": "Ataque", "sides": attack["sides"], "values": attack.get("results", [])}]
            if damage.get("sides"):
                groups.append({"label": "Dano", "sides": damage["sides"],
                               "values": damage.get("results", [])})
            spec = dice3d.build_spec(str(latest["id"]), str(data.get("title") or ""),
                                     groups)
            show_html(dice3d.stage_html(spec, height=240), 245)
            return
    show_html(dice3d.stage_html(dice3d.idle_spec(), height=240), 245)


def main():
    if not shared_enabled():
        st.error("O painel precisa do Supabase configurado. Adicione SUPABASE_URL e SUPABASE_ANON_KEY em Secrets.")
        st.stop()
    ss.setdefault("dice_qty", 1)
    ss.setdefault("dice_sides", 20)
    ss.setdefault("dice_bonus", 0)
    ss.setdefault("display_name", "")
    ss.setdefault("chat_msg", "")
    ss.setdefault("sel_player", ss.get("_midnight_role") if ss.get("_midnight_role") in PLAYER_IDS else PLAYER_IDS[0])

    chars = {pid: fresh(pid) for pid in PLAYER_IDS}
    ss["_char_names"] = {pid: char_name(chars[pid], pid) for pid in PLAYER_IDS}
    pid = ss["sel_player"] if ss["sel_player"] in PLAYER_IDS else PLAYER_IDS[0]

    left, center, right = st.columns([1.55, 1.0, 1.45], gap="medium")
    with left:
        left_column(pid, chars)
    with center:
        render_defenses_and_skills(pid, chars.get(pid) or {})
    with right:
        right_column(pid, chars)

    chat_col, scene_col = st.columns([1.15, 1], gap="medium")
    with chat_col:
        st.markdown("#### Chat da mesa")
        chat_history()
        chat_composer()
        boss_panel()
    with scene_col:
        scene_panel()
        render_grid()


if __name__ == "__main__":
    main()
