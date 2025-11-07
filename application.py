import streamlit as st
import pandas as pd
import numpy as np
import re
from io import BytesIO

# =====================
# CONFIG PAGE
# =====================
st.set_page_config(page_title="Outil Provisions", page_icon="📊")
st.title("📊 Outil de calcul des provisions et reprises différées")
st.sidebar.markdown("**Auteur : Nicolas CUISSET**")

# =====================
# AUTHENTIFICATION
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
# PAGE ACCUEIL
# =====================
st.header("📂 Import et calcul des provisions")
st.markdown("""
⚠️ Le fichier Excel doit contenir les colonnes suivantes :
- `ISBN`  
- `Vente`  

La date est extraite automatiquement depuis la ligne 2 du fichier Excel.
""")

# =====================
# IMPORT FICHIER
# =====================
fichier_excel = st.file_uploader("Sélectionnez votre fichier Excel", type=["xlsx"])

if fichier_excel:
    try:
        # Lecture complète pour extraction date
        df_info = pd.read_excel(fichier_excel, header=None, nrows=2)
        ligne_info = str(df_info.iloc[1,0])
        match = re.search(r"DU\s+(\d{1,2}/\d{1,2}/\d{4})", ligne_info)
        if match:
            date_val = pd.to_datetime(match.group(1), dayfirst=True)
        else:
            st.error("⚠️ Impossible de trouver la date dans le fichier Excel (ligne 2).")
            st.stop()

        # Lecture des données à partir de la 3e ligne
        df = pd.read_excel(fichier_excel, header=0)
        df.columns = df.columns.str.strip()

        # Vérification des colonnes
        required_cols = ["ISBN", "Vente"]
        for col in required_cols:
            if col not in df.columns:
                st.error(f"⚠️ Le fichier doit contenir la colonne '{col}'")
                st.stop()

        # Ajout de la colonne Date
        df["Date"] = date_val

        st.success(f"✅ Fichier chargé : {df.shape[0]} lignes")
        st.dataframe(df.head())

        # =====================
        # CALCUL PROVISION
        # =====================
        taux_tva = 0.055
        taux_provision = 0.10

        # Calcul TTC
        df["Vente_TTC"] = df["Vente"] * (1 + taux_tva)
        df["Provision"] = df["Vente_TTC"] * taux_provision

        # Calcul reprise différée 6 mois
        df["Date_Reprise"] = df["Date"] + pd.DateOffset(months=6)
        df["Reprise"] = df["Provision"]  # même montant, 6 mois plus tard

        st.subheader("📋 Aperçu des provisions et reprises")
        st.dataframe(df[["ISBN","Vente","Vente_TTC","Provision","Date","Date_Reprise","Reprise"]])

        # =====================
        # TELECHARGEMENT
        # =====================
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Provisions")
        buffer.seek(0)

        st.download_button(
            "📥 Télécharger le fichier provisions",
            buffer,
            file_name="Provisions.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"❌ Erreur lors de l'importation : {e}")
