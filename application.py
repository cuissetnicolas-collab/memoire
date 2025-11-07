import streamlit as st
import pandas as pd
from io import BytesIO
from dateutil.relativedelta import relativedelta
from datetime import datetime
import calendar

# ============================================================
# 🔐 AUTHENTIFICATION
# ============================================================
if "login" not in st.session_state:
    st.session_state["login"] = False

def login(username, password):
    users = {
        "aurore": {"password": "12345", "name": "Aurore Demoulin"},
        "laure.froidefond": {"password": "Laure2019$", "name": "Laure Froidefond"},
        "Bruno": {"password": "Toto1963$", "name": "Toto El Gringo"},
    }
    if username in users and password == users[username]["password"]:
        st.session_state["login"] = True
        st.session_state["username"] = username
        st.session_state["name"] = users[username]["name"]
        st.session_state["page"] = "Accueil"
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
# 🧭 MENU LATÉRAL
# ============================================================
st.sidebar.title("Menu")
st.sidebar.write(f"👋 Connecté en tant que **{st.session_state['name']}**")

if st.sidebar.button("Déconnexion"):
    st.session_state["login"] = False
    st.session_state["username"] = ""
    st.session_state["name"] = ""
    st.success("Vous êtes déconnecté(e).")
    st.stop()

# ============================================================
# ⚙️ PARAMÈTRES PRINCIPAUX
# ============================================================
st.title("📘 Génération des écritures analytiques - Provision retours BLDD")

uploaded_file = st.file_uploader("📂 Importer le fichier Excel des ventes par ISBN", type=["xlsx"])
if uploaded_file is None:
    st.info("Veuillez importer un fichier Excel pour continuer.")
    st.stop()

# Lecture du fichier
df = pd.read_excel(uploaded_file)

# Vérifications colonnes
colonnes_attendues = ["ISBN", "Titre", "Vente"]
for col in colonnes_attendues:
    if col not in df.columns:
        st.error(f"❌ Colonne manquante : {col}")
        st.stop()

# Entrée de la période
mois = st.selectbox("Mois de l'écriture", 
                    ["Janvier","Février","Mars","Avril","Mai","Juin",
                     "Juillet","Août","Septembre","Octobre","Novembre","Décembre"])
annee = st.number_input("Année", min_value=2020, max_value=2100, value=datetime.now().year)

# Calcul de la date de fin de mois
mois_num = list(calendar.month_name).index(mois.capitalize())
dernier_jour = calendar.monthrange(annee, mois_num)[1]
date_ecriture = datetime(annee, mois_num, dernier_jour)
date_reprise = (date_ecriture + relativedelta(months=6)).date()

# ============================================================
# 🧾 GÉNÉRATION DES ÉCRITURES
# ============================================================

journal = "VT"
famille_analytique = "EDITION"
libelle_base = f"VENTES BLDD {mois.upper()} {annee}"

compte_client = "411100011"
compte_ca = "701100000"
compte_commission = "622200000"
compte_tva_collectee = "445710060"
compte_tva_deductible = "445660000"
compte_provision = "681000000"
compte_reprise = "781000000"

ecritures = []

def add_ligne(compte, libelle, debit, credit, isbn="", date_ligne=None):
    ecritures.append({
        "Date": (date_ligne.strftime("%d/%m/%Y") if date_ligne else date_ecriture.strftime("%d/%m/%Y")),
        "Journal": journal,
        "Compte": compte,
        "Libelle": libelle,
        "Famille analytique": famille_analytique,
        "ISBN": isbn,
        "Débit": round(debit, 2),
        "Crédit": round(credit, 2),
    })

# Calcul des lignes analytiques
for _, r in df.iterrows():
    isbn = str(r["ISBN"])
    vente_ttc = float(r["Vente"])

    vente_ht = vente_ttc / 1.055
    commission_ttc = vente_ttc * 0.1
    commission_ht = commission_ttc / 1.2
    provision_isbn = commission_ht

    # CA brut
    add_ligne(compte_ca, f"{libelle_base} - CA brut", 0.0, vente_ht, isbn)
    # Commission
    add_ligne(compte_commission, f"{libelle_base} - Commissions", commission_ht, 0.0, isbn)
    # TVA collectée
    add_ligne(compte_tva_collectee, f"{libelle_base} - TVA collectée", 0.0, vente_ht * 0.055, isbn)
    # TVA déductible
    add_ligne(compte_tva_deductible, f"{libelle_base} - TVA déductible commissions", commission_ht * 0.2, 0.0, isbn)
    # Provision retours
    add_ligne(compte_provision, f"{libelle_base} - Provision retours", provision_isbn, 0.0, isbn)
    # Reprise 6 mois après
    add_ligne(compte_reprise, f"{libelle_base} - Reprise provision", 0.0, provision_isbn, isbn, date_reprise)
    add_ligne(compte_client, f"{libelle_base} - Contrepartie reprise", provision_isbn, 0.0, isbn, date_reprise)

df_final = pd.DataFrame(ecritures)

# Lignes globales TVA
total_ventes_ht = df["Vente"].sum() / 1.055
tva_collectee = total_ventes_ht * 0.055
tva_deductible = (df["Vente"].sum() * 0.1 / 1.2) * 0.2

df_glob = pd.DataFrame([
    {"Date": date_ecriture.strftime("%d/%m/%Y"), "Journal": journal, "Compte": compte_tva_collectee,
     "Libelle": f"{libelle_base} - TVA collectée", "Famille analytique": famille_analytique,
     "ISBN": "", "Débit": 0, "Crédit": round(tva_collectee, 2)},
    {"Date": date_ecriture.strftime("%d/%m/%Y"), "Journal": journal, "Compte": compte_tva_deductible,
     "Libelle": f"{libelle_base} - TVA déductible commissions", "Famille analytique": famille_analytique,
     "ISBN": "", "Débit": round(tva_deductible, 2), "Crédit": 0},
])

# ============================================================
# 📤 EXPORT & APERÇU
# ============================================================
st.divider()
st.subheader("📦 Export des écritures")

# Fusion + tri des écritures
df_total = pd.concat([df_final, df_glob], ignore_index=True)
df_total["Date_dt"] = pd.to_datetime(df_total["Date"], format="%d/%m/%Y")
df_total = df_total.sort_values("Date_dt").drop(columns=["Date_dt"])

# Export Excel
buffer = BytesIO()
with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
    df_total.to_excel(writer, index=False, sheet_name="Ecritures")
buffer.seek(0)

st.download_button(
    label="📥 Télécharger les écritures (Excel)",
    data=buffer,
    file_name="Ecritures_BLDD.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)

# Aperçu
st.subheader("👀 Aperçu des écritures générées")
st.dataframe(df_total)
