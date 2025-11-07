import streamlit as st
import pandas as pd
from io import BytesIO

# =====================
# INFO AUTEUR
# =====================
st.set_page_config(page_title="Outil Provisions", page_icon="📚")
st.sidebar.markdown("**Auteur : Nicolas CUISSET**")

# =====================
# 🔐 AUTHENTIFICATION
# =====================
if "login" not in st.session_state:
    st.session_state["login"] = False
if "page" not in st.session_state:
    st.session_state["page"] = "Accueil"

def login(username, password):
    users = {
        "aurore": {"password": "12345", "name": "Aurore Demoulin"},
        "laure.froidefond": {"password": "Laure2019$", "name": "Laure Froidefond"},
        "Bruno": {"password": "Toto1963$", "name": "Toto El Gringo"},
        "Manana": {"password": "193827", "name": "Manana"}
    }
    if username in users and password == users[username]["password"]:
        st.session_state["login"] = True
        st.session_state["username"] = username
        st.session_state["name"] = users[username]["name"]
        st.session_state["page"] = "Accueil"
        st.success(f"Bienvenue {st.session_state['name']} 👋")
        st.rerun()
    else:
        st.error("❌ Identifiants incorrects")

if not st.session_state["login"]:
    st.title("🔑 Connexion espace expert-comptable")
    username_input = st.text_input("Identifiant")
    password_input = st.text_input("Mot de passe", type="password")
    if st.button("Connexion"):
        login(username_input, password_input)
    st.stop()

st.sidebar.success(f"👤 {st.session_state['name']}")

# =====================
# ACCUEIL
# =====================
st.title("📂 Gestion des Provisions")
st.markdown("""
Cet outil permet :
- d'importer vos ventes par ISBN
- de calculer la provision (10% TTC à 5,5%)
- de générer l'écriture du mois et la reprise différée 6 mois plus tard
""")

# =====================
# IMPORT FICHIER
# =====================
fichier = st.file_uploader("Sélectionnez votre fichier Excel", type=["xlsx"])
if fichier:
    try:
        df = pd.read_excel(fichier)
        df.columns = df.columns.str.strip()
        
        # Vérification colonnes
        required_cols = ["ISBN", "Vente", "Date"]
        if not all(col in df.columns for col in required_cols):
            st.error("⚠️ Le fichier doit contenir les colonnes suivantes : ISBN, Vente, Date")
        else:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            df["Vente"] = pd.to_numeric(df["Vente"], errors="coerce").fillna(0)
            st.success(f"✅ Fichier chargé : {df.shape[0]} lignes")
            st.dataframe(df.head())

            # =====================
            # CALCUL PROVISION
            # =====================
            tva = 5.5 / 100
            provision_pct = 10 / 100

            # TTC
            df["Vente_TTC"] = df["Vente"] * (1 + tva)
            # Provision
            df["Provision"] = df["Vente_TTC"] * provision_pct

            # Génération écriture du mois
            df["Mois_Ecriture"] = df["Date"].dt.to_period("M").dt.to_timestamp()
            df["Mois_Reprise"] = df["Mois_Ecriture"] + pd.DateOffset(months=6)

            # Création dataframe final avec deux écritures
            df_ecritures = pd.concat([
                df.assign(Type="Provision"),
                df.assign(Date=df["Mois_Reprise"], Type="Reprise")
            ], ignore_index=True)[["ISBN", "Date", "Type", "Provision"]].sort_values("Date")

            st.subheader("📋 Écritures générées")
            st.dataframe(df_ecritures)

            # Téléchargement Excel
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df_ecritures.to_excel(writer, index=False, sheet_name="Provisions")
            buffer.seek(0)
            st.download_button("📥 Télécharger les écritures", buffer, file_name="Ecritures_Provisions.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    except Exception as e:
        st.error(f"❌ Erreur lors de l'importation : {e}")
