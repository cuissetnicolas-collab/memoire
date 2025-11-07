import pandas as pd
import numpy as np
from io import BytesIO
import streamlit as st
from pandas.tseries.offsets import MonthEnd

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

# Saisie montants totaux commissions et reprise provision
com_distribution_total = st.number_input("Montant total commissions distribution", value=1000.00, format="%.2f")
com_diffusion_total = st.number_input("Montant total commissions diffusion", value=500.00, format="%.2f")
provision_reprise = st.number_input("Montant de reprise de provision (6 mois)", value=0.0, format="%.2f")

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
            adjust[idx_sorted[len(raw) + diff :]] = -1
        return (cents_floor + adjust) / 100.0

    df["Commission_distribution"] = repartir_commissions(df["Vente"], com_distribution_total)
    df["Commission_diffusion"] = repartir_commissions(df["Net"], com_diffusion_total)

    # ============================
    # Construction écritures par ISBN
    # ============================
    ecritures = []

    for _, r in df.iterrows():
        isbn = r["ISBN"]
        def add_ligne(compte, libelle, debit, credit):
            ecritures.append({
                "Date": date_ecriture.strftime("%d/%m/%Y"),
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
        # Commissions distribution
        add_ligne(compte_com_dist, f"{libelle_base} - Com. distribution", r["Commission_distribution"], 0.0)
        # Commissions diffusion
        add_ligne(compte_com_diff, f"{libelle_base} - Com. diffusion", r["Commission_diffusion"], 0.0)
        # Provision retours (681)
        provision_isbn = round(r["Vente"] * 1.055 * 0.10, 2)
        add_ligne(compte_provision, f"{libelle_base} - Provision retours", provision_isbn, 0.0)

        # ➤ Reprise de provision 6 mois plus tard dans le compte 781
        if provision_isbn > 0:
            reprise_date = pd.to_datetime(date_ecriture) + MonthEnd(6)
            ecritures.append({
                "Date": reprise_date.strftime("%d/%m/%Y"),
                "Journal": journal,
                "Compte": compte_reprise,
                "Libelle": f"{libelle_base} - Reprise provision ISBN {isbn}",
                "Famille analytique": famille_analytique,
                "ISBN": isbn,
                "Débit": 0.0,
                "Crédit": provision_isbn
            })

    df_ecr = pd.DataFrame(ecritures)

    # ============================
    # Totaux globaux
    # ============================
    ca_net_total = df["Facture"].sum()
    com_total = df["Commission_distribution"].sum() + df["Commission_diffusion"].sum()
    tva_collectee = round(ca_net_total * 0.055, 2)
    tva_com = round(com_total * 0.055, 2)

    # ============================
    # Lignes globales
    # ============================
    lignes_globales = [
        {"Compte": compte_tva_collectee, "Libelle": f"{libelle_base} - TVA collectée", "Débit": 0.0, "Crédit": tva_collectee},
        {"Compte": compte_tva_com, "Libelle": f"{libelle_base} - TVA déductible commissions", "Débit": tva_com, "Crédit": 0.0},
        {"Compte": compte_client, "Libelle": f"{libelle_base} - Contrepartie reprise provision", "Débit": 0.0, "Crédit": provision_reprise},
        {"Compte": compte_reprise, "Libelle": f"{libelle_base} - Reprise provision globale", "Débit": provision_reprise, "Crédit": 0.0},
    ]

    df_glob = pd.DataFrame(lignes_globales)
    df_glob["Date"] = date_ecriture.strftime("%d/%m/%Y")
    df_glob["Journal"] = journal
    df_glob["Famille analytique"] = famille_analytique
    df_glob["ISBN"] = ""

    # ============================
    # Solde final 411 pour équilibrage automatique
    # ============================
    df_temp = pd.concat([df_ecr, df_glob], ignore_index=True)
    total_debit = df_temp["Débit"].sum()
    total_credit = df_temp["Crédit"].sum()
    diff = round(total_debit - total_credit, 2)

    if diff > 0:
        # Débit > Crédit → créditer 411
        ligne_411 = pd.DataFrame([{
            "Date": date_ecriture.strftime("%d/%m/%Y"),
            "Journal": journal,
            "Compte": compte_client,
            "Libelle": f"{libelle_base} - Contrepartie client",
            "Famille analytique": famille_analytique,
            "ISBN": "",
            "Débit": 0.0,
            "Crédit": diff
        }])
    elif diff < 0:
        # Crédit > Débit → débiter 411
        ligne_411 = pd.DataFrame([{
            "Date": date_ecriture.strftime("%d/%m/%Y"),
            "Journal": journal,
            "Compte": compte_client,
            "Libelle": f"{libelle_base} - Contrepartie client",
            "Famille analytique": famille_analytique,
            "ISBN": "",
            "Débit": -diff,
            "Crédit": 0.0
        }])
    else:
        ligne_411 = pd.DataFrame()

    # ============================
    # Fusion finale
    # ============================
    df_final = pd.concat([df_ecr, df_glob, ligne_411], ignore_index=True)

    total_debit = df_final["Débit"].sum()
    total_credit = df_final["Crédit"].sum()
    if abs(total_debit - total_credit) > 0.01:
        st.error(f"⚠️ Écritures déséquilibrées : Débit={total_debit}, Crédit={total_credit}")
    else:
        st.success("✅ Écritures équilibrées !")

    # ============================
    # Export Excel
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
