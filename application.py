import pandas as pd
import numpy as np
from io import BytesIO
import streamlit as st
from dateutil.relativedelta import relativedelta
import calendar

# ============================
# AUTHENTIFICATION (inchangée)
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

# Déconnexion
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
# convertir date_ecriture en pandas Timestamp pour faciliter les opérations
date_ecriture = st.date_input("📅 Date d'écriture")
date_ecriture = pd.Timestamp(date_ecriture)
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

# Taux commissions (si besoin)
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
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).round(2)
        else:
            df[c] = 0.0

    # ============================
    # Calcul commissions (répartition centimes)
    # ============================
    def repartir_commissions(montants, total):
        raw = montants.copy()
        s = raw.sum()
        if s == 0 or total == 0:
            return pd.Series([0.0]*len(raw), index=raw.index)
        scaled = raw * (total / s)
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
    # Construire écritures (incluant reprises datées)
    # ============================
    ecritures = []

    def last_day_of_month(ts):
        # ts attendu comme pd.Timestamp
        yr = ts.year
        mo = ts.month
        day = calendar.monthrange(yr, mo)[1]
        return pd.Timestamp(year=yr, month=mo, day=day)

    def add_ligne(compte, libelle, debit, credit, isbn_val="", date_ligne=None):
        date_use = pd.Timestamp(date_ligne) if date_ligne is not None else date_ecriture
        ecritures.append({
            "Date": date_use.strftime("%d/%m/%Y"),
            "Date_dt": date_use,  # champ auxiliaire pour tri/groupes
            "Journal": journal,
            "Compte": compte,
            "Libelle": libelle,
            "Famille analytique": famille_analytique,
            "ISBN": isbn_val,
            "Débit": round(float(debit), 2),
            "Crédit": round(float(credit), 2)
        })

    # boucle par ISBN
    for _, r in df.iterrows():
        isbn = r["ISBN"]

        # CA brut (crédit)
        add_ligne(compte_ca, f"{libelle_base} - CA brut", 0.0, r["Vente"], isbn_val=isbn)
        # Retours (débit)
        add_ligne(compte_retour, f"{libelle_base} - Retours", r["Retour"], 0.0, isbn_val=isbn)
        # Remises libraires (selon signe)
        remise = r.get("Net", 0.0) - r.get("Facture", 0.0)
        if remise != 0:
            if remise > 0:
                add_ligne(compte_remise, f"{libelle_base} - Remises libraires", remise, 0.0, isbn_val=isbn)
            else:
                add_ligne(compte_remise, f"{libelle_base} - Remises libraires", 0.0, abs(remise), isbn_val=isbn)
        # Commissions distribution & diffusion
        add_ligne(compte_com_dist, f"{libelle_base} - Com. distribution", r["Commission_distribution"], 0.0, isbn_val=isbn)
        add_ligne(compte_com_diff, f"{libelle_base} - Com. diffusion", r["Commission_diffusion"], 0.0, isbn_val=isbn)
        # Provision retours (681) à la date d'écriture
        provision_isbn = round(r["Vente"] * 1.055 * 0.10, 2)
        add_ligne(compte_provision, f"{libelle_base} - Provision retours", provision_isbn, 0.0, isbn_val=isbn)

        # Reprise 6 mois plus tard (781) : on crée la ligne datée
        date_reprise = last_day_of_month(date_ecriture + relativedelta(months=6))
        add_ligne(compte_reprise, f"{libelle_base} - Reprise provision", 0.0, provision_isbn, isbn_val=isbn, date_ligne=date_reprise)

    # ============================
    # Lignes globales TVA (même format, même tableau)
    # ============================
    ca_net_total = df["Facture"].sum()
    com_total = df["Commission_distribution"].sum() + df["Commission_diffusion"].sum()
    tva_collectee = round(ca_net_total * 0.055, 2)
    tva_com = round(com_total * 0.055, 2)

    add_ligne(compte_tva_collectee, f"{libelle_base} - TVA collectée", 0.0, tva_collectee, isbn_val="", date_ligne=date_ecriture)
    add_ligne(compte_tva_com, f"{libelle_base} - TVA déductible commissions", tva_com, 0.0, isbn_val="", date_ligne=date_ecriture)

    # transforme en DataFrame
    df_final = pd.DataFrame(ecritures)

    # ============================
    # AJOUT D'UNE SEULE LIGNE 411 PAR DATE (équilibrage par date)
    # ============================
    # on regroupe par date (champ Date_dt) et on calcule l'écart (Crédit - Débit)
    grp = df_final.groupby("Date_dt").agg({"Débit": "sum", "Crédit": "sum"}).reset_index()
    # pour chaque date où il y a un écart, on ajoute une ligne 411 pour équilibrer (sens approprié)
    for _, row in grp.iterrows():
        date_dt = row["Date_dt"]
        total_debit = row["Débit"]
        total_credit = row["Crédit"]
        diff = round(total_credit - total_debit, 2)  # positif => il manque un débit (on doit débiter 411), négatif => il manque un crédit
        if abs(diff) > 0.009:  # tolérance centime
            if diff > 0:
                # on doit ajouter une écriture au débit (411 débité)
                add_ligne(compte_client, f"{libelle_base} - Contrepartie client", diff, 0.0, isbn_val="", date_ligne=date_dt)
            else:
                # diff < 0 : il manque un crédit -> on crédite 411
                add_ligne(compte_client, f"{libelle_base} - Contrepartie client", 0.0, abs(diff), isbn_val="", date_ligne=date_dt)

    # recomposer le df final et trier par date
    df_final = pd.DataFrame(ecritures)
    df_final["Date_dt"] = pd.to_datetime(df_final["Date_dt"])
    df_final = df_final.sort_values(["Date_dt", "Compte", "ISBN"]).drop(columns=["Date_dt"]).reset_index(drop=True)

    # vérif équilibre global (optionnel)
    total_debit = df_final["Débit"].sum()
    total_credit = df_final["Crédit"].sum()
    if abs(total_debit - total_credit) > 0.01:
        st.warning(f"⚠️ Attention : écritures globalement déséquilibrées (Débit={total_debit:.2f} / Crédit={total_credit:.2f})")
    else:
        st.success("✅ Écritures équilibrées par date (et globalement).")

    # ============================
    # Export Excel trié
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

    # Aperçu final
    st.subheader("👀 Aperçu des écritures générées (triées par date)")
    st.dataframe(df_final)
