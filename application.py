import pandas as pd
import numpy as np
from io import BytesIO
import streamlit as st
from dateutil.relativedelta import relativedelta
import calendar

# ============================
# AUTHENTIFICATION
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
        "laure.froidefond": {"password": "Laure2019$", "name": "Laure Froidefond"},
        "Bruno": {"password": "Toto1963$", "name": "Toto El Gringo"}
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
# Déconnexion
# ============================
if st.sidebar.button("Déconnexion"):
    st.session_state["login"] = False
    st.session_state["username"] = ""
    st.session_state["name"] = ""
    st.success("Vous êtes déconnecté(e).")
    st.stop()

# ============================
# Interface utilisateur
# ============================
st.title("📊 Générateur d'écritures analytiques - BLDD")

# Import du fichier
fichier_entree = st.file_uploader("📂 Importer le fichier Excel BLDD", type=["xlsx"])
date_ecriture = st.date_input("📅 Date d'écriture")
journal = st.text_input("📒 Journal", value="VT")
libelle_base = st.text_input("📝 Libellé", value="VENTES BLDD")

# ✅ Saisie famille analytique
famille_analytique = st.text_input("🏷️ Famille analytique", value="EDITION")

# Comptes utilisés
compte_ca = "701100000"
compte_retour = "709000000"
compte_remise = "709100000"
compte_com_dist = "622800000"
compte_com_diff = "622800010"
compte_tva_collectee = "445710060"
compte_tva_com = "445660000"
compte_provision = "681000000"
compte_reprise = "781000000"
compte_client = "411100011"

# Saisie montants totaux commissions
com_distribution_total = st.number_input("Montant total commissions distribution", value=1000.00, format="%.2f")
com_diffusion_total = st.number_input("Montant total commissions diffusion", value=500.00, format="%.2f")

# Taux commissions
taux_dist = st.number_input("Taux distribution (%)", value=12.5) / 100
taux_diff = st.number_input("Taux diffusion (%)", value=9.0) / 100

# ============================
# Traitement
# ============================
if fichier_entree is not None:
    df = pd.read_excel(fichier_entree, header=9, dtype={"ISBN": str})
    df.columns = df.columns.str.strip()
    df = df.dropna(subset=["ISBN"]).copy()

    df["ISBN"] = (
        df["ISBN"].astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.replace("-", "", regex=False)
        .str.replace(" ", "", regex=False)
    )

    for c in ["Vente", "Retour", "Net", "Facture"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).round(2)

    # ============================
    # Calcul commissions
    # ============================
    def repartir_commissions(montants, total):
        raw = montants.copy()
        scaled = raw * (total / raw.sum())
        cents_floor = np.floor(scaled * 100).astype(int)
        remainders = (scaled * 100) - cents_floor
        diff = int(round(total * 100)) - cents_floor.sum()
        idx_sorted = np.argsort(-remainders.values)
        adjust = np.zeros(len(raw), dtype=int)
        if diff > 0:
            adjust[idx_sorted[:diff]] = 1
        elif diff < 0:
            adjust[idx_sorted[len(raw) + diff:]] = -1
        return (cents_floor + adjust) / 100.0

    df["Commission_distribution"] = repartir_commissions(df["Vente"], com_distribution_total)
    df["Commission_diffusion"] = repartir_commissions(df["Net"], com_diffusion_total)

    # ============================
    # Construction écritures par ISBN
    # ============================
    ecritures = []

    def last_day_of_month(date):
        return date.replace(day=calendar.monthrange(date.year, date.month)[1])

    for _, r in df.iterrows():
        isbn = r["ISBN"]

        def add_ligne(compte, libelle, debit, credit, date_ligne=None):
            ecritures.append({
                "Date": (date_ligne.strftime("%d/%m/%Y") if date_ligne else date_ecriture.strftime("%d/%m/%Y")),
                "Journal": journal,
                "Compte": compte,
                "Libelle": libelle,
                "Famille analytique": famille_analytique,
                "ISBN": isbn,
                "Débit": round(debit, 2),
                "Crédit": round(credit, 2)
            })

        # CA brut
        add_ligne(compte_ca, f"{libelle_base} - CA brut", 0.0, max(0, r["Vente"]))
        # Retours
        add_ligne(compte_retour, f"{libelle_base} - Retours", abs(r["Retour"]), 0.0)
        # Remises libraires
        remise = r["Net"] - r["Facture"]
        if remise != 0:
            add_ligne(compte_remise, f"{libelle_base} - Remises libraires",
                      0.0 if remise < 0 else remise,
                      abs(remise) if remise < 0 else 0.0)
        # Commissions
        add_ligne(compte_com_dist, f"{libelle_base} - Com. distribution", r["Commission_distribution"], 0.0)
        add_ligne(compte_com_diff, f"{libelle_base} - Com. diffusion", r["Commission_diffusion"], 0.0)
        # Provision et reprise
        provision_isbn = round(r["Vente"] * 1.055 * 0.10, 2)
        add_ligne(compte_provision, f"{libelle_base} - Provision retours", provision_isbn, 0.0)
        date_reprise = last_day_of_month(date_ecriture + relativedelta(months=6))
        add_ligne(compte_reprise, f"{libelle_base} - Reprise provision", 0.0, provision_isbn, date_ligne=date_reprise)
        add_ligne(compte_client, f"{libelle_base} - Contrepartie reprise", provision_isbn, 0.0, date_ligne=date_reprise)

    # ============================
    # TVA globale (mêmes colonnes)
    # ============================
    ca_net_total = df["Facture"].sum()
    com_total = df["Commission_distribution"].sum() + df["Commission_diffusion"].sum()
    tva_collectee = round(ca_net_total * 0.055, 2)
    tva_com = round(com_total * 0.055, 2)

    ecritures.append({
        "Date": date_ecriture.strftime("%d/%m/%Y"),
        "Journal": journal,
        "Compte": compte_tva_collectee,
        "Libelle": f"{libelle_base} - TVA collectée",
        "Famille analytique": famille_analytique,
        "ISBN": "",
        "Débit": 0.0,
        "Crédit": tva_collectee
    })
    ecritures.append({
        "Date": date_ecriture.strftime("%d/%m/%Y"),
        "Journal": journal,
        "Compte": compte_tva_com,
        "Libelle": f"{libelle_base} - TVA déductible commissions",
        "Famille analytique": famille_analytique,
        "ISBN": "",
        "Débit": tva_com,
        "Crédit": 0.0
    })

    df_final = pd.DataFrame(ecritures)

    # ============================
    # Export unique
    # ============================
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_final.to_excel(writer, index=False, sheet_name="Ecritures")
    buffer.seek(0)

    st.download_button(
        label="📥 Télécharger les écritures (Excel)",
        data=buffer,
        file_name="Ecritures_BLDD.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # Aperçu
    st.subheader("👀 Aperçu des écritures générées")
    st.dataframe(df_final)
