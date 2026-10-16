"""Camada compartilhada dos cinco apps Midnight Sun (Supabase)."""
import os
from datetime import datetime, timezone
import streamlit as st


def config_value(key, default=None):
    try:
        value = st.secrets.get(key, default)
    except Exception:
        value = default
    if value in (None, ""):
        value = os.getenv(key, default)
    return value


def get_client():
    url = config_value("SUPABASE_URL")
    key = config_value("SUPABASE_ANON_KEY")
    if not url or not key:
        return None
    try:
        from supabase import create_client
        return create_client(str(url), str(key))
    except Exception as exc:
        st.error(f"Não foi possível conectar ao Supabase: {exc}")
        return None


def shared_enabled():
    return bool(config_value("SUPABASE_URL") and config_value("SUPABASE_ANON_KEY"))


def get_player_id(default="jogador_1"):
    return str(config_value("PLAYER_ID", default))


def load_character(player_id):
    client = get_client()
    if client is None:
        return None
    try:
        response = client.table("characters").select("data").eq("player_id", player_id).limit(1).execute()
        if response.data:
            return response.data[0].get("data") or {}
    except Exception as exc:
        st.error(f"Falha ao carregar a ficha compartilhada ({player_id}): {exc}")
    return None


def save_character(player_id, data):
    client = get_client()
    if client is None:
        return False
    try:
        client.table("characters").upsert({
            "player_id": player_id,
            "data": data,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }, on_conflict="player_id").execute()
        return True
    except Exception as exc:
        st.error(f"Falha ao salvar a ficha compartilhada ({player_id}): {exc}")
        return False


def load_app_state(key, default=None):
    client = get_client()
    if client is None:
        return default
    try:
        response = client.table("app_state").select("data").eq("key", key).limit(1).execute()
        if response.data:
            return response.data[0].get("data", default)
    except Exception as exc:
        st.error(f"Falha ao carregar estado compartilhado '{key}': {exc}")
    return default


def save_app_state(key, data):
    client = get_client()
    if client is None:
        return False
    try:
        client.table("app_state").upsert({
            "key": key,
            "data": data,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }, on_conflict="key").execute()
        return True
    except Exception as exc:
        st.error(f"Falha ao salvar estado compartilhado '{key}': {exc}")
        return False


def upload_asset(path, file_bytes, content_type="image/png"):
    """Envia arquivo ao bucket público rpg-assets e retorna a URL pública."""
    client = get_client()
    if client is None:
        return None
    try:
        client.storage.from_("rpg-assets").upload(
            path, file_bytes,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        return client.storage.from_("rpg-assets").get_public_url(path)
    except Exception as exc:
        st.error(f"Falha ao enviar imagem para o armazenamento compartilhado: {exc}")
        return None


def add_chat_message(message_type, data, author="Mesa"):
    client = get_client()
    if client is None:
        return False
    try:
        client.table("chat_messages").insert({
            "message_type": message_type,
            "author": author,
            "data": data,
        }).execute()
        return True
    except Exception as exc:
        st.error(f"Falha ao publicar no chat: {exc}")
        return False


def get_chat_messages(limit=100):
    client = get_client()
    if client is None:
        return []
    try:
        response = client.table("chat_messages").select("id,created_at,message_type,author,data").order("id", desc=True).limit(limit).execute()
        return list(reversed(response.data or []))
    except Exception as exc:
        st.error(f"Falha ao carregar o chat: {exc}")
        return []


def clear_chat_messages():
    client = get_client()
    if client is None:
        return False
    try:
        client.table("chat_messages").delete().neq("id", -1).execute()
        return True
    except Exception as exc:
        st.error(f"Falha ao limpar o chat: {exc}")
        return False
