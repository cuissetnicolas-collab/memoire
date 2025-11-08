import pandas as pd
import numpy as np
from io import BytesIO
import streamlit as st
from dateutil.relativedelta import relativedelta
import calendar

# ============================
# 🔐 AUTHENTIFICATION
# ============================
if "login" not in st.session_state:
    st.session_state["login"] = False
if "username" not in st.session_state:
    st.session_state["username"] = ""
if "name" not in st.session_state:
    st.session_state["name"] = ""

def login(username, password):
    users = {
        "aurore": {"password": "12345", "name": "Aurore Demoulin"},
        "laure.froidefond": {"password": "Laure Froidefond"},
        "Bruno": {"password": "Toto1963$", "name": "Toto El Gringo"},
    }
    if username in users and password == users[username]["password"]:
        st.session_state["login"] = True
        st.session_state["username"] = username
        st.session_state["name"] = users[username]["name"]
        st.success(f"Bienvenue {st.session_state['name']} 👋")
    else:
        st.error("❌ Identifiants incorrects")

if not st.session_state["login"]:
    st.title("🔑 Connexion espace expert-comptable")
    username_input = st.text_input("Identifiant")
    password_input = st.text_input("Mot de passe", type="password")
    if st.button("Connexion"):
        login(username_input, password_input)
    st.stop()

# ============================
# 🔓 Déconnexion
# ============================
if st.sidebar.button("Déconnexion"):
    st.session_state["login"] = False
    st.session_state["username"] = ""
    st.session_state["name"] = ""
    st.success("Vous êtes déconnecté(e).")
    st.stop()

# ============================
# ⚙️ Application principale
# ============================

st.title("📘 Génération des écritures analytiques")

uploaded_file = st.file_uploader("Importe ton fichier Excel des ventes", type=["xlsx"])

if uploaded_file:
    df = pd.read_excel(uploaded_file)

    # Vérification des colonnes nécessaires
    required_cols = ["ISBN", "Famille", "Vente", "Remise", "Retour"]
    if not all(col in df.columns for col in required_cols):
        st.error(f"⚠️ Le fichier doit contenir les colonnes suivantes : {', '.join(required_cols)}")
        st.stop()

    # Demande de la date
    date_input = st.date_input("Date des écritures")
    date_reprise = date_input + relativedelta(months=6)

    lignes = []

    for _, row in df.iterrows():
        isbn = str(row["ISBN"])
        famille = row["Famille"]
        vente = float(row["Vente"])
        remise = float(row["Remise"])
        retour = float(row["Retour"])

        # --- CA brut ---
        if vente != 0:
            lignes.append({
                "Date": date_input,
                "Journal": "VT",
                "Compte": "707000000",
                "Libelle": f"VENTES {famille.upper()} {calendar.month_name[date_input.month].upper()} {date_input.year}",
                "Famille analytique": famille,
                "ISBN": isbn,
                "Débit": 0,
                "Crédit": vente
            })

        # --- Remises libraires ---
        if remise != 0:
            lignes.append({
                "Date": date_input,
                "Journal": "VT",
                "Compte": "709000000",
                "Libelle": f"VENTES {famille.upper()} {calendar.month_name[date_input.month].upper()} {date_input.year} - Remises libraires",
                "Famille analytique": famille,
                "ISBN": isbn,
                "Débit": remise,
                "Crédit": 0
            })

        # --- Retours (toujours négatifs dans le fichier) ---
        if retour != 0:
            lignes.append({
                "Date": date_input,
                "Journal": "VT",
                "Compte": "709100000",
                "Libelle": f"VENTES {famille.upper()} {calendar.month_name[date_input.month].upper()} {date_input.year} - Retours",
                "Famille analytique": famille,
                "ISBN": isbn,
                "Débit": abs(retour),
                "Crédit": 0
            })

        # --- Provision retours (6 mois après) ---
        provision = abs(retour) * 0.1
        if provision != 0:
            lignes.append({
                "Date": date_reprise,
                "Journal": "VT",
                "Compte": "681000000",
                "Libelle": f"VENTES {famille.upper()} {calendar.month_name[date_input.month].upper()} {date_input.year} - Provision retours",
                "Famille analytique": famille,
                "ISBN": isbn,
                "Débit": provision,
                "Crédit": 0
            })
            lignes.append({
                "Date": date_reprise,
                "Journal": "VT",
                "Compte": "781000000",
                "Libelle": f"VENTES {famille.upper()} {calendar.month_name[date_input.month].upper()} {date_input.year} - Reprise provision",
                "Famille analytique": famille,
                "ISBN": isbn,
                "Débit": 0,
                "Crédit": provision
            })

    df_final = pd.DataFrame(lignes)

    # --- Regroupement par date pour équilibrer avec le 411 ---
    result = []
    for date, group in df_final.groupby("Date"):
        total_debit = group["Débit"].sum()
        total_credit = group["Crédit"].sum()
        ecart = round(total_debit - total_credit, 2)

        result.append(group)

        if ecart != 0:
            # Ajoute la contrepartie client 411
            result.append(pd.DataFrame([{
                "Date": date,
                "Journal": "VT",
                "Compte": "411100000",
                "Libelle": f"VENTES CLIENTS {calendar.month_name[date.month].upper()} {date.year}",
                "Famille analytique": "",
                "ISBN": "",
                "Débit": max(0, -ecart),
                "Crédit": max(0, ecart)
            }]))

    df_final = pd.concat(result, ignore_index=True)

    st.success("✅ Écritures générées et équilibrées")
    st.dataframe(df_final)

    # --- Vérification de l'équilibre global ---
    total_debit = df_final["Débit"].sum()
    total_credit = df_final["Crédit"].sum()
    st.write(f"💰 Total Débit : {total_debit:,.2f} | Total Crédit : {total_credit:,.2f}")
    st.write(f"⚖️ Écart : {round(total_debit - total_credit, 2)}")

    # --- Export Excel ---
    output = BytesIO()
    df_final.to_excel(output, index=False, sheet_name="Ecritures")
    st.download_button(
        label="📥 Télécharger le fichier d’écritures équilibrées",
        data=output.getvalue(),
        file_name="ecritures_equilibrees.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
