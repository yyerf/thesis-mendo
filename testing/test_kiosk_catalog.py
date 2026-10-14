"""Public catalog and server purchase gates tested against an isolated POS database."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from pos import db
from pos.routes_checkout import checkout_bp
from pos.routes_consultation import consultation_bp
from mendo_core.unstocked_symptoms import reported_complaints, complaint_red_flags


class KioskCatalogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db_patch = patch.object(db, 'DB_PATH', str(Path(self.tmp.name) / 'pos.db'))
        self.db_patch.start()
        self.addCleanup(self.db_patch.stop)
        self.app = Flask(__name__)
        self.app.secret_key = 'catalog-tests'
        self.app.register_blueprint(consultation_bp)
        self.app.register_blueprint(checkout_bp)
        self.app.teardown_appcontext(db.close_db)
        with self.app.app_context():
            db.init_db()
            conn = db.get_db()
            conn.execute('UPDATE inventory SET stock_quantity=99 WHERE is_active=1')
            conn.commit()
        self.client = self.app.test_client()

    def test_catalog_information_stock_images_and_active_supplement(self):
        response = self.client.get('/consult/api/catalog')
        self.assertEqual(response.status_code, 200)
        products = response.get_json()['products']
        self.assertEqual(len(products), 10)
        root = Path(__file__).resolve().parents[1]
        for product in products:
            self.assertEqual(product['available_quantity'], 99)
            self.assertTrue((root / 'web' / product['image'].lstrip('/')).is_file(), product['image'])
            self.assertTrue(product['generic_name'])
            self.assertTrue(product['instructions'])
        supplement = next(p for p in products if p['is_supplement'])
        self.assertTrue(supplement['purchasable'])
        self.assertEqual(supplement['hardware_slot'], 10)
        self.assertEqual(supplement['minimum_age'], 12)

    def test_nutrabliss_adds_to_cart_and_reserves_real_stock(self):
        from pos.order_service import OrderService
        brand = 'Nutrabliss Daily Defense Probiotic'
        self.client.post('/consult/api/catalog-age', json={'age':11})
        self.assertEqual(self.client.post('/checkout/api/cart/add', json={'brand':brand}).status_code, 400)
        self.client.post('/consult/api/catalog-age', json={'age':25})
        self.assertEqual(self.client.post('/checkout/api/cart/add', json={'brand':brand}).status_code, 200)
        item = self.client.get('/checkout/api/cart').get_json()['items'][0]
        self.assertEqual(item['brand'], brand)
        self.assertEqual(item['hardware_slot'], 10)
        self.assertEqual(item['unit_price_centavos'], 3500)
        with self.app.app_context():
            OrderService().create_order([{'inventory_id':item['inventory_id'],'quantity':1}],idempotency_key='nutrabliss-reservation')
            stored = db.get_inventory_item(item['inventory_id'])
            self.assertEqual(stored['reserved_quantity'], 1)
            self.assertEqual(stored['available_quantity'], 98)

    def test_age_limit_enforced_on_server_and_cart_quantity_enforced(self):
        product = next(p for p in self.client.get('/consult/api/catalog').get_json()['products'] if p['brand'] == 'Loperamide')
        self.assertEqual(product['minimum_age'], 12)
        self.assertEqual(self.client.post('/checkout/api/cart/add', json={'brand':'Loperamide'}).status_code, 400)
        self.client.post('/consult/api/catalog-age', json={'age':11})
        self.assertEqual(self.client.post('/checkout/api/cart/add', json={'brand':'Loperamide'}).status_code, 400)
        self.client.post('/consult/api/catalog-age', json={'age':25})
        self.assertEqual(self.client.post('/checkout/api/cart/add', json={'brand':'Loperamide','quantity':2}).status_code, 200)
        self.assertEqual(self.client.post('/checkout/api/cart/add', json={'brand':'Loperamide','quantity':2}).status_code, 400)
        self.assertEqual(self.client.get('/checkout/api/cart').get_json()['items'][0]['quantity'], 2)

    def test_new_cart_item_cannot_exceed_unreserved_stock(self):
        with self.app.app_context():
            conn = db.get_db()
            conn.execute("UPDATE inventory SET stock_quantity=2,reserved_quantity=1 WHERE brand='Biogesic'")
            conn.commit()
        self.client.post('/consult/api/catalog-age', json={'age':25})
        response = self.client.post('/checkout/api/cart/add', json={'brand':'Biogesic','quantity':2})
        self.assertEqual(response.status_code, 400)

    def test_consent_new_session_clears_old_age_and_screen(self):
        with self.client.session_transaction() as state:
            state.update(catalog_age=25, consult_age=25, diarrhea_answers={'blood':'no'})
        self.client.post('/consult/api/research-consent', json={'consent':False})
        with self.client.session_transaction() as state:
            self.assertNotIn('catalog_age', state)
            self.assertNotIn('diarrhea_answers', state)

    def test_age_change_cannot_bypass_checkout_check(self):
        self.client.post('/consult/api/catalog-age', json={'age':25})
        self.assertEqual(self.client.post('/checkout/api/cart/add', json={'brand':'Loperamide'}).status_code, 200)
        self.client.post('/consult/api/catalog-age', json={'age':6})
        result = self.client.post('/checkout/api/orders', json={'idempotency_key':'underage-checkout'})
        self.assertEqual(result.status_code, 409)
        self.assertIn('age', result.get_json()['error'])


class UnstockedComplaintTests(unittest.TestCase):
    def test_multilingual_complaints_and_negation(self):
        for text, key in [('tootache', 'dental'), ('samad sa kamot', 'wound'), ('may sugat ako', 'wound'), ('athlete\'s foot', 'fungal'), ('bugason akong nawong', 'acne'), ('constipated', 'constipation')]:
            with self.subTest(text=text):
                self.assertIn(key, {row['key'] for row in reported_complaints(text)})
        self.assertEqual(reported_complaints('no toothache'), [])
        self.assertEqual(reported_complaints('walay samad'), [])
        self.assertEqual(reported_complaints('I have a cough'), [])
        self.assertEqual(reported_complaints('cutting costs'), [])

    def test_urgent_complaint_keeps_medical_referral(self):
        self.assertTrue(complaint_red_flags('deep cut on my hand'))
        self.assertTrue(complaint_red_flags('eye problem cannot see'))
        self.assertFalse(complaint_red_flags('small scrape on my hand'))


if __name__ == '__main__':
    unittest.main()
