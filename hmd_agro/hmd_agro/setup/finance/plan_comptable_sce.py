"""
FIN-S01 (RG-FIN-01) — Plan comptable inspiré du SCE tunisien (Système
Comptable des Entreprises), réduit aux comptes utiles au contrôle de gestion
de la ferme. Structure au format `create_charts(custom_chart=...)` d'ERPNext.

Les 5 racines suivent les root_type ERPNext (bilan/CPC fonctionnels) ; la
numérotation des comptes porte la sémantique SCE (classes 1 à 7).
"""

CHART_SCE = {
    "Actifs": {
        "root_type": "Asset",
        "is_group": 1,
        "Actifs non courants": {
            "account_number": "2",
            "is_group": 1,
            "Immobilisations corporelles": {
                "account_number": "22",
                "account_type": "Fixed Asset",
                "is_group": 1,
                "Terrains": {"account_number": "221", "account_type": "Fixed Asset"},
                "Constructions": {"account_number": "222", "account_type": "Fixed Asset"},
                "Installations techniques, matériel et outillage": {
                    "account_number": "223", "account_type": "Fixed Asset"},
                "Matériel de transport": {"account_number": "224", "account_type": "Fixed Asset"},
                "Cheptel reproducteur": {"account_number": "225", "account_type": "Fixed Asset"},
                "Autres immobilisations corporelles": {
                    "account_number": "228", "account_type": "Fixed Asset"},
            },
            "Immobilisations en cours": {
                "account_number": "23", "account_type": "Capital Work in Progress"},
            "Amortissements des immobilisations": {
                "account_number": "28",
                "account_type": "Accumulated Depreciation",
                "is_group": 1,
                "Amortissements des constructions": {
                    "account_number": "282", "account_type": "Accumulated Depreciation"},
                "Amortissements installations et matériel": {
                    "account_number": "283", "account_type": "Accumulated Depreciation"},
                "Amortissements matériel de transport": {
                    "account_number": "284", "account_type": "Accumulated Depreciation"},
                "Amortissements cheptel reproducteur": {
                    "account_number": "285", "account_type": "Accumulated Depreciation"},
                "Amortissements autres immobilisations": {
                    "account_number": "288", "account_type": "Accumulated Depreciation"},
            },
        },
        "Stocks": {
            "account_number": "3",
            "is_group": 1,
            "Matières premières - Aliments": {"account_number": "31", "account_type": "Stock"},
            "Autres approvisionnements - Intrants": {"account_number": "32", "account_type": "Stock"},
            "Produits finis - Lait": {"account_number": "35", "account_type": "Stock"},
            "Animaux destinés à la vente": {"account_number": "37", "account_type": "Stock"},
        },
        "Clients et comptes rattachés": {
            "account_number": "41",
            "is_group": 1,
            "Clients": {"account_number": "411", "account_type": "Receivable"},
        },
        "État - TVA déductible": {"account_number": "4366", "account_type": "Tax"},
        "Liquidités et équivalents": {
            "account_number": "5",
            "is_group": 1,
            "Banques": {"account_number": "532", "account_type": "Bank"},
            "Caisse": {"account_number": "54", "account_type": "Cash"},
        },
    },
    "Passifs": {
        "root_type": "Liability",
        "is_group": 1,
        "Emprunts et dettes financières": {"account_number": "14"},
        "Fournisseurs et comptes rattachés": {
            "account_number": "40",
            "is_group": 1,
            "Fournisseurs d'exploitation": {"account_number": "401", "account_type": "Payable"},
            "Fournisseurs - Factures non parvenues": {
                "account_number": "408", "account_type": "Stock Received But Not Billed"},
            "Fournisseurs - Services non facturés": {
                "account_number": "4088", "account_type": "Service Received But Not Billed"},
        },
        "Personnel - Rémunérations dues": {"account_number": "421"},
        "État - TVA collectée": {"account_number": "4367", "account_type": "Tax"},
        "Comptes d'attente - Ouverture": {"account_number": "471", "account_type": "Temporary"},
    },
    "Capitaux propres": {
        "root_type": "Equity",
        "is_group": 1,
        "Capital social": {"account_number": "101", "account_type": "Equity"},
        "Réserves": {"account_number": "106", "account_type": "Equity"},
        "Résultats reportés": {"account_number": "12", "account_type": "Equity"},
    },
    "Produits": {
        "root_type": "Income",
        "is_group": 1,
        "Ventes de produits": {
            "account_number": "70",
            "is_group": 1,
            "Ventes de lait": {"account_number": "701", "account_type": "Income Account"},
            "Ventes d'animaux": {"account_number": "702", "account_type": "Income Account"},
            "Produits annexes - Fumier et divers": {
                "account_number": "708", "account_type": "Income Account"},
        },
        "Production immobilisée": {"account_number": "73", "account_type": "Income Account"},
        "Produits nets sur cession d'immobilisations": {
            "account_number": "736", "account_type": "Income Account"},
        "Reprises et autres produits": {"account_number": "78", "account_type": "Income Account"},
    },
    "Charges": {
        "root_type": "Expense",
        "is_group": 1,
        "Achats et consommations": {
            "account_number": "60",
            "is_group": 1,
            "Consommation d'aliments": {"account_number": "601", "account_type": "Expense Account"},
            "Consommation de médicaments et produits vétérinaires": {
                "account_number": "602", "account_type": "Expense Account"},
            "Variation des stocks": {"account_number": "603", "account_type": "Stock Adjustment"},
            "Consommation de semences (IA)": {
                "account_number": "604", "account_type": "Expense Account"},
            "Coût des marchandises vendues": {
                "account_number": "605", "account_type": "Cost of Goods Sold"},
            "Achats non stockés - Eau et énergie": {
                "account_number": "606", "account_type": "Expense Account"},
            "Frais accessoires d'achat": {
                "account_number": "608", "account_type": "Expenses Included In Valuation"},
        },
        "Services extérieurs": {
            "account_number": "61",
            "is_group": 1,
            "Locations": {"account_number": "613", "account_type": "Expense Account"},
            "Entretien et réparations": {"account_number": "615", "account_type": "Expense Account"},
            "Assurances": {"account_number": "616", "account_type": "Expense Account"},
        },
        "Autres services extérieurs": {
            "account_number": "62",
            "is_group": 1,
            "Personnel extérieur et honoraires": {
                "account_number": "621", "account_type": "Expense Account"},
            "Divers services extérieurs": {
                "account_number": "628", "account_type": "Expense Account"},
        },
        "Charges de personnel": {
            "account_number": "64",
            "is_group": 1,
            "Salaires et compléments": {"account_number": "640", "account_type": "Expense Account"},
            "Charges sociales": {"account_number": "647", "account_type": "Expense Account"},
        },
        "Autres charges d'exploitation": {
            "account_number": "65",
            "is_group": 1,
            "Redevances et divers": {"account_number": "651", "account_type": "Expense Account"},
            "Charges diverses - Arrondis": {"account_number": "658", "account_type": "Round Off"},
            "Pertes et gains de change": {"account_number": "665", "account_type": "Expense Account"},
        },
        "Charges financières": {
            "account_number": "66",
            "is_group": 1,
            "Intérêts des emprunts": {"account_number": "661", "account_type": "Expense Account"},
        },
        "Dotations aux amortissements": {
            "account_number": "68",
            "is_group": 1,
            "Dotations aux amortissements d'exploitation": {
                "account_number": "681", "account_type": "Depreciation"},
        },
        "Impôts sur les bénéfices": {"account_number": "691", "account_type": "Expense Account"},
    },
}
