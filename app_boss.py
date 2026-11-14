
        last_imported_name = imported[-1][0].name
        st.session_state.selected_boss = last_imported_name
        st.session_state.editor_target = last_imported_name
        st.session_state.editor_creating = False
        st.session_state.confirm_delete = False

        st.success(
            "Boss(es) importado(s): "
            + ", ".join(boss.name for boss, _ in imported)
        )
        st.rerun()


def render_editor_main(bosses: dict):

    if st.session_state.confirm_delete:
        render_delete_confirmation(bosses)
    else:
        render_json_import(bosses)
        render_boss_editor_form(bosses)


# ============================================================
# APP PRINCIPAL
#
#              app.py
#                │
#       carrega bosses.json
#                │
#        ┌───────┴───────┐
#        ↓               ↓
#  MODO COMBATE       EDITOR
#        │               │
#  usa dados do      altera dados
#     boss                │
#        │               ↓
#        └────────→ bosses.json
# ============================================================

def render_shared_display_controls(bosses: dict):
    """Configura o painel de cena/chefe consumido pelo painel geral."""
    if not shared_enabled():
        st.sidebar.warning("Configure SUPABASE_URL e SUPABASE_ANON_KEY para sincronizar com o painel geral.")
        return
    config = load_app_state("boss_config", {}) or {}
    display = config.get("display", {}) or {}
    st.sidebar.divider()
    st.sidebar.subheader("Cena compartilhada")
    mode = st.sidebar.radio("Modo exibido", ["Chefe", "Cena narrativa"], index=0 if display.get("mode", "Chefe") == "Chefe" else 1, key="shared_display_mode")
    scene_name = st.sidebar.text_input("Nome da cena", value=display.get("scene_name", "Cena atual"), key="shared_scene_name")
    show_scene = st.sidebar.checkbox("Exibir imagem da cena", value=display.get("show_scene", True), key="shared_show_scene")
    scene_file = st.sidebar.file_uploader("Imagem da cena (PNG/JPG)", type=["png", "jpg", "jpeg"], key="shared_scene_upload")
    if scene_file is not None and st.session_state.get("_scene_upload_name") != scene_file.name:
        mime = scene_file.type or "image/png"
        url = upload_asset(f"scenes/{scene_file.name.replace(' ', '_')}", scene_file.getvalue(), mime)
        if url:
            display["scene_image_url"] = url
            st.session_state["_scene_upload_name"] = scene_file.name
    selected_name = st.session_state.get("selected_boss", next(iter(bosses)))
    boss_file = st.sidebar.file_uploader(f"Imagem do chefe: {selected_name}", type=["png", "jpg", "jpeg"], key="shared_boss_upload")
    boss_images = display.get("boss_images", {}) or {}
    if boss_file is not None and st.session_state.get("_boss_upload_name") != boss_file.name:
        mime = boss_file.type or "image/png"
        url = upload_asset(f"bosses/{selected_name.replace(' ', '_')}_{boss_file.name.replace(' ', '_')}", boss_file.getvalue(), mime)
        if url:
            boss_images[selected_name] = url
            display["boss_images"] = boss_images
            st.session_state["_boss_upload_name"] = boss_file.name
    if st.sidebar.button("Publicar cena no painel", use_container_width=True):
        display.update({"mode": mode, "scene_name": scene_name, "show_scene": show_scene, "boss_images": boss_images})
        config["display"] = display
        save_app_state("boss_config", config)
        st.sidebar.success("Configuração da cena salva.")
    # Publica estado atual do chefe mesmo quando não há upload novo.
    display.update({"mode": mode, "scene_name": scene_name, "show_scene": show_scene, "boss_images": boss_images})
    config["display"] = display
    config["bosses"] = {name: boss_to_dict(boss) for name, boss in bosses.items()}
    save_app_state("boss_config", config)


def publish_current_boss(bosses: dict):
    if not shared_enabled() or not bosses:
        return
    name = st.session_state.get("selected_boss", next(iter(bosses)))
    boss = bosses.get(name)
    if not boss:
        return
    config = load_app_state("boss_config", {}) or {}
    display = config.get("display", {}) or {}
    hp = st.session_state.get("boss_hp", {}).get(name, boss.max_hp)
    save_app_state("table_display", {
        "mode": display.get("mode", "Chefe"),
        "scene_name": display.get("scene_name", "Cena atual"),
        "show_scene": display.get("show_scene", True),
        "scene_image_url": display.get("scene_image_url", ""),
        "boss_name": name,
        "boss_image_url": (display.get("boss_images", {}) or {}).get(name, ""),
        "boss_hp": max(0, min(int(hp), int(boss.max_hp))),
        "boss_max_hp": int(boss.max_hp),
        "updated_at": __import__("datetime").datetime.now().isoformat(),
    })


def main():

    bosses = load_bosses()
    init_session_state(bosses)

    render_shared_display_controls(bosses)
    if st.session_state.app_mode == "editor":
        render_editor_sidebar(bosses)
        render_editor_main(bosses)
    else:
        boss = bosses[st.session_state.selected_boss]
        render_combat_sidebar(bosses, boss)
        render_combat_main(boss)
    publish_current_boss(bosses)


if __name__ == "__main__":
    main()
