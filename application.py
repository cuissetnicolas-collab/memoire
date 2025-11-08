import pandas as pd
import numpy as np
from io import BytesIO
import streamlit as st
from dateutil.relativedelta import relativedelta
import calendar
from datetime import datetime, date

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
# 🔓 Déconnexion
# ============================
if st.sidebar.button("Déconnexion"):
    st.session_state["login"] = False
    st.session_state["username"] = ""
    st.session_state["name"] = ""
    st.success("Vous êtes déconnecté(e).")
    st.stop()

# ============================
# 📊 Interface principale
# ============================
st.title("📊 Générateur d'écritures analytiques - BLDD (vérif. d'équilibre)")

fichier_entree = st.file_uploader("📂 Importer le fichier Excel BLDD", type=["xlsx"])
date_ecriture = st.date_input("📅 Date d'écriture", value=date.today())
journal = st.text_input("📒 Journal", value="VT")
libelle_base = st.text_input("📝 Libellé", value="VENTES BLDD")
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

# Paramètres commissions
com_distribution_total = st.number_input("Montant total commissions distribution", value=1000.00, format="%.2f")
com_diffusion_total = st.number_input("Montant total commissions diffusion", value=500.00, format="%.2f")

# ============================
# 🧮 Traitement
# ============================
def last_day_of_month(dt: date) -> date:
    return dt.replace(day=calendar.monthrange(dt.year, dt.month)[1])

def repartir_commissions(montants, total):
    if montants.sum() == 0:
        return pd.Series([0] * len(montants))
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

if fichier_entree is not None:
    # lecture et nettoyage
    df = pd.read_excel(fichier_entree, header=9, dtype={"ISBN": str})
    df.columns = df.columns.str.strip()
    df = df.dropna(subset=["ISBN"]).copy()
    df["ISBN"] = (df["ISBN"].astype(str).str.strip()
                  .str.replace(r"\.0$", "", regex=True)
                  .str.replace("-", "", regex=False)
                  .str.replace(" ", "", regex=False))
    for c in ["Vente", "Retour", "Net", "Facture"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).round(2)

    # commissions
    df["Commission_distribution"] = repartir_commissions(df["Vente"], com_distribution_total)
    df["Commission_diffusion"] = repartir_commissions(df["Net"], com_diffusion_total)

    # construction des lignes (on stocke Date (string) ET Date_dt (datetime) pour faciliter les calculs)
    ecritures = []
    def add_ligne(compte, libelle, debit, credit, date_ligne=None, isbn_val=""):
        if date_ligne is None:
            date_ligne = pd.to_datetime(date_ecriture)
        date_dt = pd.to_datetime(date_ligne)
        date_str = date_dt.strftime("%d/%m/%Y")
        ecritures.append({
            "Date": date_str,
            "Date_dt": date_dt,
            "Journal": journal,
            "Compte": compte,
            "Libelle": libelle,
            "Famille analytique": famille_analytique,
            "ISBN": isbn_val,
            "Débit": round(float(debit), 2),
            "Crédit": round(float(credit), 2)
        })

    # générer les écritures analytiques par ISBN (sans 411 ni TVA pour l'instant)
    for _, r in df.iterrows():
        isbn = r["ISBN"]

        # CA brut (au crédit)
        add_ligne(compte_ca, f"{libelle_base} - CA brut", 0.0, r["Vente"], date_ligne=date_ecriture, isbn_val=isbn)

        # Retours : le fichier contient normalement des valeurs négatives → on met toujours le montant au débit (positif)
        if r["Retour"] != 0:
            retour_val = abs(r["Retour"])
            add_ligne(compte_retour, f"{libelle_base} - Retours", retour_val, 0.0, date_ligne=date_ecriture, isbn_val=isbn)

        # Remises libraires : respect du signe (positif -> débit ; négatif -> crédit)
        remise_val = r["Net"] - r["Facture"]
        if remise_val != 0:
            if remise_val > 0:
                add_ligne(compte_remise, f"{libelle_base} - Remises libraires", remise_val, 0.0, date_ligne=date_ecriture, isbn_val=isbn)
            else:
                add_ligne(compte_remise, f"{libelle_base} - Remises libraires (ajustement)", 0.0, abs(remise_val), date_ligne=date_ecriture, isbn_val=isbn)

        # Commissions distribution & diffusion (au débit)
        if r["Commission_distribution"] != 0:
            add_ligne(compte_com_dist, f"{libelle_base} - Com. distribution", r["Commission_distribution"], 0.0, date_ligne=date_ecriture, isbn_val=isbn)
        if r["Commission_diffusion"] != 0:
            add_ligne(compte_com_diff, f"{libelle_base} - Com. diffusion", r["Commission_diffusion"], 0.0, date_ligne=date_ecriture, isbn_val=isbn)

        # Provision retours (au débit)
        provision_isbn = round(r["Vente"] * 1.055 * 0.10, 2)
        if provision_isbn != 0:
            add_ligne(compte_provision, f"{libelle_base} - Provision retours", provision_isbn, 0.0, date_ligne=date_ecriture, isbn_val=isbn)

        # Reprise 6 mois plus tard (au crédit) — ligne par ISBN
        date_reprise = last_day_of_month(date_ecriture + relativedelta(months=6))
        if provision_isbn != 0:
            add_ligne(compte_reprise, f"{libelle_base} - Reprise provision", 0.0, provision_isbn, date_ligne=date_reprise, isbn_val=isbn)

    # 1) On crée un DataFrame temporaire à partir des écritures actuelles (sans 411 ni TVA)
    df_tmp = pd.DataFrame(ecritures)

    if df_tmp.empty:
        st.warning("Aucune écriture générée (données vides après import).")
        st.stop()

    # 2) Pour chaque date distincte, calculer l'écart et ajouter une seule ligne 411 qui équilibre cette date
    dates_uniques = df_tmp["Date_dt"].dt.normalize().unique()
    for dt in dates_uniques:
        df_date = df_tmp[df_tmp["Date_dt"].dt.normalize() == pd.to_datetime(dt).normalize()]
        total_debit = df_date["Débit"].sum()
        total_credit = df_date["Crédit"].sum()
        # diff = total_debit - total_credit ; si >0 -> créditer 411 ; si <0 -> débiter 411
        diff = round(total_debit - total_credit, 2)
        if diff > 0:
            # Débit > Crédit → on crédite 411 pour équilibrer
            add_ligne(compte_client, f"{libelle_base} - Contrepartie client", 0.0, diff, date_ligne=dt)
        elif diff < 0:
            # Crédit > Débit → on débite 411 pour équilibrer
            add_ligne(compte_client, f"{libelle_base} - Contrepartie client", abs(diff), 0.0, date_ligne=dt)
        # si diff == 0 : pas besoin d'ajouter 411

    # 3) Maintenant on reconstitue le df_final incluant les 411
    df_final = pd.DataFrame(ecritures)

    # 4) On ajoute les lignes TVA (globales à la date d'écriture)
    ca_net_total = df["Facture"].sum()
    com_total = df["Commission_distribution"].sum() + df["Commission_diffusion"].sum()
    tva_collectee = round(ca_net_total * 0.055, 2)
    tva_com = round(com_total * 0.055, 2)

    lignes_tva = []
    if tva_collectee != 0:
        lignes_tva.append({
            "Date": pd.to_datetime(date_ecriture).strftime("%d/%m/%Y"),
            "Date_dt": pd.to_datetime(date_ecriture),
            "Journal": journal,
            "Compte": compte_tva_collectee,
            "Libelle": f"{libelle_base} - TVA collectée",
            "Famille analytique": famille_analytique,
            "ISBN": "",
            "Débit": 0.0,
            "Crédit": tva_collectee
        })
    if tva_com != 0:
        lignes_tva.append({
            "Date": pd.to_datetime(date_ecriture).strftime("%d/%m/%Y"),
            "Date_dt": pd.to_datetime(date_ecriture),
            "Journal": journal,
            "Compte": compte_tva_com,
            "Libelle": f"{libelle_base} - TVA déductible commissions",
            "Famille analytique": famille_analytique,
            "ISBN": "",
            "Débit": tva_com,
            "Crédit": 0.0
        })
    if lignes_tva:
        df_final = pd.concat([df_final, pd.DataFrame(lignes_tva)], ignore_index=True)

    # 5) Vérification d'équilibre par date ET global
    df_final["Date_dt"] = pd.to_datetime(df_final["Date_dt"])
    summary = (df_final.groupby(df_final["Date_dt"].dt.strftime("%d/%m/%Y"))
               .agg(Total_Débit=("Débit", "sum"), Total_Crédit=("Crédit", "sum"))
               .reset_index()
               .rename(columns={"Date_dt": "Date"}))
    summary["Diff"] = (summary["Total_Débit"] - summary["Total_Crédit"]).round(2)
    summary["Équilibré"] = summary["Diff"].abs() < 0.01  # tolérance centime

    total_debit_global = df_final["Débit"].sum()
    total_credit_global = df_final["Crédit"].sum()
    diff_global = round(total_debit_global - total_credit_global, 2)

    # Affichage résumé par date
    st.subheader("✅ Vérification d'équilibre par date")
    st.dataframe(summary.style.format({"Total_Débit":"{:,.2f}","Total_Crédit":"{:,.2f}","Diff":"{:,.2f}"}))

    # Message global
    if abs(diff_global) < 0.01:
        st.success(f"Toutes les écritures sont équilibrées — Total Débit = Total Crédit = {total_debit_global:,.2f} €")
    else:
        st.error(f"ÉCRITURES DÉSÉQUILIBRÉES → Écart global : {diff_global:,.2f} €. Le compte {compte_client} devrait solder chaque date.")
        # Montrer détail des écritures non équilibrées (par date)
        not_balanced = summary[~summary["Équilibré"]]
        if not_balanced.empty:
            st.info("Global non équilibré mais toutes les dates semblent équilibrées (vérifier arrondis/TVA).")
        else:
            st.warning("Dates non équilibrées (voir ci-dessous) :")
            st.dataframe(not_balanced.style.format({"Total_Débit":"{:,.2f}","Total_Crédit":"{:,.2f}","Diff":"{:,.2f}"}))

    # Aperçu des écritures finales
    display_df = df_final.copy()
    # afficher Date en dd/mm/YYYY (déjà formaté) et masquer Date_dt si souhaité
    display_df = display_df[["Date","Journal","Compte","Libelle","Famille analytique","ISBN","Débit","Crédit"]]
    st.subheader("👀 Aperçu des écritures générées")
    st.dataframe(display_df.style.format({"Débit":"{:,.2f}","Crédit":"{:,.2f}"}))

    # Export Excel
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
