import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
import sqlite3
import hashlib
from datetime import date, datetime

st.set_page_config(page_title="Smart Budget AI", page_icon="💰", layout="wide")

DB_NAME = "smart_budget_ai.db"


# ----------------------------
# DATABASE
# ----------------------------
def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)


def ensure_column_exists(cur, table_name, column_name, alter_sql):
    cur.execute(f"PRAGMA table_info({table_name})")
    columns = [row[1] for row in cur.fetchall()]
    if column_name not in columns:
        cur.execute(alter_sql)


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            monthly_income REAL DEFAULT 0,
            savings_goal REAL DEFAULT 0
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            nickname TEXT NOT NULL,
            bank_name TEXT NOT NULL,
            card_type TEXT NOT NULL,
            last4 TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            card_id INTEGER NOT NULL,
            merchant TEXT NOT NULL,
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            transaction_date TEXT NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(card_id) REFERENCES cards(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS category_budgets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            category TEXT NOT NULL,
            budget_limit REAL DEFAULT 0,
            UNIQUE(user_id, category),
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    # Safe migrations for older database files
    ensure_column_exists(
        cur,
        "users",
        "monthly_income",
        "ALTER TABLE users ADD COLUMN monthly_income REAL DEFAULT 0"
    )
    ensure_column_exists(
        cur,
        "users",
        "savings_goal",
        "ALTER TABLE users ADD COLUMN savings_goal REAL DEFAULT 0"
    )
    ensure_column_exists(
        cur,
        "transactions",
        "notes",
        "ALTER TABLE transactions ADD COLUMN notes TEXT"
    )
    ensure_column_exists(
        cur,
        "transactions",
        "created_at",
        "ALTER TABLE transactions ADD COLUMN created_at TEXT"
    )
    ensure_column_exists(
        cur,
        "cards",
        "created_at",
        "ALTER TABLE cards ADD COLUMN created_at TEXT"
    )

    conn.commit()
    conn.close()


init_db()


# ----------------------------
# HELPERS
# ----------------------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def detect_category(merchant: str) -> str:
    merchant = merchant.lower().strip()

    rules = {
        "uber": "Transportation",
        "lyft": "Transportation",
        "shell": "Transportation",
        "exxon": "Transportation",
        "bp": "Transportation",
        "starbucks": "Food",
        "mcdonald": "Food",
        "chipotle": "Food",
        "subway": "Food",
        "dominos": "Food",
        "pizza": "Food",
        "netflix": "Entertainment",
        "spotify": "Entertainment",
        "amc": "Entertainment",
        "amazon": "Shopping",
        "target": "Shopping",
        "best buy": "Shopping",
        "nike": "Shopping",
        "walmart": "Groceries",
        "aldi": "Groceries",
        "costco": "Groceries",
        "trader joe": "Groceries",
        "rent": "Housing",
        "apple": "Subscriptions",
        "youtube": "Subscriptions",
        "hulu": "Subscriptions",
        "disney": "Subscriptions",
        "cvs": "Healthcare",
        "walgreens": "Healthcare",
        "hospital": "Healthcare"
    }

    for key, value in rules.items():
        if key in merchant:
            return value

    return "Other"


def register_user(full_name: str, email: str, password: str):
    try:
        conn = get_connection()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO users (full_name, email, password_hash) VALUES (?, ?, ?)",
            (full_name.strip(), email.strip().lower(), hash_password(password))
        )
        conn.commit()
        conn.close()
        return True, "Account created successfully."
    except sqlite3.IntegrityError:
        return False, "An account with this email already exists."


def login_user(email: str, password: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, full_name, email FROM users WHERE email = ? AND password_hash = ?",
        (email.strip().lower(), hash_password(password))
    )
    user = cur.fetchone()
    conn.close()
    return user


def get_user_finance_settings(user_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT monthly_income, savings_goal FROM users WHERE id = ?",
        (user_id,)
    )
    row = cur.fetchone()
    conn.close()
    if row:
        return float(row[0] or 0), float(row[1] or 0)
    return 0.0, 0.0


def update_user_finance_settings(user_id: int, income: float, savings_goal: float):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET monthly_income = ?, savings_goal = ? WHERE id = ?",
        (income, savings_goal, user_id)
    )
    conn.commit()
    conn.close()


def add_card(user_id: int, nickname: str, bank_name: str, card_type: str, last4: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO cards (user_id, nickname, bank_name, card_type, last4, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, nickname.strip(), bank_name.strip(), card_type, last4.strip(), datetime.now().isoformat()))
    conn.commit()
    conn.close()


def get_cards(user_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, nickname, bank_name, card_type, last4
        FROM cards
        WHERE user_id = ?
        ORDER BY id DESC
    """, (user_id,))
    rows = cur.fetchall()
    conn.close()
    return rows


def add_transaction(user_id: int, card_id: int, merchant: str, amount: float, category: str, transaction_date: str, notes: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO transactions (user_id, card_id, merchant, amount, category, transaction_date, notes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        card_id,
        merchant.strip(),
        amount,
        category,
        transaction_date,
        notes.strip(),
        datetime.now().isoformat()
    ))
    conn.commit()
    conn.close()


def get_transactions(user_id: int):
    conn = get_connection()
    query = """
        SELECT
            t.id,
            t.card_id,
            c.nickname || ' - ****' || c.last4 AS card,
            t.merchant,
            t.amount,
            t.category,
            t.transaction_date,
            COALESCE(t.notes, '') as notes
        FROM transactions t
        JOIN cards c ON t.card_id = c.id
        WHERE t.user_id = ?
        ORDER BY t.transaction_date DESC, t.id DESC
    """
    df = pd.read_sql_query(query, conn, params=(user_id,))
    conn.close()
    return df


def update_transaction(tx_id: int, card_id: int, merchant: str, amount: float, category: str, transaction_date: str, notes: str):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        UPDATE transactions
        SET card_id = ?, merchant = ?, amount = ?, category = ?, transaction_date = ?, notes = ?
        WHERE id = ?
    """, (card_id, merchant.strip(), amount, category, transaction_date, notes.strip(), tx_id))
    conn.commit()
    conn.close()


def delete_transaction(tx_id: int):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM transactions WHERE id = ?", (tx_id,))
    conn.commit()
    conn.close()


def upsert_category_budget(user_id: int, category: str, budget_limit: float):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO category_budgets (user_id, category, budget_limit)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, category)
        DO UPDATE SET budget_limit = excluded.budget_limit
    """, (user_id, category, budget_limit))
    conn.commit()
    conn.close()


def get_category_budgets(user_id: int):
    conn = get_connection()
    df = pd.read_sql_query(
        "SELECT category, budget_limit FROM category_budgets WHERE user_id = ?",
        conn,
        params=(user_id,)
    )
    conn.close()
    return df


# ----------------------------
# SESSION STATE
# ----------------------------
if "user_id" not in st.session_state:
    st.session_state.user_id = None
if "user_name" not in st.session_state:
    st.session_state.user_name = None
if "user_email" not in st.session_state:
    st.session_state.user_email = None


# ----------------------------
# STYLING
# ----------------------------
st.markdown("""
<style>
.block-container {
    padding-top: 1.2rem;
    padding-bottom: 1rem;
}
.main-title {
    font-size: 38px;
    font-weight: 800;
    margin-bottom: 4px;
}
.sub-title {
    font-size: 16px;
    color: #94a3b8;
    margin-bottom: 24px;
}
.section-title {
    font-size: 24px;
    font-weight: 700;
    margin-top: 12px;
    margin-bottom: 14px;
}
.card-box {
    background-color: #111827;
    border: 1px solid #1f2937;
    padding: 16px;
    border-radius: 16px;
    margin-bottom: 12px;
    color: white;
}
.insight-box {
    background-color: #0f172a;
    border: 1px solid #1e293b;
    padding: 14px;
    border-radius: 14px;
    margin-bottom: 10px;
    color: #e2e8f0;
}
.success-box {
    background-color: #052e16;
    border: 1px solid #166534;
    padding: 14px;
    border-radius: 14px;
    margin-bottom: 10px;
    color: #dcfce7;
}
.warning-box {
    background-color: #3b2106;
    border: 1px solid #b45309;
    padding: 14px;
    border-radius: 14px;
    margin-bottom: 10px;
    color: #fde68a;
}
.danger-box {
    background-color: #450a0a;
    border: 1px solid #b91c1c;
    padding: 14px;
    border-radius: 14px;
    margin-bottom: 10px;
    color: #fecaca;
}
.small-note {
    color: #94a3b8;
    font-size: 13px;
}
div[data-testid="stSidebar"] {
    background-color: #0b1220;
}
div[data-testid="stSidebar"] * {
    color: #e5e7eb;
}
.stButton > button {
    width: 100%;
    border-radius: 12px;
    height: 44px;
    font-weight: 600;
}
.stTextInput input, .stNumberInput input {
    border-radius: 10px !important;
}
[data-baseweb="select"] > div {
    border-radius: 10px !important;
}
</style>
""", unsafe_allow_html=True)


# ----------------------------
# AUTH
# ----------------------------
if st.session_state.user_id is None:
    st.markdown('<div class="main-title">💰 Smart Budget AI</div>', unsafe_allow_html=True)
    st.markdown('<div class="sub-title">Login or create an account to continue.</div>', unsafe_allow_html=True)

    auth_mode = st.radio("Choose", ["Login", "Register"], horizontal=True)

    if auth_mode == "Login":
        st.markdown('<div class="section-title">Login</div>', unsafe_allow_html=True)
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")

        if st.button("Login"):
            user = login_user(email, password)
            if user:
                st.session_state.user_id = user[0]
                st.session_state.user_name = user[1]
                st.session_state.user_email = user[2]
                st.success("Logged in successfully.")
                st.rerun()
            else:
                st.error("Invalid email or password.")

    else:
        st.markdown('<div class="section-title">Create Account</div>', unsafe_allow_html=True)
        full_name = st.text_input("Full Name")
        reg_email = st.text_input("Email")
        reg_password = st.text_input("Password", type="password")

        if st.button("Create Account"):
            if full_name.strip() and reg_email.strip() and reg_password.strip():
                ok, msg = register_user(full_name, reg_email, reg_password)
                if ok:
                    st.success(msg)
                else:
                    st.error(msg)
            else:
                st.warning("Fill all fields.")

    st.stop()


# ----------------------------
# SIDEBAR
# ----------------------------
with st.sidebar:
    st.markdown("## 💰 Smart Budget AI")
    st.caption("Navigation")

    page = st.radio(
        "Go to",
        ["Dashboard", "Cards", "Transactions", "Reports"],
        label_visibility="collapsed"
    )

    st.markdown("---")
    st.markdown(f"**User:** {st.session_state.user_name}")
    st.caption(st.session_state.user_email)

    if st.button("Logout"):
        st.session_state.user_id = None
        st.session_state.user_name = None
        st.session_state.user_email = None
        st.rerun()


user_id = st.session_state.user_id
cards = get_cards(user_id)
tx_df = get_transactions(user_id)
income, savings_goal = get_user_finance_settings(user_id)
budget_df = get_category_budgets(user_id)

budget_map = {}
if not budget_df.empty:
    budget_map = dict(zip(budget_df["category"], budget_df["budget_limit"]))

all_categories = [
    "Food", "Transportation", "Entertainment", "Shopping",
    "Groceries", "Housing", "Subscriptions", "Healthcare", "Other"
]


# ----------------------------
# MAIN HEADER
# ----------------------------
st.markdown('<div class="main-title">Smart Budget AI</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">Track spending, set goals, manage budgets, filter transactions, and understand where your money goes.</div>',
    unsafe_allow_html=True
)


# ----------------------------
# DASHBOARD PAGE
# ----------------------------
if page == "Dashboard":
    st.markdown('<div class="section-title">Dashboard</div>', unsafe_allow_html=True)

    s1, s2 = st.columns(2)
    with s1:
        new_income = st.number_input("Monthly Income", min_value=0.0, value=float(income), step=100.0)
    with s2:
        new_savings_goal = st.number_input("Savings Goal", min_value=0.0, value=float(savings_goal), step=100.0)

    if st.button("Save Financial Settings"):
        update_user_finance_settings(user_id, new_income, new_savings_goal)
        st.success("Financial settings updated.")
        st.rerun()

    total_spending = float(tx_df["amount"].sum()) if not tx_df.empty else 0.0
    savings_left = income - total_spending

    m1, m2, m3 = st.columns(3)
    m1.metric("Income", f"${income:,.2f}")
    m2.metric("Total Spending", f"${total_spending:,.2f}")
    m3.metric("Savings Left", f"${savings_left:,.2f}")

    st.markdown('<div class="section-title">Savings Goal Tracker</div>', unsafe_allow_html=True)

    if savings_goal > 0:
        saved_toward_goal = max(savings_left, 0)
        goal_progress = min(saved_toward_goal / savings_goal, 1.0)
        remaining_goal = max(savings_goal - saved_toward_goal, 0)

        st.progress(goal_progress, text=f"${saved_toward_goal:,.2f} saved toward ${savings_goal:,.2f}")
        st.write(f"Remaining to goal: **${remaining_goal:,.2f}**")

        if goal_progress >= 1:
            st.markdown("<div class='success-box'>Great job! You reached your savings goal.</div>", unsafe_allow_html=True)
    else:
        st.info("Set a savings goal to track progress.")

    st.markdown('<div class="section-title">Category Budget Limits</div>', unsafe_allow_html=True)

    b1, b2, b3 = st.columns(3)
    for i, category in enumerate(all_categories):
        current_limit = float(budget_map.get(category, 0))
        target_col = [b1, b2, b3][i % 3]
        with target_col:
            new_limit = st.number_input(
                f"{category} Budget",
                min_value=0.0,
                value=current_limit,
                step=10.0,
                key=f"budget_{category}"
            )
            if st.button(f"Save {category}", key=f"save_{category}"):
                upsert_category_budget(user_id, category, new_limit)
                st.success(f"{category} budget saved.")
                st.rerun()

    if not tx_df.empty:
        st.markdown('<div class="section-title">Where Your Money Goes</div>', unsafe_allow_html=True)

        category_totals = (
            tx_df.groupby("category", as_index=False)["amount"]
            .sum()
            .sort_values("amount", ascending=False)
        )

        c1, c2 = st.columns(2)

        with c1:
            fig1, ax1 = plt.subplots(figsize=(6, 6))
            ax1.pie(
                category_totals["amount"],
                labels=category_totals["category"],
                autopct="%1.1f%%"
            )
            ax1.axis("equal")
            st.pyplot(fig1)

        with c2:
            fig2, ax2 = plt.subplots(figsize=(7, 4))
            ax2.bar(category_totals["category"], category_totals["amount"])
            ax2.set_ylabel("Amount")
            ax2.set_title("Spending by Category")
            plt.xticks(rotation=20)
            st.pyplot(fig2)

        st.markdown('<div class="section-title">Top Spending Categories</div>', unsafe_allow_html=True)
        for _, row in category_totals.iterrows():
            pct = (row["amount"] / total_spending * 100) if total_spending > 0 else 0
            st.progress(min(pct / 100, 1.0), text=f"{row['category']} — ${row['amount']:.2f} ({pct:.1f}%)")

        st.markdown('<div class="section-title">Current Month vs Previous Month</div>', unsafe_allow_html=True)

        month_df = tx_df.copy()
        month_df["transaction_date"] = pd.to_datetime(month_df["transaction_date"])
        month_df["month"] = month_df["transaction_date"].dt.to_period("M").astype(str)

        available_months = sorted(month_df["month"].unique())
        current_month = available_months[-1]
        previous_month = available_months[-2] if len(available_months) >= 2 else None
        current_total = month_df[month_df["month"] == current_month]["amount"].sum()

        previous_total = 0.0
        if previous_month:
            previous_total = month_df[month_df["month"] == previous_month]["amount"].sum()
            change = current_total - previous_total
            pct_change = (change / previous_total * 100) if previous_total > 0 else 0

            x1, x2, x3 = st.columns(3)
            x1.metric("Current Month", f"${current_total:,.2f}", current_month)
            x2.metric("Previous Month", f"${previous_total:,.2f}", previous_month)
            x3.metric("Difference", f"${change:,.2f}", f"{pct_change:.1f}%")
        else:
            st.info("Add transactions from at least two different months to see comparison.")

        st.markdown('<div class="section-title">Insights</div>', unsafe_allow_html=True)

        top_category = category_totals.iloc[0]["category"]
        top_amount = float(category_totals.iloc[0]["amount"])
        top_pct = (top_amount / total_spending * 100) if total_spending > 0 else 0

        insights = [
            f"Your highest spending category is **{top_category}** at **${top_amount:,.2f}**.",
            f"That category represents **{top_pct:.1f}%** of your total tracked spending."
        ]

        if income > 0 and total_spending > income * 0.8:
            insights.append("You are spending more than 80% of your monthly income.")

        if income > 0 and savings_left < income * 0.2:
            insights.append("Your remaining savings are below 20% of your monthly income.")

        if previous_month:
            if current_total > previous_total:
                insights.append(f"Your spending increased by **${(current_total - previous_total):,.2f}** compared to last month.")
            elif current_total < previous_total:
                insights.append(f"Good job — your spending decreased by **${(previous_total - current_total):,.2f}** compared to last month.")
            else:
                insights.append("Your spending is the same as last month.")

        for category in all_categories:
            spent_amt = float(category_totals[category_totals["category"] == category]["amount"].sum()) if category in category_totals["category"].values else 0.0
            limit_amt = float(budget_map.get(category, 0))
            if limit_amt > 0 and spent_amt > limit_amt:
                insights.append(f"**{category}** is over budget by **${(spent_amt - limit_amt):,.2f}**.")
            elif limit_amt > 0 and spent_amt >= limit_amt * 0.8:
                insights.append(f"**{category}** is close to budget limit. You have used **{(spent_amt / limit_amt) * 100:.1f}%** of it.")

        for item in insights:
            st.markdown(f"<div class='insight-box'>{item}</div>", unsafe_allow_html=True)

        st.markdown('<div class="section-title">Budget Alerts</div>', unsafe_allow_html=True)
        for category in all_categories:
            spent_amt = float(category_totals[category_totals["category"] == category]["amount"].sum()) if category in category_totals["category"].values else 0.0
            limit_amt = float(budget_map.get(category, 0))

            if limit_amt > 0:
                usage = spent_amt / limit_amt if limit_amt > 0 else 0
                st.progress(min(usage, 1.0), text=f"{category}: ${spent_amt:.2f} / ${limit_amt:.2f}")
                if usage > 1:
                    st.markdown(f"<div class='danger-box'>{category} budget exceeded.</div>", unsafe_allow_html=True)
                elif usage >= 0.8:
                    st.markdown(f"<div class='warning-box'>{category} budget is near the limit.</div>", unsafe_allow_html=True)

        st.markdown('<div class="section-title">Top Merchants</div>', unsafe_allow_html=True)
        merchant_totals = (
            tx_df.groupby("merchant", as_index=False)["amount"]
            .sum()
            .sort_values("amount", ascending=False)
        )
        st.dataframe(merchant_totals, use_container_width=True)

    else:
        st.info("Add cards and transactions to start seeing dashboard insights.")


# ----------------------------
# CARDS PAGE
# ----------------------------
elif page == "Cards":
    st.markdown('<div class="section-title">Cards</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        card_nickname = st.text_input("Card Nickname", placeholder="Chase Freedom")
        bank_name = st.text_input("Bank Name", placeholder="Chase")
    with col2:
        card_type = st.selectbox("Card Type", ["Credit", "Debit"])
        last4 = st.text_input("Last 4 Digits", max_chars=4, placeholder="4821")

    if st.button("Add Card"):
        if card_nickname.strip() and bank_name.strip() and last4.strip():
            add_card(user_id, card_nickname, bank_name, card_type, last4)
            st.success("Card added successfully.")
            st.rerun()
        else:
            st.warning("Please fill all fields.")

    st.markdown('<div class="section-title">Saved Cards</div>', unsafe_allow_html=True)

    if cards:
        for card in cards:
            st.markdown(
                f"<div class='card-box'>"
                f"💳 <strong>{card[1]}</strong><br>"
                f"Bank: {card[2]}<br>"
                f"Type: {card[3]}<br>"
                f"Last 4: **** {card[4]}"
                f"</div>",
                unsafe_allow_html=True
            )
    else:
        st.info("No cards added yet.")


# ----------------------------
# TRANSACTIONS PAGE
# ----------------------------
elif page == "Transactions":
    st.markdown('<div class="section-title">Transactions</div>', unsafe_allow_html=True)

    if cards:
        card_options = {f"{c[1]} - ****{c[4]}": c[0] for c in cards}

        col1, col2 = st.columns(2)
        with col1:
            selected_card_label = st.selectbox("Select Card", list(card_options.keys()), key="add_card_select")
            merchant = st.text_input("Merchant Name", placeholder="Uber, Starbucks, Amazon...")
            notes = st.text_input("Notes", placeholder="optional")
        with col2:
            amount = st.number_input("Amount", min_value=0.0, step=1.0)
            transaction_date = st.date_input("Transaction Date", value=date.today())

        if st.button("Add Transaction"):
            if merchant.strip() and amount > 0:
                category = detect_category(merchant)
                card_id = card_options[selected_card_label]
                add_transaction(
                    user_id=user_id,
                    card_id=card_id,
                    merchant=merchant,
                    amount=amount,
                    category=category,
                    transaction_date=transaction_date.strftime("%Y-%m-%d"),
                    notes=notes
                )
                st.success(f"Transaction added under {category}.")
                st.rerun()
            else:
                st.warning("Enter merchant name and amount.")
    else:
        st.warning("Add a card first from the Cards section.")

    st.markdown('<div class="section-title">Filter Transactions</div>', unsafe_allow_html=True)

    filtered_df = tx_df.copy()
    if not filtered_df.empty:
        f1, f2, f3 = st.columns(3)

        with f1:
            search_merchant = st.text_input("Search Merchant")
        with f2:
            category_options = ["All"] + sorted(filtered_df["category"].unique().tolist())
            selected_category = st.selectbox("Filter by Category", category_options)
        with f3:
            card_options_filter = ["All"] + sorted(filtered_df["card"].unique().tolist())
            selected_card_filter = st.selectbox("Filter by Card", card_options_filter)

        date_col1, date_col2 = st.columns(2)
        with date_col1:
            min_date = pd.to_datetime(filtered_df["transaction_date"]).min().date()
            start_date = st.date_input("Start Date", value=min_date)
        with date_col2:
            max_date = pd.to_datetime(filtered_df["transaction_date"]).max().date()
            end_date = st.date_input("End Date", value=max_date)

        if search_merchant.strip():
            filtered_df = filtered_df[filtered_df["merchant"].str.contains(search_merchant, case=False, na=False)]

        if selected_category != "All":
            filtered_df = filtered_df[filtered_df["category"] == selected_category]

        if selected_card_filter != "All":
            filtered_df = filtered_df[filtered_df["card"] == selected_card_filter]

        filtered_df["transaction_date"] = pd.to_datetime(filtered_df["transaction_date"])
        filtered_df = filtered_df[
            (filtered_df["transaction_date"].dt.date >= start_date) &
            (filtered_df["transaction_date"].dt.date <= end_date)
        ]
        filtered_df["transaction_date"] = filtered_df["transaction_date"].dt.strftime("%Y-%m-%d")

    st.markdown('<div class="section-title">Transaction History</div>', unsafe_allow_html=True)

    if not filtered_df.empty:
        st.dataframe(filtered_df.drop(columns=["card_id"]), use_container_width=True)
    else:
        st.info("No transactions match the filters.")

    if not tx_df.empty and cards:
        st.markdown('<div class="section-title">Edit or Delete Transaction</div>', unsafe_allow_html=True)

        card_options = {f"{c[1]} - ****{c[4]}": c[0] for c in cards}
        reverse_card_options = {v: k for k, v in card_options.items()}

        tx_options = {
            f"#{row['id']} | {row['transaction_date']} | {row['merchant']} | ${row['amount']:.2f}": row["id"]
            for _, row in tx_df.iterrows()
        }

        selected_tx_label = st.selectbox("Select Transaction", list(tx_options.keys()))
        selected_tx_id = tx_options[selected_tx_label]
        selected_row = tx_df[tx_df["id"] == selected_tx_id].iloc[0]

        e1, e2 = st.columns(2)
        with e1:
            edit_card_label = st.selectbox(
                "Edit Card",
                list(card_options.keys()),
                index=list(card_options.keys()).index(reverse_card_options[selected_row["card_id"]])
            )
            edit_merchant = st.text_input("Edit Merchant", value=selected_row["merchant"])
            edit_notes = st.text_input("Edit Notes", value=selected_row["notes"])
        with e2:
            edit_amount = st.number_input("Edit Amount", min_value=0.0, value=float(selected_row["amount"]), step=1.0)
            edit_date = st.date_input("Edit Date", value=pd.to_datetime(selected_row["transaction_date"]).date())

        b1, b2 = st.columns(2)

        with b1:
            if st.button("Update Transaction"):
                if edit_merchant.strip() and edit_amount > 0:
                    edit_category = detect_category(edit_merchant)
                    update_transaction(
                        tx_id=selected_tx_id,
                        card_id=card_options[edit_card_label],
                        merchant=edit_merchant,
                        amount=edit_amount,
                        category=edit_category,
                        transaction_date=edit_date.strftime("%Y-%m-%d"),
                        notes=edit_notes
                    )
                    st.success("Transaction updated.")
                    st.rerun()
                else:
                    st.warning("Merchant and amount are required.")

        with b2:
            if st.button("Delete Transaction"):
                delete_transaction(selected_tx_id)
                st.success("Transaction deleted.")
                st.rerun()
    elif tx_df.empty:
        st.info("No transactions yet.")


# ----------------------------
# REPORTS PAGE
# ----------------------------
elif page == "Reports":
    st.markdown('<div class="section-title">Reports</div>', unsafe_allow_html=True)

    if not tx_df.empty:
        report_df = tx_df.drop(columns=["card_id"])
        csv = report_df.to_csv(index=False).encode("utf-8")

        st.download_button(
            "Download CSV Report",
            data=csv,
            file_name="smart_budget_report.csv",
            mime="text/csv"
        )

        st.dataframe(report_df, use_container_width=True)

        st.markdown('<div class="section-title">Summary</div>', unsafe_allow_html=True)
        total_spending = float(tx_df["amount"].sum())
        total_transactions = len(tx_df)
        avg_transaction = total_spending / total_transactions if total_transactions > 0 else 0

        r1, r2, r3 = st.columns(3)
        r1.metric("Total Transactions", total_transactions)
        r2.metric("Total Spending", f"${total_spending:,.2f}")
        r3.metric("Average Transaction", f"${avg_transaction:,.2f}")

    else:
        st.info("No transactions available to export.")


st.markdown("---")
st.markdown('<div class="small-note">Smart Budget AI • Login, saved data, savings goal, budget limits, filters, insights, and reports.</div>', unsafe_allow_html=True)