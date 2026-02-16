"""Simple password authentication gate for Streamlit."""

import os

import streamlit as st


def check_authentication() -> bool:
    """Return True if authenticated or no password is configured."""
    password = os.environ.get("LB_PASSWORD", "")
    if not password:
        return True

    if st.session_state.get("authenticated"):
        return True

    st.markdown(
        "<div style='text-align:center; margin-top:3em;'>"
        "<h2>Letterboxd Death Race</h2>"
        "</div>",
        unsafe_allow_html=True,
    )

    with st.form("login_form"):
        entered = st.text_input("Contrasena", type="password")
        submitted = st.form_submit_button("Entrar")

    if submitted:
        if entered == password:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Contrasena incorrecta")

    return False
