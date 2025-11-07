import streamlit as st
import pandas as pd
import numpy as np
import re
from io import BytesIO
from datetime import timedelta

# =====================
# PAGE CONFIG
# =====================
st.set_page_config(page_title="Outil Provisions Édition", page_icon="📚")
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
st.title("📚 Outil de génération des provisions")
st.markdown("""
Cet outil permet de :
- Importer vos ventes par ISBN
- Calculer la provision à 10 % TTC
- Générer les écritures comptables avec reprise différée à 6 mois
⚠️ Le fichier Excel doit contenir les colonnes suivantes : **ISBN**, **Vente**.
""")

# =====================
# IMPORT FICHIER
# =====================
fichier_excel = st.file_uploader("Sélectionnez votre fichier Excel", type=["xlsx"])
if fichier_excel:
    try:
        df = pd.read_excel(fichier_excel, header=None)
        # Vérifier colonnes ISBN et Vente
        if df.shape[1] < 2:
            st.error("⚠️ Le fichier doit contenir au moins deux colonnes : ISBN et Vente")
        else:
            df.columns = ["ISBN","Vente"] + list(df.columns[2:])
            st.session_state["df_import"] = df[["ISBN","Vente"]].copy()
            st.success(f"✅ Fichier chargé : {df.shape[0]} lignes")
            st.dataframe(st.session_state["df_import"].head())

        # EXTRACTION DE LA DATE (ligne 2)
        try:
            ligne_info = pd.read_excel(fichier_excel, header=None).iloc[1,0]
            match = re.search(r"DU\s*(\d{1,2}/\d{1,2}/\d{4})", str(ligne_info), re.IGNORECASE)
            if match:
                date_debut = pd.to_datetime(match.group(1), dayfirst=True)
                st.session_state["date_vente"] = date_debut
                st.info(f"Date de vente détectée : {date_debut.strftime('%d/%m/%Y')}")
            else:
                st.error("⚠️ Impossible de trouver la date dans le fichier Excel (ligne 2).")
        except Exception as e:
            st.error(f"⚠️ Erreur lors de l'extraction de la date : {e}")

    except Exception as e:
        st.error(f"❌ Erreur lors de l'importation : {e}")

# =====================
# CALCUL PROVISION
# =====================
if "df_import" in st.session_state and "date_vente" in st.session_state:
    st.header("🧮 Calcul de la provision")
    df_calc = st.session_state["df_import"].copy()
    df_calc["Vente_TTC"] = df_calc["Vente"] * 1.055  # TTC 5,5%
    df_calc["Provision"] = df_calc["Vente_TTC"] * 0.10  # 10%
    
    st.dataframe(df_calc)

    # Écriture comptable
    st.subheader("📄 Génération des écritures comptables")
    ecritures = []

    for idx, row in df_calc.iterrows():
        isbn = row["ISBN"]
        montant = row["Provision"]
        date = st.session_state["date_vente"]

        # Écriture provision immédiate
        ecritures.append({
            "Date": date.strftime("%d/%m/%Y"),
            "Compte Débit": "411",
            "Compte Crédit": "781",
            "Montant": montant,
            "Libellé": f"Provision sur ventes ISBN {isbn}"
        })

        # Écriture reprise différée 6 mois
        date_reprise = date + pd.DateOffset(months=6)
        ecritures.append({
            "Date": date_reprise.strftime("%d/%m/%Y"),
            "Compte Débit": "781",
            "Compte Crédit": "411",
            "Montant": montant,
            "Libellé": f"Reprise provision 6 mois ISBN {isbn}"
        })

    df_ecritures = pd.DataFrame(ecritures)
    st.dataframe(df_ecritures)

    # Bouton téléchargement
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_ecritures.to_excel(writer, index=False, sheet_name="Provisions")
    buffer.seek(0)
    st.download_button(
        "📥 Télécharger les écritures comptables",
        buffer,
        file_name="Ecritures_Provisions.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
