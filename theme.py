"""Shared VEVOR-inspired visual theme for Streamlit pages."""
import streamlit as st
import pandas as pd
from functools import wraps

CSS = '''<style>
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

/* Operational filter labels only: yellow on navy; input values remain dark blue. */
[data-testid="stSidebar"] [class*="st-key-gtms_filter_region"] [data-testid="stWidgetLabel"] p,
[data-testid="stSidebar"] [class*="st-key-gtms_filter_supplier"] [data-testid="stWidgetLabel"] p,
[data-testid="stSidebar"] [class*="st-key-gtms_filter_region"] label p,
[data-testid="stSidebar"] [class*="st-key-gtms_filter_supplier"] label p {
    color:#ffdf45!important;
    -webkit-text-fill-color:#ffdf45!important;
    font-weight:800!important;
}

/* Compact desktop application layout; keep shared navigation and controls intact. */
.stApp {background:#f3f6fa}
[data-testid="stMainBlockContainer"],.block-container {max-width:none!important;padding:1.8rem 1.15rem 1rem!important}
[data-testid="stMain"] [data-testid="stVerticalBlock"] {gap:.45rem}
[data-testid="stMain"] h1 {font-size:20px!important;line-height:1.35!important;padding:.2rem 0!important}
[data-testid="stMain"] h2 {font-size:18px!important;line-height:1.35!important;padding:.2rem 0!important}
[data-testid="stMain"] h3,[data-testid="stMain"] h4,[data-testid="stMain"] h5 {font-size:14px!important;line-height:1.4!important;padding:.15rem 0!important}
[data-testid="stMain"] [data-testid="stMarkdownContainer"] p,[data-testid="stMain"] [data-testid="stWidgetLabel"] p {font-size:13px;line-height:1.45;margin-bottom:.2rem}
[data-testid="stMain"] [data-testid="stCaptionContainer"] p {font-size:11px!important;line-height:1.35}
[data-testid="stMain"] [data-testid="stMetric"] {padding:7px 10px;border-radius:7px;border-top:2px solid #f97316;box-shadow:none;background:#fff}
[data-testid="stMetricValue"],[data-testid="stMetricValue"] > div {font-size:20px!important;line-height:1.3!important}
[data-testid="stMetricLabel"] p,[data-testid="stMetricDelta"] {font-size:11px!important}
[data-testid="stMain"] [data-testid="stButton"] button,[data-testid="stMain"] [data-testid="stDownloadButton"] button {min-height:30px;padding:4px 10px;border-radius:6px}
[data-testid="stMain"] [data-testid="stTabs"] button[role="tab"] {padding:6px 12px;font-size:13px}
[data-testid="stMain"] [data-testid="stVerticalBlockBorderWrapper"] > div[style*="border"] {border-radius:8px;box-shadow:none}
[data-testid="stDataFrame"] {border-radius:6px}
[data-testid="stMain"] table th,[data-testid="stMain"] table td {font-size:12px;padding:5px 8px}
[data-testid="stMain"] hr {margin:.5rem 0}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {gap:.35rem}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] {padding-top:.5rem}
[data-testid="stSidebar"] .vevor-sidebar-logo {padding:7px 10px;margin-bottom:3px;border:0!important;background:transparent!important;font-size:24px;color:#ff6428!important;letter-spacing:-1.5px}
[data-testid="stSidebar"] [data-testid="stExpander"] summary {min-height:30px!important;padding:4px 8px!important}
[data-testid="stSidebar"] [data-testid="stExpander"] .stButton button {min-height:28px!important;padding-top:3px!important;padding-bottom:3px!important}
[data-testid="stSidebar"] [data-testid="stExpander"] summary p {font-size:13px!important}
[data-testid="stSidebar"] [data-testid="stExpander"] .stButton button p {font-size:12px!important}
div[class*="st-key-overview_metric_"] button p {font-size:19px!important}
@media(max-width:700px){[data-testid="stMainBlockContainer"],.block-container{padding:2.5rem .65rem 1rem!important}}
 
/* Lightning-inspired workspace */
.stApp {background:#eef2f7}
[data-testid="stSidebar"] {background:#fff!important;border-right:1px solid #d8e0eb!important;color:#243b53}
[data-testid="stSidebar"] [data-testid="stExpander"] summary p {color:#243b53!important}
[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {background:#edf3fa!important}
[data-testid="stSidebar"] [data-testid="stExpander"] .stButton button {color:#425b76!important}
[data-testid="stSidebar"] [data-testid="stExpander"] .stButton button:hover {background:#edf3fa!important;color:#165da8!important}
[data-testid="stSidebar"] [data-testid="stExpander"] .stButton button[kind="primary"] {background:#e5effc!important;color:#145ca8!important;border-left:3px solid #1764ad!important}
[data-testid="stSidebar"] [data-testid="stExpander"] .stButton button[kind="primary"]:hover {background:#dbe9fa!important}
[data-testid="stSidebar"] [data-testid="stExpanderDetails"] {border-left-color:#dce5ef!important}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p,[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {color:#52677e!important}
[data-testid="stSidebar"] [data-testid="stExpander"] summary svg {color:#52677e!important}
[data-testid="stSidebar"] .vevor-sidebar-logo {color:#ff5418!important;margin:0 0 5px!important;padding:2px 8px!important}
[data-testid="stMain"] [data-testid="stVerticalBlockBorderWrapper"] > div[style*="border"] {background:white;border-color:#d7e0eb!important}
.gtms-kpi-label {font-size:11px;color:#52677e;line-height:1.4;min-height:30px;display:flex;align-items:end}
div[class*="st-key-overview_metric_"] button {width:100%!important;min-height:48px!important;border-radius:6px!important;background:#fff!important;box-shadow:none!important;border:1px solid #d8e2ee!important;border-top:2px solid #1764ad!important;justify-content:flex-start!important;padding:6px 10px!important}
div[class*="st-key-overview_metric_"] button p {font-size:20px!important;color:#17365a!important}
div[class*="st-key-overview_metric_"][class$="_3"] button p {color:#ba3c43!important}
div[class*="st-key-overview_metric_"][class$="_7"] button p {color:#b47716!important}
[data-testid="stTabs"] button[role="tab"][aria-selected="true"] {background:transparent!important;color:#1764ad!important}
[data-testid="stTabs"] [data-baseweb="tab-list"] {background:#fff;border-radius:6px;padding:0 8px}

/* Fix header collision and KPI text layout. */
[data-testid="stMainBlockContainer"],.block-container {padding-top:4rem!important}
[data-testid="stSidebar"] [data-testid="stSidebarHeader"] {padding:0 12px!important;min-height:40px!important;height:40px!important}
[data-testid="stSidebar"] [data-testid="stSidebarContent"] {padding-top:0!important}
[data-testid="stSidebar"] [data-testid="stSidebarUserContent"] {padding-top:0!important}
[data-testid="stSidebar"] .vevor-sidebar-logo {line-height:1.15!important;padding:0 8px!important;margin:0!important}
[data-testid="stMain"] [data-testid="stVerticalBlock"] {gap:.65rem!important}
[data-testid="stMain"] h1,[data-testid="stMain"] h2,[data-testid="stMain"] h3,[data-testid="stMain"] h4,[data-testid="stMain"] h5 {line-height:1.5!important;overflow:visible!important;padding:3px 0!important;margin:0!important}
div[class*="st-key-overview_metric_"]:not([class*="close"]) button {height:auto!important;min-height:70px!important;align-items:center!important;justify-content:center!important;padding:8px 4px!important}
div[class*="st-key-overview_metric_"]:not([class*="close"]) button [data-testid="stMarkdownContainer"] {width:100%;overflow:visible!important}
div[class*="st-key-overview_metric_"]:not([class*="close"]) button p {font-size:11px!important;line-height:1.4!important;white-space:normal!important;overflow-wrap:anywhere!important;margin:0!important;text-align:center!important;color:#52677e!important}
div[class*="st-key-overview_metric_"]:not([class*="close"]) button p strong {display:inline-block;font-size:20px!important;line-height:1.35!important;color:#17365a!important;margin-top:4px}
div[class*="st-key-overview_metric_"][class$="_3"] button strong {color:#ba3c43!important}
div[class*="st-key-overview_metric_"][class$="_7"] button strong {color:#b47716!important}
[data-testid="stTabs"] button[role="tab"] {min-height:36px!important;line-height:1.4!important}

/* Remove hosted toolbar chrome while retaining sidebar navigation controls. */
[data-testid="stToolbar"],[data-testid="stDecoration"] {display:none!important}
[data-testid="stHeader"] {background:transparent!important;height:0!important;min-height:0!important;overflow:visible!important;pointer-events:none!important}
[data-testid="stSidebarCollapsedControl"],[data-testid="collapsedControl"],[data-testid="stSidebarCollapseButton"] {pointer-events:auto!important}
[data-testid="stMainBlockContainer"],.block-container {padding-top:12px!important}
.stApp:has([data-testid="stSidebar"][aria-expanded="false"]) [data-testid="stMainBlockContainer"],
.stApp:has([data-testid="stSidebarCollapsedControl"] button) [data-testid="stMainBlockContainer"] {padding-top:48px!important}
[data-testid="stSidebar"] [data-testid="stSidebarHeader"] {min-height:30px!important;height:30px!important}
@media(max-width:700px){[data-testid="stMainBlockContainer"],.block-container{padding-top:48px!important}}

/* Final sidebar palette: slate navigation, orange brand, accessible labels. */
[data-testid="stSidebar"] {background:#172b43!important;border-right:1px solid #243d58!important;color:#e1eaf5!important}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {gap:.25rem!important}
[data-testid="stSidebar"] [data-testid="stExpander"] details {border:0!important;background:transparent!important}
[data-testid="stSidebar"] [data-testid="stExpander"] summary {background:#203650!important;border-radius:5px!important;min-height:30px!important}
[data-testid="stSidebar"] [data-testid="stExpander"] summary p {color:#f0f5fb!important;font-weight:600!important}
[data-testid="stSidebar"] [data-testid="stExpander"] summary svg {color:#a9bfd7!important}
[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {background:#294763!important}
[data-testid="stSidebar"] [data-testid="stExpanderDetails"] {border-left:1px solid #39536e!important}
[data-testid="stSidebar"] [class*="st-key-gtms_tree_"] button {background:transparent!important;color:#c5d5e7!important;border:0!important;min-height:29px!important;padding:4px 9px!important;box-shadow:none!important}
[data-testid="stSidebar"] [class*="st-key-gtms_tree_"] button p {color:inherit!important;line-height:1.45!important;font-weight:500!important}
[data-testid="stSidebar"] [class*="st-key-gtms_tree_"] button:hover {background:#294763!important;color:#fff!important}
[data-testid="stSidebar"] [class*="st-key-gtms_tree_"] button[kind="primary"] {background:#34577b!important;color:#fff!important;border-left:3px solid #ff7845!important}
[data-testid="stSidebar"] [class*="st-key-gtms_tree_"] button[kind="primary"]:hover {background:#41688f!important}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {color:#a9bfd7!important}
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {color:#d4e1ef!important;font-size:12px!important}
[data-testid="stSidebar"] [class*="st-key-gtms_filter_"] label p,[data-testid="stSidebar"] [class*="st-key-gtms_filter_"] [data-testid="stWidgetLabel"] p {color:#f4d39a!important;-webkit-text-fill-color:#f4d39a!important;font-weight:600!important}
[data-testid="stSidebar"] [data-testid="stCheckbox"] label p {color:#e2eaf4!important}
[data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] svg {color:#c5d5e7!important}
[data-testid="stSidebar"] hr {border-color:#39536e!important;margin:6px 0!important}
.gtms-filter-title {font-size:14px;font-weight:700;color:#f5f8fc;border-top:1px solid #39536e;padding-top:10px;margin:6px 0 3px;line-height:1.5}
</style>'''

def _numbered_display(renderer):
    @wraps(renderer)
    def display(data=None, *args, **kwargs):
        # Display-only; do not mutate source frames or selectable row positions.
        if isinstance(data, pd.DataFrame) and not isinstance(data.columns, pd.MultiIndex):
            data = data.copy()
            if kwargs.get("hide_index") is not True and not isinstance(data.index, pd.RangeIndex):
                index_frame = data.index.to_frame(index=False)
                index_frame.columns = [str(n) if n is not None else f"索引{i+1}" for i,n in enumerate(data.index.names)]
                for col in reversed(index_frame.columns.tolist()):
                    if col not in data.columns:
                        data.insert(0,col,index_frame[col].to_numpy())
            if "序号" not in data.columns:
                data.insert(0, "序号", pd.RangeIndex(1, len(data)+1).astype("int64"))
            data = data.reset_index(drop=True)
            if renderer.__name__ == "dataframe":
                kwargs["hide_index"] = True
                config = dict(kwargs.get("column_config") or {})
                config["序号"] = st.column_config.NumberColumn("序号", format="%d", width="small")
                kwargs["column_config"] = config
                if kwargs.get("column_order") is not None:
                    kwargs["column_order"] = ["序号"] + [c for c in kwargs["column_order"] if c != "序号"]
            elif renderer.__name__ == "table":
                data = data.style.hide(axis="index")
        return renderer(data, *args, **kwargs)
    display._gtms_numbered = True
    return display

def apply_theme():
    # Shared presentation layer; editable data_editor is intentionally untouched.
    for name in ("dataframe", "table"):
        renderer = getattr(st, name)
        if not getattr(renderer, "_gtms_numbered", False):
            setattr(st, name, _numbered_display(renderer))
    st.markdown(CSS, unsafe_allow_html=True)
