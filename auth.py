"""
auth.py — login / signup / forgot-password gate
===============================================
Wraps streamlit-authenticator and adds email via emailer.py:
  - Log in tab
  - Sign up tab        -> on success, sends a welcome email
  - Forgot password tab -> generates a new password, saves it, emails it

Passwords live ONLY as bcrypt hashes in config.yaml. We never store plain text.
Email needs GMAIL_ADDRESS and GMAIL_APP_PW env vars; if absent, the app still
works and simply skips sending (the new password is shown on screen instead).
"""
import yaml
import streamlit as st
import streamlit_authenticator as stauth

import emailer

CONFIG_PATH = "config.yaml"


def _load_config():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def _save_config(config):
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


def _email_for(config, username):
    """Look up a user's email from the credentials, for sending."""
    return (config["credentials"]["usernames"]
            .get(username, {})
            .get("email"))


def require_login():
    """Gate the app. Returns (authenticator, name, username) when logged in;
    otherwise renders the forms and halts the script."""
    config = _load_config()

    authenticator = stauth.Authenticate(
        config["credentials"],
        config["cookie"]["name"],
        config["cookie"]["key"],
        config["cookie"]["expiry_days"],
    )

    # Already logged in via cookie -> straight through.
    if st.session_state.get("authentication_status"):
        return authenticator, st.session_state["name"], st.session_state["username"]

    st.title("📄 Skimr")
    st.caption("Sign in to study your papers.")

    tab_login, tab_signup, tab_forgot = st.tabs(
        ["Log in", "Sign up", "Forgot password"]
    )

    # ---- Log in ----
    with tab_login:
        authenticator.login(location="main")
        status = st.session_state.get("authentication_status")
        if status is False:
            st.error("Username or password is incorrect.")
        elif status is None:
            st.info("Enter your username and password.")

    # ---- Sign up (sends welcome email) ----
    with tab_signup:
        try:
            email, username_new, name_new = authenticator.register_user(
                location="main",
                captcha=False,
                merge_username_email=False,
            )
            if username_new:
                _save_config(config)             # persist new user (hashed pw)
                # Fire the welcome email (silently skips if email not configured).
                sent = emailer.send_welcome(email, name_new)
                if sent:
                    st.success("Account created — a welcome email is on its way. "
                               "Switch to the Log in tab.")
                else:
                    st.success("Account created. Switch to the Log in tab.")
        except Exception as e:
            st.error(str(e))

    # ---- Forgot password (emails a new password) ----
    with tab_forgot:
        try:
            fp_username, fp_email, new_pw = authenticator.forgot_password(
                location="main"
            )
            if fp_username:
                # Library already reset the hash in-memory; persist it.
                _save_config(config)
                name_for = (config["credentials"]["usernames"]
                            .get(fp_username, {})
                            .get("name", fp_username))
                sent = emailer.send_new_password(fp_email, name_for, new_pw)
                if sent:
                    st.success("A new password has been emailed to you.")
                else:
                    # No email configured -> show it on screen as a fallback.
                    st.warning("Email isn't configured, so here is your new "
                               "password (copy it now):")
                    st.code(new_pw)
            elif fp_username is False:
                st.error("Username not found.")
        except Exception as e:
            st.error(str(e))

    if not st.session_state.get("authentication_status"):
        st.stop()

    return authenticator, st.session_state["name"], st.session_state["username"]
