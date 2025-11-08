import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from pandas.tseries.offsets import MonthEnd

# ============================
# 📦 Application Reprises Provisions
# ============================
st.title("📆 Générateur de reprises de provisions - BLDD")

# Import du fichier Excel source
fichier = st.file_uploader("📂 Importer le fichier Excel BLDD (octobre 2024 à mars 2025)", type=["xlsx"])
journal = st.text_input("📒 Journal", value="VT")
libelle_base = st.text_input("📝 Libellé", value="REPRISE PROVISIONS RETOURS BLDD")
famille_analytique = st.text_input("🏷️ Famille analytique", value="EDITION")
compte_reprise = "781000000"
compte_client = "411100011"

# Traitement
if fichier is not None:
    df = pd.read_excel(fichier, header=9, dtype={"ISBN": str})
    df.columns = df.columns.str.strip()
    df = df.dropna(subset=["ISBN"]).copy()

    # Nettoyage ISBN
    df["ISBN"] = (
        df["ISBN"].astype(str)
        .str.strip()
        .str.replace(r"\.0$", "", regex=True)
        .str.replace("-", "", regex=False)
        .str.replace(" ", "", regex=False)
    )

    for c in ["Vente"]:
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).round(2)

    # Calcul provision initiale si non présente
    df["Provision_initiale"] = round(df["Vente"] * 1.055 * 0.10, 2)

    # Génération des reprises (6 mois plus tard)
    ecritures = []
    for _, r in df.iterrows():
        isbn = r["ISBN"]
        date_origine = pd.to_datetime(st.date_input("Date de référence", value=pd.Timestamp("2024-10-31")))
        reprise_date = date_origine + MonthEnd(6)

        def add_ligne(date, compte, libelle, debit, credit):
            ecritures.append({
                "Date": date.strftime("%d/%m/%Y"),
                "Journal": journal,
                "Compte": compte,
                "Libelle": libelle,
                "Famille analytique": famille_analytique,
                "ISBN": isbn,
                "Débit": round(debit, 2),
                "Crédit": round(credit, 2)
            })

        provision = r["Provision_initiale"]
        if provision > 0:
            add_ligne(reprise_date, compte_reprise, f"{libelle_base}", 0.0, provision)

    df_ecr = pd.DataFrame(ecritures)

    # Ajout contrepartie client par date
    if not df_ecr.empty:
        for date_str, groupe in df_ecr.groupby("Date"):
            diff = round(groupe["Débit"].sum() - groupe["Crédit"].sum(), 2)
            ligne_411 = {
                "Date": date_str,
                "Journal": journal,
                "Compte": compte_client,
                "Libelle": f"{libelle_base} - Contrepartie client",
                "Famille analytique": famille_analytique,
                "ISBN": "",
                "Débit": 0.0 if diff > 0 else abs(diff),
                "Crédit": diff if diff > 0 else 0.0
            }
            df_ecr = pd.concat([df_ecr, pd.DataFrame([ligne_411])], ignore_index=True)

    # Vérif équilibre
    total_debit = df_ecr["Débit"].sum()
    total_credit = df_ecr["Crédit"].sum()
    ecart = round(total_debit - total_credit, 2)

    if ecart == 0:
        st.success("✅ Écritures équilibrées !")
    else:
        st.error(f"⚠️ Écart global : {ecart} € (Débit={total_debit}, Crédit={total_credit})")

    # Export Excel
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_ecr.to_excel(writer, index=False, sheet_name="Reprises_Provisions")
    buffer.seek(0)

    st.download_button(
        label="📥 Télécharger les reprises (Excel)",
        data=buffer,
        file_name="Reprises_Provisions_BLDD.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    st.subheader("👀 Aperçu des écritures générées")
    st.dataframe(df_ecr)
