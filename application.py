import pandas as pd
import numpy as np
from io import BytesIO
import streamlit as st

st.title("📘 Générateur d'écritures de reprise globale - 411 / 781 par ISBN")

# === Import du fichier ===
fichier_entree = st.file_uploader("📂 Importer le fichier Excel BLDD (avec montants par ISBN)", type=["xlsx"])

# === Paramètres ===
date_ecriture = st.date_input("📅 Date d'écriture", value=pd.to_datetime("2025-03-31"))
journal = st.text_input("📒 Journal", value="OD")
libelle_base = st.text_input("📝 Libellé", value="Reprise provision Oct.2024 - Mars.2025")
famille_analytique = st.text_input("🏷️ Famille analytique", value="EDITION")

# Comptes
compte_reprise = st.text_input("Compte produit (781...)", value="781000000")
compte_client = st.text_input("Compte client (411...)", value="411100011")

# Montant total à ventiler
montant_total = st.number_input("💶 Montant total de la reprise", value=0.0, format="%.2f")

# Base de ventilation
base_ventilation = st.selectbox("📊 Base de ventilation", ["Vente", "Net", "Facture"], index=0)

# === Traitement ===
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

    # Conversion montants
    for c in ["Vente", "Net", "Facture"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).round(2)
        else:
            df[c] = 0.0

    base = df[base_ventilation]
    if base.sum() == 0:
        st.error(f"⚠️ Impossible de répartir : la base '{base_ventilation}' est nulle.")
    else:
        # Ventilation du montant total
        df["Montant_reprise"] = np.round((base / base.sum()) * montant_total, 2)
        diff = round(montant_total - df["Montant_reprise"].sum(), 2)
        if diff != 0 and len(df) > 0:
            idx_max = df["Montant_reprise"].idxmax()
            df.loc[idx_max, "Montant_reprise"] += diff

        # === Génération des écritures ===
        ecritures = []

        # Ligne globale 411 au DEBIT
        ecritures.append({
            "Date": date_ecriture.strftime("%d/%m/%Y"),
            "Journal": journal,
            "Compte": compte_client,
            "Libelle": f"{libelle_base} - Reprise globale client",
            "Famille analytique": famille_analytique,
            "ISBN": "",
            "Débit": round(montant_total, 2),
            "Crédit": 0.0
        })

        # Lignes 781 par ISBN au CREDIT
        for _, r in df.iterrows():
            isbn = r["ISBN"]
            montant = r["Montant_reprise"]
            ecritures.append({
                "Date": date_ecriture.strftime("%d/%m/%Y"),
                "Journal": journal,
                "Compte": compte_reprise,
                "Libelle": f"{libelle_base} - {isbn}",
                "Famille analytique": famille_analytique,
                "ISBN": isbn,
                "Débit": 0.0,
                "Crédit": round(montant, 2)
            })

        df_ecr = pd.DataFrame(ecritures)

        # Vérification équilibre
        total_debit = df_ecr["Débit"].sum()
        total_credit = df_ecr["Crédit"].sum()
        if abs(total_debit - total_credit) > 0.01:
            st.error(f"⚠️ Écritures déséquilibrées : Débit={total_debit}, Crédit={total_credit}")
        else:
            st.success(f"✅ Écritures équilibrées ! Total = {total_debit:,.2f} €")

        # Export Excel
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            df_ecr.to_excel(writer, index=False, sheet_name="Reprise_411_781")
        buffer.seek(0)

        st.download_button(
            label="📥 Télécharger les écritures (Excel)",
            data=buffer,
            file_name="Ecritures_Reprise_411_781.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # Aperçu
        st.subheader("👀 Aperçu des écritures générées")
        st.dataframe(df_ecr)
