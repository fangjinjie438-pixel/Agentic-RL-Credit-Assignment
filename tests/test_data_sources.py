"""S2 CPU source checks: quoted raw facts, units, hashes and target-metadata quarantine.

Inputs are independent synthetic excerpts for boundary checks and pinned real
pilot metadata for integration. Outputs are unittest results; no network/GPU/API.
"""
from __future__ import annotations
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from procure_rl.data.sources import normalize_records, normalize_value
from procure_rl.env.catalog import build_catalog, Catalog

ROOT = Path(__file__).resolve().parents[1]

def canonical_hash(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',', ':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()

def example():
    raw={'parent_asin':'SYNTHETIC-SOURCE-1','title':'Synthetic only','price':24.99,
         'details':{'Brand':'Example','Model':'K1','Mass':'0.25 kg','Color':'White'}}
    facts=[{'field':'price','value':'24.99','unit':'USD','source_field':['price'],'quote':'24.99'},
           {'field':'weight_g','value':'0.25','unit':'kg','source_field':['details','Mass'],'quote':'0.25 kg'},
           {'field':'color','value':'White','unit':None,'source_field':['details','Color'],'quote':'White'}]
    source={'id':'synthetic-test','url':'https://example.invalid/source','revision':'test-v1','sha256':'a'*64,
            'retrieved_at':'2026-10-22T00:00:00Z','license':{'usage':'synthetic'},'currency':'USD'}
    record={'raw':raw,'raw_sha256':canonical_hash(raw),'facts':facts,'source_row_index':0,
            'identity':{'brand_source_field':['details','Brand'],'model_source_field':['details','Model']}}
    return record,source

class SourceTests(unittest.TestCase):
    def normalize(self,record,source):return normalize_records([record],source=source)
    def test_decimal_units_and_cents(self):
        self.assertEqual(normalize_value('0.25','kg'),(250,'g'))
        self.assertEqual(normalize_value('1','pounds'),(453.59237,'g'))
        self.assertEqual(normalize_value('4','oz'),(113.3980925,'g'))
        self.assertEqual(normalize_value('65','watts'),(65,'W'))
        self.assertEqual(normalize_value('0.10','USD'),(0.1,'USD'))
        for value,unit in [('1.001','USD'),('NaN','W'),('-1','g'),('10','EUR'),(True,'W'),('1e999','g')]:
            with self.subTest(value=value,unit=unit),self.assertRaises(ValueError):normalize_value(value,unit)
    def test_valid_facts_no_split_and_input_unchanged(self):
        record,source=example();before=copy.deepcopy((record,source));result=self.normalize(record,source)
        self.assertEqual(len(result['products']),1);p=result['products'][0]
        self.assertEqual(p['specs']['weight_g'],250);self.assertEqual(p['family'],'brand:example')
        self.assertTrue(p['identity_review_required']);self.assertNotIn('split',p)
        self.assertEqual(p['evidence'][1]['provenance']['source_revision'],'test-v1')
        self.assertEqual((record,source),before)
    def test_source_revision_and_hash_required(self):
        record,source=example()
        for key in ['revision','sha256','license','url']:
            altered=copy.deepcopy(source);altered.pop(key)
            with self.subTest(key=key),self.assertRaises(ValueError):self.normalize(record,altered)
    def test_raw_hash_rejects_changed_record(self):
        record,source=example();record['raw']['price']=99
        self.assertEqual(self.normalize(record,source)['rejected'][0]['reason'],'raw_record_hash_mismatch')
    def test_quote_and_field_must_match_source(self):
        for change in ['quote','value','source_field']:
            record,source=example();f=record['facts'][2]
            f[change]={'quote':'Black','value':'Black','source_field':['details','absent']}[change]
            self.assertEqual(len(self.normalize(record,source)['products']),0)
    def test_contradictions_duplicates_and_missing_price_rejected(self):
        record,source=example();record['facts'].append(copy.deepcopy(record['facts'][2]))
        self.assertEqual(self.normalize(record,source)['rejected'][0]['reason'],'duplicate_or_conflicting_fact')
        record,source=example();record['facts']=record['facts'][1:]
        self.assertEqual(self.normalize(record,source)['rejected'][0]['reason'],'missing_price')
    def test_explicit_unit_cannot_be_overridden(self):
        record,source=example();record['facts'][1]['unit']='g'
        self.assertEqual(len(self.normalize(record,source)['products']),0)
    def test_currency_mapping_must_be_declared(self):
        record,source=example();source['currency']='EUR'
        self.assertEqual(self.normalize(record,source)['rejected'][0]['reason'],'source_currency_not_confirmed_USD')
    def test_numeric_price_must_come_from_price_field(self):
        record,source=example();record['facts'][0]['source_field']=['details','Mass']
        record['facts'][0]['quote']='0.25 kg';record['facts'][0]['unit']='kg';record['facts'][0]['value']='0.25'
        self.assertEqual(self.normalize(record,source)['rejected'][0]['reason'],'price_requires_USD_metadata_price')
    def test_pinned_real_metadata_to_readonly_catalog(self):
        fixture=json.loads((ROOT/'fixtures/s2/amazon-electronics.json').read_text())
        result=normalize_records(fixture['records'],source=fixture['source'])
        self.assertEqual(result['rejected'],[]);self.assertEqual(len(result['products']),12)
        self.assertEqual(sum('color' in p['specs'] for p in result['products']),8)
        with tempfile.TemporaryDirectory() as directory:
            directory=Path(directory);source=directory/'source.json'
            source.write_text(json.dumps({'revision':'real-pilot-test','products':[
                dict(p,split='train') for p in result['products']]}))
            build_catalog(source,directory/'catalog');catalog=Catalog(directory/'catalog','train')
            self.assertEqual(catalog.product('B0BKS1K986')['price'],89.99)
            self.assertEqual(len(catalog.evidence('B0BKS1K986','details')),4)
    def test_quarantine_uses_target_metadata_and_excludes_known_brands(self):
        exclusion=json.loads((ROOT/'fixtures/s2/official-exclusions.json').read_text())
        self.assertEqual(exclusion['official_task_count'],662)
        self.assertEqual(len(exclusion['product_ids']),660)
        self.assertTrue(all(field.startswith('target_product.') for field in exclusion['accessed_fields']))
        self.assertEqual(exclusion['coverage'],'target_ids_and_available_brand_model_title')
        self.assertFalse(exclusion['metadata_complete'])
        self.assertNotIn('rubrics',exclusion)
        self.assertEqual(len(exclusion['unknown_family_product_ids']),3)
        self.assertTrue({'brand:logitech','brand:samsung','brand:dell','brand:hp'} <= set(exclusion['families']))
        self.assertEqual(len(exclusion['titles']),660)
        fixture=json.loads((ROOT/'fixtures/s2/amazon-electronics.json').read_text())
        self.assertFalse(set(exclusion['product_ids'])&{r['raw']['parent_asin'] for r in fixture['records']})
        from procure_rl.data.split import split_products
        products=normalize_records(fixture['records'],source=fixture['source'])['products']
        result=split_products(products,exclusion,seed=0)
        self.assertEqual({p['brand'] for p in result['quarantined']},{'Logitech','SAMSUNG','Dell','HP'})

if __name__ == '__main__': unittest.main()
