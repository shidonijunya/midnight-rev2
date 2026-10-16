import html
import random
import time
import streamlit as st
from shared_backend import (shared_enabled, load_character, save_character, load_app_state,
                            add_chat_message, get_chat_messages, clear_chat_messages)

st.set_page_config(page_title="Midnight Sun — Painel da Mesa", page_icon="🎲", layout="wide")
try:
    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=3500, key="panel_autorefresh")
except Exception:
    pass

st.markdown("""
<style>
.stApp {background:#101116;color:#ececf1}
.block-container {max-width:1800px;padding-top:.7rem;padding-left:1rem;padding-right:1rem}
.panel-card {background:#191b23;border:1px solid #30323d;border-radius:14px;padding:14px;margin:6px 0}
.chat-card {background:#1a1d27;border:1px solid #363948;border-left:4px solid #9c7bff;border-radius:10px;padding:12px;margin:8px 0}
.chat-name {font-size:.8rem;color:#aaa;margin-bottom:4px}
.chat-title {font-weight:800;font-size:1.05rem;margin-bottom:5px}
.die {display:inline-flex;align-items:center;justify-content:center;width:42px;height:42px;margin:4px;border-radius:10px;background:linear-gradient(145deg,#f8f8fb,#c7c9d6);color:#15151a;font-size:20px;font-weight:900;border:2px solid #fff;box-shadow:5px 6px 0 #5e6070, inset -4px -4px 8px #999;transform:perspective(150px) rotateX(-8deg) rotateY(10deg);animation:roll .55s ease-out}
@keyframes roll {0%{transform:perspective(150px) rotateX(120deg) rotateY(180deg) scale(.5);opacity:.2}100%{transform:perspective(150px) rotateX(-8deg) rotateY(10deg) scale(1);opacity:1}}
.bar-label {display:flex;justify-content:space-between;font-size:.76rem;margin:3px 0 2px}
.small-muted {font-size:.8rem;color:#a1a4b3}
</style>
""", unsafe_allow_html=True)

PLAYER_IDS = ["jogador_1", "jogador_2", "jogador_3"]
PLAYER_LABELS = {"jogador_1":"Jogador 1", "jogador_2":"Jogador 2", "jogador_3":"Jogador 3"}
DICE_SIDES = [4,6,8,10,12,20,100]
DEFENSES = [("Parry","parry"),("Rolagem","rolagem"),("Bloquear","bloquear"),("Pular","pular"),("Correr","correr")]


def attrs(data):
    def a(name): return int(data.get(f"attr_{name}", 10) or 10)
    return a("Força"), a("Destreza"), a("Constituição"), a("Inteligência"), a("Sabedoria"), a("Carisma"), a("Fortitude")

def maxima(data):
    f,d,c,i,s,cha,fort = attrs(data)
    hp = 50 + (c-10)*6 + (fort-10)*2
    mana = int(-(-((cha*1.7)+(s*1.7)+(i*2.3))//1))
    stamina = int(-(-((fort*4.6)+(f*1.2)+(d*1.2))//1))
    return max(0,hp), max(0,mana), max(0,stamina)

def rd_total(data):
    return sum(int(data.get(f"armor_{i}_rd",0) or 0) for i in range(4))

def signed(n): return f"+{n}" if n >= 0 else str(n)

def roll_dice(qty, sides):
    return [random.randint(1,sides) for _ in range(qty)]

def bar(label, current, maximum, color):
    maximum=max(0,int(maximum)); current=max(0,min(int(current or 0),maximum))
    pct=(current/maximum*100) if maximum else 0
    st.markdown(f"""<div class=\"bar-label\"><span>{label}</span><b>{current}/{maximum}</b></div>
    <div style=\"height:7px;background:#30323d;border-radius:8px;overflow:hidden;margin-bottom:7px\"><div style=\"width:{pct:.2f}%;height:100%;background:{color};border-radius:8px\"></div></div>""",unsafe_allow_html=True)

def save_resource(player_id, data):
    # O painel escreve no mesmo registro que a ficha individual lê.
    save_character(player_id, data)

def publish_roll(kind, payload, author):
    """Publica no chat o payload completo de uma rolagem/ação."""
    ok = add_chat_message(kind, payload, author=str(author or "Mesa").strip() or "Mesa")
    if not ok:
        st.error("Não foi possível publicar a ação no chat. Confira os logs do app e os Secrets do Supabase.")
    return ok

def dice_visual(values):
    shown=values[:10]
    st.markdown("".join(f'<span class="die">{v}</span>' for v in shown), unsafe_allow_html=True)
    if len(values)>10:
        st.caption(f"Animação limitada aos 10 primeiros dados; todos os {len(values)} foram calculados.")

def render_chat():
    st.subheader("Chat da mesa")
    with st.form("chat_form", clear_on_submit=True):
        author=st.text_input("Nome no chat", value="Jogador", key="chat_author")
        message=st.text_input("Mensagem", placeholder="Escreva para a mesa...")
        send=st.form_submit_button("Enviar mensagem", use_container_width=True)
    if send and message.strip():
        st.session_state["chat_author"] = author.strip() or "Jogador"
        publish_roll("text", {"text":message.strip()}, st.session_state["chat_author"])
    messages=get_chat_messages(100)
    if not messages:
        st.caption("As mensagens e rolagens compartilhadas aparecerão aqui.")
    for msg in reversed(messages[-50:]):
        typ=msg.get("message_type","text"); data=msg.get("data") or {}; who=html.escape(str(msg.get("author") or "Mesa"))
        if typ=="text":
            st.markdown(f'<div class="chat-card"><div class="chat-name">{who}</div>{html.escape(str(data.get("text","")))}</div>',unsafe_allow_html=True)
        elif typ in ("attack","defense","dice"):
            title=html.escape(str(data.get("title",typ.title())))
            details=html.escape(str(data.get("details",""))).replace("\n","<br>")
            st.markdown(f'<div class="chat-card"><div class="chat-name">{who} · {typ.upper()}</div><div class="chat-title">{title}</div>{details}</div>',unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-card"><div class="chat-name">{who}</div>{html.escape(str(data))}</div>',unsafe_allow_html=True)


def main():
    st.title("Midnight Sun — Painel da Mesa")
    if not shared_enabled():
        st.error("O painel precisa do Supabase configurado. Adicione SUPABASE_URL e SUPABASE_ANON_KEY em Secrets nos cinco apps.")
        st.stop()

    display=load_app_state("table_display",{}) or {}
    cfg=load_app_state("boss_config",{}) or {}
    # Cena grande no topo; a barra de chefe não revela o número atual de HP.
    if display.get("show_scene",True):
        scene_col, info_col=st.columns([2.3,1])
        with scene_col:
            if display.get("scene_image_url"):
                st.image(display["scene_image_url"], use_container_width=True)
            else:
                st.markdown('<div class="panel-card" style="min-height:220px;display:flex;align-items:center;justify-content:center;font-size:1.5rem">Cena sem imagem configurada</div>',unsafe_allow_html=True)
        with info_col:
            st.markdown(f'<div class="panel-card"><div class="chat-title">{html.escape(str(display.get("scene_name") or "Cena atual"))}</div>',unsafe_allow_html=True)
            if str(display.get("mode","Chefe")).lower() in ("chefe","boss") and display.get("boss_name"):
                if display.get("boss_image_url"): st.image(display["boss_image_url"],use_container_width=True)
                st.markdown(f'**{html.escape(str(display["boss_name"]))}**',unsafe_allow_html=True)
                hp=max(0,int(display.get("boss_hp",0))); hpmax=max(1,int(display.get("boss_max_hp",1))); pct=min(100,hp/hpmax*100)
                st.markdown(f'<div style="height:18px;background:#30323d;border-radius:10px;overflow:hidden;margin-top:8px"><div style="height:100%;width:{pct:.2f}%;background:#d83342"></div></div>',unsafe_allow_html=True)
                st.caption("Vida do chefe (valor numérico oculto)")
            st.markdown('</div>',unsafe_allow_html=True)

    st.subheader("Personagens")
    chars={pid:load_character(pid) or {} for pid in PLAYER_IDS}
    cols=st.columns(3)
    for col,pid in zip(cols,PLAYER_IDS):
        data=chars[pid]
        with col:
            st.markdown('<div class="panel-card">',unsafe_allow_html=True)
            if data.get("imagem_url"): st.image(data["imagem_url"],width=100)
            name=data.get("nome_personagem") or PLAYER_LABELS[pid]
            hpmax,manamax,stmax=maxima(data)
            st.markdown(f"**{html.escape(str(name))}**")
            bar("HP",data.get("hp_atual",hpmax),hpmax,"#d83342")
            bar("Mana",data.get("mana_atual",manamax),manamax,"#5488ff")
            bar("Estamina",data.get("estamina_atual",stmax),stmax,"#45bd83")
            st.caption(f"RD total: {rd_total(data)}")
            if st.button("Resetar estamina",key=f"reset_{pid}",use_container_width=True):
                data["estamina_atual"]=stmax; save_resource(pid,data)
                add_chat_message("text",{"text":f"{name} recuperou toda a estamina."},author="Sistema")
                st.rerun()
            st.markdown('</div>',unsafe_allow_html=True)

    st.divider()
    selected=st.selectbox("Personagem para ações e ficha detalhada",PLAYER_IDS,format_func=lambda p: f'{PLAYER_LABELS[p]} — {chars[p].get("nome_personagem") or "sem nome"}',key="selected_player")
    data=load_character(selected) or chars[selected]
    if not data:
        st.warning("Essa ficha ainda não tem dados salvos. Abra o app da ficha, configure SUPABASE_URL e SUPABASE_ANON_KEY e salve os dados.")
        st.stop()
    hpmax,manamax,stmax=maxima(data)
    with st.expander("Ficha detalhada, defesas e ataques",expanded=False):
        st.markdown(f"### {data.get('nome_personagem') or PLAYER_LABELS[selected]}")
        st.write(f"**RD total:** {rd_total(data)}")
        bar("HP",data.get("hp_atual",hpmax),hpmax,"#d83342")
        bar("Mana",data.get("mana_atual",manamax),manamax,"#5488ff")
        bar("Estamina",data.get("estamina_atual",stmax),stmax,"#45bd83")
        st.markdown("**Recursos manuais**")
        with st.form("resource_form"):
            hp_new=st.number_input("HP atual",min_value=0,max_value=max(hpmax,0),value=max(0,min(int(data.get("hp_atual",hpmax) or 0),hpmax)),step=1,key=f"hp_edit_{selected}")
            mana_new=st.number_input("Mana atual",min_value=0,max_value=max(manamax,0),value=max(0,min(int(data.get("mana_atual",manamax) or 0),manamax)),step=1,key=f"mana_edit_{selected}")
            stam_new=st.number_input("Estamina atual",min_value=0,max_value=max(stmax,0),value=max(0,min(int(data.get("estamina_atual",stmax) or 0),stmax)),step=1,key=f"stam_edit_{selected}")
            save_resources=st.form_submit_button("Salvar recursos",use_container_width=True)
        if save_resources:
            data.update({"hp_atual":hp_new,"mana_atual":mana_new,"estamina_atual":stam_new}); save_resource(selected,data)
            add_chat_message("text",{"text":f"Recursos de {data.get('nome_personagem') or PLAYER_LABELS[selected]} atualizados."},author="Sistema")
            st.rerun()
        st.markdown("**Defesas**")
        dcols=st.columns(5)
        for col,(label,key) in zip(dcols,DEFENSES):
            with col:
                bonus=int(data.get(f"defesa_{key}_bonus",0) or 0); cost=int(data.get(f"defesa_{key}_custo",0) or 0)
                if st.button(label,key=f"def_{selected}_{key}",use_container_width=True):
                    current=int(data.get("estamina_atual",stmax) or 0)
                    if current<cost:
                        st.warning(f"Estamina insuficiente para {label}: custo {cost}, disponível {current}.")
                    else:
                        roll=random.randint(1,20); total=roll+bonus; data["estamina_atual"]=current-cost; save_resource(selected,data)
                        details=f"{label}: 1d20 ({roll}) {signed(bonus)} = **{total}**\nEstamina: -{cost} · restante {data['estamina_atual']}/{stmax}"
                        publish_roll("defense",{"title":f"{data.get('nome_personagem') or PLAYER_LABELS[selected]} — {label}","details":details},data.get("nome_personagem") or PLAYER_LABELS[selected])
                        st.rerun()
        st.markdown("**Armas e ataques**")
        weapons=[]
        for i in range(5):
            k=f"arma_{i}_"; wname=data.get(k+"nome") or f"Arma {i+1}"
            if wname.strip() and wname not in ("Nenhuma",): weapons.append((i,wname))
        if not weapons: st.caption("Nenhuma arma configurada.")
        else:
            widx=st.selectbox("Arma",[i for i,_ in weapons],format_func=lambda i:dict(weapons)[i],key="attack_weapon")
            modality=st.selectbox("Modalidade",["Normal","Carregado","Weapon Art"],key="attack_modality")
            wk=f"arma_{widx}_"; name=data.get(wk+"nome") or f"Arma {widx+1}"
            if modality=="Weapon Art":
                st.write(data.get(wk+"wa_texto") or "Sem descrição cadastrada.")
                st.caption(f"Custo: {data.get(wk+'wa_estamina',0)} estamina e {data.get(wk+'wa_mana',0)} mana. Rolagens e efeitos são manuais.")
            else:
                td=int(data.get(wk+"test_dados",1) or 1); tl=int(data.get(wk+"test_lados",20) or 20); ba=int(data.get(wk+"bonus_ataque",0) or 0)
                dd=int(data.get(wk+"dano_dados",1) or 1); dl=int(data.get(wk+"dano_lados",6) or 6); bd=int(data.get(wk+"bonus_dano",0) or 0)
                critmin=int(data.get(wk+"crit_min",20) or 20); critmult=int(data.get(wk+"crit_mult",2) or 2)
                estcost=int(data.get(wk+"custo_estamina",0) or 0)*(2 if modality=="Carregado" else 1)
                if modality=="Carregado": dd*=3
                st.caption(f"Ataque: {td}d{tl}{signed(ba)} · Dano: {dd}d{dl}{signed(bd)} · Estamina: {estcost}")
            if st.button("Executar ação",type="primary",use_container_width=True):
                curst=int(data.get("estamina_atual",stmax) or 0); curmana=int(data.get("mana_atual",manamax) or 0)
                if modality=="Weapon Art":
                    estcost=int(data.get(wk+"wa_estamina",0) or 0); manacost=int(data.get(wk+"wa_mana",0) or 0)
                    if curst<estcost or curmana<manacost:
                        st.error(f"Recursos insuficientes. Estamina: {curst}/{estcost}; mana: {curmana}/{manacost}.")
                    else:
                        data["estamina_atual"]=curst-estcost; data["mana_atual"]=curmana-manacost; save_resource(selected,data)
                        details=f"Weapon Art selecionada.\nDescrição: {data.get(wk+'wa_texto') or 'Sem descrição'}\nCusto: -{estcost} estamina e -{manacost} mana.\nRolagem/dano: manual."
                        publish_roll("attack",{"title":f"{data.get('nome_personagem') or PLAYER_LABELS[selected]} — {name} / Weapon Art","details":details},data.get("nome_personagem") or PLAYER_LABELS[selected]); st.rerun()
                else:
                    if curst<estcost:
                        st.error(f"Estamina insuficiente: custo {estcost}, disponível {curst}.")
                    else:
                        test=roll_dice(td,tl); attack_total=sum(test)+ba
                        damage_rolls=roll_dice(dd,dl); damage=sum(damage_rolls)+bd
                        crit=any(v>=critmin for v in test)
                        if crit: damage*=critmult
                        data["estamina_atual"]=curst-estcost; save_resource(selected,data)
                        details=f"Modalidade: {modality}\nTeste: {test} {signed(ba)} = **{attack_total}**\nDano: {damage_rolls} {signed(bd)} = **{sum(damage_rolls)+bd}**"+(f" × {critmult} = **{damage}** (CRÍTICO)" if crit else f" = **{damage}**")+f"\nEstamina: -{estcost} · restante {data['estamina_atual']}/{stmax}\nDano não aplicado automaticamente ao alvo."
                        publish_roll("attack",{"title":f"{data.get('nome_personagem') or PLAYER_LABELS[selected]} — {name}","details":details},data.get("nome_personagem") or PLAYER_LABELS[selected]); st.rerun()

    st.divider()
    left,right=st.columns([1,1.5])
    with left:
        st.subheader("Rolador de dados")
        with st.form("dice_form"):
            qty=st.number_input("Quantidade",min_value=1,max_value=1000,value=1,step=1)
            sides=st.selectbox("Tipo de dado",DICE_SIDES,index=5,format_func=lambda x:f"d{x}")
            bonus=st.number_input("Bônus",value=0,step=1)
            roller_author=st.text_input("Quem está rolando",value=data.get("nome_personagem") or PLAYER_LABELS[selected])
            do_roll=st.form_submit_button("Rolar",use_container_width=True)
        if do_roll:
            results=roll_dice(int(qty),int(sides)); total=sum(results)+int(bonus)
            st.session_state["dice_session_history"] = st.session_state.get("dice_session_history",[])+[{"dice":f"{qty}d{sides}{signed(int(bonus))}","total":total,"time":time.strftime("%H:%M:%S") }]
            st.markdown(f"**Resultado total: {total}**")
            dice_visual(results)
            details=f"Rolagem: {qty}d{sides}{signed(int(bonus))}\nTotal: **{total}**\nDados exibidos: {results[:10]}"+(f"\nDados calculados: {qty}; visualização limitada a 10." if qty>10 else f"\nDados: {results}")
            publish_roll("dice",{"title":f"{roller_author or 'Jogador'} — {qty}d{sides}","details":details},roller_author or "Jogador")
        with st.expander("Histórico desta sessão",expanded=False):
            for item in reversed(st.session_state.get("dice_session_history",[]) [-20:]): st.write(f"{item['time']} · {item['dice']} = **{item['total']}**")
    with right:
        render_chat()

if __name__ == "__main__":
    main()
