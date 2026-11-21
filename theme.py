"""Shared VEVOR-inspired visual theme for Streamlit pages."""
import streamlit as st

CSS = '''/* VEVOR V0.98-inspired visual system. Presentation only; no business logic. */
<style>
:root {--vevor-navy:#071f56;--vevor-blue:#0c4aa0;--vevor-orange:#ff5418;--vevor-ice:#edf5ff}
.stApp {background:linear-gradient(125deg,#f4f8ff 0%,#eaf3ff 75%,#e6f0ff 100%);color:#071f56}
.block-container {max-width:1800px;padding-top:1rem;padding-bottom:2rem}
h1,h2,h3,h4,h5 {color:#09275d;letter-spacing:-.025em}
h3 {font-weight:800}
[data-testid="stSidebar"] {background:linear-gradient(180deg,#08275a 0%,#041934 100%);border-right:2px solid #163e79}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] {padding-top:1.1rem}
[data-testid="stSidebar"] {color:#e8f2ff}
[data-testid="stSidebar"] [role="radiogroup"] {gap:.28rem}
[data-testid="stSidebar"] [role="radiogroup"] label {padding:.56rem .65rem;border-radius:10px;transition:background .15s ease}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {background:linear-gradient(100deg,#ff6a1c,#f04411);box-shadow:0 4px 14px #ff5a2038}
[data-testid="stSidebar"] [role="radiogroup"] label:hover {background-color:#23538b}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked):hover {background:linear-gradient(100deg,#ff6a1c,#f04411)}
[data-testid="stSidebar"] [data-baseweb="select"] *,[data-testid="stSidebar"] [data-testid="stDateInput"] input {color:#0b2b5f!important}
[data-testid="stMetric"] {background:linear-gradient(145deg,#fff,#eff6ff);border:1px solid #d2e2fa;border-top:3px solid #1d63cb;border-radius:12px;padding:.65rem .75rem;box-shadow:0 3px 9px #153e7810}
[data-testid="stMetricLabel"] {font-weight:700}
[data-testid="stMetricValue"] {color:#1152bc;font-weight:800}
[data-testid="stVerticalBlockBorderWrapper"] > div[style*="border"] {border-color:#c9dcf7;border-radius:14px;box-shadow:0 4px 14px #19447b12;background:#fff}
[data-testid="stDataFrame"] {border:1px solid #d3e2f5;border-radius:10px;overflow:hidden}
[data-testid="stTabs"] [data-baseweb="tab-list"] {gap:.2rem;border-bottom:2px solid #d5e4f8}
[data-testid="stTabs"] button[role="tab"] {font-weight:750;color:#143b76;border-radius:9px 9px 0 0;padding:.55rem .85rem}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {background:#0c4594;color:white}
.stButton button[kind="primary"],[data-testid="stFormSubmitButton"] button[kind="primary"] {background:#ff581b;border-color:#ff581b;color:white;font-weight:750}
.stButton button:not([kind="primary"]) {border-color:#bad0ef;color:#103c81}
.stButton button:hover {border-color:#ff6427;color:#f04d12}
.vevor-topbar {display:flex;align-items:center;gap:16px;flex-wrap:wrap;background:#fff;padding:14px 20px;border-radius:12px;border-top:4px solid #ff5b19;border-bottom:1px solid #d1e2f7;box-shadow:0 4px 16px #0b34701b;margin-bottom:.4rem}
.vevor-logo {font-size:1.9rem;font-weight:1000;color:#ff5418;letter-spacing:-.065em;white-space:nowrap}
.vevor-divider {height:33px;width:2px;background:#123d83}
.vevor-title {font-size:1.42rem;font-weight:900;color:#071f56;flex:1;min-width:230px}
.vevor-tag {font-size:.77rem;font-weight:750;background:#ff5a19;color:#fff;padding:7px 11px;border-radius:7px}
.vevor-subtitle {font-size:.79rem;color:#46699b;margin:.25rem 0 .8rem .4rem}
.vevor-sidebar-logo {background:#0b356d;border:1px solid #24548a;border-radius:12px;padding:14px 12px;margin-bottom:12px;color:#ff6428;font-size:1.55rem;font-weight:1000;letter-spacing:-.045em}
.vevor-sidebar-logo span {display:block;font-size:.74rem;color:#d8e8ff;letter-spacing:0;font-weight:600;margin-top:3px}
div[class*="st-key-overview_metric_"] button {border:1px solid #d2e2f7!important;border-top:3px solid #0b5dcc!important;background:linear-gradient(145deg,#fff,#edf5ff)!important;border-radius:10px!important;padding:.22rem .45rem!important;min-height:2.3rem!important;justify-content:center!important;box-shadow:0 2px 9px #153e7814!important}
div[class*="st-key-overview_metric_"] button p {font-size:1.38rem!important;font-weight:850!important;color:#0b4ab0!important;line-height:1.2!important}
div[class*="st-key-overview_metric_"] button:hover {border-color:#ff6427!important;background:#fff4ee!important}
div[class*="st-key-overview_metric_"] button:hover p {color:#f04e16!important}
@media(max-width:900px){.vevor-title{font-size:1.1rem}.vevor-logo{font-size:1.5rem}.block-container{padding-left:.8rem;padding-right:.8rem}}

/* GTMS refined sidebar navigation: calm enterprise navy with muted blue selection. */
[data-testid="stSidebar"] {background:#101e33!important;border-right:1px solid #273a54!important}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] {padding-top:1.1rem}
[data-testid="stSidebar"] .vevor-sidebar-logo {background:#172b45!important;border:1px solid #2b405b!important;box-shadow:none!important;color:#ff8058!important}
[data-testid="stSidebar"] .vevor-sidebar-logo span {color:#a9bbd1!important}
[data-testid="stSidebar"] [data-testid="stExpander"] {border:0!important;background:transparent!important;box-shadow:none!important;margin:.15rem 0!important}
[data-testid="stSidebar"] [data-testid="stExpander"] details {border:0!important;background:transparent!important}
[data-testid="stSidebar"] [data-testid="stExpander"] summary {background:transparent!important;border-radius:9px!important;padding:.62rem .65rem!important;min-height:2.5rem!important;transition:background .16s ease}
[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {background:#213550!important}
[data-testid="stSidebar"] [data-testid="stExpander"] summary p {color:#e6edf7!important;font-size:.9rem!important;font-weight:650!important;letter-spacing:.01em!important}
[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stExpanderDetails"] {padding:.2rem .1rem .45rem .65rem!important;border-left:1px solid #30455e!important;margin-left:1.1rem!important}
[data-testid="stSidebar"] [data-testid="stExpander"] .stButton {margin:.1rem 0!important}
[data-testid="stSidebar"] [data-testid="stExpander"] .stButton button {background:transparent!important;border:1px solid transparent!important;box-shadow:none!important;border-radius:7px!important;color:#aebed1!important;min-height:2.1rem!important;padding:.36rem .55rem!important;justify-content:flex-start!important;text-align:left!important;transition:background .15s ease,color .15s ease!important}
[data-testid="stSidebar"] [data-testid="stExpander"] .stButton button p {color:inherit!important;font-size:.84rem!important;font-weight:450!important;white-space:normal!important;line-height:1.35!important;text-align:left!important}
[data-testid="stSidebar"] [data-testid="stExpander"] .stButton button:hover {background:#253b55!important;color:#f5f9ff!important;border-color:transparent!important}
[data-testid="stSidebar"] [data-testid="stExpander"] .stButton button[kind="primary"] {background:#263f5c!important;color:#f5f9ff!important;border-left:3px solid #75a9e8!important;border-radius:5px 8px 8px 5px!important}
[data-testid="stSidebar"] [data-testid="stExpander"] .stButton button[kind="primary"] p {font-weight:650!important}
[data-testid="stSidebar"] [data-testid="stExpander"] .stButton button[kind="primary"]:hover {background:#2d4b6c!important}
[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stExpanderDetails"] > div {gap:.05rem!important}

/* Dedicated logout action: subdued rose outline, separate from navigation selection. */
[data-testid="stSidebar"] .st-key-logout_user button {
    background:#2b2638!important;
    color:#f4c7cd!important;
    border:1px solid #684858!important;
    border-radius:9px!important;
    min-height:2.55rem!important;
    font-weight:650!important;
    box-shadow:none!important;
    transition:background .16s ease,border-color .16s ease!important;
}
[data-testid="stSidebar"] .st-key-logout_user button p {color:#f4c7cd!important;font-weight:650!important}
[data-testid="stSidebar"] .st-key-logout_user button:hover {background:#473044!important;border-color:#bb7786!important;color:#fff1f2!important}
[data-testid="stSidebar"] .st-key-logout_user button:hover p {color:#fff1f2!important}

/* Align every sidebar navigation label to the left, including nested tree items. */
[data-testid="stSidebar"] [data-testid="stExpander"] summary {
    display:flex!important;
    justify-content:flex-start!important;
    text-align:left!important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] summary p,
[data-testid="stSidebar"] [data-testid="stExpander"] summary span {
    text-align:left!important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] .stButton button {
    width:100%!important;
    display:flex!important;
    justify-content:flex-start!important;
    align-items:center!important;
    text-align:left!important;
}
[data-testid="stSidebar"] [data-testid="stExpander"] .stButton button > div,
[data-testid="stSidebar"] [data-testid="stExpander"] .stButton button p {
    width:100%!important;
    text-align:left!important;
    margin-left:0!important;
}

/* Force expanded second-level navigation labels to align at the left edge. */
[data-testid="stSidebar"] [data-testid="stExpanderDetails"] .stButton,
[data-testid="stSidebar"] [data-testid="stExpanderDetails"] .stButton > div,
[data-testid="stSidebar"] [data-testid="stExpanderDetails"] .stButton button {
    width:100%!important;
    text-align:left!important;
}
[data-testid="stSidebar"] [data-testid="stExpanderDetails"] .stButton button {
    justify-content:flex-start!important;
    padding-left:.55rem!important;
}
[data-testid="stSidebar"] [data-testid="stExpanderDetails"] .stButton button [data-testid="stMarkdownContainer"] {
    display:block!important;
    flex:1 1 auto!important;
    width:100%!important;
    text-align:left!important;
}
[data-testid="stSidebar"] [data-testid="stExpanderDetails"] .stButton button [data-testid="stMarkdownContainer"] p {
    text-align:left!important;
    width:100%!important;
    margin:0!important;
}

/* Directly target Streamlit's keyed navigation buttons, independent of expander DOM. */
[data-testid="stSidebar"] [class*="st-key-gtms_tree_"] button,
[data-testid="stSidebar"] [class*="st-key-gtms_tree_"] button[kind="secondary"],
[data-testid="stSidebar"] [class*="st-key-gtms_tree_"] button[kind="primary"] {
    display:flex!important;
    flex-direction:row!important;
    justify-content:flex-start!important;
    align-items:center!important;
    text-align:left!important;
    padding-left:10px!important;
    padding-right:8px!important;
}
[data-testid="stSidebar"] [class*="st-key-gtms_tree_"] button > div,
[data-testid="stSidebar"] [class*="st-key-gtms_tree_"] button [data-testid="stMarkdownContainer"],
[data-testid="stSidebar"] [class*="st-key-gtms_tree_"] button [data-testid="stMarkdownContainer"] > p {
    display:block!important;
    flex:1 1 auto!important;
    width:100%!important;
    text-align:left!important;
    margin-left:0!important;
    margin-right:0!important;
}

/* Streamlit/BaseWeb input text contrast. Avoid key-specific selectors: keys can be
   attached to different wrappers across Streamlit releases. */
[data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"],
[data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stSidebar"] [data-testid="stDateInput"] [data-baseweb="input"],
[data-testid="stSidebar"] [data-testid="stDateInput"] [data-baseweb="input"] > div {
    background-color:#ffffff!important;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"] *,
[data-testid="stSidebar"] [data-testid="stSelectbox"] [role="combobox"],
[data-testid="stSidebar"] [data-testid="stSelectbox"] [role="combobox"] *,
[data-testid="stSidebar"] [data-testid="stDateInput"] input,
[data-testid="stSidebar"] [data-testid="stDateInput"] [data-baseweb="input"] *,
[data-testid="stSidebar"] [data-testid="stDateInput"] [data-baseweb="input"] input {
    color:#0b2b5f!important;
    -webkit-text-fill-color:#0b2b5f!important;
    opacity:1!important;
    font-weight:800!important;
}
[data-testid="stSidebar"] [data-testid="stSelectbox"] [data-baseweb="select"] svg {
    color:#0b2b5f!important;
    fill:#0b2b5f!important;
}
[data-testid="stSidebar"] [data-testid="stDateInput"] label p,
[data-testid="stSidebar"] [data-testid="stDateInput"] [data-testid="stWidgetLabel"] p {
    color:#ffdf45!important;
}
</style>'''

def apply_theme():
    st.markdown(CSS, unsafe_allow_html=True)
