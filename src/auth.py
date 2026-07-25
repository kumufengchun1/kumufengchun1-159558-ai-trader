from __future__ import annotations

import hmac
import streamlit as st


def require_password() -> None:
    password = st.secrets.get("APP_PASSWORD", "") if hasattr(st, "secrets") else ""
    if not password:
        return
    if st.session_state.get("authenticated"):
        return
    st.title("159558 AI Trading System")
    entered = st.text_input("访问密码", type="password")
    if st.button("进入"):
        if hmac.compare_digest(entered, str(password)):
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("密码错误")
    st.stop()
