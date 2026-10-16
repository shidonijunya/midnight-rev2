"""Painel da mesa: ficha à esquerda; rolador 3D e chat à direita."""
import html
import inspect
import math
import re
import secrets
import uuid
from datetime import datetime, timezone

import streamlit as st

from shared_backend import (shared_enabled, load_character, save_character, load_app_state,
                            publish_roll, send_chat_message, get_chat_messages, clean_author,
                            config_value)
import dice3d

st.set_page_config(page_title="Painel da Mesa", page_icon="🎲", layout="wide")

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
.chat-card.dice {border-left-color:#5488ff}.chat-card.attack {border-left-color:#d83342}.chat-card.defense {border-left-color:#45bd83}
.chat-head {display:flex;justify-content:space-between;font-size:.72rem;color:#9a9db0;margin-bottom:2px}
.chat-head b {color:#d7d9e6}
.chat-title {font-weight:800;font-size:.9rem;margin-bottom:2px}
.result-card {background:#191b23;border:1px solid #30323d;border-radius:10px;padding:8px 12px;font-size:.88rem;line-height:1.45}
.result-card.warn {border-color:#e0a02f}
.muted {font-size:.78rem;color:#a1a4b3}
</style>
""", unsafe_allow_html=True)

PLAYER_IDS = ["jogador_1", "jogador_2", "jogador_3"]
PLAYER_LABELS = {"jogador_1": "Jogador 1", "jogador_2": "Jogador 2", "jogador_3": "Jogador 3"}
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
    return (value - 1) // 2 - 5


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
        return max(0, min(num(v, mx) if v is not None else mx, mx))

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
    """Incorpora HTML/JS: st.iframe nas versões novas, components.html nas antigas."""
    if hasattr(st, "iframe"):
        try:
            st.iframe(html_str, height=height)
            return
        except Exception:
            pass
    import streamlit.components.v1 as components
    components.html(html_str, height=height)


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
def cb_roll():
    qty = max(1, min(MAX_QTY, num(ss.get("dice_qty"), 1)))
    sides = num(ss.get("dice_sides"), 20)
    if sides not in DICE_SIDES:
        sides = 20
    bonus = num(ss.get("dice_bonus"), 0)
    who = effective_name()
    results = roll_dice(qty, sides)
    total = sum(results) + bonus
    label = f"{qty}d{sides}{signed(bonus) if bonus else ''}"
    shown = results if len(results) <= 20 else results[:20]
    more = " …" if len(results) > 20 else ""
    details = f"Rolagem: {label}\nDados: {shown}{more}\nTotal: **{total}**"
    payload = {"title": f"{who} — {label}", "details": details,
               "dice": {"sides": sides, "qty": qty, "bonus": bonus, "total": total, "results": shown}}
    ok = publish_roll("dice", payload, who, notify=False)
    set_result(kind="dice", caption=f"{who} — {label}",
               groups=[{"label": "", "sides": sides, "values": results}],
               totals=[{"label": "Total", "value": total}],
               lines=[f"**{who}** rolou **{label}**: {shown}{more}"
                      f"{(' ' + signed(bonus)) if bonus else ''} = **{total}**"],
               published=ok)


def cb_send_chat():
    ok, err = send_chat_message(effective_name(), ss.get("chat_msg", ""))
    if ok:
        ss["chat_msg"] = ""           # só limpa depois do sucesso confirmado
        ss["chat_feedback"] = None
    else:
        ss["chat_feedback"] = {"level": "warning" if "Escreva" in (err or "") else "error", "text": err}


def cb_save_resources(pid, k_hp, k_mana, k_st):
    data = fresh(pid)                  # relê antes de gravar: não sobrescreve edições feitas na ficha
    if not data:
        ss["notice"] = {"level": "error", "text": "Essa ficha ainda não tem dados salvos."}
        return
    hpmax, manamax, stmax = maxima(data)
    data["hp_atual"] = max(0, min(num(ss.get(k_hp)), hpmax))
    data["mana_atual"] = max(0, min(num(ss.get(k_mana)), manamax))
    data["estamina_atual"] = max(0, min(num(ss.get(k_st)), stmax))
    if save_character(pid, data):
        publish_roll("text", {"text": f"Recursos de {char_name(data, pid)} atualizados."}, "Sistema", notify=False)
        ss["notice"] = {"level": "success", "text": "Recursos salvos."}
    else:
        ss["notice"] = {"level": "error", "text": "Não foi possível salvar os recursos no Supabase."}


def cb_reset_stamina(pid):
    data = fresh(pid)
    if not data:
        ss["notice"] = {"level": "error", "text": "Essa ficha ainda não tem dados salvos."}
        return
    data["estamina_atual"] = maxima(data)[2]
    if save_character(pid, data):
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
    if not save_character(pid, data):
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


def cb_attack(pid):
    data = fresh(pid)
    if not data:
        set_error("Essa ficha ainda não tem dados salvos. Salve a ficha no app do jogador primeiro.")
        return
    widx = ss.get(f"atk_weapon_{pid}")
    modality = ss.get(f"atk_mod_{pid}", "Normal")
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
        if not save_character(pid, data):
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
    if not save_character(pid, data):
        set_error("Não foi possível salvar a estamina; o ataque não foi registrado.")
        return
    dmg_line = f"Dano: {dmg_rolls} {signed(bd)} = **{base_damage}**"
    if crit:
        dmg_line += f" × {critmult} = **{damage}** (CRÍTICO)"
    details = (f"Modalidade: {modality}\nTeste: {test} {signed(ba)} = **{attack_total}**\n{dmg_line}\n"
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
    with st.expander("Grupo", expanded=False):
        render_party()


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
    with st.container(height=360, border=True):
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
    st.selectbox("Personagem", PLAYER_IDS, key="sel_player", label_visibility="collapsed",
                 format_func=lambda p: f"{PLAYER_LABELS[p]} — {char_name(chars.get(p), p)}")
    render_notice()
    live_character(pid)
    if not data:
        return
    hp, hpmax, mana, manamax, stam, stmax = resources(data)

    with st.expander("Ajustar recursos", expanded=False):
        k_hp = f"res_hp_{pid}_{hp}_{hpmax}"
        k_mana = f"res_mana_{pid}_{mana}_{manamax}"
        k_st = f"res_st_{pid}_{stam}_{stmax}"
        c1, c2, c3 = st.columns(3)
        c1.number_input("HP", min_value=0, max_value=hpmax, value=hp, step=1, key=k_hp)
        c2.number_input("Mana", min_value=0, max_value=manamax, value=mana, step=1, key=k_mana)
        c3.number_input("Est.", min_value=0, max_value=stmax, value=stam, step=1, key=k_st)
        b1, b2 = st.columns(2)
        b1.button("Salvar", key=f"save_res_{pid}", **STRETCH,
                  on_click=cb_save_resources, args=(pid, k_hp, k_mana, k_st))
        b2.button("Resetar estamina", key=f"reset_st_{pid}", **STRETCH,
                  on_click=cb_reset_stamina, args=(pid,))

    st.markdown("##### Defesas")
    for row in (DEFENSES[:3], DEFENSES[3:]):
        cols = st.columns(3)
        for col, (label, key) in zip(cols, row):
            bonus, cost = num(data.get(f"defesa_{key}_bonus")), num(data.get(f"defesa_{key}_custo"))
            col.button(f"{label} {signed(bonus)}", key=f"def_{pid}_{key}", **STRETCH,
                       help=f"1d20 {signed(bonus)} · custo {cost} de estamina",
                       on_click=cb_defense, args=(pid, key, label))

    st.markdown("##### Ataques")
    weapons = []
    for i in range(NUM_WEAPONS):
        wname = str(data.get(f"arma_{i}_nome") or "").strip()
        if wname and wname.lower() != "nenhuma":
            weapons.append((i, wname))
    if not weapons:
        st.caption("Nenhuma arma configurada. Preencha o nome e os dados da arma na ficha do jogador.")
        return
    wkey = f"atk_weapon_{pid}"
    if ss.get(wkey) not in [i for i, _ in weapons]:
        ss.pop(wkey, None)
    c1, c2 = st.columns([3, 2])
    widx = c1.selectbox("Arma", [i for i, _ in weapons], key=wkey, format_func=lambda i: dict(weapons)[i])
    modality = c2.selectbox("Modalidade", ["Normal", "Carregado", "Weapon Art"], key=f"atk_mod_{pid}")
    wk = f"arma_{widx}_"
    if modality == "Weapon Art":
        st.caption(f"Custo: {num(data.get(wk + 'wa_estamina'))} estamina e {num(data.get(wk + 'wa_mana'))} mana · "
                   "rolagens e efeito manuais.")
    else:
        missing = missing_weapon_fields(data, wk)
        if missing:
            st.warning(f"Arma sem configuração ({', '.join(missing)}). Complete na ficha do jogador.")
        else:
            td, tl = max(1, num(data.get(wk + "test_dados"), 1)), num(data.get(wk + "test_lados"), 20)
            dd, dl = max(1, num(data.get(wk + "dano_dados"), 1)), num(data.get(wk + "dano_lados"), 6)
            cost = num(data.get(wk + "custo_estamina")) * (2 if modality == "Carregado" else 1)
            if modality == "Carregado":
                dd *= 3
            st.caption(f"Teste {td}d{tl}{signed(num(data.get(wk + 'bonus_ataque')))} · "
                       f"Dano {dd}d{dl}{signed(num(data.get(wk + 'bonus_dano')))} · Estamina {cost}")
    st.button("Executar ação", key=f"atk_run_{pid}", type="primary", **STRETCH,
              on_click=cb_attack, args=(pid,))


def scene_panel():
    display = load_app_state("table_display", {}) or {}
    if not display.get("show_scene", True):
        return
    has_content = bool(display.get("scene_image_url") or display.get("boss_name"))
    with st.expander("Cena e chefe", expanded=has_content):
        c1, c2 = st.columns([2, 1])
        with c1:
            if display.get("scene_image_url"):
                st.image(display["scene_image_url"], **STRETCH)
            else:
                st.caption("Cena sem imagem configurada.")
        with c2:
            st.markdown(f"**{html.escape(str(display.get('scene_name') or 'Cena atual'))}**", unsafe_allow_html=True)
            if str(display.get("mode", "Chefe")).lower() in ("chefe", "boss") and display.get("boss_name"):
                if display.get("boss_image_url"):
                    st.image(display["boss_image_url"], **STRETCH)
                st.markdown(f"**{html.escape(str(display['boss_name']))}**", unsafe_allow_html=True)
                hp, hpmax = max(0, num(display.get("boss_hp"))), max(1, num(display.get("boss_max_hp"), 1))
                st.markdown(f'<div class="res" style="grid-template-columns:1fr"><div class="rb">'
                            f'<i style="width:{min(100, hp / hpmax * 100):.1f}%;background:#d83342"></i></div></div>',
                            unsafe_allow_html=True)
                st.caption("Vida do chefe (valor numérico oculto)")


def right_column(pid, chars):
    st.markdown("#### Rolador de dados")
    ctrl, stage = st.columns([1, 2.1])
    with ctrl:
        st.text_input("Seu nome na mesa", key="display_name", placeholder=char_name(chars.get(pid), pid),
                      help="Aparece nas rolagens e no chat. Se ficar vazio, usa o nome do personagem selecionado.")
        q1, q2 = st.columns(2)
        q1.number_input("Qtd.", min_value=1, max_value=MAX_QTY, step=1, key="dice_qty")
        q2.selectbox("Dado", DICE_SIDES, key="dice_sides", format_func=lambda x: f"d{x}")
        st.number_input("Bônus", step=1, key="dice_bonus")
        st.button("🎲 Rolar", type="primary", **STRETCH, key="dice_roll", on_click=cb_roll)
    with stage:
        render_result()

    st.markdown("#### Chat da mesa")
    with st.form("chat_form", clear_on_submit=False):
        c1, c2 = st.columns([5, 1])
        c1.text_input("Mensagem", key="chat_msg", placeholder="Escreva para a mesa e tecle Enter…",
                      label_visibility="collapsed")
        c2.form_submit_button("Enviar", **STRETCH, on_click=cb_send_chat)
    fb = ss.get("chat_feedback")
    if fb:
        getattr(st, fb["level"], st.error)(fb["text"])
    chat_history()
    scene_panel()


def main():
    if not shared_enabled():
        st.error("O painel precisa do Supabase configurado. Adicione SUPABASE_URL e SUPABASE_ANON_KEY em Secrets.")
        st.stop()
    ss.setdefault("dice_qty", 1)
    ss.setdefault("dice_sides", 20)
    ss.setdefault("dice_bonus", 0)
    ss.setdefault("display_name", "")
    ss.setdefault("chat_msg", "")
    ss.setdefault("sel_player", PLAYER_IDS[0])

    chars = {pid: fresh(pid) for pid in PLAYER_IDS}
    ss["_char_names"] = {pid: char_name(chars[pid], pid) for pid in PLAYER_IDS}
    pid = ss["sel_player"] if ss["sel_player"] in PLAYER_IDS else PLAYER_IDS[0]

    left, right = st.columns([1, 2.05], gap="medium")
    with left:
        left_column(pid, chars)
    with right:
        right_column(pid, chars)


if __name__ == "__main__":
    main()
