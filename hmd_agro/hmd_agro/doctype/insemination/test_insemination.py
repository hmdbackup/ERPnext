# Copyright (c) 2026, Mouhib Bouzamita and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import today, add_days, getdate


class TestInsemination(FrappeTestCase):
    """Comprehensive tests for Insemination doctype validations and side effects."""

    def setUp(self):
        # --- Batiment ---
        if not frappe.db.exists("Batiment", "Test Batiment IA"):
            frappe.get_doc({
                "doctype": "Batiment",
                "nom_batiment": "Test Batiment IA",
                "type_batiment": "ELEVAGE",
            }).insert(ignore_permissions=True)

        # --- Lot ---
        if not frappe.db.exists("Lot", "Test Lot IA"):
            frappe.get_doc({
                "doctype": "Lot",
                "nom": "Test Lot IA",
                "batiment": "Test Batiment IA",
                "superficie_m2": 100.0,
                "capacite_optimale": 20,
                "capacite_maximale": 30,
            }).insert(ignore_permissions=True)

        # --- Taureau ---
        if not frappe.db.exists("Taureau", "Test Taureau IA"):
            frappe.get_doc({
                "doctype": "Taureau",
                "nom_taureau": "Test Taureau IA",
                "code_taureau": "TIA001",
                "race": "Holstein",
            }).insert(ignore_permissions=True)

        # --- Mere externe ---
        self.mere_externe = None
        meres = frappe.get_all("Mere externe", limit=1)
        if meres:
            self.mere_externe = meres[0].name
        else:
            doc = frappe.get_doc({"doctype": "Mere externe"}).insert(ignore_permissions=True)
            self.mere_externe = doc.name

        # --- Semence (stock seeded to 10 via Material Receipt) ---
        # ST5-14 (Phase C): legacy stock fields removed in ST5-12. Stock now
        # lives in Batch.batch_qty (auto-maintained from Stock Entries). To
        # have 10 paillettes for the decrement test, we ensure a Semence row
        # exists, then top up its Batch via a Material Receipt to qty=10.
        existing_semence = frappe.get_all("Semence", filters={
            "taureau": "Test Taureau IA",
            "type_semence": "CONVENTIONNELLE",
        }, limit=1)
        if existing_semence:
            self.semence = existing_semence[0].name
        else:
            sem = frappe.get_doc({
                "doctype": "Semence",
                "taureau": "Test Taureau IA",
                "type_semence": "CONVENTIONNELLE",
                "date_reception": add_days(today(), -30),
            }).insert(ignore_permissions=True)
            self.semence = sem.name

        # Top up Batch.batch_qty to 10 if it's currently below.
        sem_item = frappe.db.get_value("Semence", self.semence, "item")
        current_qty = frappe.db.get_value("Batch", self.semence, "batch_qty") or 0
        if sem_item and current_qty < 10:
            top_up = 10 - current_qty
            se = frappe.get_doc({
                "doctype": "Stock Entry",
                "stock_entry_type": "Material Receipt",
                "company": "hmd-agro",
                "posting_date": today(),
                "items": [{
                    "item_code": sem_item,
                    "qty": top_up,
                    "uom": "Paillette",
                    "stock_uom": "Paillette",
                    "conversion_factor": 1,
                    "t_warehouse": "Magasin Principal - HMD",
                    "batch_no": self.semence,
                    "basic_rate": 1,
                }],
                "remarks": f"test_insemination setUp top-up to 10",
            })
            se.insert(ignore_permissions=True)
            se.submit()
            frappe.db.commit()

        # --- Animal (VACHE, ACTIF, VIDE) ---
        if not frappe.db.exists("Animal", "8100000001"):
            frappe.get_doc({
                "doctype": "Animal",
                "identification_tn": "8100000001",
                "categorie": "VACHE",
                "sexe": "F",
                "race": "Holstein",
                "date_naissance": "2020-01-01",
                "id_lot": "Test Lot IA",
                "id_pere": "Test Taureau IA",
                "date_entree": add_days(today(), -500), "est_achat": 1,
                "id_mere_externe": self.mere_externe,
                "statut": "ACTIF",
                "etat_gestation": "VIDE",
            }).insert(ignore_permissions=True)
        else:
            # Reset state for each test
            frappe.db.set_value("Animal", "8100000001", {
                "etat_gestation": "VIDE",
                "id_ia_fecondante": None,
                "date_velage_prevue": None,
                "date_tarissement": None,
                "categorie": "VACHE",
                "statut": "ACTIF",
            })

        # --- Lactation EN_COURS ---
        existing_lac = frappe.db.exists("Lactation", {
            "animal": "8100000001",
            "statut": "EN_COURS",
        })
        if existing_lac:
            self.lactation = existing_lac
        else:
            lac = frappe.get_doc({
                "doctype": "Lactation",
                "animal": "8100000001",
                "statut": "EN_COURS",
                "date_debut": "2024-06-01",
            })
            lac.flags.ignore_validate = True
            lac.insert(ignore_permissions=True)
            self.lactation = lac.name

        frappe.db.commit()

    def tearDown(self):
        frappe.db.rollback()

    # ─── Helpers ───────────────────────────────────────────────

    def _make_ia(self, **kwargs):
        """Create and return an Insemination doc with sensible defaults."""
        defaults = {
            "doctype": "Insemination",
            "animal": "8100000001",
            "taureau": "Test Taureau IA",
            "type_semence": "CONVENTIONNELLE",
            "date_ia": add_days(today(), -5),
            "resultat": "EN_ATTENTE",
        }
        defaults.update(kwargs)
        return frappe.get_doc(defaults)

    def _create_genisse(self):
        """Create a GENISSE animal for tests that need one."""
        name = "8100000002"
        if not frappe.db.exists("Animal", name):
            frappe.get_doc({
                "doctype": "Animal",
                "identification_tn": name,
                "categorie": "GENISSE",
                "sexe": "F",
                "race": "Holstein",
                "date_naissance": "2022-06-01",
                "id_lot": "Test Lot IA",
                "id_pere": "Test Taureau IA",
                "date_entree": add_days(today(), -500), "est_achat": 1,
                "id_mere_externe": self.mere_externe,
                "statut": "ACTIF",
                "etat_gestation": "VIDE",
            }).insert(ignore_permissions=True)
        else:
            frappe.db.set_value("Animal", name, {
                "etat_gestation": "VIDE",
                "id_ia_fecondante": None,
                "categorie": "GENISSE",
                "statut": "ACTIF",
            })
        return name

    def _create_male_animal(self):
        """Create a male VEAU animal for tests."""
        name = "8100000003"
        if not frappe.db.exists("Animal", name):
            frappe.get_doc({
                "doctype": "Animal",
                "identification_tn": name,
                "categorie": "VEAU",
                "sexe": "M",
                "race": "Holstein",
                "date_naissance": "2023-01-01",
                "id_lot": "Test Lot IA",
                "id_pere": "Test Taureau IA",
                "date_entree": add_days(today(), -500), "est_achat": 1,
                "id_mere_externe": self.mere_externe,
                "statut": "ACTIF",
            }).insert(ignore_permissions=True)
        return name

    # ─── 1. Happy Path ─────────────────────────────────────────

    def test_valid_ia_creation(self):
        """A valid IA on VACHE/VIDE should succeed."""
        ia = self._make_ia()
        ia.insert(ignore_permissions=True)

        self.assertTrue(ia.name)
        self.assertEqual(ia.resultat, "EN_ATTENTE")
        self.assertEqual(ia.lactation, self.lactation)
        self.assertGreaterEqual(ia.numero_ia, 1)

    # ─── 2. ERR-IA-06: IA on GESTANTE animal ──────────────────

    def test_ia_on_gestante_animal_fails(self):
        """IA on a GESTANTE animal should throw ERR-IA-06."""
        frappe.db.set_value("Animal", "8100000001", "etat_gestation", "GESTANTE")
        ia = self._make_ia()
        self.assertRaisesRegex(
            frappe.exceptions.ValidationError,
            "ERR-IA-06",
            ia.insert,
            ignore_permissions=True,
        )

    # ─── 3. ERR-IA-01: IA on male / VEAU ──────────────────────

    def test_ia_on_male_animal_fails(self):
        """IA on a male VEAU should throw ERR-IA-01."""
        male = self._create_male_animal()
        ia = self._make_ia(animal=male)
        self.assertRaisesRegex(
            frappe.exceptions.ValidationError,
            "ERR-IA-01",
            ia.insert,
            ignore_permissions=True,
        )

    # ─── 4. Duplicate pending IA ───────────────────────────────

    def test_duplicate_pending_ia_fails(self):
        """Two pending IAs for the same animal should throw."""
        ia1 = self._make_ia()
        ia1.insert(ignore_permissions=True)

        ia2 = self._make_ia(date_ia=add_days(today(), -3))
        self.assertRaises(
            frappe.exceptions.ValidationError,
            ia2.insert,
            ignore_permissions=True,
        )

    # ─── 5. ERR-IA-02: Future date_ia ─────────────────────────

    def test_future_date_ia_fails(self):
        """date_ia in the future should throw ERR-IA-02."""
        ia = self._make_ia(date_ia=add_days(today(), 5))
        self.assertRaisesRegex(
            frappe.exceptions.ValidationError,
            "ERR-IA-02",
            ia.insert,
            ignore_permissions=True,
        )

    # ─── 6. ERR-IA-03: date_ia before birth ───────────────────

    def test_date_ia_before_birth_fails(self):
        """date_ia on or before date_naissance should throw ERR-IA-03."""
        # Animal born 2020-01-01
        ia = self._make_ia(date_ia="2019-12-31")
        self.assertRaisesRegex(
            frappe.exceptions.ValidationError,
            "ERR-IA-03",
            ia.insert,
            ignore_permissions=True,
        )

    def test_date_ia_on_birth_date_fails(self):
        """date_ia exactly on date_naissance should throw ERR-IA-03 (uses <=)."""
        ia = self._make_ia(date_ia="2020-01-01")
        self.assertRaisesRegex(
            frappe.exceptions.ValidationError,
            "ERR-IA-03",
            ia.insert,
            ignore_permissions=True,
        )

    # ─── 7. ERR-IA-04: date_ia before last velage ─────────────

    def test_date_ia_before_last_velage_fails(self):
        """date_ia before the last velage date should throw ERR-IA-04."""
        # Create a Velage record for this animal (vivant_veau1=0 to skip calf creation)
        velage = frappe.get_doc({
            "doctype": "Velage",
            "animal": "8100000001",
            "date_velage": "2024-06-01",
            "vivant_veau1": 0,
        })
        velage.flags.ignore_validate = True
        velage.flags.ignore_mandatory = True
        velage.flags.ignore_links = True
        velage.insert(ignore_permissions=True)

        ia = self._make_ia(date_ia="2024-05-15")
        self.assertRaisesRegex(
            frappe.exceptions.ValidationError,
            "ERR-IA-04",
            ia.insert,
            ignore_permissions=True,
        )

        # Cleanup — use db.delete to bypass on_trash cascades
        frappe.db.delete("Velage", velage.name)

    # ─── 8. Resultat transitions ──────────────────────────────

    def test_transition_en_attente_to_reussie(self):
        """EN_ATTENTE -> REUSSIE is valid."""
        ia = self._make_ia()
        ia.insert(ignore_permissions=True)

        ia.resultat = "REUSSIE"
        ia.save(ignore_permissions=True)

        self.assertEqual(ia.resultat, "REUSSIE")
        # Animal should be GESTANTE
        animal = frappe.get_doc("Animal", "8100000001")
        self.assertEqual(animal.etat_gestation, "GESTANTE")
        self.assertEqual(animal.id_ia_fecondante, ia.name)
        self.assertIsNotNone(animal.date_velage_prevue)
        self.assertIsNotNone(animal.date_tarissement)

    def test_transition_en_attente_to_echouee(self):
        """EN_ATTENTE -> ECHOUEE is valid."""
        ia = self._make_ia()
        ia.insert(ignore_permissions=True)

        ia.resultat = "ECHOUEE"
        ia.save(ignore_permissions=True)

        self.assertEqual(ia.resultat, "ECHOUEE")

    def test_transition_echouee_to_reussie_fails(self):
        """ECHOUEE -> REUSSIE is NOT allowed (ECHOUEE is final)."""
        ia = self._make_ia()
        ia.insert(ignore_permissions=True)

        ia.resultat = "ECHOUEE"
        ia.save(ignore_permissions=True)

        ia.reload()
        ia.resultat = "REUSSIE"
        self.assertRaises(
            frappe.exceptions.ValidationError,
            ia.save,
            ignore_permissions=True,
        )

    def test_transition_reussie_to_echouee_valid(self):
        """REUSSIE -> ECHOUEE is allowed (when no velage depends)."""
        ia = self._make_ia()
        ia.insert(ignore_permissions=True)

        ia.resultat = "REUSSIE"
        ia.save(ignore_permissions=True)

        ia.reload()
        ia.resultat = "ECHOUEE"
        ia.save(ignore_permissions=True)

        self.assertEqual(ia.resultat, "ECHOUEE")
        # Animal should be reset to VIDE
        animal = frappe.get_doc("Animal", "8100000001")
        self.assertEqual(animal.etat_gestation, "VIDE")
        self.assertIsNone(animal.id_ia_fecondante)

    def test_transition_echouee_to_echouee_noop(self):
        """ECHOUEE -> ECHOUEE (no change) should not throw."""
        ia = self._make_ia()
        ia.insert(ignore_permissions=True)

        ia.resultat = "ECHOUEE"
        ia.save(ignore_permissions=True)

        ia.reload()
        # No change to resultat, just save
        ia.observations = "test"
        ia.save(ignore_permissions=True)  # should not throw

    # ─── 9. lock_identity_fields ──────────────────────────────

    def test_cannot_change_animal_after_creation(self):
        """Changing animal field after creation should throw."""
        genisse = self._create_genisse()
        ia = self._make_ia()
        ia.insert(ignore_permissions=True)

        ia.reload()
        ia.animal = genisse
        self.assertRaises(
            frappe.exceptions.ValidationError,
            ia.save,
            ignore_permissions=True,
        )

    def test_cannot_change_taureau_after_creation(self):
        """Changing taureau field after creation should throw."""
        # Create a second taureau
        if not frappe.db.exists("Taureau", "Test Taureau IA 2"):
            frappe.get_doc({
                "doctype": "Taureau",
                "nom_taureau": "Test Taureau IA 2",
                "code_taureau": "TIA002",
                "race": "Holstein",
            }).insert(ignore_permissions=True)

        ia = self._make_ia()
        ia.insert(ignore_permissions=True)

        ia.reload()
        ia.taureau = "Test Taureau IA 2"
        self.assertRaises(
            frappe.exceptions.ValidationError,
            ia.save,
            ignore_permissions=True,
        )

    # ─── 10. date_ia editable only when EN_ATTENTE ────────────

    def test_date_ia_editable_when_en_attente(self):
        """date_ia can be changed while resultat is EN_ATTENTE."""
        ia = self._make_ia()
        ia.insert(ignore_permissions=True)

        ia.reload()
        ia.date_ia = add_days(today(), -10)
        ia.save(ignore_permissions=True)  # should not throw
        self.assertEqual(str(ia.date_ia), str(getdate(add_days(today(), -10))))

    def test_date_ia_not_editable_after_resultat_confirmed(self):
        """date_ia cannot be changed once resultat is REUSSIE."""
        ia = self._make_ia()
        ia.insert(ignore_permissions=True)

        ia.resultat = "REUSSIE"
        ia.save(ignore_permissions=True)

        ia.reload()
        ia.date_ia = add_days(today(), -20)
        self.assertRaises(
            frappe.exceptions.ValidationError,
            ia.save,
            ignore_permissions=True,
        )

    # ─── 11. auto_link_lactation ──────────────────────────────

    def test_auto_link_lactation_for_vache(self):
        """IA on VACHE with active lactation should auto-link lactation field."""
        ia = self._make_ia()
        ia.insert(ignore_permissions=True)

        self.assertEqual(ia.lactation, self.lactation)

    def test_no_lactation_for_genisse(self):
        """IA on GENISSE (no lactation) should have lactation=None."""
        genisse = self._create_genisse()
        ia = self._make_ia(animal=genisse)
        ia.insert(ignore_permissions=True)

        self.assertFalse(ia.lactation)

    # ─── 12. set_numero_ia ────────────────────────────────────

    def test_numero_ia_auto_set_first_ia(self):
        """First IA for a VACHE in a lactation should get numero_ia=1."""
        ia = self._make_ia()
        ia.insert(ignore_permissions=True)

        self.assertEqual(ia.numero_ia, 1)

    def test_numero_ia_increments_for_genisse(self):
        """GENISSE IAs should count all IAs for the animal."""
        genisse = self._create_genisse()

        ia1 = self._make_ia(animal=genisse)
        ia1.insert(ignore_permissions=True)
        self.assertEqual(ia1.numero_ia, 1)

        # Mark first as ECHOUEE so we can create a second
        ia1.resultat = "ECHOUEE"
        ia1.save(ignore_permissions=True)

        ia2 = self._make_ia(animal=genisse, date_ia=add_days(today(), -2))
        ia2.insert(ignore_permissions=True)
        self.assertEqual(ia2.numero_ia, 2)

    # ─── 13. semence stock decrement on insert ────────────────

    def test_semence_stock_decremented_on_insert(self):
        """Inserting IA should decrement semence Batch.batch_qty by 1.
        ST5-14: post-Phase C, stock is tracked in Batch (auto-maintained
        from Stock Entries) rather than the legacy Semence.quantite_restante."""
        stock_before = frappe.db.get_value("Batch", self.semence, "batch_qty") or 0

        ia = self._make_ia()
        ia.insert(ignore_permissions=True)

        stock_after = frappe.db.get_value("Batch", self.semence, "batch_qty") or 0
        self.assertEqual(stock_after, stock_before - 1)

    # ─── 14. close_chaleur_alerts on insert ───────────────────

    def test_close_chaleur_alerts_on_insert(self):
        """Inserting IA should close open chaleur alerts for the animal."""
        # Create a chaleur alert
        alert = frappe.get_doc({
            "doctype": "Alerte",
            "animal": "8100000001",
            "type_alerte": "CHALEUR_POST_VELAGE",
            "statut": "NOUVELLE",
            "date_generation": today(),
        })
        alert.flags.ignore_validate = True
        alert.flags.ignore_mandatory = True
        alert.insert(ignore_permissions=True)

        ia = self._make_ia()
        ia.insert(ignore_permissions=True)

        alert.reload()
        self.assertEqual(alert.statut, "TRAITEE")

    # ─── 15. update_lactation_count on_update ─────────────────

    def test_update_lactation_count(self):
        """Inserting IA should update nb_inseminations on linked lactation."""
        ia = self._make_ia()
        ia.insert(ignore_permissions=True)

        nb = frappe.db.get_value("Lactation", self.lactation, "nb_inseminations")
        self.assertGreaterEqual(nb, 1)

    # ─── 16. on_trash: restore semence stock ──────────────────

    def test_semence_stock_restored_on_delete(self):
        """Deleting IA should restore semence Batch.batch_qty by 1.
        ST5-14: post-Phase C, stock is tracked in Batch (auto-maintained
        from Stock Entries) rather than the legacy Semence.quantite_restante."""
        stock_before = frappe.db.get_value("Batch", self.semence, "batch_qty") or 0

        ia = self._make_ia()
        ia.insert(ignore_permissions=True)

        stock_after_insert = frappe.db.get_value("Batch", self.semence, "batch_qty") or 0
        self.assertEqual(stock_after_insert, stock_before - 1)

        frappe.delete_doc("Insemination", ia.name, force=True, ignore_permissions=True)

        stock_after_delete = frappe.db.get_value("Batch", self.semence, "batch_qty") or 0
        self.assertEqual(stock_after_delete, stock_before)

    # ─── 17. on_trash: restore animal state if REUSSIE ────────

    def test_on_trash_reussie_restores_animal(self):
        """Deleting a REUSSIE IA should reset animal to VIDE."""
        ia = self._make_ia()
        ia.insert(ignore_permissions=True)

        ia.resultat = "REUSSIE"
        ia.save(ignore_permissions=True)

        # Confirm animal is GESTANTE
        animal = frappe.get_doc("Animal", "8100000001")
        self.assertEqual(animal.etat_gestation, "GESTANTE")

        frappe.delete_doc("Insemination", ia.name, force=True, ignore_permissions=True)

        animal.reload()
        self.assertEqual(animal.etat_gestation, "VIDE")
        self.assertIsNone(animal.id_ia_fecondante)

    # ─── 18. REUSSIE -> ECHOUEE blocked if velage depends ─────

    def test_reussie_to_echouee_blocked_if_velage_depends(self):
        """REUSSIE -> ECHOUEE should fail if a Velage depends on this IA."""
        ia = self._make_ia()
        ia.insert(ignore_permissions=True)

        ia.resultat = "REUSSIE"
        ia.save(ignore_permissions=True)

        # Create a minimal Velage record via SQL to avoid after_insert cascades
        velage_name = frappe.generate_hash("Velage", 10)
        frappe.db.sql("""
            INSERT INTO `tabVelage` (name, animal, date_velage, insemination, owner, creation, modified, modified_by, docstatus)
            VALUES (%s, %s, %s, %s, 'Administrator', NOW(), NOW(), 'Administrator', 0)
        """, (velage_name, "8100000001", add_days(today(), -1), ia.name))

        ia.reload()
        ia.resultat = "ECHOUEE"
        self.assertRaises(
            frappe.exceptions.ValidationError,
            ia.save,
            ignore_permissions=True,
        )

        # Cleanup
        frappe.db.sql("DELETE FROM `tabVelage` WHERE name = %s", velage_name)

    # ─── 19. on_trash blocked if velage depends ───────────────

    def test_on_trash_blocked_if_velage_depends(self):
        """Deleting IA should fail if a Velage depends on it."""
        ia = self._make_ia()
        ia.insert(ignore_permissions=True)

        # Create a minimal Velage record via SQL to avoid after_insert cascades
        velage_name = frappe.generate_hash("Velage", 10)
        frappe.db.sql("""
            INSERT INTO `tabVelage` (name, animal, date_velage, insemination, owner, creation, modified, modified_by, docstatus)
            VALUES (%s, %s, %s, %s, 'Administrator', NOW(), NOW(), 'Administrator', 0)
        """, (velage_name, "8100000001", add_days(today(), -1), ia.name))

        self.assertRaises(
            frappe.exceptions.ValidationError,
            frappe.delete_doc,
            "Insemination",
            ia.name,
            force=True,
            ignore_permissions=True,
        )

        # Cleanup
        frappe.db.sql("DELETE FROM `tabVelage` WHERE name = %s", velage_name)

    # ─── 20. REUSSIE sets correct dates on animal ─────────────

    def test_reussie_sets_correct_dates(self):
        """REUSSIE should set date_velage_prevue = date_ia + 280 days, tarissement = prevue - 60."""
        ia = self._make_ia(date_ia=add_days(today(), -10))
        ia.insert(ignore_permissions=True)

        ia.resultat = "REUSSIE"
        ia.save(ignore_permissions=True)

        animal = frappe.get_doc("Animal", "8100000001")
        expected_velage = getdate(add_days(ia.date_ia, 280))
        expected_tarissement = getdate(add_days(expected_velage, -60))

        self.assertEqual(getdate(animal.date_velage_prevue), expected_velage)
        self.assertEqual(getdate(animal.date_tarissement), expected_tarissement)
