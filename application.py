import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime

# ============================================================
# 🔐 AUTHENTIFICATION
# ============================================================
if "login" not in st.session_state:
    st.session_state["login"] = False

def check_credentials(username, password):
    return username == "admin" and password == "1234"

def login(username, password):
    if check_credentials(username, password):
        st.session_state["login"] = True
    else:
        st.error("Identifiants incorrects")

def logout():
    st.session_state["login"] = False

if not st.session_state["login"]:
    st.title("🔐 Connexion")
    username_input = st.text_input("Nom d'utilisateur")
    password_input = st.text_input("Mot de passe", type="password")
    if st.button("Se connecter"):
        login(username_input, password_input)
    st.stop()

# ============================================================
# 📁 INTERFACE PRINCIPALE
# ============================================================
st.title("📘 Génération des écritures analytiques")
st.button("Se déconnecter", on_click=logout)

uploaded_file = st.file_uploader("Importer le fichier Excel des ventes", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    # Vérification colonnes attendues
    colonnes_attendues = ["Famille", "ISBN", "Vente", "Retours", "Remises libraires"]
    if not all(col in df.columns for col in colonnes_attendues):
        st.error(f"Le fichier doit contenir les colonnes suivantes : {', '.join(colonnes_attendues)}")
        st.stop()

    # Saisie de la date (unique)
    date_saisie = st.date_input("Date des écritures (par ex. 30/04/2025)")

    # Conversion au format datetime
    date_saisie_str = pd.to_datetime(date_saisie).strftime("%d/%m/%Y")

    # Nettoyage et calculs
    df["Vente"] = df["Vente"].fillna(0)
    df["Retours"] = df["Retours"].fillna(0)
    df["Remises libraires"] = df["Remises libraires"].fillna(0)

    ecritures = []

    for _, row in df.iterrows():
        famille = row["Famille"]
        isbn = row["ISBN"]

        vente = row["Vente"]
        retours = abs(row["Retours"])  # toujours positifs au débit
        remises = row["Remises libraires"]

        # --- Écritures comptables ---
        # Vente
        if vente != 0:
            ecritures.append({
                "Date": date_saisie_str,
                "Journal": "VT",
                "Compte": "706000000",
                "Libelle": f"VENTES BLDD - Ventes {famille}",
                "Famille analytique": famille,
                "ISBN": isbn,
                "Débit": 0,
                "Crédit": vente
            })
        # Retours (débit)
        if retours != 0:
            ecritures.append({
                "Date": date_saisie_str,
                "Journal": "VT",
                "Compte": "709000000",
                "Libelle": f"VENTES BLDD - Retours {famille}",
                "Famille analytique": famille,
                "ISBN": isbn,
                "Débit": retours,
                "Crédit": 0
            })
        # Remises libraires (débit)
        if remises != 0:
            ecritures.append({
                "Date": date_saisie_str,
                "Journal": "VT",
                "Compte": "709700000",
                "Libelle": f"VENTES BLDD - Remises libraires {famille}",
                "Famille analytique": famille,
                "ISBN": isbn,
                "Débit": remises,
                "Crédit": 0
            })

    # Création du DataFrame des écritures
    df_ecritures = pd.DataFrame(ecritures)

    # Calcul du solde pour le compte 411 (contrepartie globale)
    total_debit = df_ecritures["Débit"].sum()
    total_credit = df_ecritures["Crédit"].sum()
    solde_411 = total_credit - total_debit

    df_ecritures.loc[len(df_ecritures)] = {
        "Date": date_saisie_str,
        "Journal": "VT",
        "Compte": "411100011",
        "Libelle": "VENTES BLDD - Contrepartie clients",
        "Famille analytique": "",
        "ISBN": "",
        "Débit": 0 if solde_411 > 0 else abs(solde_411),
        "Crédit": solde_411 if solde_411 > 0 else 0
    }

    # Vérification équilibre
    ecart = round(df_ecritures["Débit"].sum() - df_ecritures["Crédit"].sum(), 2)

    st.subheader("📊 Écritures générées")
    st.dataframe(df_ecritures)

    if ecart == 0:
        st.success("✅ Les écritures sont équilibrées.")
    else:
        st.error(f"⚠️ Les écritures ne sont pas équilibrées. Écart : {ecart} €")

    # Export Excel
    output = BytesIO()
    df_ecritures.to_excel(output, index=False, engine="openpyxl")
    output.seek(0)
    st.download_button("📥 Télécharger le fichier des écritures", output, file_name="ecritures_comptables.xlsx")
