import streamlit as st
import pandas as pd
from io import BytesIO
from datetime import datetime, timedelta

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
        "Bruno": {"password": "Toto1963$", "name": "Toto El Gringo"}
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

# Page de connexion
if not st.session_state["login"]:
    st.title("🔑 Connexion espace expert-comptable")
    username_input = st.text_input("Identifiant")
    password_input = st.text_input("Mot de passe", type="password")
    if st.button("Connexion"):
        login(username_input, password_input)
    st.stop()

# Déconnexion
col1, col2 = st.columns([4, 1])
with col2:
    if st.button("🚪 Déconnexion"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.session_state["login"] = False
        st.success("Déconnecté avec succès.")
        st.stop()

# ============================================================
# 📁 IMPORT DU FICHIER
# ============================================================
st.title("📊 Génération des écritures analytiques (provisions retours)")

uploaded_file = st.file_uploader("Importer le fichier Excel", type=["xlsx"])
if uploaded_file is None:
    st.stop()

df = pd.read_excel(uploaded_file)
st.success("✅ Fichier importé avec succès")

# Vérification colonnes minimales
colonnes_attendues = {"ISBN", "Famille analytique", "Vente"}
if not colonnes_attendues.issubset(df.columns):
    st.error("❌ Le fichier doit contenir les colonnes : ISBN, Famille analytique, Vente")
    st.stop()

# ============================================================
# 🧮 TRAITEMENT
# ============================================================
date_saisie = st.date_input("📅 Date des écritures (fin de période)")
if not date_saisie:
    st.stop()

taux_tva = 5.5
taux_provision = 0.10

# Calcul du TTC et provision
df["Vente_TTC"] = df["Vente"] * (1 + taux_tva / 100)
df["Provision"] = df["Vente_TTC"] * taux_provision

# Date de reprise = 6 mois plus tard
date_reprise = date_saisie + timedelta(days=183)

# Liste d'écritures
ecritures = []

def add_ligne(date, journal, compte, libelle, famille, isbn, debit, credit):
    ecritures.append({
        "Date": date.strftime("%d/%m/%Y"),
        "Journal": journal,
        "Compte": compte,
        "Libellé": libelle,
        "Famille analytique": famille,
        "ISBN": isbn,
        "Débit": round(debit, 2),
        "Crédit": round(credit, 2)
    })

for _, r in df.iterrows():
    isbn = r["ISBN"]
    famille = r["Famille analytique"]
    vente = r["Vente"]
    vente_ttc = r["Vente_TTC"]
    provision = r["Provision"]

    # Comptes
    c_ventes = "707000000"
    c_tva = "445710000"
    c_provision = "681000000"
    c_reprise = "781000000"
    c_retour = "709000000"
    c_client = "411000000"

    # --- ÉCRITURE 1 : à la date saisie ---
    libelle = f"VENTES {famille.upper()} {date_saisie.strftime('%B %Y').upper()}"

    # Ventes HT
    add_ligne(date_saisie, "VT", c_ventes, f"{libelle} - CA HT", famille, isbn, 0, vente)
    # TVA
    add_ligne(date_saisie, "VT", c_tva, f"{libelle} - TVA collectée", famille, isbn, 0, vente * taux_tva / 100)
    # Dotation provision
    add_ligne(date_saisie, "VT", c_provision, f"{libelle} - Dotation provision retours", famille, isbn, provision, 0)
    # 411 : total TTC + provision
    total_411 = vente_ttc + provision
    add_ligne(date_saisie, "VT", c_client, f"{libelle} - Client", famille, isbn, total_411, 0)

    # --- ÉCRITURE 2 : reprise 6 mois plus tard ---
    libelle_r = f"REPRISE {famille.upper()} {date_reprise.strftime('%B %Y').upper()}"
    # Reprise provision
    add_ligne(date_reprise, "VT", c_reprise, f"{libelle_r} - Reprise provision", famille, isbn, provision, 0)
    # Retours (709 au débit)
    add_ligne(date_reprise, "VT", c_retour, f"{libelle_r} - Retours sur ventes", famille, isbn, provision, 0)
    # 411 contrepartie
    add_ligne(date_reprise, "VT", c_client, f"{libelle_r} - Client", famille, isbn, 0, provision * 2)

# ============================================================
# 📤 EXPORT & AFFICHAGE
# ============================================================
df_final = pd.DataFrame(ecritures)
st.subheader("Aperçu des écritures générées")
st.dataframe(df_final)

# Export Excel
output = BytesIO()
with pd.ExcelWriter(output, engine='openpyxl') as writer:
    df_final.to_excel(writer, index=False, sheet_name="Écritures")
st.download_button(
    label="📥 Télécharger les écritures Excel",
    data=output.getvalue(),
    file_name=f"ecritures_provision_retours_{date_saisie.strftime('%Y%m%d')}.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
