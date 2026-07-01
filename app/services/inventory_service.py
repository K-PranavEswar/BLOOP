"""
Inventory service – manages blood stock levels.

Key invariants enforced here:
  - One row per (blood_type, component) combination.
  - update_stock() always UPDATEs an existing row; never INSERTs a second one.
  - seed_inventory_from_csv() is idempotent: safe to call on every startup.
  - _deduplicate_inventory() merges any rows that already exist as duplicates.
"""
from datetime import datetime
from app.extensions import db
from app.models.blood_inventory import BloodInventory
from app.utils.helpers import log_activity

BLOOD_TYPES = ['O+', 'O-', 'A+', 'A-', 'B+', 'B-', 'AB+', 'AB-']
COMPONENTS  = ['Whole Blood', 'Platelets', 'Plasma']


# ─────────────────────────────────────────────────────────────────────────────
#  Deduplication (run once at startup — no-op if table is already clean)
# ─────────────────────────────────────────────────────────────────────────────

def _deduplicate_inventory():
    """
    Merge duplicate (blood_type, component) rows that were created before the
    UniqueConstraint existed.  For each duplicate group:
      - Keep the row with the highest current_units (most credible value).
      - Delete all others.
    This is a one-time safe migration and is idempotent.
    """
    from sqlalchemy import func, text

    # Find groups that have more than one row
    duplicates = (
        db.session.query(BloodInventory.blood_type, BloodInventory.component)
        .group_by(BloodInventory.blood_type, BloodInventory.component)
        .having(func.count(BloodInventory.id) > 1)
        .all()
    )

    merged_count = 0
    for blood_type, component in duplicates:
        rows = (
            BloodInventory.query
            .filter_by(blood_type=blood_type, component=component)
            .order_by(BloodInventory.current_units.desc(), BloodInventory.id.asc())
            .all()
        )
        # Keep the first (highest stock), delete the rest
        keep = rows[0]
        for dupe in rows[1:]:
            # Accumulate units into the keeper row before deleting dupes
            keep.current_units += dupe.current_units
            db.session.delete(dupe)
            merged_count += 1

    if merged_count:
        db.session.commit()
        print(f'[inventory_service] Merged {merged_count} duplicate inventory row(s).')


# ─────────────────────────────────────────────────────────────────────────────
#  Unique constraint migration (add it to existing databases)
# ─────────────────────────────────────────────────────────────────────────────

def _ensure_unique_constraint():
    """
    Attempt to create the UNIQUE index on (blood_type, component) if it does
    not already exist.  SQLite does not support ALTER TABLE ADD CONSTRAINT, so
    we create a standalone unique index instead.
    """
    from sqlalchemy import text
    try:
        db.session.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_blood_type_component "
            "ON blood_inventory (blood_type, component)"
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()   # index may already exist — that is fine


# ─────────────────────────────────────────────────────────────────────────────
#  Seeding
# ─────────────────────────────────────────────────────────────────────────────

def seed_inventory_from_csv():
    """
    Seed inventory from the dataset CSV (or hardcoded defaults).
    Idempotent: uses INSERT OR IGNORE so it never creates duplicate rows.
    Safe to call on every application startup.
    """
    # Step 1: merge any pre-existing duplicates before we do anything else
    _deduplicate_inventory()

    # Step 2: ensure the unique index exists on the live DB
    _ensure_unique_constraint()

    # Step 3: fill in any missing (blood_type, component) combinations
    import os, csv
    csv_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        'dataset', 'inventory.csv'
    )

    # Build a set of already-present (blood_type, component) pairs
    existing = {
        (row.blood_type, row.component)
        for row in BloodInventory.query.all()
    }

    if csv_path and os.path.exists(csv_path):
        _seed_from_csv_file(csv_path, existing)
    else:
        _seed_defaults(existing)


def _seed_from_csv_file(csv_path, existing):
    """Insert only the rows that are not already present."""
    import csv
    added = 0
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            # The dataset/inventory.csv uses 'blood_group' as the column name
            bt = row.get('blood_group') or row.get('blood_type')
            if not bt:
                continue
            for component in COMPONENTS:
                if (bt, component) in existing:
                    continue   # already present – do NOT insert
                factor = _component_factor(component)
                inv = BloodInventory(
                    blood_type=bt, component=component,
                    current_units=int(float(row['current_stock']) * factor),
                    max_capacity=int(float(row['max_capacity']) * factor),
                    safety_stock=int(float(row['safety_stock']) * factor)
                )
                db.session.add(inv)
                added += 1
    if added:
        db.session.commit()
        print(f'[inventory_service] Seeded {added} inventory row(s) from CSV.')


def _seed_defaults(existing):
    """Insert only the rows that are not already present (hardcoded defaults)."""
    defaults = {
        'O+':  (52, 154, 64), 'A+':  (54, 121, 50),
        'B+':  (22, 62,  26), 'AB+': (7,  17,   7),
        'O-':  (23, 45,  19), 'A-':  (6,  9,    3),
        'B-':  (4,  10,   2), 'AB-': (1,  3,    1),
    }
    added = 0
    for bt, (stock, cap, safety) in defaults.items():
        for component in COMPONENTS:
            if (bt, component) in existing:
                continue   # already present – do NOT insert
            factor = _component_factor(component)
            inv = BloodInventory(
                blood_type=bt, component=component,
                current_units=int(stock * factor),
                max_capacity=int(cap * factor),
                safety_stock=int(safety * factor)
            )
            db.session.add(inv)
            added += 1
    if added:
        db.session.commit()
        print(f'[inventory_service] Seeded {added} default inventory row(s).')


def _component_factor(component):
    return {'Whole Blood': 1.0, 'Platelets': 0.3, 'Plasma': 0.2}.get(component, 1.0)


# ─────────────────────────────────────────────────────────────────────────────
#  Upsert / update (never inserts a new row)
# ─────────────────────────────────────────────────────────────────────────────

def update_stock(blood_type, component, units, transaction_type, user_id=None):
    """
    Update blood stock.  transaction_type: 'receive' or 'issue'.

    IMPORTANT: this function always fetches the SINGLE existing row for the
    given (blood_type, component) and mutates it in-place.  It never calls
    db.session.add(), so it can never create a second row.

    Returns (success: bool, message: str).
    """
    inv = BloodInventory.query.filter_by(
        blood_type=blood_type, component=component
    ).first()

    if not inv:
        return False, f'Inventory record not found for {blood_type} / {component}.'

    if transaction_type == 'receive':
        new_val = min(inv.max_capacity, inv.current_units + units)
        inv.current_units = new_val
        action = f'Received {units} units of {blood_type} ({component})'

    elif transaction_type == 'issue':
        if inv.current_units < units:
            return False, f'Insufficient stock. Available: {inv.current_units} units.'
        inv.current_units -= units
        action = f'Issued {units} units of {blood_type} ({component})'

    else:
        return False, 'Invalid transaction type.'

    inv.last_updated = datetime.utcnow()
    db.session.commit()

    if user_id:
        log_activity(user_id, action)

    # Trigger AI analysis in background (non-blocking)
    from flask import current_app
    from app.services.llm_service import run_and_log_analysis_async
    try:
        app = current_app._get_current_object()
        run_and_log_analysis_async(app.app_context)
    except Exception as e:
        print(f'[inventory_service] AI analysis trigger failed (non-critical): {e}')

    return True, action


# ─────────────────────────────────────────────────────────────────────────────
#  Read helpers
# ─────────────────────────────────────────────────────────────────────────────

def get_all_inventory():
    """Return all inventory records ordered by blood type then component."""
    return BloodInventory.query.order_by(
        BloodInventory.blood_type, BloodInventory.component
    ).all()


def get_inventory_by_type(blood_type, component='Whole Blood'):
    """Return the single inventory record for a given blood type + component."""
    return BloodInventory.query.filter_by(
        blood_type=blood_type, component=component
    ).first()


def get_inventory_summary():
    from app.services.ai_risk_engine import calculate_global_risk
    return calculate_global_risk()['blood_groups']


def get_total_stock():
    """Sum of current_units across all Whole Blood records."""
    items = BloodInventory.query.filter_by(component='Whole Blood').all()
    return sum(item.current_units for item in items)
