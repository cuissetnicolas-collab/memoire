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
        reprise_date = pd.to_datetime(date_ecriture) + pd.DateOffset(months=6)
        ecritures.append({
            "Date": reprise_date.strftime("%d/%m/%Y"),
            "Journal": journal,
            "Compte": "781000000",
            "Libelle": f"{libelle_base} - Reprise provision ISBN {isbn}",
            "Famille analytique": famille_analytique,
            "ISBN": isbn,
            "Débit": 0.0,
            "Crédit": provision_isbn
        })
