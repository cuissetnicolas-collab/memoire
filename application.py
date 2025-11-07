import streamlit as st
import pandas as pd
from io import BytesIO

# ============================================================
# 🔐 AUTHENTIFICATION
# ============================================================
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
        st.experimental_rerun()
    else:
        st.error("❌ Identifiants incorrects")

if not st.session_state["login"]:
    st.title("🔑 Connexion espace expert-comptable")
    username_input = st.text_input("Identifiant")
    password_input = st.text_input("Mot de passe", type="password")
    if st.button("Connexion"):
        login(username_input, password_input)
    st.stop()

# ============================================================
# 📑 MENU PRINCIPAL
# ============================================================
pages = [
    "Accueil",
    "DATA EDITION",
    "SOCLE EDITION",
    "REPARTITION CHARGES FIXES",
    "VISION EDITION",
    "ISBN VIEW",
    "ROYALTIES EDITION",
    "RETURNS EDITION",
    "PROVISIONS EDITION",  # ← Nouvelle page
    "CASH EDITION",
    "SYNTHESE GLOBALE"
]

page = st.sidebar.selectbox("📘 Navigation", pages)

# ============================================================
# 🏠 PAGE ACCUEIL
# ============================================================
if page == "Accueil":
    st.title("Bienvenue dans l'application comptable 📊")
    st.write("Choisissez une section dans le menu de gauche.")

# ============================================================
# 📘 PROVISIONS EDITION
# ============================================================
elif page == "PROVISIONS EDITION":
    st.header("📘 PROVISIONS EDITION - Génération automatique des écritures de provisions et reprises différées")

    # Import du fichier Excel
    fichier_provisions = st.file_uploader("📂 Importez votre fichier de ventes (Excel)", type=["xlsx"])
    if fichier_provisions:
        try:
            df = pd.read_excel(fichier_provisions)
            st.success(f"✅ Fichier chargé ({len(df)} lignes)")

            # Vérification des colonnes nécessaires
            colonnes_attendues = ["ISBN", "Vente", "Date"]
            if not all(col in df.columns for col in colonnes_attendues):
                st.error(f"⚠️ Le fichier doit contenir les colonnes suivantes : {', '.join(colonnes_attendues)}")
                st.stop()

            # =====================
            # PARAMÉTRAGE UTILISATEUR
            # =====================
            col1, col2, col3 = st.columns(3)
            with col1:
                mode_calcul = st.radio("Mode de calcul", ["TTC", "HT"])
            with col2:
                tva = st.number_input("Taux de TVA (%)", value=5.5, step=0.1) / 100
            with col3:
                taux_provision = st.number_input("Taux de provision (%)", value=10.0, step=0.5) / 100

            delai_reprise = st.slider("⏱️ Délai de reprise (mois)", 3, 12, 6, step=3)

            st.subheader("🔢 Comptes comptables")
            col1, col2, col3 = st.columns(3)
            with col1:
                compte_provision = st.text_input("Compte de provision (Crédit)", value="151000")
            with col2:
                compte_dotation = st.text_input("Compte de dotation (Débit)", value="681500")
            with col3:
                compte_reprise = st.text_input("Compte de reprise (Crédit)", value="781500")

            # =====================
            # CALCUL DES MONTANTS
            # =====================
            df["Vente_TTC"] = pd.to_numeric(df["Vente"], errors="coerce").fillna(0)
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

            if mode_calcul == "HT":
                df["Vente_HT"] = df["Vente_TTC"] / (1 + tva)
                base = df["Vente_HT"]
            else:
                base = df["Vente_TTC"]

            df["Provision"] = base * taux_provision
            df["Provision"] = df["Provision"].round(2)

            st.write("Aperçu du calcul :")
            st.dataframe(df.head())

            # =====================
            # GÉNÉRATION DES ÉCRITURES
            # =====================
            ecritures = []
            for _, row in df.iterrows():
                if pd.isna(row["Date"]):
                    continue
                date_base = row["Date"]
                montant = row["Provision"]
                isbn = str(row["ISBN"])

                # Écriture de constitution
                ecritures.append({
                    "Date": date_base,
                    "Compte_D": compte_dotation,
                    "Compte_C": compte_provision,
                    "Montant": montant,
                    "Libellé": f"Provision {isbn}"
                })

                # Écriture de reprise différée
                date_reprise = date_base + pd.DateOffset(months=delai_reprise)
                ecritures.append({
                    "Date": date_reprise,
                    "Compte_D": compte_provision,
                    "Compte_C": compte_reprise,
                    "Montant": montant,
                    "Libellé": f"Reprise provision {isbn}"
                })

            df_ecritures = pd.DataFrame(ecritures)
            df_ecritures = df_ecritures.sort_values("Date").reset_index(drop=True)

            # =====================
            # AFFICHAGE ET EXPORT
            # =====================
            st.success(f"✅ {len(df_ecritures)} écritures générées avec succès !")
            st.dataframe(df_ecritures)

            # Export Excel
            buffer = BytesIO()
            with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
                df_ecritures.to_excel(writer, index=False, sheet_name="Provisions")
            buffer.seek(0)

            st.download_button(
                "📥 Télécharger les écritures de provisions et reprises différées",
                buffer,
                file_name="Ecritures_Provisions.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        except Exception as e:
            st.error(f"❌ Erreur lors du traitement : {e}")
