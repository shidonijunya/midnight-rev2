"""Server-side password-only login for Midnight Sun.

Hashes belong in Streamlit Secrets, never in Git.
"""
import hashlib
import hmac
import secrets
import streamlit as st

ROLES = ("jogador_1", "jogador_2", "jogador_3", "mestre")
ITERATIONS = 600_000


def hash_password(password, salt=None):
    if len(password) < 12:
        raise ValueError("A senha precisa de pelo menos 12 caracteres.")
    salt = salt if salt is not None else secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, ITERATIONS)
    return "pbkdf2_sha256$" + str(ITERATIONS) + "$" + salt.hex() + "$" + derived.hex()


def verify_password(candidate, stored):
    try:
        kind, count, salt, digest = stored.split("$")
        count = int(count)
        if kind != "pbkdf2_sha256" or not (300_000 <= count <= 2_000_000):
            return False
        derived = hashlib.pbkdf2_hmac("sha256", candidate.encode(),
                                     bytes.fromhex(salt), count)
        return hmac.compare_digest(derived, bytes.fromhex(digest))
    except (ValueError, TypeError, AttributeError):
        return False


def resolve_role(password):
    hashes = st.secrets.get("ACCESS_PASSWORD_HASHES", {})
    matches = []
    for role in ROLES:
        encoded = hashes.get(role, "")
        if encoded and verify_password(password, encoded):
            matches.append(role)
    return matches[0] if len(matches) == 1 else None


def credentials_ready():
    try:
        hashes = st.secrets.get("ACCESS_PASSWORD_HASHES", {})
        return all(bool(hashes.get(role)) for role in ROLES)
    except Exception:
        return False


def login_gate():
    if not credentials_ready():
        st.error("Configure ACCESS_PASSWORD_HASHES nos Secrets para ativar o acesso unificado por senha.")
        st.stop()
    role = st.session_state.get("_midnight_role")
    if role in ROLES:
        return role
    st.title("🌘 Midnight Sun")
    st.caption("Acesso à mesa")
    with st.form("login", clear_on_submit=True):
        pwd = st.text_input("Senha", type="password")
        submitted = st.form_submit_button("Entrar", use_container_width=True)
    if submitted:
        found = resolve_role(pwd)
        if found:
            st.session_state["_midnight_role"] = found
            st.rerun()
        st.error("Senha incorreta.")
    st.stop()


def require_role(*allowed):
    # Backward compatibility: the five previously deployed app URLs continue to
    # run on their existing Supabase config. Password gate becomes mandatory
    # as soon as all four credential hashes are installed in that deployment.
    if not credentials_ready():
        return None
    role = st.session_state.get("_midnight_role")
    if role not in ROLES:
        login_gate()
    if allowed and role not in allowed:
        st.error("Sem permissão para acessar esta seção.")
        st.stop()
    return role


def logout():
    st.session_state.clear()
    st.rerun()
