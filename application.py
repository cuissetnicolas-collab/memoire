import pandas as pd
import numpy as np
from io import BytesIO
import streamlit as st
from pandas.tseries.offsets import MonthEnd

# ============================
# Interface utilisateur
# ============================
st.title("📊 Générateur des reprises de provisions BLDD (octobre 2024 → mars 2025)")

# Import du fichier
fichier_entree = st.file_uploader("📂 Importer le fichier Excel BLDD", type=["xlsx"])

# Saisie de la date de référence pour calculer les reprises
date_origine = st.date_input(
    "📅 Date de référence pour les reprises",
    value=pd.Timestamp("2024-10-31")
)

journal = st.text_input("📒 Journal", value="VT")
libelle_base = st.text_input("📝 Libellé", value="REPRISE PROVISION BLDD")
famille_analytique = st.text_input("🏷️ Famille analytique", value="EDITION")

# Comptes comptables
compte_reprise = "781000000"
compte_client = "411100011"

# ============================
# Traitement principal
# ============================
if fichier_entree is not None:
    # Lecture du fichier source
    df = pd.read_excel(fichier_entree, header=9, dtype={"ISBN": str})
    df.columns = df.columns.str.strip()
    df = df.dropna(subset=["ISBN"]).copy()

    # Nettoyage des ISBN
    df["ISBN"] = (
        df["ISBN"].astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.replace("-", "", regex=False)
        .str.replace(" ", "", regex=False)
    )

    # Conversion des colonnes numériques
    for c in ["Vente", "Retour", "Net", "Facture"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).round(2)

    # ============================
    # Génération des écritures de reprise
    # ============================
    ecritures = []

    for _, r in df.iterrows():
        isbn = r["ISBN"]

        # Calcul de la provision (10 % du TTC)
        provision = round(r["Vente"] * 1.055 * 0.10, 2)
        if provision > 0:
            reprise_date = pd.to_datetime(date_origine) + MonthEnd(6)
            ecritures.append({
                "Date": reprise_date.strftime("%d/%m/%Y"),
                "Journal": journal,
                "Compte": compte_reprise,
                "Libelle": libelle_base,
                "Famille analytique": famille_analytique,
                "ISBN": isbn,
                "Débit": 0.0,
                "Crédit": provision
            })

    df_ecr = pd.DataFrame(ecritures)

    # ============================
    # Ligne de contrepartie client (411)
    # ============================
    total_credit = df_ecr["Crédit"].sum()
    if total_credit > 0:
        reprise_date = pd.to_datetime(date_origine) + MonthEnd(6)
        ligne_411 = pd.DataFrame([{
            "Date": reprise_date.strftime("%d/%m/%Y"),
            "Journal": journal,
            "Compte": compte_client,
            "Libelle": f"{libelle_base} - Contrepartie client",
            "Famille analytique": famille_analytique,
            "ISBN": "",
            "Débit": total_credit,
            "Crédit": 0.0
        }])
        df_final = pd.concat([df_ecr, ligne_411], ignore_index=True)
    else:
        df_final = df_ecr

    # ============================
    # Vérification de l'équilibre
    # ============================
    total_debit = df_final["Débit"].sum()
    total_credit = df_final["Crédit"].sum()

    if abs(total_debit - total_credit) < 0.01:
        st.success("✅ Écritures équilibrées !")
    else:
        st.error(f"⚠️ Écart : Débit={total_debit}, Crédit={total_credit}")

    # ============================
    # Export Excel
    # ============================
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_final.to_excel(writer, index=False, sheet_name="Reprises_Provisions")
    buffer.seek(0)

    st.download_button(
        label="📥 Télécharger les écritures de reprise (Excel)",
        data=buffer,
        file_name="Reprises_Provisions_BLDD.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # ============================
    # Aperçu des écritures
    # ============================
    st.subheader("👀 Aperçu des écritures générées")
    st.dataframe(df_final)
