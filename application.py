import pandas as pd
from io import BytesIO
import streamlit as st

st.title("📘 Générateur d'écritures de reprise - 411 / 781 par ISBN")

# === Import du fichier ===
fichier_entree = st.file_uploader("📂 Importer le fichier Excel BLDD (avec colonne 'Vente')", type=["xlsx"])

# === Paramètres ===
date_ecriture = st.date_input("📅 Date d'écriture", value=pd.to_datetime("2025-03-31"))
journal = st.text_input("📒 Journal", value="OD")
libelle_base = st.text_input("📝 Libellé", value="Reprise provision Oct.2024 - Mars.2025")
famille_analytique = st.text_input("🏷️ Famille analytique", value="EDITION")

# Comptes
compte_reprise = st.text_input("Compte produit (781...)", value="781000000")
compte_client = st.text_input("Compte client (411...)", value="411100011")

if fichier_entree is not None:
    df = pd.read_excel(fichier_entree, header=9, dtype={"ISBN": str})
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

    # Conversion colonne Vente
    if "Vente" not in df.columns:
        st.error("⚠️ La colonne 'Vente' est introuvable dans le fichier.")
    else:
        df["Vente"] = pd.to_numeric(df["Vente"], errors="coerce").fillna(0)

        # Calcul TTC et provision
        df["Vente_TTC"] = df["Vente"] * 1.055
        df["Montant_reprise"] = df["Vente_TTC"] * 0.10

        montant_total = round(df["Montant_reprise"].sum(), 2)

        st.info(f"💶 Montant total de reprise calculé : {montant_total:,.2f} €")

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
            "Débit": montant_total,
            "Crédit": 0.0
        })

        # Lignes 781 par ISBN au CREDIT
        for _, r in df.iterrows():
            isbn = r["ISBN"]
            montant = round(r["Montant_reprise"], 2)
            ecritures.append({
                "Date": date_ecriture.strftime("%d/%m/%Y"),
                "Journal": journal,
                "Compte": compte_reprise,
                "Libelle": f"{libelle_base} - {isbn}",
                "Famille analytique": famille_analytique,
                "ISBN": isbn,
                "Débit": 0.0,
                "Crédit": montant
            })

        df_ecr = pd.DataFrame(ecritures)

        # Vérif équilibre
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
