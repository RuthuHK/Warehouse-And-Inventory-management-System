'''
# app.py
import streamlit as st
import pandas as pd
import mysql.connector
from mysql.connector import Error
from config import DB_CONFIG
from datetime import datetime
import re
import traceback
import time

# ---------- PAGE CONFIG ----------
st.set_page_config(
    page_title=" Inventory & Warehouse Management",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------- ROLE MAP (UI -> DB ENUM) ----------
# DB enum is: ENUM('manager','staff','picker','packer','driver','admin')
ROLE_MAP = {
    "Warehouse Manager": "manager",
    "Receiver": "staff",
    "Picker": "picker",
    "Admin": "admin",
    "Clerk": "staff",
    "Auditor": "staff",
    "Supervisor": "staff",
    # fallback for anything else:
}

# ---------- LIGHT THEME / UI (original CSS included verbatim) ----------
st.markdown("""
    <style>
    :root {
        --primary-color: #2E86AB;
        --secondary-color: #A23B72;
        --success-color: #06A77D;
        --warning-color: #F18F01;
        --danger-color: #C73E1D;
        --background-light: #F3F6F9;
        --text-dark: #1f2d3a;
    }

    /* Lighter sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #e9f3fb 0%, #d0e4f5 100%);
        border-right: 1px solid rgba(0,0,0,0.04);
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        color: #1f2d3a !important;
        font-weight: 500;
    }
    [data-testid="stSidebar"] .stRadio > label {
        color: #1f2d3a !important;
        font-weight: 600;
        font-size: 1.05rem;
    }
    [data-testid="stSidebar"] .stRadio [role="radiogroup"] label {
        background-color: rgba(255,255,255,0.55);
        padding: 10px 14px;
        border-radius: 8px;
        margin: 4px 0;
        transition: all 0.25s ease;
        color: #1f2d3a !important;
    }
    [data-testid="stSidebar"] .stRadio [role="radiogroup"] label:hover {
        background-color: rgba(255,255,255,0.8);
        transform: translateX(2px);
    }

    /* Very light app background */
    [data-testid="stAppViewContainer"] {
        background: #f7f9fb;
    }
    /* Main block area */
    .main {
        background: #f7f9fb;
    }

    /* Card-like look for blocks on light bg */
    [data-testid="stExpander"],
    [data-testid="stDataFrame"],
    .stForm,
    .stAlert {
        background: #ffffff !important;
        border-radius: 10px;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.03);
    }

    /* Headers */
    h1 {
        color: #215f7c !important;
        font-weight: 700 !important;
        padding-bottom: 10px;
        border-bottom: 3px solid rgba(33,95,124,0.18);
        margin-bottom: 18px !important;
    }
    h2 {
        color: #2E86AB !important;
        font-weight: 600 !important;
    }
    h3 {
        color: #A23B72 !important;
        font-weight: 600 !important;
    }

    /* Buttons */
    .stButton>button {
        background: linear-gradient(135deg, #2E86AB 0%, #1a4d6b 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 10px 24px;
        font-weight: 600;
        transition: all 0.3s ease;
        box-shadow: 0 2px 4px rgba(0,0,0,0.08);
    }
    .stButton>button:hover {
        filter: brightness(1.02);
        transform: translateY(-1px);
    }

    /* Form submit buttons */
    .stFormSubmitButton>button {
        background: linear-gradient(135deg, #06A77D 0%, #048060 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 10px 24px;
        font-weight: 600;
    }
    .stFormSubmitButton>button:hover {
        background: linear-gradient(135deg, #048060 0%, #06A77D 100%);
        box-shadow: 0 4px 8px rgba(0,0,0,0.08);
    }

    /* Inputs */
    .stTextInput>div>div>input,
    .stNumberInput>div>div>input,
    .stSelectbox>div>div>select {
        border-radius: 8px;
        border: 2px solid #e0e0e0;
        padding: 8px 12px;
        transition: all 0.3s ease;
    }
    .stTextInput>div>div>input:focus,
    .stNumberInput>div>div>input:focus {
        border-color: #2E86AB;
        box-shadow: 0 0 0 2px rgba(46,134,171,0.08);
    }

    /* Metrics */
    [data-testid="stMetricValue"] {
        font-size: 2rem !important;
        color: #2E86AB !important;
        font-weight: 700 !important;
    }
    [data-testid="stMetricLabel"] {
        color: #5A6C7D !important;
        font-weight: 600 !important;
    }

    /* Alerts */
    .stSuccess {
        background-color: #d4edda;
        border-left: 4px solid #06A77D !important;
        color: #155724;
    }
    .stError {
        background-color: #f8d7da;
        border-left: 4px solid #C73E1D !important;
        color: #721c24;
    }
    .stWarning {
        background-color: #fff3cd;
        border-left: 4px solid #F18F01 !important;
        color: #856404;
    }
    .stInfo {
        background-color: #d1ecf1;
        border-left: 4px solid #2E86AB !important;
        color: #0c5460;
    }

    /* Divider */
    hr {
        border: none;
        height: 2px;
        background: linear-gradient(90deg, transparent 0%, #2E86AB 50%, transparent 100%);
        margin: 20px 0;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* remove card-like boxes from sidebar radio options */
[data-testid="stSidebar"] .stRadio [role="radiogroup"] label {
    background: transparent !important;
    padding: 4px 0 !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    margin: 2px 0 !important;
}
</style>
""", unsafe_allow_html=True)


# ---------- SAFE RERUN UTIL ----------
def safe_rerun():
    """
    Attempt to rerun the Streamlit script in a robust way that works across
    Streamlit versions:
      1) Try st.experimental_rerun() if available.
      2) Fallback to changing st.query_params which triggers a rerun.
      3) As last resort, toggle a session_state flag and stop.
    """
    try:
        # Use experimental_rerun if present (keeps compatibility)
        if hasattr(st, "experimental_rerun"):
            try:
                st.experimental_rerun()
                return
            except Exception:
                pass
    except Exception:
        pass

    try:
        # Use st.query_params read/assign to trigger a rerun. This
        # follows the newer API where st.query_params is the replacement.
        params = dict(st.query_params) if st.query_params is not None else {}
        # ensure _refresh exists as a list (Streamlit's query params are lists)
        params["_refresh"] = [str(time.time())]
        # assign back to trigger rerun
        st.query_params = params
        return
    except Exception:
        pass

    # last resort: toggle a session flag and stop
    st.session_state["_refresh_toggle"] = not st.session_state.get("_refresh_toggle", False)
    st.stop()


# ---------- DB HELPERS ----------
def get_connection():
    try:
        cfg = DB_CONFIG.copy()
        if "port" in cfg and isinstance(cfg["port"], str):
            try:
                cfg["port"] = int(cfg["port"])
            except Exception:
                pass
        conn = mysql.connector.connect(**cfg)
        if conn.is_connected():
            return conn
    except Error as e:
        st.error(f"Database connection failed: {e}")
        st.write(traceback.format_exc())
        return None

def fetch_df(query, params=None):
    conn = get_connection()
    if not conn:
        return pd.DataFrame()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(query, params or ())
        rows = cur.fetchall()
        df = pd.DataFrame(rows)
        cur.close()
        return df
    except Error as e:
        st.error(f"Query failed: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

def exec_query(query, params=None, commit=True, get_lastrowid=False):
    conn = get_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        cur.execute(query, params or ())
        if commit:
            conn.commit()
        lastrowid = cur.lastrowid if get_lastrowid else None
        cur.close()
        return lastrowid
    except Error as e:
        st.error(f"DB operation failed: {e}")
        st.write(traceback.format_exc())
        return None
    finally:
        conn.close()

# ---------- AUTH (SQL-only) HELPERS ----------
def authenticate_user_sql(username: str, password: str):
    """
    Call stored-proc sp_get_menu_for_user OR fn_auth_role to authenticate.
    Returns dict: {'username','role','user_id','menu'} on success, else None.
    NOTE: This passes plaintext password to DB so ensure DB connection is secure.
    """
    if not username or not password:
        return None

    # Try stored-proc first
    try:
        # call stored-proc to get menu rows for the user
        df_menu = fetch_df("CALL sp_get_menu_for_user(%s,%s)", (username, password))
        # If proc returns a single row with AUTH_FAILED, auth failed
        if df_menu.shape[0] == 1 and 'status' in df_menu.columns and str(df_menu.at[0,'status']) == 'AUTH_FAILED':
            return None

        # get role + user_id
        role_df = fetch_df("SELECT user_id, role FROM app_user WHERE username = %s AND password_hash = SHA2(%s,256)", (username, password))
        if role_df.empty:
            return None
        role = role_df.at[0, 'role']
        user_id = int(role_df.at[0, 'user_id'])
        menu = df_menu['menu_item'].tolist() if 'menu_item' in df_menu.columns else []
        return {"username": username, "role": role, "user_id": user_id, "menu": menu}
    except Exception:
        # fallback: try scalar function
        try:
            role_df = fetch_df("SELECT fn_auth_role(%s,%s) AS role", (username, password))
            if role_df.empty or role_df.at[0,'role'] is None:
                return None
            role = role_df.at[0,'role']
            user_df = fetch_df("SELECT user_id FROM app_user WHERE username = %s", (username,))
            user_id = int(user_df.at[0,'user_id']) if not user_df.empty else None
            menu_df = fetch_df("SELECT menu_item FROM role_menu WHERE role = %s ORDER BY sort_order", (role,))
            menu = menu_df['menu_item'].tolist() if not menu_df.empty else []
            return {"username": username, "role": role, "user_id": user_id, "menu": menu}
        except Exception:
            return None

# ---------- LOGIN / SIDEBAR WIDGETS ----------
def show_login_page():
    """
    Show login form in the main page when no session user exists.
    Returns True if logged-in session exists (after successful login), False otherwise.
    """
    st.markdown("<div style='max-width:760px;margin:0 auto'>", unsafe_allow_html=True)
    st.header("Sign in")
    st.write("Please sign in with your username and password to continue.")
    with st.form("login_form_main", clear_on_submit=False):
        username = st.text_input("Username", value="", key="login_username_main")
        password = st.text_input("Password", value="", type="password", key="login_password_main")
        submitted = st.form_submit_button("Sign in")
        if submitted:
            auth = authenticate_user_sql(username.strip(), password)
            if auth:
                # store the minimal user info + menu list
                st.session_state["user"] = {
                    "username": auth["username"],
                    "role": auth["role"],
                    "user_id": auth["user_id"],
                    "menu": auth.get("menu", [])
                }
                st.success("Login successful. Redirecting...")
                # robust rerun
                safe_rerun()
            else:
                st.error("Invalid credentials.")
    st.markdown("</div>", unsafe_allow_html=True)
    return st.session_state.get("user") is not None

def show_sidebar_user_widget():
    """
    Show username + logout button in the sidebar when logged in.
    """
    st.sidebar.markdown("### Account")
    u = st.session_state.get("user")
    if u:
        st.sidebar.success(f"{u.get('username')} ({u.get('role')})")
        if st.sidebar.button("Logout"):
            st.session_state.pop("user", None)
            # After logging out, send user back to login page (force rerun)
            safe_rerun()

# ---------- REQUIRE ROLE ----------
def require_role(allowed_roles):
    """
    Call at top of admin pages. Returns True if allowed, else shows error and returns False.
    """
    us = st.session_state.get("user")
    if not us:
        st.error("Please log in to access this page (use the sidebar).")
        return False
    if us.get("role") not in allowed_roles:
        st.error("You are not authorized to access this page.")
        return False
    return True

# ---------- UTIL ----------
def load_choices(table, key_col, label_col=None, where=None, order_by=None):
    q = f"SELECT {key_col}" + (f", {label_col}" if label_col else "") + f" FROM {table}"
    if where:
        q += " WHERE " + where
    if order_by:
        q += " ORDER BY " + order_by
    df = fetch_df(q)
    if df.empty:
        return {}
    if label_col:
        return {row[key_col]: row[label_col] for _, row in df.iterrows()}
    else:
        return {row[key_col]: str(row[key_col]) for _, row in df.iterrows()}

def ensure_non_empty(text, field_name):
    if not text or (isinstance(text, str) and not text.strip()):
        st.error(f"{field_name} cannot be empty.")
        return False
    return True

def is_valid_gmail(email: str) -> bool:
    if not email or not isinstance(email, str):
        return False
    pattern = r"^[a-zA-Z0-9._%+-]+@gmail\.com$"
    return re.match(pattern, email.strip()) is not None

# ---------- STOCK PAGE ----------
def page_stock():
    st.header(" Stock ")
    st.markdown("")

    warehouses = load_choices("warehouse", "warehouse_id", "name", order_by="name")
    if not warehouses:
        st.info("No warehouses found. Make sure warehouse table exists.")
    wh_choice = st.selectbox("Select warehouse", options=["All"] + [f"{k} - {v}" for k,v in warehouses.items()])

    if wh_choice == "All":
        q = """
        SELECT s.warehouse_id, w.name as warehouse_name,
               i.item_id, i.name as item_name, s.quantity, i.unit_of_measure, i.price, i.reorder_level
        FROM stock s
        JOIN item i ON s.item_id = i.item_id
        LEFT JOIN warehouse w ON s.warehouse_id = w.warehouse_id
        """
        params = ()
    else:
        try:
            wid = int(str(wh_choice).split(" - ")[0])
        except Exception:
            wid = None
        q = """
        SELECT s.warehouse_id, w.name as warehouse_name,
               i.item_id, i.name as item_name, s.quantity, i.unit_of_measure, i.price, i.reorder_level
        FROM stock s
        JOIN item i ON s.item_id = i.item_id
        LEFT JOIN warehouse w ON s.warehouse_id = w.warehouse_id
        WHERE s.warehouse_id = %s
        """
        params = (wid,)
    df = fetch_df(q, params)
    if df.empty:
        st.info("No stock records found.")
    else:
        df["status"] = df.apply(
            lambda r: "LOW" if (r.get("quantity") is not None and r.get("reorder_level") is not None and r["quantity"] < r["reorder_level"]) else "OK",
            axis=1
        )
        st.subheader("Inventory")
        st.dataframe(df[["warehouse_id","warehouse_name","item_id","item_name","quantity","unit_of_measure","price","reorder_level","status"]], use_container_width=True)

        st.subheader("Low-stock items (across all warehouses)")
        low_df = df[df["status"]=="LOW"]
        if low_df.empty:
            st.success("No low-stock items ")
        else:
            st.dataframe(low_df[["warehouse_id","warehouse_name","item_id","item_name","quantity","reorder_level"]], use_container_width=True)

# ---------- PURCHASE / RECEIVE PAGE ----------
def page_purchase():
    st.header(" Purchase Orders")
    st.markdown("")

    # 2.1 Create PO
    with st.expander("2.1 Create PO", expanded=True):
        suppliers = load_choices("supplier", "supplier_id", "name", order_by="name")
        warehouses = load_choices("warehouse", "warehouse_id", "name", order_by="name")
        col1, col2, col3 = st.columns(3)
        with col1:
            supplier_sel = st.selectbox("Pick supplier", options=["-- Add new --"] + [f"{k} - {v}" for k,v in suppliers.items()])
        with col2:
            warehouse_sel = st.selectbox("Pick receiving warehouse", options=[f"{k} - {v}" for k,v in warehouses.items()] if warehouses else ["-- none --"])
        with col3:
            po_date = st.date_input("PO Date", value=datetime.today())

        if supplier_sel == "-- Add new --":
            with st.form("add_supplier"):
                sname = st.text_input("Supplier Name")
                scontact = st.text_input("Supplier Contact")
                add_sup = st.form_submit_button("➕ Add Supplier")
                if add_sup:
                    if ensure_non_empty(sname, "Supplier Name"):
                        q = "INSERT INTO supplier (name, contact) VALUES (%s, %s)"
                        new_id = exec_query(q, (sname, scontact), commit=True, get_lastrowid=True)
                        if new_id:
                            st.success(f"Supplier created with id {new_id}. Refresh the page to use it.")

        if st.button("Create PO"):
            if supplier_sel == "-- Add new --":
                st.error("Add the supplier first (use the add supplier form).")
            else:
                try:
                    sup_id = int(str(supplier_sel).split(" - ")[0])
                    wh_id = int(str(warehouse_sel).split(" - ")[0])
                    q = "INSERT INTO purchase_order (supplier_id, warehouse_id, po_date, status) VALUES (%s,%s,%s,%s)"
                    po_id = exec_query(q, (sup_id, wh_id, po_date, "CREATED"), commit=True, get_lastrowid=True)
                    if po_id:
                        st.success(f"Purchase Order created: PO#{po_id}")
                except Exception:
                    st.error("Failed to create PO. Check warehouse/supplier selections.")

    # 2.2 Add items to PO
    st.markdown("### 2.2 Add items to PO (price fixed from item, quantity editable later)")
    po_choices = fetch_df("SELECT po_id, supplier_id, warehouse_id, po_date, status FROM purchase_order ORDER BY po_id DESC")
    if po_choices.empty:
        st.info("No Purchase Orders found. Create one first in 2.1.")
    else:
        po_map = {row["po_id"]: row for _, row in po_choices.iterrows()}
        po_option_list = ["-- select --"] + [f'{r["po_id"]} (status={r["status"]})' for _, r in po_choices.iterrows()]
        po_sel = st.selectbox("Pick PO to add lines / edit lines", options=po_option_list, key="po_select_box")

        selected_po_id = None
        if po_sel != "-- select --":
            try:
                selected_po_id = int(str(po_sel).split(" ")[0])
            except Exception:
                selected_po_id = None

        if selected_po_id is None:
            st.info("Select a PO above to add lines or edit its lines.")
        else:
            st.write("PO details:", po_map[selected_po_id])

            with st.expander("Add item to this PO (unit price is fixed from item)", expanded=False):
                items = load_choices("item", "item_id", "name", order_by="name")
                if not items:
                    st.info("No items found. Add items to the item table first.")
                else:
                    item_choice = st.selectbox("Pick item (or add new)", options=["-- Add new --"] + [f"{k} - {v}" for k,v in items.items()], key=f"po_add_item_{selected_po_id}")
                    if item_choice == "-- Add new --":
                        with st.form("add_item_form"):
                            iname = st.text_input("Item Name")
                            uom = st.text_input("UOM (e.g., pcs, kg)")
                            price = st.number_input("Price", min_value=0.0, step=0.01, format="%.2f")
                            reorder = st.number_input("Reorder level", min_value=0, step=1)
                            add_it = st.form_submit_button("➕ Add Item")
                            if add_it:
                                if ensure_non_empty(iname, "Item Name"):
                                    q = "INSERT INTO item (name, unit_of_measure, price, reorder_level) VALUES (%s,%s,%s,%s)"
                                    new_item_id = exec_query(q, (iname, uom, price, reorder), commit=True, get_lastrowid=True)
                                    if new_item_id:
                                        st.success(f"Item created with id {new_item_id}. Refresh lists to use it.")
                    else:
                        try:
                            item_id = int(str(item_choice).split(" - ")[0])
                        except Exception:
                            item_id = None
                        if item_id:
                            item_row = fetch_df("SELECT item_id, name, price FROM item WHERE item_id = %s", (item_id,))
                            price_val = float(item_row.at[0,'price']) if not item_row.empty and item_row.at[0,'price'] is not None else 0.0
                            qty = st.number_input("Quantity", min_value=1, step=1, key=f"add_po_qty_{selected_po_id}_{item_id}")
                            st.number_input("Unit Price (fixed from item)", value=price_val, format="%.2f", disabled=True, key=f"add_po_price_{selected_po_id}_{item_id}")
                            if st.button("➕ Add line to PO", key=f"add_line_btn_{selected_po_id}_{item_id}"):
                                q = "INSERT INTO purchase_order_details (po_id, item_id, quantity, price) VALUES (%s,%s,%s,%s)"
                                last = exec_query(q, (selected_po_id, item_id, qty, price_val), commit=True, get_lastrowid=True)
                                if last is not None:
                                    st.success("Line added to PO.")

            # show/edit lines
            podf = fetch_df("""
                SELECT pod.po_detail_id,
                       pod.item_id,
                       i.name AS item_name,
                       pod.quantity,
                       pod.price,
                       (pod.quantity * pod.price) AS line_total
                FROM purchase_order_details pod
                JOIN item i ON pod.item_id = i.item_id
                WHERE pod.po_id = %s
                """, (selected_po_id,))

            if podf.empty:
                st.info("This PO has no lines yet.")
            else:
                st.subheader(f"PO #{selected_po_id} lines")
                st.dataframe(podf[['po_detail_id','item_id','item_name','quantity','price','line_total']], use_container_width=True)

                st.markdown("*Edit quantity per line (unit price is fixed for PO).*")
                for _, row in podf.iterrows():
                    pid = int(row['po_detail_id'])
                    item_name = row['item_name']
                    cur_qty = int(row['quantity'])
                    cur_price = float(row['price'])
                    col1, col2, col3, col4 = st.columns([3,2,2,1])
                    with col1:
                        st.write(f"{item_name}** (line {pid})")
                    with col2:
                        new_qty = st.number_input(f"Quantity (line {pid})", min_value=0, value=cur_qty, step=1, key=f"po_qty_{pid}")
                    with col3:
                        st.number_input(f"Unit Price (fixed)", value=cur_price, format="%.2f", disabled=True, key=f"po_price_{pid}")
                    with col4:
                        if st.button("Update", key=f"update_line_{pid}"):
                            upd = exec_query("UPDATE purchase_order_details SET quantity = %s WHERE po_detail_id = %s", (new_qty, pid))
                            if upd is not None:
                                st.success(f"Updated line {pid} → qty={new_qty}")
                                try:
                                    df_total = fetch_df("SELECT fn_po_total(%s) AS po_total", (selected_po_id,))
                                    if not df_total.empty and 'po_total' in df_total.columns:
                                        po_total = float(df_total.at[0,'po_total'])
                                    else:
                                        raise Exception("fn_po_total missing or returned empty")
                                except Exception:
                                    df_tot2 = fetch_df("SELECT IFNULL(SUM(quantity * price),0) AS po_total FROM purchase_order_details WHERE po_id = %s", (selected_po_id,))
                                    po_total = float(df_tot2.at[0,'po_total']) if not df_tot2.empty else 0.0
                                st.info(f"PO #{selected_po_id} total: {po_total:.2f}")
                try:
                    df_total = fetch_df("SELECT fn_po_total(%s) AS po_total", (selected_po_id,))
                    if not df_total.empty and 'po_total' in df_total.columns:
                        po_total = float(df_total.at[0,'po_total'])
                    else:
                        raise Exception("fn_po_total missing")
                except Exception:
                    df_tot2 = fetch_df("SELECT IFNULL(SUM(quantity * price),0) AS po_total FROM purchase_order_details WHERE po_id = %s", (selected_po_id,))
                    po_total = float(df_tot2.at[0,'po_total']) if not df_tot2.empty else 0.0
                st.markdown("---")
                st.metric(label=f"PO #{selected_po_id} total", value=f"{po_total:.2f}")

    # 2.3 Receive PO
    with st.expander("2.3 Receive PO (Stock IN)", expanded=False):
        po_to_receive = fetch_df("SELECT po_id, supplier_id, warehouse_id, po_date, status FROM purchase_order WHERE status IN ('CREATED','APPROVED','PARTIAL') ORDER BY po_id DESC")
        if po_to_receive.empty:
            st.info("No PO available to receive.")
        else:
            po_map = {row["po_id"]: row for _, row in po_to_receive.iterrows()}
            po_sel2 = st.selectbox("Pick PO to receive", options=["-- select --"] + [str(r["po_id"]) for _, r in po_to_receive.iterrows()], key="po_receive_select")
            if po_sel2 != "-- select --":
                poid = int(po_sel2)
                st.write("PO details:", po_map[poid])
                employee = load_choices("employee", "emp_id", "name", order_by="name")
                emp_sel = st.selectbox("Enter receiving employee", options=["-- select employee --"] + [f"{k} - {v}" for k,v in employee.items()], key=f"receive_emp_{poid}")
                if emp_sel != "-- select employee --":
                    emp_id = int(emp_sel.split(" - ")[0])
                    if st.button("Receive this PO", key=f"receive_btn_{poid}"):
                        lines = fetch_df("SELECT item_id, quantity, price FROM purchase_order_details WHERE po_id = %s", (poid,))
                        if lines.empty:
                            st.error("PO has no lines.")
                        else:
                            conn = get_connection()
                            if not conn:
                                st.error("DB connection failed.")
                            else:
                                try:
                                    cur = conn.cursor()
                                    for _, r in lines.iterrows():
                                        item_id = r["item_id"]
                                        qty = r["quantity"]
                                        cur.execute("SELECT quantity FROM stock WHERE warehouse_id = %s AND item_id = %s", (po_map[poid]["warehouse_id"], item_id))
                                        currow = cur.fetchone()
                                        if currow:
                                            new_qty = currow[0] + qty
                                            cur.execute("UPDATE stock SET quantity = %s, last_updated = %s WHERE warehouse_id = %s AND item_id = %s", (new_qty, datetime.now(), po_map[poid]["warehouse_id"], item_id))
                                        else:
                                            cur.execute("INSERT INTO stock (warehouse_id, item_id, quantity, last_updated) VALUES (%s,%s,%s,%s)", (po_map[poid]["warehouse_id"], item_id, qty, datetime.now()))
                                        try:
                                            cur.execute(
                                                "INSERT INTO transaction_log (warehouse_id, item_id, change_type, delta_qty, ref_type, ref_id, emp_id, logged_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                                                (po_map[poid]["warehouse_id"], item_id, "IN", qty, "PO", poid, emp_id, datetime.now())
                                            )
                                        except Error:
                                            pass
                                    cur.execute("UPDATE purchase_order SET status = %s WHERE po_id = %s", ("RECEIVED", poid))
                                    conn.commit()
                                    st.success(f"PO {poid} received and stock updated.")
                                except Error as e:
                                    conn.rollback()
                                    st.error(f"Failed to receive PO: {e}")
                                    st.write(traceback.format_exc())
                                finally:
                                    cur.close()
                                    conn.close()

# ---------- SALES / SHIP PAGE ----------
def page_sales():
    st.header(" Sales / Ship (SO flow)")
    st.markdown("Create SO → Add lines (price editable) → Ship SO (stock OUT).")
    st.markdown("---")

    # 3.1 Create SO
    with st.expander("3.1 Create SO", expanded=False):
        customers = load_choices("customer", "customer_id", "name", order_by="name")
        warehouses = load_choices("warehouse", "warehouse_id", "name", order_by="name")
        col1, col2, col3 = st.columns(3)
        with col1:
            customer_sel = st.selectbox("Pick customer", options=["-- Add new --"] + [f"{k} - {v}" for k,v in customers.items()])
        with col2:
            warehouse_sel = st.selectbox("Pick warehouse to ship from", options=[f"{k} - {v}" for k,v in warehouses.items()])
        with col3:
            so_date = st.date_input("SO Date", value=datetime.today())

        if customer_sel == "-- Add new --":
            with st.form("add_customer"):
                cname = st.text_input("Customer Name")
                ccontact = st.text_input("Customer Contact")
                add_c = st.form_submit_button("➕ Add Customer")
                if add_c:
                    if ensure_non_empty(cname, "Customer Name"):
                        q = "INSERT INTO customer (name, phone) VALUES (%s, %s)"
                        new_id = exec_query(q, (cname, ccontact), commit=True, get_lastrowid=True)
                        if new_id:
                            st.success(f"Customer created with id {new_id}. Refresh the page to use it.")

        if st.button("Create SO"):
            if customer_sel == "-- Add new --":
                st.error("Add the customer first.")
            else:
                try:
                    cust_id = int(str(customer_sel).split(" - ")[0])
                    wh_id = int(str(warehouse_sel).split(" - ")[0])
                    q = "INSERT INTO sales_order (customer_id, warehouse_id, so_date, status) VALUES (%s,%s,%s,%s)"
                    so_id = exec_query(q, (cust_id, wh_id, so_date, "NEW"), commit=True, get_lastrowid=True)
                    if so_id:
                        st.success(f"Sales Order created: SO#{so_id}")
                except Exception:
                    st.error("Failed to create SO. Check customer/warehouse selections.")

    # 3.2 Add items to SO
    with st.expander("3.2 Add items to SO (price editable)", expanded=False):
        so_choices = fetch_df("SELECT so_id, customer_id, warehouse_id, so_date, status FROM sales_order ORDER BY so_id DESC")
        if so_choices.empty:
            st.info("No Sales Orders found. Create one above.")
        else:
            so_map = {row["so_id"]: row for _, row in so_choices.iterrows()}
            so_sel = st.selectbox("Pick SO to add lines", options=["-- select --"] + [f'{r["so_id"]} (status={r["status"]})' for _, r in so_choices.iterrows()], key="so_select_box")
            if so_sel != "-- select --":
                selected_so_id = int(str(so_sel).split(" ")[0])
                st.write("SO details:", so_map[selected_so_id])
                items = load_choices("item", "item_id", "name", order_by="name")
                item_choice = st.selectbox("Pick item", options=[f"{k} - {v}" for k,v in items.items()], key=f"so_item_{selected_so_id}")
                item_id = int(item_choice.split(" - ")[0])
                item_row = fetch_df("SELECT item_id, name, price FROM item WHERE item_id = %s", (item_id,))
                price_val = float(item_row.at[0,'price']) if not item_row.empty and item_row.at[0,'price'] is not None else 0.0
                qty = st.number_input("Quantity", min_value=1, step=1, key=f"so_qty_{selected_so_id}_{item_id}")
                price_input = st.number_input("Price (editable for sales)", value=price_val, format="%.2f", key=f"so_price_{selected_so_id}_{item_id}")
                if st.button("➕ Add line to SO", key=f"add_so_line_{selected_so_id}_{item_id}"):
                    q = "INSERT INTO sales_order_details (so_id, item_id, quantity, price) VALUES (%s,%s,%s,%s)"
                    last = exec_query(q, (selected_so_id, item_id, qty, price_input), commit=True, get_lastrowid=True)
                    if last is not None:
                        st.success("Line added to SO.")
                sodf = fetch_df("SELECT sod.so_detail_id, sod.item_id, i.name AS item_name, sod.quantity, sod.price FROM sales_order_details sod JOIN item i ON sod.item_id = i.item_id WHERE sod.so_id = %s", (selected_so_id,))
                if not sodf.empty:
                    st.dataframe(sodf, use_container_width=True)

    # 3.3 Ship / Dispatch (Stock OUT)
    with st.expander("3.3 Ship / Dispatch (Stock OUT)", expanded=False):
        so_to_ship = fetch_df("SELECT so_id, customer_id, warehouse_id, so_date, status FROM sales_order WHERE status IN ('NEW','CONFIRMED') ORDER BY so_id DESC")
        if so_to_ship.empty:
            st.info("No Sales Orders ready to ship.")
        else:
            so_sel2 = st.selectbox("Pick SO to ship", options=["-- select --"] + [str(r["so_id"]) for _, r in so_to_ship.iterrows()], key="so_ship_select")
            if so_sel2 != "-- select --":
                soid = int(so_sel2)
                emp_map = load_choices("employee", "emp_id", "name", order_by="name")
                emp_sel = st.selectbox("Enter shipping employee", options=["-- select employee --"] + [f"{k} - {v}" for k,v in emp_map.items()], key=f"ship_emp_{soid}")
                check_stock = st.checkbox("Check stock before ship", value=True, key=f"check_stock_{soid}")
                if emp_sel != "-- select employee --":
                    emp_id = int(emp_sel.split(" - ")[0])
                    if st.button("Ship this SO", key=f"ship_btn_{soid}"):

                        lines = fetch_df("SELECT item_id, quantity FROM sales_order_details WHERE so_id = %s", (soid,))
                        if lines.empty:
                            st.error("SO has no lines.")
                        else:
                            conn = get_connection()
                            if not conn:
                                st.error("DB connection failed.")
                            else:
                                try:
                                    cur = conn.cursor()
                                    so_row = so_to_ship[so_to_ship["so_id"] == soid].iloc[0]
                                    whid = int(so_row["warehouse_id"])
                                    if check_stock:
                                        for _, r in lines.iterrows():
                                            item_id = int(r["item_id"])
                                            qty = int(r["quantity"])
                                            cur.execute("SELECT quantity FROM stock WHERE warehouse_id = %s AND item_id = %s", (whid, item_id))
                                            row = cur.fetchone()
                                            available = int(row[0]) if row else 0
                                            if available < qty:
                                                st.error(f"Insufficient stock for item {item_id}. Available {available}, requested {qty}. Aborting.")
                                                cur.close()
                                                conn.close()
                                                return
                                    for _, r in lines.iterrows():
                                        item_id = int(r["item_id"])
                                        qty = int(r["quantity"])
                                        cur.execute("SELECT quantity FROM stock WHERE warehouse_id = %s AND item_id = %s", (whid, item_id))
                                        row = cur.fetchone()
                                        if row:
                                            new_qty = int(row[0]) - qty
                                            cur.execute("UPDATE stock SET quantity = %s, last_updated = %s WHERE warehouse_id = %s AND item_id = %s",
                                                        (new_qty, datetime.now(), whid, item_id))
                                        else:
                                            st.warning(f"No stock row for item {item_id} in warehouse {whid}. Skipping update.")
                                        try:
                                            cur.execute(
                                                "INSERT INTO transaction_log (warehouse_id, item_id, change_type, delta_qty, ref_type, ref_id, emp_id, logged_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                                                (whid, item_id, "OUT", qty, "SO", soid, emp_id, datetime.now())
                                            )
                                        except Error:
                                            pass
                                    cur.execute("UPDATE sales_order SET status = %s WHERE so_id = %s", ("SHIPPED", soid))
                                    conn.commit()
                                    st.success(f"SO {soid} shipped and stock updated.")
                                except Error as e:
                                    conn.rollback()
                                    st.error(f"Failed to ship SO: {e}")
                                    st.write(traceback.format_exc())
                                finally:
                                    cur.close()
                                    conn.close()

# ---------- ADJUST / RETURN PAGE ----------
def page_adjust_return():
    st.header(" Adjustments & Returns")
    st.markdown("Manual adjustments or processing returns.")
    st.markdown("---")

    warehouses = load_choices("warehouse", "warehouse_id", "name", order_by="name")
    items = load_choices("item", "item_id", "name", order_by="name")
    emp_map = load_choices("employee", "emp_id", "name", order_by="name")

    with st.expander("4.1 Manual Stock Adjustment", expanded=False):
        col1, col2, col3 = st.columns(3)
        with col1:
            wh = st.selectbox("Warehouse", options=[f"{k} - {v}" for k,v in warehouses.items()], key="adj_wh")
        with col2:
            it = st.selectbox("Item", options=[f"{k} - {v}" for k,v in items.items()], key="adj_item")
        with col3:
            qty = st.number_input("Quantity (+ to add, - to remove)", value=0, step=1, key="adj_qty")
        emp = st.selectbox("Employee", options=["-- select --"] + [f"{k} - {v}" for k,v in emp_map.items()], key="adj_emp")
        if st.button("Apply Adjustment"):
            if wh and it and emp:
                whid = int(wh.split(" - ")[0])
                itemid = int(it.split(" - ")[0])
                empid = int(emp.split(" - ")[0])
                conn = get_connection()
                if not conn:
                    st.error("DB connection failed.")
                else:
                    try:
                        cur = conn.cursor()
                        cur.execute("SELECT quantity FROM stock WHERE warehouse_id = %s AND item_id = %s", (whid, itemid))
                        row = cur.fetchone()
                        if row:
                            new_qty = int(row[0]) + int(qty)
                            cur.execute("UPDATE stock SET quantity = %s, last_updated = %s WHERE warehouse_id = %s AND item_id = %s", (new_qty, datetime.now(), whid, itemid))
                        else:
                            cur.execute("INSERT INTO stock (warehouse_id, item_id, quantity, last_updated) VALUES (%s,%s,%s,%s)", (whid, itemid, qty, datetime.now()))
                        try:
                            cur.execute("INSERT INTO transaction_log (warehouse_id, item_id, change_type, delta_qty, ref_type, ref_id, emp_id, logged_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                                        (whid, itemid, "ADJUST", qty, "MANUAL", None, empid, datetime.now()))
                        except Error:
                            pass
                        conn.commit()
                        st.success("Stock adjusted.")
                    except Error as e:
                        conn.rollback()
                        st.error(f"Adjustment failed: {e}")
                        st.write(traceback.format_exc())
                    finally:
                        cur.close()
                        conn.close()
            else:
                st.error("Please pick warehouse, item and employee.")

    with st.expander("4.2 Returns", expanded=False):
        return_type = st.radio("Return type", ["Customer return (stock IN)", "Return to supplier (stock OUT)"], key="return_type")
        wh2 = st.selectbox("Warehouse", options=[f"{k} - {v}" for k,v in warehouses.items()], key="ret_wh")
        it2 = st.selectbox("Item", options=[f"{k} - {v}" for k,v in items.items()], key="ret_item")
        qty2 = st.number_input("Quantity", min_value=1, step=1, key="ret_qty")
        if st.button("Process return"):
            whid = int(wh2.split(" - ")[0])
            itemid = int(it2.split(" - ")[0])
            conn = get_connection()
            if not conn:
                st.error("DB connection failed.")
            else:
                try:
                    cur = conn.cursor()
                    if return_type.startswith("Customer"):
                        cur.execute("SELECT quantity FROM stock WHERE warehouse_id = %s AND item_id = %s", (whid, itemid))
                        row = cur.fetchone()
                        if row:
                            new_qty = int(row[0]) + int(qty2)
                            cur.execute("UPDATE stock SET quantity = %s, last_updated = %s WHERE warehouse_id = %s AND item_id = %s", (new_qty, datetime.now(), whid, itemid))
                        else:
                            cur.execute("INSERT INTO stock (warehouse_id, item_id, quantity, last_updated) VALUES (%s,%s,%s,%s)", (whid, itemid, qty2, datetime.now()))
                        try:
                            cur.execute("INSERT INTO transaction_log (warehouse_id, item_id, change_type, delta_qty, ref_type, ref_id, emp_id, logged_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                                        (whid, itemid, "IN", qty2, "RETURN_CUST", None, None, datetime.now()))
                        except Error:
                            pass
                        conn.commit()
                        st.success("Customer return processed (stock IN).")
                    else:
                        cur.execute("SELECT quantity FROM stock WHERE warehouse_id = %s AND item_id = %s", (whid, itemid))
                        row = cur.fetchone()
                        if row:
                            new_qty = int(row[0]) - int(qty2)
                            cur.execute("UPDATE stock SET quantity = %s, last_updated = %s WHERE warehouse_id = %s AND item_id = %s", (new_qty, datetime.now(), whid, itemid))
                        else:
                            st.warning("No stock row found; negative stock not created.")
                        try:
                            cur.execute("INSERT INTO transaction_log (warehouse_id, item_id, change_type, delta_qty, ref_type, ref_id, emp_id, logged_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                                        (whid, itemid, "OUT", qty2, "RETURN_SUPP", None, None, datetime.now()))
                        except Error:
                            pass
                        conn.commit()
                        st.success("Return to supplier processed (stock OUT).")
                except Error as e:
                    conn.rollback()
                    st.error(f"Return failed: {e}")
                    st.write(traceback.format_exc())
                finally:
                    cur.close()
                    conn.close()

# ---------- EMPLOYEES PAGE ----------
def page_employees():
    st.header(" Employees")
    st.markdown("View, add, or delete employees. Employee contact must be a valid Gmail address.")
    st.markdown("---")

    df = fetch_df("SELECT emp_id, name, role, contact, warehouse_id FROM employee ORDER BY emp_id")
    if df.empty:
        st.info("No employees found.")
    else:
        try:
            wh = fetch_df("SELECT warehouse_id, name FROM warehouse")
            if not wh.empty:
                df = df.merge(wh, how="left", left_on="warehouse_id", right_on="warehouse_id")
                df = df.rename(columns={"name":"warehouse_name"})
        except Exception:
            pass
        st.dataframe(df, use_container_width=True)

    st.markdown("### Add employee")
    with st.form("add_employee"):
        ename = st.text_input("Name")
        erole_label = st.selectbox(
            "Role",
            options=["Warehouse Manager", "Receiver", "Picker", "Admin", "Clerk", "Auditor", "Supervisor"]
        )
        econtact = st.text_input("Contact (Gmail only, e.g. user@gmail.com)")
        warehouses = load_choices("warehouse", "warehouse_id", "name", order_by="name")
        ewh = st.selectbox("Warehouse (optional)", options=["-- none --"] + [f"{k} - {v}" for k,v in warehouses.items()])
        add_b = st.form_submit_button("➕ Add employee")
        if add_b:
            if ensure_non_empty(ename, "Name") and ensure_non_empty(econtact, "Contact"):
                if not is_valid_gmail(econtact):
                    st.error("Contact must be a valid Gmail address (example: user@gmail.com).")
                else:
                    erole = ROLE_MAP.get(erole_label, "staff")
                    wid = None
                    if ewh != "-- none --":
                        wid = int(ewh.split(" - ")[0])
                    q = "INSERT INTO employee (name, role, contact, warehouse_id) VALUES (%s,%s,%s,%s)"
                    last = exec_query(q, (ename, erole, econtact, wid), commit=True, get_lastrowid=True)
                    if last:
                        st.success(f"Employee added (id {last}). Refresh the page to see them listed.")

    st.markdown("### Delete employee")
    emp_map = load_choices("employee", "emp_id", "name", order_by="name")
    emp_sel = st.selectbox("Pick employee to delete", options=["-- select --"] + [f"{k} - {v}" for k,v in emp_map.items()])
    if emp_sel != "-- select --":
        empid = int(emp_sel.split(" - ")[0])
        if st.button(" Delete employee"):
            exec_query("DELETE FROM employee WHERE emp_id = %s", (empid,))
            st.success("Employee deleted.")

# ---------- REPORTS PAGE ----------
def page_reports():
    st.header(" Reports")
    st.markdown("Enter month (YYYY-MM) to compute basic P&L and list POs/SOs.")
    st.markdown("---")
    month = st.text_input("Enter month (YYYY-MM)", value=datetime.today().strftime("%Y-%m"), key="report_month")
    if st.button("Generate report"):
        try:
            start = datetime.strptime(month + "-01", "%Y-%m-%d")
            if start.month == 12:
                end = datetime(start.year + 1, 1, 1)
            else:
                end = datetime(start.year, start.month + 1, 1)
            purchases_q = """
            SELECT po.po_id, pod.item_id, pod.quantity, pod.price, pod.quantity * pod.price AS line_total
            FROM purchase_order po
            JOIN purchase_order_details pod ON po.po_id = pod.po_id
            WHERE po.po_date >= %s AND po.po_date < %s
            """
            pur_lines = fetch_df(purchases_q, (start, end))
            total_purchases = float(pur_lines["line_total"].sum()) if not pur_lines.empty else 0.0

            sales_q = """
            SELECT so.so_id, sod.item_id, sod.quantity, sod.price, sod.quantity * sod.price AS line_total
            FROM sales_order so
            JOIN sales_order_details sod ON so.so_id = sod.so_id
            WHERE so.so_date >= %s AND so.so_date < %s
            """
            sales_lines = fetch_df(sales_q, (start, end))
            total_sales = float(sales_lines["line_total"].sum()) if not sales_lines.empty else 0.0

            salaries = 0.0
            profit_loss = total_sales - total_purchases - salaries

            st.metric("Total purchases", f"{total_purchases:.2f}")
            st.metric("Total sales", f"{total_sales:.2f}")
            st.metric("Profit/Loss", f"{profit_loss:.2f}")

            st.subheader("Purchase Orders")
            po_df = fetch_df("SELECT po_id, supplier_id, warehouse_id, po_date, status FROM purchase_order WHERE po_date >= %s AND po_date < %s", (start, end))
            if po_df.empty:
                st.write("No POs in this month.")
            else:
                st.dataframe(po_df, use_container_width=True)
            st.subheader("Sales Orders")
            so_df = fetch_df("SELECT so_id, customer_id, warehouse_id, so_date, status FROM sales_order WHERE so_date >= %s AND so_date < %s", (start, end))
            if so_df.empty:
                st.write("No SOs in this month.")
            else:
                st.dataframe(so_df, use_container_width=True)
        except Exception as e:
            st.error(f"Failed to generate report: {e}")
            st.write(traceback.format_exc())

# ---------- MAIN NAV ----------
def main():
    st.title(" Inventory & Warehouse Management")

    # If not logged-in, show only the login page (first page is login)
    if not st.session_state.get("user"):
        logged_in_now = show_login_page()
        if not logged_in_now:
            # Stop further rendering - the login page is the only thing visible
            return

    # From here onwards, user is logged in
    show_sidebar_user_widget()

    # determine menu items based on login (fallback to limited preview)
    if st.session_state.get("user") and st.session_state["user"].get("menu"):
        # proc delivered explicit menu items
        menu_options = st.session_state["user"]["menu"]
    else:
        # no proc or no menu — try to infer role-based menus
        role = st.session_state.get("user", {}).get("role")
        if role == "admin":
            menu_options = ["Stock", "Purchase", "Sales", "Adjust/Return", "Employees", "Reports", "Raw SQL (admin)"]
        elif role == "worker":
            menu_options = ["Stock", "Reports"]
        else:
            menu_options = ["Stock"]

    # Sidebar navigation
    menu = st.sidebar.radio("Go to", menu_options)

    try:
        # enforce role checks before page execution
        if menu == "Stock":
            page_stock()
        elif menu == "Purchase":
            if not require_role(["admin"]): return
            page_purchase()
        elif menu == "Sales":
            if not require_role(["admin"]): return
            page_sales()
        elif menu == "Adjust/Return":
            if not require_role(["admin"]): return
            page_adjust_return()
        elif menu == "Employees":
            if not require_role(["admin"]): return
            page_employees()
        elif menu == "Reports":
            if not require_role(["admin","worker"]): return
            page_reports()
        elif menu == "Raw SQL (admin)":
            if not require_role(["admin"]): return
            st.header(" Admin — run SELECT queries (read-only)")
            q = st.text_area("Enter a SELECT query", height=150, value="SELECT * FROM item LIMIT 50;")
            if st.button("Run (read-only)"):
                if q.strip().lower().startswith("select"):
                    df = fetch_df(q)
                    if not df.empty:
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.write("No results.")
                else:
                    st.error("Only SELECT queries are allowed in this admin area.")
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        st.write(traceback.format_exc())

if __name__ == "__main__":
    main()'''



























# app.py
import streamlit as st
import pandas as pd
import mysql.connector
from mysql.connector import Error
from config import DB_CONFIG
from datetime import datetime
import re
import traceback
import time

# ---------- PAGE CONFIG ----------
st.set_page_config(
    page_title=" Inventory & Warehouse Management",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------- ROLE MAP (UI -> DB ENUM) ----------
# DB enum is: ENUM('manager','staff','picker','packer','driver','admin')
ROLE_MAP = {
    "Warehouse Manager": "manager",
    "Receiver": "staff",
    "Picker": "picker",
    "Admin": "admin",
    "Clerk": "staff",
    "Auditor": "staff",
    "Supervisor": "staff",
    # fallback for anything else:
}

# ---------- LIGHT THEME / UI (original CSS included verbatim) ----------
st.markdown("""
    <style>
    :root {
        --primary-color: #2E86AB;
        --secondary-color: #A23B72;
        --success-color: #06A77D;
        --warning-color: #F18F01;
        --danger-color: #C73E1D;
        --background-light: #F3F6F9;
        --text-dark: #1f2d3a;
    }

    /* Lighter sidebar */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #e9f3fb 0%, #d0e4f5 100%);
        border-right: 1px solid rgba(0,0,0,0.04);
    }
    [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
        color: #1f2d3a !important;
        font-weight: 500;
    }
    [data-testid="stSidebar"] .stRadio > label {
        color: #1f2d3a !important;
        font-weight: 600;
        font-size: 1.05rem;
    }
    [data-testid="stSidebar"] .stRadio [role="radiogroup"] label {
        background-color: rgba(255,255,255,0.55);
        padding: 10px 14px;
        border-radius: 8px;
        margin: 4px 0;
        transition: all 0.25s ease;
        color: #1f2d3a !important;
    }
    [data-testid="stSidebar"] .stRadio [role="radiogroup"] label:hover {
        background-color: rgba(255,255,255,0.8);
        transform: translateX(2px);
    }

    /* Very light app background */
    [data-testid="stAppViewContainer"] {
        background: #f7f9fb;
    }
    .main { background: #f7f9fb; }

    /* Card-like look */
    [data-testid="stExpander"],
    [data-testid="stDataFrame"],
    .stForm,
    .stAlert {
        background: #ffffff !important;
        border-radius: 10px;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.03);
    }

    /* Headers */
    h1 {
        color: #215f7c !important;
        font-weight: 700 !important;
        padding-bottom: 10px;
        border-bottom: 3px solid rgba(33,95,124,0.18);
        margin-bottom: 18px !important;
    }
    h2 { color: #2E86AB !important; font-weight: 600 !important; }
    h3 { color: #A23B72 !important; font-weight: 600 !important; }

    /* Buttons */
    .stButton>button {
        background: linear-gradient(135deg, #2E86AB 0%, #1a4d6b 100%);
        color: white; border: none; border-radius: 8px;
        padding: 10px 24px; font-weight: 600; transition: all 0.3s ease;
        box-shadow: 0 2px 4px rgba(0,0,0,0.08);
    }
    .stButton>button:hover { filter: brightness(1.02); transform: translateY(-1px); }

    /* Form submit buttons */
    .stFormSubmitButton>button {
        background: linear-gradient(135deg, #06A77D 0%, #048060 100%);
        color: white; border: none; border-radius: 8px; padding: 10px 24px; font-weight: 600;
    }
    .stFormSubmitButton>button:hover {
        background: linear-gradient(135deg, #048060 0%, #06A77D 100%);
        box-shadow: 0 4px 8px rgba(0,0,0,0.08);
    }

    /* Inputs */
    .stTextInput>div>div>input,
    .stNumberInput>div>div>input,
    .stSelectbox>div>div>select {
        border-radius: 8px; border: 2px solid #e0e0e0; padding: 8px 12px; transition: all 0.3s ease;
    }
    .stTextInput>div>div>input:focus,
    .stNumberInput>div>div>input:focus {
        border-color: #2E86AB; box-shadow: 0 0 0 2px rgba(46,134,171,0.08);
    }

    /* Metrics */
    [data-testid="stMetricValue"] { font-size: 2rem !important; color: #2E86AB !important; font-weight: 700 !important; }
    [data-testid="stMetricLabel"] { color: #5A6C7D !important; font-weight: 600 !important; }

    /* Alerts */
    .stSuccess { background-color: #d4edda; border-left: 4px solid #06A77D !important; color: #155724; }
    .stError   { background-color: #f8d7da; border-left: 4px solid #C73E1D !important; color: #721c24; }
    .stWarning { background-color: #fff3cd; border-left: 4px solid #F18F01 !important; color: #856404; }
    .stInfo    { background-color: #d1ecf1; border-left: 4px solid #2E86AB !important; color: #0c5460; }

    /* Divider */
    hr { border: none; height: 2px; background: linear-gradient(90deg, transparent 0%, #2E86AB 50%, transparent 100%); margin: 20px 0; }

    /* Tiny DB feature notes */
    .dbnote {
        font-size: 0.78rem;
        color: #6b7280;
        margin-top: 6px;
        margin-bottom: -4px;
    }
    </style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* remove card-like boxes from sidebar radio options */
[data-testid="stSidebar"] .stRadio [role="radiogroup"] label {
    background: transparent !important;
    padding: 4px 0 !important;
    border-radius: 0 !important;
    box-shadow: none !important;
    margin: 2px 0 !important;
}
</style>
""", unsafe_allow_html=True)

# ---------- SAFE RERUN UTIL ----------
def safe_rerun():
    """Robust rerun across Streamlit versions."""
    try:
        if hasattr(st, "experimental_rerun"):
            try:
                st.experimental_rerun()
                return
            except Exception:
                pass
    except Exception:
        pass
    try:
        params = dict(st.query_params) if st.query_params is not None else {}
        params["_refresh"] = [str(time.time())]
        st.query_params = params
        return
    except Exception:
        pass
    st.session_state["_refresh_toggle"] = not st.session_state.get("_refresh_toggle", False)
    st.stop()

# ---------- DB HELPERS ----------
def get_connection():
    try:
        cfg = DB_CONFIG.copy()
        if "port" in cfg and isinstance(cfg["port"], str):
            try:
                cfg["port"] = int(cfg["port"])
            except Exception:
                pass
        conn = mysql.connector.connect(**cfg)
        if conn.is_connected():
            return conn
    except Error as e:
        st.error(f"Database connection failed: {e}")
        st.write(traceback.format_exc())
        return None

def fetch_df(query, params=None):
    conn = get_connection()
    if not conn:
        return pd.DataFrame()
    try:
        cur = conn.cursor(dictionary=True)
        cur.execute(query, params or ())
        rows = cur.fetchall()
        df = pd.DataFrame(rows)
        cur.close()
        return df
    except Error as e:
        st.error(f"Query failed: {e}")
        return pd.DataFrame()
    finally:
        conn.close()

def exec_query(query, params=None, commit=True, get_lastrowid=False):
    conn = get_connection()
    if not conn:
        return None
    try:
        cur = conn.cursor()
        cur.execute(query, params or ())
        if commit:
            conn.commit()
        lastrowid = cur.lastrowid if get_lastrowid else None
        cur.close()
        return lastrowid
    except Error as e:
        st.error(f"DB operation failed: {e}")
        st.write(traceback.format_exc())
        return None
    finally:
        conn.close()

# ---------- AUTH (SQL-only) HELPERS ----------
def authenticate_user_sql(username: str, password: str):
    """
    Uses stored proc (preferred) or scalar function for auth.
    Returns {'username','role','user_id','menu'} or None.
    """
    if not username or not password:
        return None
    try:
        # PROCEDURE: sp_get_menu_for_user(username,password)  (JOINs internally)
        df_menu = fetch_df("CALL sp_get_menu_for_user(%s,%s)", (username, password))
        if df_menu.shape[0] == 1 and 'status' in df_menu.columns and str(df_menu.at[0,'status']) == 'AUTH_FAILED':
            return None
        role_df = fetch_df(
            "SELECT user_id, role FROM app_user WHERE username = %s AND password_hash = SHA2(%s,256)",
            (username, password)
        )
        if role_df.empty:
            return None
        role = role_df.at[0, 'role']
        user_id = int(role_df.at[0, 'user_id'])
        menu = df_menu['menu_item'].tolist() if 'menu_item' in df_menu.columns else []
        return {"username": username, "role": role, "user_id": user_id, "menu": menu}
    except Exception:
        # FUNCTION fallback: fn_auth_role(username,password)
        try:
            role_df = fetch_df("SELECT fn_auth_role(%s,%s) AS role", (username, password))
            if role_df.empty or role_df.at[0,'role'] is None:
                return None
            role = role_df.at[0,'role']
            user_df = fetch_df("SELECT user_id FROM app_user WHERE username = %s", (username,))
            user_id = int(user_df.at[0,'user_id']) if not user_df.empty else None
            menu_df = fetch_df("SELECT menu_item FROM role_menu WHERE role = %s ORDER BY sort_order", (role,))
            menu = menu_df['menu_item'].tolist() if not menu_df.empty else []
            return {"username": username, "role": role, "user_id": user_id, "menu": menu}
        except Exception:
            return None

# ---------- LOGIN / SIDEBAR WIDGETS ----------
def show_login_page():
    st.markdown("<div style='max-width:760px;margin:0 auto'>", unsafe_allow_html=True)
    st.header("Sign in")
    st.write("Please sign in with your username and password to continue.")
    with st.form("login_form_main", clear_on_submit=False):
        username = st.text_input("Username", value="", key="login_username_main")
        password = st.text_input("Password", value="", type="password", key="login_password_main")
        submitted = st.form_submit_button("Sign in")
        if submitted:
            auth = authenticate_user_sql(username.strip(), password)
            if auth:
                st.session_state["user"] = {
                    "username": auth["username"],
                    "role": auth["role"],
                    "user_id": auth["user_id"],
                    "menu": auth.get("menu", [])
                }
                st.success("Login successful. Redirecting...")
                # DB NOTE
                st.markdown(
                    "<div class='dbnote'>Uses <b>PROCEDURE</b> <code>sp_get_menu_for_user</code> or "
                    "<b>FUNCTION</b> <code>fn_auth_role</code> for authentication/authorization.</div>",
                    unsafe_allow_html=True
                )
                safe_rerun()
            else:
                st.error("Invalid credentials.")
    st.markdown("</div>", unsafe_allow_html=True)
    return st.session_state.get("user") is not None

def show_sidebar_user_widget():
    st.sidebar.markdown("### Account")
    u = st.session_state.get("user")
    if u:
        st.sidebar.success(f"{u.get('username')} ({u.get('role')})")
        if st.sidebar.button("Logout"):
            st.session_state.pop("user", None)
            safe_rerun()

# ---------- REQUIRE ROLE ----------
def require_role(allowed_roles):
    us = st.session_state.get("user")
    if not us:
        st.error("Please log in to access this page (use the sidebar).")
        return False
    if us.get("role") not in allowed_roles:
        st.error("You are not authorized to access this page.")
        return False
    return True

# ---------- UTIL ----------
def load_choices(table, key_col, label_col=None, where=None, order_by=None):
    q = f"SELECT {key_col}" + (f", {label_col}" if label_col else "") + f" FROM {table}"
    if where:
        q += " WHERE " + where
    if order_by:
        q += " ORDER BY " + order_by
    df = fetch_df(q)
    if df.empty:
        return {}
    if label_col:
        return {row[key_col]: row[label_col] for _, row in df.iterrows()}
    else:
        return {row[key_col]: str(row[key_col]) for _, row in df.iterrows()}

def ensure_non_empty(text, field_name):
    if not text or (isinstance(text, str) and not text.strip()):
        st.error(f"{field_name} cannot be empty.")
        return False
    return True

def is_valid_gmail(email: str) -> bool:
    if not email or not isinstance(email, str):
        return False
    pattern = r"^[a-zA-Z0-9._%+-]+@gmail\.com$"
    return re.match(pattern, email.strip()) is not None

# ---------- STOCK PAGE ----------
def page_stock():
    st.header(" Stock ")
    st.markdown("")

    warehouses = load_choices("warehouse", "warehouse_id", "name", order_by="name")
    if not warehouses:
        st.info("No warehouses found. Make sure warehouse table exists.")
    wh_choice = st.selectbox("Select warehouse", options=["All"] + [f"{k} - {v}" for k,v in warehouses.items()])

    # JOINs are used below (stock→item, left join warehouse)
    st.markdown(
        "<div class='dbnote'>Uses <b>JOIN</b>: <code>stock s</code> "
        "<b>JOIN</b> <code>item i</code> and <b>LEFT JOIN</b> <code>warehouse w</code>.</div>",
        unsafe_allow_html=True
    )

    if wh_choice == "All":
        q = """
        SELECT s.warehouse_id, w.name as warehouse_name,
               i.item_id, i.name as item_name, s.quantity, i.unit_of_measure, i.price, i.reorder_level
        FROM stock s
        JOIN item i ON s.item_id = i.item_id
        LEFT JOIN warehouse w ON s.warehouse_id = w.warehouse_id
        """
        params = ()
    else:
        try:
            wid = int(str(wh_choice).split(" - ")[0])
        except Exception:
            wid = None
        q = """
        SELECT s.warehouse_id, w.name as warehouse_name,
               i.item_id, i.name as item_name, s.quantity, i.unit_of_measure, i.price, i.reorder_level
        FROM stock s
        JOIN item i ON s.item_id = i.item_id
        LEFT JOIN warehouse w ON s.warehouse_id = w.warehouse_id
        WHERE s.warehouse_id = %s
        """
        params = (wid,)
    df = fetch_df(q, params)
    if df.empty:
        st.info("No stock records found.")
    else:
        df["status"] = df.apply(
            lambda r: "LOW" if (r.get("quantity") is not None and r.get("reorder_level") is not None and r["quantity"] < r["reorder_level"]) else "OK",
            axis=1
        )
        st.subheader("Inventory")
        st.dataframe(df[["warehouse_id","warehouse_name","item_id","item_name","quantity","unit_of_measure","price","reorder_level","status"]], use_container_width=True)

        st.subheader("Low-stock items (across all warehouses)")
        # NESTED SUBQUERY example (equivalent to status=LOW)
        low_nested = fetch_df("""
            SELECT s.warehouse_id, w.name AS warehouse_name, s.item_id, i.name AS item_name, s.quantity,
                   (SELECT reorder_level FROM item WHERE item_id = s.item_id) AS reorder_level
            FROM stock s
            LEFT JOIN warehouse w ON s.warehouse_id = w.warehouse_id
            JOIN item i ON i.item_id = s.item_id
            WHERE s.quantity < (SELECT reorder_level FROM item WHERE item_id = s.item_id);
        """)
        st.markdown(
            "<div class='dbnote'>Uses <b>Nested Subquery</b> to compute "
            "<i>items below reorder level</i>.</div>",
            unsafe_allow_html=True
        )
        if low_nested.empty:
            st.success("No low-stock items ")
        else:
            st.dataframe(low_nested[["warehouse_id","warehouse_name","item_id","item_name","quantity","reorder_level"]], use_container_width=True)

# ---------- PURCHASE / RECEIVE PAGE ----------
def page_purchase():
    st.header(" Purchase Orders")
    st.markdown("")

    # 2.1 Create PO
    with st.expander("2.1 Create PO", expanded=True):
        suppliers = load_choices("supplier", "supplier_id", "name", order_by="name")
        warehouses = load_choices("warehouse", "warehouse_id", "name", order_by="name")
        col1, col2, col3 = st.columns(3)
        with col1:
            supplier_sel = st.selectbox("Pick supplier", options=["-- Add new --"] + [f"{k} - {v}" for k,v in suppliers.items()])
        with col2:
            warehouse_sel = st.selectbox("Pick receiving warehouse", options=[f"{k} - {v}" for k,v in warehouses.items()] if warehouses else ["-- none --"])
        with col3:
            po_date = st.date_input("PO Date", value=datetime.today())

        if supplier_sel == "-- Add new --":
            with st.form("add_supplier"):
                sname = st.text_input("Supplier Name")
                scontact = st.text_input("Supplier Contact")
                add_sup = st.form_submit_button("➕ Add Supplier")
                if add_sup:
                    if ensure_non_empty(sname, "Supplier Name"):
                        q = "INSERT INTO supplier (name, contact) VALUES (%s, %s)"
                        new_id = exec_query(q, (sname, scontact), commit=True, get_lastrowid=True)
                        if new_id:
                            st.success(f"Supplier created with id {new_id}. Refresh the page to use it.")

        if st.button("Create PO"):
            if supplier_sel == "-- Add new --":
                st.error("Add the supplier first (use the add supplier form).")
            else:
                try:
                    sup_id = int(str(supplier_sel).split(" - ")[0])
                    wh_id = int(str(warehouse_sel).split(" - ")[0])
                    q = "INSERT INTO purchase_order (supplier_id, warehouse_id, po_date, status) VALUES (%s,%s,%s,%s)"
                    po_id = exec_query(q, (sup_id, wh_id, po_date, "CREATED"), commit=True, get_lastrowid=True)
                    if po_id:
                        st.success(f"Purchase Order created: PO#{po_id}")
                        st.markdown("<div class='dbnote'>PO header insert; "
                                    "line items (next step) use <b>JOIN</b> to show item names.</div>", unsafe_allow_html=True)
                except Exception:
                    st.error("Failed to create PO. Check warehouse/supplier selections.")

    # 2.2 Add items to PO
    st.markdown("### 2.2 Add items to PO (price fixed from item, quantity editable later)")
    po_choices = fetch_df("SELECT po_id, supplier_id, warehouse_id, po_date, status FROM purchase_order ORDER BY po_id DESC")
    if po_choices.empty:
        st.info("No Purchase Orders found. Create one first in 2.1.")
    else:
        po_map = {row["po_id"]: row for _, row in po_choices.iterrows()}
        po_option_list = ["-- select --"] + [f'{r["po_id"]} (status={r["status"]})' for _, r in po_choices.iterrows()]
        po_sel = st.selectbox("Pick PO to add lines / edit lines", options=po_option_list, key="po_select_box")

        selected_po_id = None
        if po_sel != "-- select --":
            try:
                selected_po_id = int(str(po_sel).split(" ")[0])
            except Exception:
                selected_po_id = None

        if selected_po_id is None:
            st.info("Select a PO above to add lines or edit its lines.")
        else:
            st.write("PO details:", po_map[selected_po_id])

            with st.expander("Add item to this PO (unit price is fixed from item)", expanded=False):
                items = load_choices("item", "item_id", "name", order_by="name")
                if not items:
                    st.info("No items found. Add items to the item table first.")
                else:
                    item_choice = st.selectbox("Pick item (or add new)", options=["-- Add new --"] + [f"{k} - {v}" for k,v in items.items()], key=f"po_add_item_{selected_po_id}")
                    if item_choice == "-- Add new --":
                        with st.form("add_item_form"):
                            iname = st.text_input("Item Name")
                            uom = st.text_input("UOM (e.g., pcs, kg)")
                            price = st.number_input("Price", min_value=0.0, step=0.01, format="%.2f")
                            reorder = st.number_input("Reorder level", min_value=0, step=1)
                            add_it = st.form_submit_button("➕ Add Item")
                            if add_it:
                                if ensure_non_empty(iname, "Item Name"):
                                    q = "INSERT INTO item (name, unit_of_measure, price, reorder_level) VALUES (%s,%s,%s,%s)"
                                    new_item_id = exec_query(q, (iname, uom, price, reorder), commit=True, get_lastrowid=True)
                                    if new_item_id:
                                        st.success(f"Item created with id {new_item_id}. Refresh lists to use it.")
                    else:
                        try:
                            item_id = int(str(item_choice).split(" - ")[0])
                        except Exception:
                            item_id = None
                        if item_id:
                            item_row = fetch_df("SELECT item_id, name, price FROM item WHERE item_id = %s", (item_id,))
                            price_val = float(item_row.at[0,'price']) if not item_row.empty and item_row.at[0,'price'] is not None else 0.0
                            qty = st.number_input("Quantity", min_value=1, step=1, key=f"add_po_qty_{selected_po_id}_{item_id}")
                            st.number_input("Unit Price (fixed from item)", value=price_val, format="%.2f", disabled=True, key=f"add_po_price_{selected_po_id}_{item_id}")
                            if st.button("➕ Add line to PO", key=f"add_line_btn_{selected_po_id}_{item_id}"):
                                q = "INSERT INTO purchase_order_details (po_id, item_id, quantity, price) VALUES (%s,%s,%s,%s)"
                                last = exec_query(q, (selected_po_id, item_id, qty, price_val), commit=True, get_lastrowid=True)
                                if last is not None:
                                    st.success("Line added to PO.")
                                    st.markdown("<div class='dbnote'>Detail insert uses <b>FOREIGN KEYS</b>. "
                                                "PO total later uses <b>FUNCTION</b> <code>fn_po_total()</code> and <b>AGGREGATE</b> <code>SUM</code>.</div>", unsafe_allow_html=True)

            # show/edit lines (JOIN to show item names)
            podf = fetch_df("""
                SELECT pod.po_detail_id,
                       pod.item_id,
                       i.name AS item_name,
                       pod.quantity,
                       pod.price,
                       (pod.quantity * pod.price) AS line_total
                FROM purchase_order_details pod
                JOIN item i ON pod.item_id = i.item_id
                WHERE pod.po_id = %s
                """, (selected_po_id,))
            st.markdown("<div class='dbnote'>Uses <b>JOIN</b> to display item names for PO lines.</div>", unsafe_allow_html=True)

            if podf.empty:
                st.info("This PO has no lines yet.")
            else:
                st.subheader(f"PO #{selected_po_id} lines")
                st.dataframe(podf[['po_detail_id','item_id','item_name','quantity','price','line_total']], use_container_width=True)

                st.markdown("*Edit quantity per line (unit price is fixed for PO).*")
                for _, row in podf.iterrows():
                    pid = int(row['po_detail_id'])
                    item_name = row['item_name']
                    cur_qty = int(row['quantity'])
                    cur_price = float(row['price'])
                    col1, col2, col3, col4 = st.columns([3,2,2,1])
                    with col1:
                        st.write(f"{item_name} (line {pid})")
                    with col2:
                        new_qty = st.number_input(f"Quantity (line {pid})", min_value=0, value=cur_qty, step=1, key=f"po_qty_{pid}")
                    with col3:
                        st.number_input(f"Unit Price (fixed)", value=cur_price, format="%.2f", disabled=True, key=f"po_price_{pid}")
                    with col4:
                        if st.button("Update", key=f"update_line_{pid}"):
                            upd = exec_query("UPDATE purchase_order_details SET quantity = %s WHERE po_detail_id = %s", (new_qty, pid))
                            if upd is not None:
                                st.success(f"Updated line {pid} → qty={new_qty}")
                                try:
                                    df_total = fetch_df("SELECT fn_po_total(%s) AS po_total", (selected_po_id,))
                                    if not df_total.empty and 'po_total' in df_total.columns:
                                        po_total = float(df_total.at[0,'po_total'])
                                    else:
                                        raise Exception("fn_po_total missing or returned empty")
                                except Exception:
                                    df_tot2 = fetch_df("SELECT IFNULL(SUM(quantity * price),0) AS po_total FROM purchase_order_details WHERE po_id = %s", (selected_po_id,))
                                    po_total = float(df_tot2.at[0,'po_total']) if not df_tot2.empty else 0.0
                                st.info(f"PO #{selected_po_id} total: {po_total:.2f}")
                try:
                    # FUNCTION + AGGREGATE usage shown here
                    df_total = fetch_df("SELECT fn_po_total(%s) AS po_total", (selected_po_id,))
                    if not df_total.empty and 'po_total' in df_total.columns:
                        po_total = float(df_total.at[0,'po_total'])
                        st.markdown("<div class='dbnote'><b>FUNCTION</b>: <code>fn_po_total(po_id)</code> returns PO value.</div>", unsafe_allow_html=True)
                    else:
                        raise Exception("fn_po_total missing")
                except Exception:
                    df_tot2 = fetch_df("SELECT IFNULL(SUM(quantity * price),0) AS po_total FROM purchase_order_details WHERE po_id = %s", (selected_po_id,))
                    po_total = float(df_tot2.at[0,'po_total']) if not df_tot2.empty else 0.0
                    st.markdown("<div class='dbnote'><b>AGGREGATE</b>: Fallback <code>SUM(quantity*price)</code> computes total.</div>", unsafe_allow_html=True)
                st.markdown("---")
                st.metric(label=f"PO #{selected_po_id} total", value=f"{po_total:.2f}")

    # 2.3 Receive PO
    with st.expander("2.3 Receive PO (Stock IN)", expanded=False):
        st.markdown("<div class='dbnote'>Receiving updates <code>stock</code> and logs to <code>transaction_log</code>. "
                    "DB <b>TRIGGER</b> <code>trg_stock_after_update</code> manages <code>reorder_alerts</code> (low-stock).</div>", unsafe_allow_html=True)
        po_to_receive = fetch_df("SELECT po_id, supplier_id, warehouse_id, po_date, status FROM purchase_order WHERE status IN ('CREATED','APPROVED','PARTIAL') ORDER BY po_id DESC")
        if po_to_receive.empty:
            st.info("No PO available to receive.")
        else:
            po_map = {row["po_id"]: row for _, row in po_to_receive.iterrows()}
            po_sel2 = st.selectbox("Pick PO to receive", options=["-- select --"] + [str(r["po_id"]) for _, r in po_to_receive.iterrows()], key="po_receive_select")
            if po_sel2 != "-- select --":
                poid = int(po_sel2)
                st.write("PO details:", po_map[poid])
                employee = load_choices("employee", "emp_id", "name", order_by="name")
                emp_sel = st.selectbox("Enter receiving employee", options=["-- select employee --"] + [f"{k} - {v}" for k,v in employee.items()], key=f"receive_emp_{poid}")
                if emp_sel != "-- select employee --":
                    emp_id = int(emp_sel.split(" - ")[0])
                    if st.button("Receive this PO", key=f"receive_btn_{poid}"):
                        lines = fetch_df("SELECT item_id, quantity, price FROM purchase_order_details WHERE po_id = %s", (poid,))
                        if lines.empty:
                            st.error("PO has no lines.")
                        else:
                            conn = get_connection()
                            if not conn:
                                st.error("DB connection failed.")
                            else:
                                try:
                                    cur = conn.cursor()
                                    for _, r in lines.iterrows():
                                        item_id = r["item_id"]
                                        qty = r["quantity"]
                                        cur.execute("SELECT quantity FROM stock WHERE warehouse_id = %s AND item_id = %s", (po_map[poid]["warehouse_id"], item_id))
                                        currow = cur.fetchone()
                                        if currow:
                                            new_qty = currow[0] + qty
                                            cur.execute("UPDATE stock SET quantity = %s, last_updated = %s WHERE warehouse_id = %s AND item_id = %s", (new_qty, datetime.now(), po_map[poid]["warehouse_id"], item_id))
                                        else:
                                            cur.execute("INSERT INTO stock (warehouse_id, item_id, quantity, last_updated) VALUES (%s,%s,%s,%s)", (po_map[poid]["warehouse_id"], item_id, qty, datetime.now()))
                                        try:
                                            cur.execute(
                                                "INSERT INTO transaction_log (warehouse_id, item_id, change_type, delta_qty, ref_type, ref_id, emp_id, logged_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                                                (po_map[poid]["warehouse_id"], item_id, "IN", qty, "PO", poid, emp_id, datetime.now())
                                            )
                                        except Error:
                                            pass
                                    cur.execute("UPDATE purchase_order SET status = %s WHERE po_id = %s", ("RECEIVED", poid))
                                    conn.commit()
                                    st.success(f"PO {poid} received and stock updated.")
                                except Error as e:
                                    conn.rollback()
                                    st.error(f"Failed to receive PO: {e}")
                                    st.write(traceback.format_exc())
                                finally:
                                    cur.close()
                                    conn.close()

# ---------- SALES / SHIP PAGE ----------
def page_sales():
    st.header(" Sales / Ship (SO flow)")
    st.markdown("Create SO → Add lines (price editable) → Ship SO (stock OUT).")
    st.markdown("---")

    # 3.1 Create SO
    with st.expander("3.1 Create SO", expanded=False):
        customers = load_choices("customer", "customer_id", "name", order_by="name")
        warehouses = load_choices("warehouse", "warehouse_id", "name", order_by="name")
        col1, col2, col3 = st.columns(3)
        with col1:
            customer_sel = st.selectbox("Pick customer", options=["-- Add new --"] + [f"{k} - {v}" for k,v in customers.items()])
        with col2:
            warehouse_sel = st.selectbox("Pick warehouse to ship from", options=[f"{k} - {v}" for k,v in warehouses.items()])
        with col3:
            so_date = st.date_input("SO Date", value=datetime.today())

        if customer_sel == "-- Add new --":
            with st.form("add_customer"):
                cname = st.text_input("Customer Name")
                ccontact = st.text_input("Customer Contact")
                add_c = st.form_submit_button("➕ Add Customer")
                if add_c:
                    if ensure_non_empty(cname, "Customer Name"):
                        q = "INSERT INTO customer (name, phone) VALUES (%s, %s)"
                        new_id = exec_query(q, (cname, ccontact), commit=True, get_lastrowid=True)
                        if new_id:
                            st.success(f"Customer created with id {new_id}. Refresh the page to use it.")

        if st.button("Create SO"):
            if customer_sel == "-- Add new --":
                st.error("Add the customer first.")
            else:
                try:
                    cust_id = int(str(customer_sel).split(" - ")[0])
                    wh_id = int(str(warehouse_sel).split(" - ")[0])
                    q = "INSERT INTO sales_order (customer_id, warehouse_id, so_date, status) VALUES (%s,%s,%s,%s)"
                    so_id = exec_query(q, (cust_id, wh_id, so_date, "NEW"), commit=True, get_lastrowid=True)
                    if so_id:
                        st.success(f"Sales Order created: SO#{so_id}")
                        st.markdown("<div class='dbnote'>SO header insert; detail lines use <b>JOIN</b> to show item names.</div>", unsafe_allow_html=True)
                except Exception:
                    st.error("Failed to create SO. Check customer/warehouse selections.")

    # 3.2 Add items to SO
    with st.expander("3.2 Add items to SO (price editable)", expanded=False):
        so_choices = fetch_df("SELECT so_id, customer_id, warehouse_id, so_date, status FROM sales_order ORDER BY so_id DESC")
        if so_choices.empty:
            st.info("No Sales Orders found. Create one above.")
        else:
            so_map = {row["so_id"]: row for _, row in so_choices.iterrows()}
            so_sel = st.selectbox("Pick SO to add lines", options=["-- select --"] + [f'{r["so_id"]} (status={r["status"]})' for _, r in so_choices.iterrows()], key="so_select_box")
            if so_sel != "-- select --":
                selected_so_id = int(str(so_sel).split(" ")[0])
                st.write("SO details:", so_map[selected_so_id])
                items = load_choices("item", "item_id", "name", order_by="name")
                item_choice = st.selectbox("Pick item", options=[f"{k} - {v}" for k,v in items.items()], key=f"so_item_{selected_so_id}")
                item_id = int(item_choice.split(" - ")[0])
                item_row = fetch_df("SELECT item_id, name, price FROM item WHERE item_id = %s", (item_id,))
                price_val = float(item_row.at[0,'price']) if not item_row.empty and item_row.at[0,'price'] is not None else 0.0
                qty = st.number_input("Quantity", min_value=1, step=1, key=f"so_qty_{selected_so_id}_{item_id}")
                price_input = st.number_input("Price (editable for sales)", value=price_val, format="%.2f", key=f"so_price_{selected_so_id}_{item_id}")
                if st.button("➕ Add line to SO", key=f"add_so_line_{selected_so_id}_{item_id}"):
                    q = "INSERT INTO sales_order_details (so_id, item_id, quantity, price) VALUES (%s,%s,%s,%s)"
                    last = exec_query(q, (selected_so_id, item_id, qty, price_input), commit=True, get_lastrowid=True)
                    if last is not None:
                        st.success("Line added to SO.")
                        st.markdown("<div class='dbnote'>Detail insert; reporting later uses <b>AGGREGATE</b> <code>SUM</code>.</div>", unsafe_allow_html=True)
                sodf = fetch_df("SELECT sod.so_detail_id, sod.item_id, i.name AS item_name, sod.quantity, sod.price FROM sales_order_details sod JOIN item i ON sod.item_id = i.item_id WHERE sod.so_id = %s", (selected_so_id,))
                st.markdown("<div class='dbnote'>Uses <b>JOIN</b> to display item names for SO lines.</div>", unsafe_allow_html=True)
                if not sodf.empty:
                    st.dataframe(sodf, use_container_width=True)

    # 3.3 Ship / Dispatch (Stock OUT)
    with st.expander("3.3 Ship / Dispatch (Stock OUT)", expanded=False):
        st.markdown("<div class='dbnote'>Shipping updates <code>stock</code> and writes to <code>transaction_log</code>. "
                    "DB <b>TRIGGER</b> on <code>stock</code> maintains <code>reorder_alerts</code>.</div>", unsafe_allow_html=True)
        so_to_ship = fetch_df("SELECT so_id, customer_id, warehouse_id, so_date, status FROM sales_order WHERE status IN ('NEW','CONFIRMED') ORDER BY so_id DESC")
        if so_to_ship.empty:
            st.info("No Sales Orders ready to ship.")
        else:
            so_sel2 = st.selectbox("Pick SO to ship", options=["-- select --"] + [str(r["so_id"]) for _, r in so_to_ship.iterrows()], key="so_ship_select")
            if so_sel2 != "-- select --":
                soid = int(so_sel2)
                emp_map = load_choices("employee", "emp_id", "name", order_by="name")
                emp_sel = st.selectbox("Enter shipping employee", options=["-- select employee --"] + [f"{k} - {v}" for k,v in emp_map.items()], key=f"ship_emp_{soid}")
                check_stock = st.checkbox("Check stock before ship", value=True, key=f"check_stock_{soid}")
                if emp_sel != "-- select employee --":
                    emp_id = int(emp_sel.split(" - ")[0])
                    if st.button("Ship this SO", key=f"ship_btn_{soid}"):

                        lines = fetch_df("SELECT item_id, quantity FROM sales_order_details WHERE so_id = %s", (soid,))
                        if lines.empty:
                            st.error("SO has no lines.")
                        else:
                            conn = get_connection()
                            if not conn:
                                st.error("DB connection failed.")
                            else:
                                try:
                                    cur = conn.cursor()
                                    so_row = so_to_ship[so_to_ship["so_id"] == soid].iloc[0]
                                    whid = int(so_row["warehouse_id"])
                                    if check_stock:
                                        for _, r in lines.iterrows():
                                            item_id = int(r["item_id"])
                                            qty = int(r["quantity"])
                                            cur.execute("SELECT quantity FROM stock WHERE warehouse_id = %s AND item_id = %s", (whid, item_id))
                                            row = cur.fetchone()
                                            available = int(row[0]) if row else 0
                                            if available < qty:
                                                st.error(f"Insufficient stock for item {item_id}. Available {available}, requested {qty}. Aborting.")
                                                cur.close()
                                                conn.close()
                                                return
                                    for _, r in lines.iterrows():
                                        item_id = int(r["item_id"])
                                        qty = int(r["quantity"])
                                        cur.execute("SELECT quantity FROM stock WHERE warehouse_id = %s AND item_id = %s", (whid, item_id))
                                        row = cur.fetchone()
                                        if row:
                                            new_qty = int(row[0]) - qty
                                            cur.execute("UPDATE stock SET quantity = %s, last_updated = %s WHERE warehouse_id = %s AND item_id = %s",
                                                        (new_qty, datetime.now(), whid, item_id))
                                        else:
                                            st.warning(f"No stock row for item {item_id} in warehouse {whid}. Skipping update.")
                                        try:
                                            cur.execute(
                                                "INSERT INTO transaction_log (warehouse_id, item_id, change_type, delta_qty, ref_type, ref_id, emp_id, logged_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                                                (whid, item_id, "OUT", qty, "SO", soid, emp_id, datetime.now())
                                            )
                                        except Error:
                                            pass
                                    cur.execute("UPDATE sales_order SET status = %s WHERE so_id = %s", ("SHIPPED", soid))
                                    conn.commit()
                                    st.success(f"SO {soid} shipped and stock updated.")
                                except Error as e:
                                    conn.rollback()
                                    st.error(f"Failed to ship SO: {e}")
                                    st.write(traceback.format_exc())
                                finally:
                                    cur.close()
                                    conn.close()

# ---------- ADJUST / RETURN PAGE ----------
def page_adjust_return():
    st.header(" Adjustments & Returns")
    st.markdown("Manual adjustments or processing returns.")
    st.markdown("---")

    warehouses = load_choices("warehouse", "warehouse_id", "name", order_by="name")
    items = load_choices("item", "item_id", "name", order_by="name")
    emp_map = load_choices("employee", "emp_id", "name", order_by="name")

    with st.expander("4.1 Manual Stock Adjustment", expanded=False):
        st.markdown("<div class='dbnote'>Writes to <code>stock</code> and <code>transaction_log</code>. "
                    "DB <b>TRIGGER</b> on <code>stock</code> keeps <code>reorder_alerts</code> correct.</div>", unsafe_allow_html=True)
        col1, col2, col3 = st.columns(3)
        with col1:
            wh = st.selectbox("Warehouse", options=[f"{k} - {v}" for k,v in warehouses.items()], key="adj_wh")
        with col2:
            it = st.selectbox("Item", options=[f"{k} - {v}" for k,v in items.items()], key="adj_item")
        with col3:
            qty = st.number_input("Quantity (+ to add, - to remove)", value=0, step=1, key="adj_qty")
        emp = st.selectbox("Employee", options=["-- select --"] + [f"{k} - {v}" for k,v in emp_map.items()], key="adj_emp")
        if st.button("Apply Adjustment"):
            if wh and it and emp:
                whid = int(wh.split(" - ")[0])
                itemid = int(it.split(" - ")[0])
                empid = int(emp.split(" - ")[0])
                conn = get_connection()
                if not conn:
                    st.error("DB connection failed.")
                else:
                    try:
                        cur = conn.cursor()
                        cur.execute("SELECT quantity FROM stock WHERE warehouse_id = %s AND item_id = %s", (whid, itemid))
                        row = cur.fetchone()
                        if row:
                            new_qty = int(row[0]) + int(qty)
                            cur.execute("UPDATE stock SET quantity = %s, last_updated = %s WHERE warehouse_id = %s AND item_id = %s", (new_qty, datetime.now(), whid, itemid))
                        else:
                            cur.execute("INSERT INTO stock (warehouse_id, item_id, quantity, last_updated) VALUES (%s,%s,%s,%s)", (whid, itemid, qty, datetime.now()))
                        try:
                            cur.execute("INSERT INTO transaction_log (warehouse_id, item_id, change_type, delta_qty, ref_type, ref_id, emp_id, logged_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                                        (whid, itemid, "ADJUST", qty, "MANUAL", None, empid, datetime.now()))
                        except Error:
                            pass
                        conn.commit()
                        st.success("Stock adjusted.")
                    except Error as e:
                        conn.rollback()
                        st.error(f"Adjustment failed: {e}")
                        st.write(traceback.format_exc())
                    finally:
                        cur.close()
                        conn.close()
            else:
                st.error("Please pick warehouse, item and employee.")

    with st.expander("4.2 Returns", expanded=False):
        st.markdown("<div class='dbnote'>Customer return → <code>IN</code>; Return to supplier → <code>OUT</code>. "
                    "Both logged; <b>TRIGGER</b> maintains alerts.</div>", unsafe_allow_html=True)
        return_type = st.radio("Return type", ["Customer return (stock IN)", "Return to supplier (stock OUT)"], key="return_type")
        wh2 = st.selectbox("Warehouse", options=[f"{k} - {v}" for k,v in warehouses.items()], key="ret_wh")
        it2 = st.selectbox("Item", options=[f"{k} - {v}" for k,v in items.items()], key="ret_item")
        qty2 = st.number_input("Quantity", min_value=1, step=1, key="ret_qty")
        if st.button("Process return"):
            whid = int(wh2.split(" - ")[0])
            itemid = int(it2.split(" - ")[0])
            conn = get_connection()
            if not conn:
                st.error("DB connection failed.")
            else:
                try:
                    cur = conn.cursor()
                    if return_type.startswith("Customer"):
                        cur.execute("SELECT quantity FROM stock WHERE warehouse_id = %s AND item_id = %s", (whid, itemid))
                        row = cur.fetchone()
                        if row:
                            new_qty = int(row[0]) + int(qty2)
                            cur.execute("UPDATE stock SET quantity = %s, last_updated = %s WHERE warehouse_id = %s AND item_id = %s", (new_qty, datetime.now(), whid, itemid))
                        else:
                            cur.execute("INSERT INTO stock (warehouse_id, item_id, quantity, last_updated) VALUES (%s,%s,%s,%s)", (whid, itemid, qty2, datetime.now()))
                        try:
                            cur.execute("INSERT INTO transaction_log (warehouse_id, item_id, change_type, delta_qty, ref_type, ref_id, emp_id, logged_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                                        (whid, itemid, "IN", qty2, "RETURN_CUST", None, None, datetime.now()))
                        except Error:
                            pass
                        conn.commit()
                        st.success("Customer return processed (stock IN).")
                    else:
                        cur.execute("SELECT quantity FROM stock WHERE warehouse_id = %s AND item_id = %s", (whid, itemid))
                        row = cur.fetchone()
                        if row:
                            new_qty = int(row[0]) - int(qty2)
                            cur.execute("UPDATE stock SET quantity = %s, last_updated = %s WHERE warehouse_id = %s AND item_id = %s", (new_qty, datetime.now(), whid, itemid))
                        else:
                            st.warning("No stock row found; negative stock not created.")
                        try:
                            cur.execute("INSERT INTO transaction_log (warehouse_id, item_id, change_type, delta_qty, ref_type, ref_id, emp_id, logged_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                                        (whid, itemid, "OUT", qty2, "RETURN_SUPP", None, None, datetime.now()))
                        except Error:
                            pass
                        conn.commit()
                        st.success("Return to supplier processed (stock OUT).")
                except Error as e:
                    conn.rollback()
                    st.error(f"Return failed: {e}")
                    st.write(traceback.format_exc())
                finally:
                    cur.close()
                    conn.close()

# ---------- EMPLOYEES PAGE ----------
def page_employees():
    st.header(" Employees")
    st.markdown("View, add, or delete employees. Employee contact must be a valid Gmail address.")
    st.markdown("---")

    df = fetch_df("SELECT emp_id, name, role, contact, warehouse_id FROM employee ORDER BY emp_id")
    if df.empty:
        st.info("No employees found.")
    else:
        try:
            wh = fetch_df("SELECT warehouse_id, name FROM warehouse")
            if not wh.empty:
                df = df.merge(wh, how="left", left_on="warehouse_id", right_on="warehouse_id")
                df = df.rename(columns={"name":"warehouse_name"})
        except Exception:
            pass
        st.dataframe(df, use_container_width=True)
        st.markdown("<div class='dbnote'>Simple read; could be viewed as a <b>JOIN</b> with warehouse for the name.</div>", unsafe_allow_html=True)

    st.markdown("### Add employee")
    with st.form("add_employee"):
        ename = st.text_input("Name")
        erole_label = st.selectbox(
            "Role",
            options=["Warehouse Manager", "Receiver", "Picker", "Admin", "Clerk", "Auditor", "Supervisor"]
        )
        econtact = st.text_input("Contact (Gmail only, e.g. user@gmail.com)")
        warehouses = load_choices("warehouse", "warehouse_id", "name", order_by="name")
        ewh = st.selectbox("Warehouse (optional)", options=["-- none --"] + [f"{k} - {v}" for k,v in warehouses.items()])
        add_b = st.form_submit_button("➕ Add employee")
        if add_b:
            if ensure_non_empty(ename, "Name") and ensure_non_empty(econtact, "Contact"):
                if not is_valid_gmail(econtact):
                    st.error("Contact must be a valid Gmail address (example: user@gmail.com).")
                else:
                    erole = ROLE_MAP.get(erole_label, "staff")
                    wid = None
                    if ewh != "-- none --":
                        wid = int(ewh.split(" - ")[0])
                    q = "INSERT INTO employee (name, role, contact, warehouse_id) VALUES (%s,%s,%s,%s)"
                    last = exec_query(q, (ename, erole, econtact, wid), commit=True, get_lastrowid=True)
                    if last:
                        st.success(f"Employee added (id {last}). Refresh the page to see them listed.")

    st.markdown("### Delete employee")
    emp_map = load_choices("employee", "emp_id", "name", order_by="name")
    emp_sel = st.selectbox("Pick employee to delete", options=["-- select --"] + [f"{k} - {v}" for k,v in emp_map.items()])
    if emp_sel != "-- select --":
        empid = int(emp_sel.split(" - ")[0])
        if st.button(" Delete employee"):
            exec_query("DELETE FROM employee WHERE emp_id = %s", (empid,))
            st.success("Employee deleted.")

# ---------- REPORTS PAGE ----------
def page_reports():
    st.header(" Reports")
    st.markdown("Enter month (YYYY-MM) to compute basic P&L and list POs/SOs.")
    st.markdown("---")
    month = st.text_input("Enter month (YYYY-MM)", value=datetime.today().strftime("%Y-%m"), key="report_month")
    if st.button("Generate report"):
        try:
            start = datetime.strptime(month + "-01", "%Y-%m-%d")
            if start.month == 12:
                end = datetime(start.year + 1, 1, 1)
            else:
                end = datetime(start.year, start.month + 1, 1)
            purchases_q = """
            SELECT po.po_id, pod.item_id, pod.quantity, pod.price, pod.quantity * pod.price AS line_total
            FROM purchase_order po
            JOIN purchase_order_details pod ON po.po_id = pod.po_id
            WHERE po.po_date >= %s AND po.po_date < %s
            """
            pur_lines = fetch_df(purchases_q, (start, end))
            total_purchases = float(pur_lines["line_total"].sum()) if not pur_lines.empty else 0.0

            sales_q = """
            SELECT so.so_id, sod.item_id, sod.quantity, sod.price, sod.quantity * sod.price AS line_total
            FROM sales_order so
            JOIN sales_order_details sod ON so.so_id = sod.so_id
            WHERE so.so_date >= %s AND so.so_date < %s
            """
            sales_lines = fetch_df(sales_q, (start, end))
            total_sales = float(sales_lines["line_total"].sum()) if not sales_lines.empty else 0.0

            salaries = 0.0
            profit_loss = total_sales - total_purchases - salaries

            st.metric("Total purchases", f"{total_purchases:.2f}")
            st.metric("Total sales", f"{total_sales:.2f}")
            st.metric("Profit/Loss", f"{profit_loss:.2f}")
            st.markdown("<div class='dbnote'><b>AGGREGATE</b> totals via <code>SUM</code>; tables above use <b>JOIN</b> between headers and details.</div>", unsafe_allow_html=True)

            st.subheader("Purchase Orders")
            po_df = fetch_df("SELECT po_id, supplier_id, warehouse_id, po_date, status FROM purchase_order WHERE po_date >= %s AND po_date < %s", (start, end))
            if po_df.empty:
                st.write("No POs in this month.")
            else:
                st.dataframe(po_df, use_container_width=True)
            st.subheader("Sales Orders")
            so_df = fetch_df("SELECT so_id, customer_id, warehouse_id, so_date, status FROM sales_order WHERE so_date >= %s AND so_date < %s", (start, end))
            if so_df.empty:
                st.write("No SOs in this month.")
            else:
                st.dataframe(so_df, use_container_width=True)
        except Exception as e:
            st.error(f"Failed to generate report: {e}")
            st.write(traceback.format_exc())

# ---------- MAIN NAV ----------
def main():
    st.title(" Inventory & Warehouse Management")

    # If not logged-in, show only the login page
    if not st.session_state.get("user"):
        logged_in_now = show_login_page()
        if not logged_in_now:
            return

    # From here onwards, user is logged in
    show_sidebar_user_widget()

    # determine menu items based on login (fallback to limited preview)
    if st.session_state.get("user") and st.session_state["user"].get("menu"):
        menu_options = st.session_state["user"]["menu"]
    else:
        role = st.session_state.get("user", {}).get("role")
        if role == "admin":
            menu_options = ["Stock", "Purchase", "Sales", "Adjust/Return", "Employees", "Reports", "Raw SQL (admin)"]
        elif role == "worker":
            menu_options = ["Stock", "Reports"]
        else:
            menu_options = ["Stock"]

    # Sidebar navigation
    menu = st.sidebar.radio("Go to", menu_options)

    try:
        if menu == "Stock":
            page_stock()
        elif menu == "Purchase":
            if not require_role(["admin"]): return
            page_purchase()
        elif menu == "Sales":
            if not require_role(["admin"]): return
            page_sales()
        elif menu == "Adjust/Return":
            if not require_role(["admin"]): return
            page_adjust_return()
        elif menu == "Employees":
            if not require_role(["admin"]): return
            page_employees()
        elif menu == "Reports":
            if not require_role(["admin","worker"]): return
            page_reports()
        elif menu == "Raw SQL (admin)":
            if not require_role(["admin"]): return
            st.header(" Admin — run SELECT queries (read-only)")
            st.markdown("<div class='dbnote'>For viva: demonstrate <b>Nested</b> and <b>JOIN</b> queries here as needed.</div>", unsafe_allow_html=True)
            q = st.text_area("Enter a SELECT query", height=150, value="SELECT * FROM item LIMIT 50;")
            if st.button("Run (read-only)"):
                if q.strip().lower().startswith("select"):
                    df = fetch_df(q)
                    if not df.empty:
                        st.dataframe(df, use_container_width=True)
                    else:
                        st.write("No results.")
                else:
                    st.error("Only SELECT queries are allowed in this admin area.")
    except Exception as e:
        st.error(f"Unexpected error: {e}")
        st.write(traceback.format_exc())

if __name__ == "__main__":
    main()
