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
    for secret in (config_value("SUPABASE_SERVICE_ROLE_KEY"), config_value("SUPABASE_ANON_KEY"), config_value("SUPABASE_URL")):
        if secret:
            text = text.replace(str(secret), "***")
    return text[:300]


@st.cache_resource(show_spinner=False)
def _cached_client(url, key):
    from supabase import create_client
    return create_client(str(url), str(key))


def get_client():
    url = config_value("SUPABASE_URL")
    # Existing Streamlit apps keep working with their current anon secrets.
    # Service-role access is opt-in and kept exclusively on the Python server.
    key = config_value("SUPABASE_SERVICE_ROLE_KEY") or config_value("SUPABASE_ANON_KEY")
    if not url or not key:
        return None
    try:
        return _cached_client(str(url), str(key))
    except Exception as exc:
        st.error(f"Não foi possível conectar ao Supabase: {_safe_error(exc)}")
        return None


def shared_enabled():
    return bool(config_value("SUPABASE_URL") and (config_value("SUPABASE_ANON_KEY") or config_value("SUPABASE_SERVICE_ROLE_KEY")))


def get_player_id(default="jogador_1"):
    return str(config_value("PLAYER_ID", default))


ROLE_SLOT = {"jogador_1": "jogador_2", "jogador_2": "jogador_3", "jogador_3": "jogador_1"}


def can_access_character(player_id):
    role = st.session_state.get("_midnight_role")
    return role == "mestre" or (role in ROLE_SLOT and ROLE_SLOT[role] == player_id)


def fetch_character(player_id):
    """Return explicit status so a transient outage cannot look like a new character.

    Result: {"status": "found"|"missing"|"error"|"forbidden", "data": dict|None}.
    """
    if auth_configured() and not can_access_character(player_id):
        return {"status": "forbidden", "data": None}
    client = get_client()
    if client is None:
        return {"status": "error", "data": None}
    try:
        result = (client.table("characters").select("data")
                  .eq("player_id", player_id).limit(1).execute())
        rows = result.data or []
        if not rows:
            return {"status": "missing", "data": None}
        if not isinstance(rows[0].get("data"), dict):
            return {"status": "error", "data": None}
        return {"status": "found", "data": rows[0]["data"]}
    except Exception as exc:
        st.error(f"Falha ao carregar a ficha compartilhada ({player_id}): {_safe_error(exc)}")
        return {"status": "error", "data": None}


def load_character(player_id):
    """Backwards-compatible reader; use fetch_character for safe initialization."""
    result = fetch_character(player_id)
    return result["data"] if result["status"] == "found" else None


def create_character_if_missing(player_id, data):
    """Create once; never UPSERT a default sheet over an existing one."""
    if auth_configured() and not can_access_character(player_id):
        return False
    client = get_client()
    if client is None or not isinstance(data, dict):
        return False
    try:
        previous = fetch_character(player_id)
        if previous["status"] not in ("found", "missing"):
            return False
        client.table("characters").upsert({
            "player_id": player_id,
            "data": data,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }, on_conflict="player_id", ignore_duplicates=True).execute()
        return True
    except Exception as exc:
        st.error(f"Falha ao criar ficha inexistente ({player_id}): {_safe_error(exc)}")
        return False


def change_resources_atomic(player_id, deltas, attempts=7):
    """Compare-and-swap *and recompute* on every retry.

    Never use a previously calculated remaining HP/mana/stamina as a patch.
    If an RPC is installed this can be moved to a single PostgreSQL function,
    but CAS protects concurrent edits from the existing apps today.
    Returns (success, fresh_data, human_error).
    """
    allowed = {"hp_atual", "mana_atual", "estamina_atual"}
    if not isinstance(deltas, dict) or not deltas or set(deltas) - allowed:
        return False, None, "Recursos inválidos."
    try:
        values = {key: int(delta) for key, delta in deltas.items()}
    except (TypeError, ValueError):
        return False, None, "Variação inválida."
    if auth_configured() and not can_access_character(player_id):
        return False, None, "Sem permissão para alterar esta ficha."
    client = get_client()
    if client is None:
        return False, None, "Supabase indisponível."
    for _ in range(attempts):
        try:
            response = (client.table("characters").select("data,updated_at")
                        .eq("player_id", player_id).limit(1).execute())
            rows = response.data or []
            if not rows:
                return False, None, "Ficha não encontrada."
            previous = rows[0]
            fresh = dict(previous.get("data") or {})
            for key, delta in values.items():
                remaining = int(fresh.get(key) or 0) + delta
                if remaining < 0:
                    return False, fresh, f"{key.replace('_atual','')} insuficiente."
                fresh[key] = remaining
            stamped = datetime.now(timezone.utc).isoformat()
            result = (client.table("characters")
                      .update({"data": fresh, "updated_at": stamped})
                      .eq("player_id", player_id)
                      .eq("updated_at", previous["updated_at"])
                      .select("player_id").execute())
            if result.data:
                _archive_snapshot(player_id, previous.get("data") or {}, "resources")
                return True, fresh, None
            # Another session wrote in the meantime: re-read and recompute.
        except Exception as exc:
            st.error(f"Falha na atualização dos recursos: {_safe_error(exc)}")
            return False, None, "Erro ao gravar recursos."
    return False, None, "Conflito simultâneo; tente novamente."


def auth_configured():
    try:
        hashes = st.secrets.get("ACCESS_PASSWORD_HASHES", {})
        return all(bool(hashes.get(k)) for k in ("jogador_1","jogador_2","jogador_3","mestre"))
    except Exception:
        return False



def _archive_snapshot(player_id, previous_data, reason="update"):
    """Best-effort bounded history in existing app_state; no schema changes.

    This is not a substitute for an immutable DB trigger if absolute audit
    guarantees are required. Each append uses optimistic version checking.
    """
    if not isinstance(previous_data, dict) or not previous_data:
        return False
    client = get_client()
    if client is None:
        return False
    history_key = "character_history_" + str(player_id)
    entry = {"saved_at": datetime.now(timezone.utc).isoformat(),
             "reason": reason, "data": previous_data}
    for _ in range(6):
        try:
            result = (client.table("app_state").select("data,updated_at")
                      .eq("key", history_key).limit(1).execute())
            rows = result.data or []
            if not rows:
                client.table("app_state").upsert({
                    "key": history_key,
                    "data": {"versions": [entry]},
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }, on_conflict="key", ignore_duplicates=True).execute()
                # Another writer may have inserted first, re-read to be safe.
                check = (client.table("app_state").select("data")
                         .eq("key", history_key).limit(1).execute())
                versions = ((check.data or [{}])[0].get("data") or {}).get("versions") or []
                if versions and versions[0].get("saved_at") == entry["saved_at"]:
                    return True
                continue
            row = rows[0]
            versions = list((row.get("data") or {}).get("versions") or [])
            versions.insert(0, entry)
            updated = (client.table("app_state")
                       .update({"data": {"versions": versions[:30]},
                                "updated_at": datetime.now(timezone.utc).isoformat()})
                       .eq("key", history_key)
                       .eq("updated_at", row["updated_at"])
                       .select("key").execute())
            if updated.data:
                return True
        except Exception:
            return False
    return False


def list_character_history(player_id):
    if auth_configured() and not can_access_character(player_id):
        return []
    data = load_app_state("character_history_" + str(player_id), {})
    return list(data.get("versions", [])) if isinstance(data, dict) else []


def restore_character_version(player_id, history_index):
    """Explicit master-only restoration, conditional on a configured master login."""
    if not auth_configured() or st.session_state.get("_midnight_role") != "mestre":
        return False
    versions = list_character_history(player_id)
    if not isinstance(history_index, int) or not (0 <= history_index < len(versions)):
        return False
    target = versions[history_index].get("data")
    if not isinstance(target, dict):
        return False
    # Existing patch API is CAS-protected. Archive the current row before restore.
    return patch_character(player_id, target)




def save_character(player_id, data):
    if auth_configured() and not can_access_character(player_id):
        return False
    client = get_client()
    if client is None:
        return False
    try:
        client.table("characters").upsert({
            "player_id": player_id,
            "data": data,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }, on_conflict="player_id").execute()
        if previous["status"] == "found" and previous["data"] != data:
            _archive_snapshot(player_id, previous["data"], "full_save")
        return True
    except Exception as exc:
        st.error(f"Falha ao salvar a ficha compartilhada ({player_id}): {_safe_error(exc)}")
        return False


def patch_character(player_id, changes, attempts=5):
    """Optimistic JSONB update: preserve unrelated fields under concurrent edits."""
    if not isinstance(changes, dict) or not changes:
        return True
    if auth_configured() and not can_access_character(player_id):
        return False
    client = get_client()
    if client is None:
        return False
    for _ in range(attempts):
        try:
            response = (client.table("characters").select("data,updated_at")
                        .eq("player_id", player_id).limit(1).execute())
            rows = response.data or []
            if not rows:
                # A missing row must not be recreated from a partial resource update.
                return False
            stored = rows[0]
            merged = dict(stored.get("data") or {})
            merged.update(changes)
            updated = datetime.now(timezone.utc).isoformat()
            result = (client.table("characters")
                      .update({"data": merged, "updated_at": updated})
                      .eq("player_id", player_id)
                      .eq("updated_at", stored["updated_at"])
                      .select("player_id").execute())
            if result.data:
                _archive_snapshot(player_id, stored.get("data") or {}, "edit")
                return True
        except Exception as exc:
            st.error(f"Erro ao atualizar recursos: {_safe_error(exc)}")
            return False
    st.error("Outra sessão alterou a ficha simultaneamente. Tente novamente.")
    return False

def fetch_app_state(key):
    """Like fetch_character, distinguish not-found from transient failures."""
    client = get_client()
    if client is None:
        return {"status": "error", "data": None, "updated_at": None}
    try:
        response = (client.table("app_state").select("data,updated_at")
                    .eq("key", key).limit(1).execute())
        rows = response.data or []
        if not rows:
            return {"status": "missing", "data": None, "updated_at": None}
        return {"status": "found", "data": rows[0].get("data") or {},
                "updated_at": rows[0].get("updated_at")}
    except Exception as exc:
        st.error(f"Falha ao carregar estado '{key}': {_safe_error(exc)}")
        return {"status": "error", "data": None, "updated_at": None}


def load_app_state_record(key):
    """Fetch data plus revision marker. None means unavailable or missing."""
    client = get_client()
    if client is None:
        return None
    try:
        response = (client.table("app_state").select("data,updated_at")
                    .eq("key", key).limit(1).execute())
        rows = response.data or []
        if rows:
            return {"data": rows[0].get("data") or {}, "updated_at": rows[0].get("updated_at")}
    except Exception as exc:
        st.error(f"Falha ao carregar estado '{key}': {_safe_error(exc)}")
    return None

def create_app_state_if_missing(key, data):
    """Idempotent insert without replacing a concurrently created state."""
    if auth_configured() and st.session_state.get("_midnight_role") != "mestre":
        return False
    client = get_client()
    if client is None:
        return False
    try:
        client.table("app_state").upsert({
            "key": key, "data": data,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }, on_conflict="key", ignore_duplicates=True).execute()
        found = load_app_state_record(key)
        return found is not None and found["data"] == data
    except Exception as exc:
        st.error(f"Falha ao inicializar estado '{key}': {_safe_error(exc)}")
        return False



def compare_and_set_app_state(key, expected_timestamp, data):
    """Prevents a stale session overwriting a newer shared state revision."""
    if auth_configured() and st.session_state.get("_midnight_role") != "mestre":
        return False
    client = get_client()
    if client is None or not expected_timestamp:
        return False
    try:
        result = (client.table("app_state")
                  .update({"data": data, "updated_at": datetime.now(timezone.utc).isoformat()})
                  .eq("key", key).eq("updated_at", expected_timestamp)
                  .select("key").execute())
        return bool(result.data)
    except Exception as exc:
        st.error(f"Falha ao gravar estado '{key}': {_safe_error(exc)}")
        return False


def load_app_state(key, default=None):
    if auth_configured() and st.session_state.get("_midnight_role") != "mestre":
        if key not in ("table_display", "battle_grid"):
            return default
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
    if auth_configured() and st.session_state.get("_midnight_role") != "mestre":
        return False
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
    """Server-side assets uploader, enforcing role-specific paths."""
    role = st.session_state.get("_midnight_role")
    if auth_configured() and role not in ("jogador_1", "jogador_2", "jogador_3", "mestre"):
        return None
    if not isinstance(path, str) or ".." in path or path.startswith("/"):
        return None
    if auth_configured() and path.startswith(("scenes/", "bosses/")) and role != "mestre":
        return None
    if auth_configured() and path.startswith("players/") and role != "mestre" and not path.startswith(f"players/{ROLE_SLOT.get(role)}/"):
        return None
    if not path.startswith(("scenes/", "bosses/", "players/", "chat/")):
        return None
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


CHAT_KINDS = ("text", "dice", "attack", "defense", "image")
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
        return False, "Supabase não configurado (SUPABASE_URL e chave anon ou service_role)."
    try:
        if auth_configured():
            role = st.session_state.get("_midnight_role")
            author = {"jogador_1":"Kuro","jogador_2":"Andrias",
                      "jogador_3":"Bondobo","mestre":"Mestre"}.get(role, "Mesa")
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
    if auth_configured() and st.session_state.get("_midnight_role") != "mestre":
        return False
    client = get_client()
    if client is None:
        return False
    try:
        client.table("chat_messages").delete().neq("id", -1).execute()
        return True
    except Exception as exc:
        st.error(f"Falha ao limpar o chat: {_safe_error(exc)}")
        return False
