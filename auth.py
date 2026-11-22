"""Streamlit local user accounts. Store the credential DB on persistent storage in production."""
import hashlib
import hmac
import os
import secrets
import sqlite3
from db_backend import connect as db_connect, is_neon
from datetime import datetime, timezone

import psycopg

import streamlit as st

AUTH_DB = os.environ.get("AUTH_DB_PATH", os.path.join(os.path.dirname(__file__), "users.db"))
ROLES = ("系统管理员", "港后运营人员", "港后拖车商", "财务结算", "海外仓运营人员")
LEGACY_ROLES = {"管理员": "系统管理员", "运营人员": "港后运营人员", "只读用户": "海外仓运营人员"}
MODULES = {
    "港后运营管理": ["港后运营工作台", "港口与铁路到站动态监控中心", "货柜详细信息查询", "物流AI助理", "港后拖车商DO分配", "港后LFD智能预警管理", "港后供应商产能与计划管理", "港后供应商绩效KPI管理"],
    "港后拖车行结算管理": ["拖车行合同管理", "拖车行异常费用管理", "账期与费用结算管理"],
    "企业主数据管理": ["全球国家与业务区域管理", "全球港口与码头管理", "船司管理", "清关行管理", "海外仓主数据管理", "拖车行主数据管理"],
    "系统管理": ["角色管理", "用户管理", "系统数据备份", "业务数据导入管理", "数据库连接状态管理"],
}
ALL_MODULES = [name for group in MODULES.values() for name in group]
DEFAULT_PERMISSIONS = {
    "系统管理员": ALL_MODULES,
    "港后运营人员": MODULES["港后运营管理"] + ["拖车行异常费用管理", "全球国家与业务区域管理", "全球港口与码头管理", "船司管理", "清关行管理", "海外仓主数据管理", "拖车行主数据管理"],
    # External suppliers must not access unscoped business reports until supplier-level isolation is implemented.
    "港后拖车商": [],
    "财务结算": ["拖车行合同管理", "拖车行异常费用管理", "账期与费用结算管理"],
    "海外仓运营人员": [],
}
def canonical_role(role):
    return LEGACY_ROLES.get(role, role)
def is_admin(user):
    return canonical_role(user["role"]) == "系统管理员"
def ensure_roles():
    with _connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS gtms_role_permissions (
            role TEXT NOT NULL, module TEXT NOT NULL,
            PRIMARY KEY (role, module)
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS gtms_roles (
            role TEXT PRIMARY KEY, description TEXT NOT NULL DEFAULT ''
        )""")
        for role in ROLES:
            exists = conn.execute("SELECT 1 FROM gtms_roles WHERE role=?", (role,)).fetchone()
            if exists:
                continue
            conn.execute("INSERT INTO gtms_roles (role, description) VALUES (?, ?)", (role, "系统预设角色"))
            for module in DEFAULT_PERMISSIONS[role]:
                conn.execute("INSERT INTO gtms_role_permissions (role, module) VALUES (?, ?) ON CONFLICT (role, module) DO NOTHING", (role, module))
        # Convert legacy roles without losing existing user accounts or password hashes.
        for old, new in LEGACY_ROLES.items():
            conn.execute("UPDATE users SET role=? WHERE role=?", (new, old))
def permitted_modules(user):
    role = canonical_role(user["role"])
    if role == "系统管理员":
        return set(ALL_MODULES)
    with _connect() as conn:
        return {r["module"] for r in conn.execute("SELECT module FROM gtms_role_permissions WHERE role=?", (role,)).fetchall()}
def manage_roles(user):
    if not is_admin(user):
        st.error("仅系统管理员可管理角色。")
        return
    st.title("角色管理")
    st.caption("角色权限保存在当前数据库；变更后用户下次页面刷新生效。外部供应商数据隔离未完成前不开放业务数据页面。")
    ensure_roles()
    with _connect() as conn:
        rows = conn.execute("SELECT role, module FROM gtms_role_permissions").fetchall()
    grants = {(r["role"], r["module"]) for r in rows}
    role = st.selectbox("选择角色", ROLES)
    if role == "系统管理员":
        st.info("系统管理员拥有全部权限，不允许取消。")
    elif role in ("港后拖车商", "海外仓运营人员"):
        st.warning("此角色涉及业务数据隔离，目前仅预留角色身份，不开放未隔离的数据页面。")
    with st.form("role_permissions"):
        chosen = []
        for group, modules in MODULES.items():
            st.markdown("**" + group + "**")
            for module in modules:
                allowed = (role, module) in grants
                locked = role == "系统管理员" or role in ("港后拖车商", "海外仓运营人员") or group == "系统管理"
                if st.checkbox(module, value=allowed or role == "系统管理员", disabled=locked, key="role_" + role + "_" + module):
                    chosen.append(module)
        save = st.form_submit_button("保存角色权限", disabled=role == "系统管理员" or role in ("港后拖车商", "海外仓运营人员"))
    if save:
        with _connect() as conn:
            conn.execute("DELETE FROM gtms_role_permissions WHERE role=?", (role,))
            for module in chosen:
                if module not in MODULES["系统管理"]:
                    conn.execute("INSERT INTO gtms_role_permissions (role, module) VALUES (?, ?)", (role, module))
        st.success("角色权限已保存。")
        st.rerun()
    st.subheader("角色权限概览")
    st.dataframe([{"角色": r, "已授权页面数": len(ALL_MODULES) if r == "系统管理员" else sum((r,m) in grants for m in ALL_MODULES)} for r in ROLES], hide_index=True, use_container_width=True)



def _connect():
    conn = db_connect(AUTH_DB, timeout=15)
    if not is_neon():
        conn.execute("PRAGMA busy_timeout=15000")
        conn.execute("""CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY COLLATE NOCASE,
            salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""")
        conn.commit()
    return conn


def _hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                              bytes.fromhex(salt), 600000).hex()


def _new_password(password):
    salt = secrets.token_hex(16)
    return salt, _hash(password, salt)


def bootstrap():
    """Create the first admin from Streamlit Secrets, never from public source code."""
    with _connect() as conn:
        count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if count:
            return True
        initial = str(st.secrets.get("ADMIN_PASSWORD", ""))
        if not initial or len(initial) < 12:
            return False
        salt, digest = _new_password(initial)
        now = datetime.now(timezone.utc).isoformat()
        conn.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?)",
                     ("admin", salt, digest, "系统管理员", 1, now, now))
    return True


def authenticate(username, password):
    with _connect() as conn:
        row = conn.execute("SELECT * FROM users WHERE username=? AND enabled=1",
                           (username.strip(),)).fetchone()
    if row is None:
        # Keep a comparable password derivation even for unknown usernames.
        _hash(password, "00" * 16)
        return None
    actual = _hash(password, row["salt"])
    if hmac.compare_digest(actual, row["password_hash"]):
        return {"username": row["username"], "role": row["role"]}
    return None


def current_user():
    username = st.session_state.get("auth_username")
    if not username:
        return None
    with _connect() as conn:
        row = conn.execute("SELECT username, role, enabled FROM users WHERE username=?",
                           (username,)).fetchone()
    if row is None or not row["enabled"]:
        st.session_state.pop("auth_username", None)
        return None
    return {"username": row["username"], "role": row["role"]}


def login_gate():
    try:
        ready = bootstrap()
        if ready:
            ensure_roles()
            user = current_user()
    except (psycopg.OperationalError, sqlite3.OperationalError) as exc:
        # Authentication must fail closed: never switch to a local credential DB.
        # Do not render database URLs, usernames, or driver exception text.
        st.error("登录服务暂时无法连接数据库，请稍后重试。")
        st.info("请在 Streamlit Cloud 的应用日志中检查 PostgreSQL 连接失败原因，并核实 Neon 数据库状态、DATABASE_URL、SSL 和网络连接。")
        if st.button("重新尝试连接数据库",key="auth_db_retry"):
            st.rerun()
        st.stop()
    if not ready:
        st.error("尚未初始化管理员。请在 Streamlit Cloud → App settings → Secrets 配置长度至少 12 位的 ADMIN_PASSWORD。")
        st.stop()
    if user:
        return user
    # Self-contained global logistics artwork; no external image requests.
    import base64
    artwork = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900">
    <defs><linearGradient id="bg" x2="1" y2="1"><stop stop-color="#10243e"/><stop offset="1" stop-color="#245379"/></linearGradient><pattern id="grid" width="80" height="80" patternUnits="userSpaceOnUse"><path d="M80 0H0V80" fill="none" stroke="#8bb4d4" opacity=".12"/></pattern></defs>
    <rect width="1600" height="900" fill="url(#bg)"/><rect width="1600" height="900" fill="url(#grid)"/>
    <g fill="#719aba" opacity=".26"><path d="M90 190L155 126 245 114 294 154 380 149 409 209 350 233 319 303 265 313 235 373 190 343 160 270 95 253Z"/><path d="M320 360L405 384 458 450 430 522 389 588 356 655 331 601 345 519 302 441Z"/><path d="M668 178L725 138 812 149 864 195 830 241 745 240 695 271 647 231Z"/><path d="M713 282L824 268 901 327 859 440 790 533 739 473 697 364Z"/><path d="M846 165L968 115 1110 139 1227 113 1398 179 1461 249 1370 294 1286 270 1239 359 1152 330 1118 414 1050 345 970 313 907 237Z"/><path d="M1200 535L1291 484 1392 530 1423 600 1340 640 1227 610Z"/></g>
    <g fill="none" stroke="#83c9ed" stroke-width="2" opacity=".65" stroke-dasharray="7 8"><path d="M205 267Q720 -90 1240 290"/><path d="M1240 290Q1450 405 1320 565"/><path d="M205 267Q420 110 730 210"/><path d="M320 430Q640 120 1240 290"/><path d="M730 210Q1000 55 1240 290"/></g>
    <g fill="#ff7845" stroke="#ffd3b9" stroke-width="2"><circle cx="205" cy="267" r="6"/><circle cx="320" cy="430" r="6"/><circle cx="730" cy="210" r="6"/><circle cx="1240" cy="290" r="6"/><circle cx="1320" cy="565" r="6"/></g>
    <g fill="#c6e0f3" font-family="Arial" font-size="15" letter-spacing="3" opacity=".7"><text x="100" y="730">GLOBAL LOGISTICS</text><text x="1220" y="730">CONNECTED WORLD</text></g>
    </svg>"""
    encoded = base64.b64encode(artwork.encode("utf-8")).decode("ascii")
    st.markdown("""<style>
    .stApp {background:#10243e url('data:image/svg+xml;base64,""" + encoded + """') center center / cover no-repeat fixed!important}
    [data-testid="stMainBlockContainer"],.block-container {max-width:420px!important;width:calc(100% - 32px)!important;min-height:100dvh!important;display:flex!important;flex-direction:column!important;justify-content:center!important;padding:24px 0!important;margin:auto!important}
    [data-testid="stMain"] [data-testid="stForm"] {background:#fff!important;border:1px solid #d8e2ee!important;border-radius:14px!important;padding:26px!important;box-shadow:0 18px 65px #07172866!important}
    .gtms-login-brand {text-align:center;color:#ff6428;font-size:32px;font-weight:900;letter-spacing:-1px;line-height:1.3}
    .gtms-login-title {text-align:center;color:#17365a;font-size:19px;font-weight:650;margin:8px 0 2px}
    .gtms-login-sub {text-align:center;color:#64748b;font-size:12px;margin-bottom:20px}
    [data-testid="stForm"] label p {color:#334155!important;font-size:13px!important}
    [data-testid="stFormSubmitButton"] button {width:100%!important;background:#1764ad!important;color:white!important;border:0!important;min-height:42px!important}
    [data-testid="stFormSubmitButton"] button p {color:white!important}
    </style>""", unsafe_allow_html=True)
    with st.form("user_login", clear_on_submit=True):
        st.markdown('<div class="gtms-login-brand">VEVOR®</div><div class="gtms-login-title">全球运输管理系统</div><div class="gtms-login-sub">Global Transportation Management System</div>', unsafe_allow_html=True)
        username = st.text_input("用户名", value="admin")
        password = st.text_input("密码", type="password")
        submitted = st.form_submit_button("登录工作台", type="primary", use_container_width=True)
    if submitted:
        verified = authenticate(username, password)
        if verified:
            st.session_state["auth_username"] = verified["username"]
            st.rerun()
        st.error("用户名或密码错误，或账号已停用。")
    st.stop()


def _user_rows():
    with _connect() as conn:
        return conn.execute(
            "SELECT username, role, enabled, created_at FROM users ORDER BY username"
        ).fetchall()


def _verified_user(username):
    # A fresh connection verifies the committed row is visible beyond the write transaction.
    with _connect() as conn:
        return conn.execute(
            "SELECT username, role, enabled FROM users WHERE lower(username)=lower(?)",
            (username,),
        ).fetchone()


def manage_users(user):
    if not is_admin(user):
        st.error("仅管理员可访问用户管理。")
        return
    st.subheader("👥 用户管理")
    st.caption("用户账号保存在当前应用实际连接的数据库。创建成功后会使用独立连接核实持久化结果。")
    st.caption("当前数据库：" + ("Neon PostgreSQL" if is_neon() else "SQLite（本地）"))
    message = st.session_state.pop("user_management_notice", None)
    if message:
        st.success(message)

    with st.expander("➕ 新建用户"):
        with st.form("create_user", clear_on_submit=True):
            username = st.text_input("新用户名")
            password = st.text_input("初始密码（至少12位）", type="password")
            role = st.selectbox("角色", ROLES)
            submit = st.form_submit_button("创建账号")
        if submit:
            username = username.strip()
            allowed = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-"
            if not username or len(username) > 64 or any(c not in allowed for c in username):
                st.error("用户名仅允许英文字母、数字、下划线、点和短横线，最长64位。")
            elif len(password) < 12:
                st.error("密码至少12位。")
            else:
                try:
                    if _verified_user(username) is not None:
                        st.error("用户名已存在（用户名不区分大小写）。")
                    else:
                        salt, digest = _new_password(password)
                        now = datetime.now(timezone.utc).isoformat()
                        with _connect() as conn:
                            conn.execute(
                                "INSERT INTO users (username,salt,password_hash,role,enabled,created_at,updated_at) "
                                "VALUES (?,?,?,?,?,?,?)",
                                (username, salt, digest, role, 1, now, now),
                            )
                        saved = _verified_user(username)
                        if saved is None or saved["role"] != role or not saved["enabled"]:
                            st.error("写入后未能从数据库重新读取到该账号，创建未通过验证。请检查数据库连接和日志。")
                        else:
                            st.session_state["user_management_notice"] = (
                                f"账号 {saved['username']} 已提交数据库并通过独立连接验证。"
                            )
                            st.rerun()
                except (sqlite3.IntegrityError, psycopg.errors.UniqueViolation):
                    st.error("用户名已存在。")
                except Exception as exc:
                    st.error("创建账号失败，请检查数据库连接和写入权限。")
                    st.caption("错误类型：" + type(exc).__name__)

    try:
        rows = _user_rows()
    except Exception as exc:
        st.error("无法刷新用户列表。")
        st.caption("错误类型：" + type(exc).__name__)
        return

    st.markdown("#### 已保存用户")
    st.caption(f"当前数据库共 {len(rows)} 个账号；此列表每次打开页面都从数据库重新查询。")
    st.dataframe(
        [{"用户名": r["username"], "角色": r["role"],
          "状态": "启用" if r["enabled"] else "停用",
          "创建时间": str(r["created_at"])[:19]} for r in rows],
        hide_index=True, use_container_width=True,
    )
    if not rows:
        st.info("当前数据库中没有用户。")
        return
    with st.expander("🛠️ 修改账号 / 重置密码"):
        selected = st.selectbox("选择账号", [r["username"] for r in rows])
        existing = next(r for r in rows if r["username"] == selected)
        with st.form("edit_user"):
            new_role = st.selectbox("角色", ROLES, index=ROLES.index(existing["role"]))
            enabled = st.checkbox("启用账号", value=bool(existing["enabled"]))
            new_password = st.text_input("重置密码（留空则不修改）", type="password")
            save = st.form_submit_button("保存修改")
        if save:
            if new_password and len(new_password) < 12:
                st.error("新密码至少12位。")
            elif selected.lower() == user["username"].lower() and (not enabled or new_role != "管理员"):
                st.error("不能停用自己或取消自己的管理员权限。")
            else:
                try:
                    with _connect() as conn:
                        if new_password:
                            salt, digest = _new_password(new_password)
                            conn.execute(
                                "UPDATE users SET role=?, enabled=?, salt=?, password_hash=?, updated_at=? WHERE username=?",
                                (new_role, int(enabled), salt, digest,
                                 datetime.now(timezone.utc).isoformat(), selected),
                            )
                        else:
                            conn.execute(
                                "UPDATE users SET role=?, enabled=?, updated_at=? WHERE username=?",
                                (new_role, int(enabled), datetime.now(timezone.utc).isoformat(), selected),
                            )
                    saved = _verified_user(selected)
                    if saved is None or saved["role"] != new_role or bool(saved["enabled"]) != enabled:
                        st.error("修改后验证失败，请检查数据库状态。")
                    else:
                        st.session_state["user_management_notice"] = f"账号 {selected} 修改成功并通过数据库验证。"
                        st.rerun()
                except Exception as exc:
                    st.error("保存账号修改失败。")
                    st.caption("错误类型：" + type(exc).__name__)


def change_own_password(user):
    st.subheader("修改我的密码")
    with st.form("change_own_password", clear_on_submit=True):
        old = st.text_input("当前密码", type="password")
        new = st.text_input("新密码（至少12位）", type="password")
        confirm = st.text_input("确认新密码", type="password")
        submit = st.form_submit_button("修改密码")
    if submit:
        if not authenticate(user["username"], old):
            st.error("当前密码不正确。")
        elif len(new) < 12 or new != confirm:
            st.error("新密码至少12位，且两次输入必须一致。")
        else:
            salt, digest = _new_password(new)
            with _connect() as conn:
                conn.execute("UPDATE users SET salt=?, password_hash=?, updated_at=? WHERE username=?",
                             (salt, digest, datetime.now(timezone.utc).isoformat(), user["username"]))
            st.success("密码修改成功。")
