#!/usr/bin/env python3
"""
Baserow bulk‑update script
- Workspace ID : 207617
- Table MEMBRES (id 1010820)   → champ Type membre‑Rglt  (field_id 8869085)
- Table INSCRIPTIONS (id 1010823) → champ Membre (link_row, field_id 8869086)
                                            champ Statut (field_id 8869088)
"""

import os
import sys
import time
import requests
from typing import List, Dict

# ----------------------------------------------------------------------
# Configuration – à adapter à votre environnement
# ----------------------------------------------------------------------
BASE_URL = "https://api.baserow.io/api"
# Token d’accès (personal token ou token d’application)
API_TOKEN = os.getenv("BASEROW_TOKEN")          # ← export BASEROW_TOKEN=xxxx
if not API_TOKEN:
    sys.exit("❌ Veuillez définir la variable d’environnement BASEROW_TOKEN avec votre token d’API.")

HEADERS = {
    "Authorization": f"Token {API_TOKEN}",
    "Content-Type": "application/json",
}

# IDs (déjà connus dans votre workspace)
WORKSPACE_ID   = 207617
MEMBRES_TABLE_ID = 1010820
INSCRIPTIONS_TABLE_ID = 1010823

# Field IDs
FIELD_TYPE_RGTL = 8869085   # MEMBRES.Type membre‑Rglt
FIELD_MBR_LINK  = 8869086   # INSCRIPTIONS.Membre (link_row vers MEMBRES)
FIELD_STATUT    = 8869088   # INSCRIPTIONS.Statut

# Valeur cible
NEW_STATUT = "Actif"
# ----------------------------------------------------------------------


def request_get(url: str, params: dict = None) -> dict:
    """GET avec gestion d’erreurs basique."""
    resp = requests.get(url, headers=HEADERS, params=params)
    if not resp.ok:
        raise RuntimeError(f"GET {url} → {resp.status_code} {resp.text}")
    return resp.json()


def request_patch(url: str, payload: dict) -> dict:
    """PATCH avec gestion d’erreurs basique."""
    resp = requests.patch(url, headers=HEADERS, json=payload)
    if not resp.ok:
        raise RuntimeError(f"PATCH {url} → {resp.status_code} {resp.text}")
    return resp.json()


def get_members_with_valid_rglt() -> List[Dict]:
    """
    Retourne la liste des membres dont le champ Type membre‑Rglt ≠ "Non Réglés!".
    Pagination gérée automatiquement (max 100 lignes par appel).
    """
    members = []
    offset = 0
    limit = 100

    while True:
        url = f"{BASE_URL}/database/rows/table/{MEMBRES_TABLE_ID}/"
        params = {
            "limit": limit,
            "offset": offset,
            "field_ids": f"{FIELD_TYPE_RGTL}",
        }
        data = request_get(url, params=params)
        rows = data.get("results", [])
        for row in rows:
            # Le champ link‑row renvoie une liste d’objets, le champ texte renvoie la valeur brute
            type_val = row.get(str(FIELD_TYPE_RGTL))
            if type_val and type_val != "Non Réglés!":
                members.append({"id": row["id"], "type": type_val})
        if not data.get("next"):
            break
        offset += limit

    print(f"✅ {len(members)} membres éligibles trouvés.")
    return members


def get_inscriptions_for_member(member_id: int) -> List[int]:
    """
    Retourne les IDs des lignes INSCRIPTIONS où le champ Membre (link_row) pointe vers `member_id`.
    """
    inscription_ids = []
    offset = 0
    limit = 100

    while True:
        url = f"{BASE_URL}/database/rows/table/{INSCRIPTIONS_TABLE_ID}/"
        params = {
            "limit": limit,
            "offset": offset,
            "field_ids": f"{FIELD_MBR_LINK}",
        }
        data = request_get(url, params=params)
        rows = data.get("results", [])
        for row in rows:
            links = row.get(str(FIELD_MBR_LINK), [])
            # links est une liste d'objets {"id": <member_id>, "value": "..."}
            if any(link.get("id") == member_id for link in links):
                inscription_ids.append(row["id"])
        if not data.get("next"):
            break
        offset += limit

    return inscription_ids


def update_inscription_status(row_id: int):
    """Met à jour le champ Statut d’une ligne INSCRIPTIONS."""
    url = f"{BASE_URL}/database/rows/table/{INSCRIPTIONS_TABLE_ID}/{row_id}/"
    payload = {
        "fields": {
            str(FIELD_STATUT): NEW_STATUT
        }
    }
    request_patch(url, payload)


def main():
    members = get_members_with_valid_rglt()
    total_updated = 0

    for member in members:
        member_id = member["id"]
        inscriptions = get_inscriptions_for_member(member_id)

        if not inscriptions:
            continue

        print(f"🔎 Membre {member_id} → {len(inscriptions)} adhésions à mettre à jour.")
        for row_id in inscriptions:
            try:
                update_inscription_status(row_id)
                total_updated += 1
            except Exception as e:
                print(f"⚠️ Erreur sur l’inscription {row_id} : {e}")

        # Respecter les limites de taux (Baserow autorise ~30 req/s en free)
        time.sleep(0.05)   # 20 ms pause entre les PATCH

    print(f"\n✅ Mise à jour terminée – {total_updated} lignes INSCRIPTIONS passées à « {NEW_STATUT} ».")
    

if __name__ == "__main__":
    main()
