"""Validate attributed raw catalog excerpts and normalize supported physical units.

normalize_records consumes raw metadata plus explicit source-field excerpts and a
source manifest. It returns S1-compatible products (without splits), rejection
reasons and provenance; task builders and splitters must run only afterwards.
No model inference, network calls or facts inferred from marketing text occur.
"""
from __future__ import annotations

import copy
from decimal import Decimal, InvalidOperation
import hashlib
import json
import math
import re

_FIELD = re.compile(r'^[a-z][a-z0-9_]{0,63}$')
_NUMBER = re.compile(r'^\s*\$?([0-9]+(?:\.[0-9]+)?)\s*([A-Za-z]*)\s*$')
_UNITS = {'g': ('g', Decimal('1')), 'kg': ('g', Decimal('1000')),
          'lb': ('g', Decimal('453.59237')), 'lbs': ('g', Decimal('453.59237')),
          'pounds': ('g', Decimal('453.59237')), 'ounces': ('g', Decimal('28.349523125')),
          'oz': ('g', Decimal('28.349523125')), 'ounce': ('g', Decimal('28.349523125')),
          'gram': ('g', Decimal('1')), 'grams': ('g', Decimal('1')),
          'kilograms': ('g', Decimal('1000')), 'w': ('W', Decimal('1')),
          'watts': ('W', Decimal('1')), 'watt': ('W', Decimal('1')),
          'usd': ('USD', Decimal('1')), '': ('', Decimal('1'))}


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _at(raw: object, path: list) -> object:
    if not isinstance(path, list) or not path:
        raise ValueError('missing_source_field')
    value = raw
    for key in path:
        if not isinstance(key, (str, int)) or isinstance(key, bool):
            raise ValueError('invalid_source_field')
        if isinstance(value, str):
            value = json.loads(value)
        value = value[key]
    return value


def normalize_value(value: object, unit: str | None) -> tuple[object, str | None]:
    """Use Decimal for exact conversion, rejecting nonfinite/ambiguous quantities."""
    if unit is None:
        if isinstance(value, str):
            if not value.strip(): raise ValueError('empty_value')
            return value.strip(), None
        if isinstance(value, (bool, list)):
            if isinstance(value, list) and (not value or any(not isinstance(x, str) for x in value)):
                raise ValueError('invalid_value')
            return copy.deepcopy(value), None
        if type(value) is int: return value, None
        raise ValueError('unit_required_for_numeric_value')
    if not isinstance(unit, str) or unit.lower() not in _UNITS or isinstance(value, bool):
        raise ValueError('unsupported_unit')
    try: number = Decimal(str(value))
    except InvalidOperation as error: raise ValueError('invalid_numeric_value') from error
    if not number.is_finite() or number < 0: raise ValueError('invalid_numeric_value')
    canonical_unit, factor = _UNITS[unit.lower()]
    result = number * factor
    if not math.isfinite(float(result)):
        raise ValueError('numeric_overflow')
    if canonical_unit == 'USD':
        try: precise = result.quantize(Decimal('0.01'))
        except InvalidOperation as error: raise ValueError('numeric_overflow') from error
        if result != precise: raise ValueError('price_precision_exceeds_cents')
    # SQLite/JSON downstream uses finite ints/floats. The exact Decimal source and
    # conversion remain in evidence provenance, avoiding binary arithmetic here.
    return (int(result) if result == result.to_integral_value() else float(result)), canonical_unit


def _verify_fact(raw: dict, fact: dict) -> tuple[str, object, str | None, object]:
    field = fact['field']
    if not isinstance(field, str) or not _FIELD.fullmatch(field): raise ValueError('invalid_field')
    original = _at(raw, fact['source_field'])
    quote = fact['quote']
    if not isinstance(quote, str) or not quote or quote != str(original):
        raise ValueError('quote_does_not_match_source')
    value, unit = normalize_value(fact['value'], fact.get('unit'))
    if fact.get('unit') is None:
        if _digest(original) != _digest(fact['value']): raise ValueError('value_does_not_match_source')
    else:
        if not isinstance(original, (str, int, float)) or isinstance(original, bool):
            raise ValueError('invalid_numeric_source')
        match = _NUMBER.fullmatch(str(original))
        if not match: raise ValueError('ambiguous_numeric_source')
        original_unit = match.group(2) or fact['unit']
        # A currencyless metadata price may use the source-declared USD mapping;
        # explicit suffixes must agree after conversion rather than being ignored.
        original_value, original_canonical = normalize_value(match.group(1), original_unit)
        if original_canonical != unit or _digest(original_value) != _digest(value):
            raise ValueError('value_or_unit_does_not_match_source')
    if field == 'price' and (unit != 'USD' or fact['source_field'] != ['price']):
        raise ValueError('price_requires_USD_metadata_price')
    if field == 'weight_g' and unit != 'g': raise ValueError('weight_requires_mass_unit')
    return field, value, unit, original


def normalize_records(records: list[dict], *, source: dict) -> dict:
    """Reject unverifiable records; preserve accepted facts and all refusal reasons.

    source requires id/url/revision/sha256/retrieved_at/license. records each holds
    raw metadata, explicit facts, source_row_index and identity.brand_source_field.
    Family defaults conservatively to the full source brand, pending human review.
    The function never assigns a split or treats absent facts as negative facts.
    """
    required = ('id', 'url', 'revision', 'sha256', 'retrieved_at', 'license')
    if not isinstance(source, dict) or any(not source.get(k) for k in required):
        raise ValueError('Incomplete source manifest')
    if not re.fullmatch('[0-9a-f]{64}', source['sha256']):
        raise ValueError('Invalid source SHA256')
    products, rejected, seen = [], [], set()
    for index, record in enumerate(records):
        product_id = None
        try:
            raw = record['raw']
            if not isinstance(raw, dict): raise ValueError('raw_record_required')
            product_id = raw['parent_asin']
            if not isinstance(product_id, str) or not product_id.strip(): raise ValueError('product_id_required')
            if product_id in seen: raise ValueError('duplicate_product_id')
            seen.add(product_id)
            if record.get('raw_sha256') != _digest(raw): raise ValueError('raw_record_hash_mismatch')
            title = raw['title']
            if not isinstance(title, str) or not title.strip(): raise ValueError('title_required')
            brand = _at(raw, record['identity']['brand_source_field'])
            if not isinstance(brand, str) or not brand.strip(): raise ValueError('brand_source_required')
            brand = brand.strip()
            model_path = record['identity'].get('model_source_field')
            model = _at(raw, model_path) if model_path else None
            family = 'brand:' + re.sub(r'\s+', ' ', brand.lower())
            values, evidence, unit_map = {}, [], {}
            for fact in record['facts']:
                field, value, unit, original = _verify_fact(raw, fact)
                if field in values: raise ValueError('duplicate_or_conflicting_fact')
                values[field], unit_map[field] = value, unit
                evidence.append({'evidence_id':f'{product_id}:details:{field}',
                                 'product_id':product_id, 'field':field,'value':value,
                                 'channel':'details','text':fact['quote'],
                                 'provenance':{'source_id':source['id'],'source_revision':source['revision'],
                                    'source_sha256':source['sha256'],'source_field':fact['source_field'],
                                    'raw_value':original,'raw_unit':fact.get('unit'),'unit':unit,
                                    'source_row_index':record.get('source_row_index'),
                                    'raw_record_sha256':_digest(raw)}})
            if source.get('currency') != 'USD': raise ValueError('source_currency_not_confirmed_USD')
            if 'price' not in values: raise ValueError('missing_price')
            if len(values) < 3: raise ValueError('fewer_than_two_specifications')
            if values['price'] <= 0: raise ValueError('nonpositive_price')
            products.append({'product_id':product_id,'title':title.strip(),'price':values.pop('price'),
                             'specs':values,'family':family,'brand':brand,'model':model,
                             'identity_review_required':True,'units':unit_map,'evidence':evidence,
                             'provenance':{'source_id':source['id'],'source_revision':source['revision'],
                                'raw_record_sha256':_digest(raw),'source_row_index':record.get('source_row_index'),
                                'family_method':'conservative_all_products_of_source_brand',
                                'family_status':'pending_manual_review'}})
        except (KeyError, TypeError, ValueError, IndexError, OverflowError) as error:
            rejected.append({'record_index':index,'product_id':product_id,'reason':str(error)})
    return {'products':products,'rejected':rejected,'source_manifest':{
        **copy.deepcopy(source),'input_records':len(records),'accepted_records':len(products),
        'rejected_records':len(rejected),'records_sha256':_digest(records),
        'normalizer_version':'s2-source-v1','split_assigned':False}}
