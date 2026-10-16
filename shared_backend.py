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


def _safe_error(exc):
    """Texto de erro sem vazar URL/chave configuradas."""
    text = str(exc)
    for secret in (config_value("SUPABASE_ANON_KEY"), config_value("SUPABASE_URL")):
        if secret:
            text = text.replace(str(secret), "***")
    return text[:300]


@st.cache_resource(show_spinner=False)
def _cached_client(url, key):
    from supabase import create_client
    return create_client(str(url), str(key))


def get_client():
    url = config_value("SUPABASE_URL")
    key = config_value("SUPABASE_ANON_KEY")
    if not url or not key:
        return None
    try:
        return _cached_client(str(url), str(key))
    except Exception as exc:
        st.error(f"Não foi possível conectar ao Supabase: {_safe_error(exc)}")
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
        st.error(f"Falha ao carregar a ficha compartilhada ({player_id}): {_safe_error(exc)}")
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
        st.error(f"Falha ao salvar a ficha compartilhada ({player_id}): {_safe_error(exc)}")
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
        st.error(f"Falha ao carregar estado compartilhado '{key}': {_safe_error(exc)}")
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
        st.error(f"Falha ao salvar estado compartilhado '{key}': {_safe_error(exc)}")
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
        st.error(f"Falha ao enviar imagem para o armazenamento compartilhado: {_safe_error(exc)}")
        return None


CHAT_KINDS = ("text", "dice", "attack", "defense")
MAX_AUTHOR_LEN = 60
MAX_TEXT_LEN = 1000


def clean_author(author, default="Mesa"):
    """Normaliza o nome de exibição sem trocá-lo por um valor padrão se houver texto."""
    name = " ".join(str(author or "").split())[:MAX_AUTHOR_LEN]
    return name or default


def _insert_chat(message_type, data, author):
    """Insere no chat. Retorna (ok, erro_legivel_ou_None). Nunca levanta exceção."""
    client = get_client()
    if client is None:
        return False, "Supabase não configurado (SUPABASE_URL / SUPABASE_ANON_KEY)."
    try:
        client.table("chat_messages").insert({
            "message_type": message_type,
            "author": author,
            "data": data,
        }).execute()
        return True, None
    except Exception as exc:
        return False, _safe_error(exc)


def add_chat_message(message_type, data, author="Mesa"):
    """Publica no chat compartilhado (assinatura original preservada)."""
    ok, err = _insert_chat(message_type, data, clean_author(author))
    if not ok:
        st.error(f"Falha ao publicar no chat: {err}")
    return ok


def publish_roll(kind, payload, author="Mesa", notify=True):
    """Publica rolagem/ataque/defesa/texto no chat. Retorna True/False.

    Assinatura canônica: publish_roll(kind, payload, author). `author` é opcional
    e `notify=False` suprime o st.error (o chamador trata a falha).
    """
    if kind not in CHAT_KINDS:
        kind = "text"
    if not isinstance(payload, dict):
        payload = {"text": str(payload)}
    ok, err = _insert_chat(kind, payload, clean_author(author))
    if not ok and notify:
        st.error(f"Não foi possível publicar no chat: {err}")
    return ok


def send_chat_message(author, text):
    """Valida e envia uma mensagem de texto. Retorna (ok, erro_legivel_ou_None)."""
    body = str(text or "").strip()
    if not body:
        return False, "Escreva uma mensagem antes de enviar."
    if len(body) > MAX_TEXT_LEN:
        return False, f"Mensagem longa demais ({len(body)}/{MAX_TEXT_LEN} caracteres)."
    return _insert_chat("text", {"text": body}, clean_author(author, default="Jogador"))


def get_chat_messages(limit=100):
    client = get_client()
    if client is None:
        return []
    try:
        response = client.table("chat_messages").select("id,created_at,message_type,author,data").order("id", desc=True).limit(limit).execute()
        return list(reversed(response.data or []))
    except Exception as exc:
        st.error(f"Falha ao carregar o chat: {_safe_error(exc)}")
        return []


def clear_chat_messages():
    client = get_client()
    if client is None:
        return False
    try:
        client.table("chat_messages").delete().neq("id", -1).execute()
        return True
    except Exception as exc:
        st.error(f"Falha ao limpar o chat: {_safe_error(exc)}")
        return False
