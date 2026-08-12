import frappe
from frappe.utils import flt


def _is_composite_asset(doc):
    return doc.asset_type == "Composite Asset"


def _is_capitalized(doc):
    return flt(doc.net_purchase_amount) > 0


def _is_non_depreciable_category(doc):
    return bool(frappe.db.get_value("Asset Category", doc.asset_category, "non_depreciable_category"))


def _should_calculate_depreciation(doc):
    if _is_non_depreciable_category(doc):
        return False
    if _is_composite_asset(doc):
        # erpnext locks Calculate Depreciation for a Composite Asset while
        # net_purchase_amount is still 0 (only Asset Capitalization ever sets it -
        # see asset_capitalization.py: update_target_asset). Any Salvage Value >= 0
        # always fails validate_asset_finance_books against a 0 Net Purchase Amount,
        # so there's nothing valid to calculate until it's capitalized.
        return _is_capitalized(doc)
    return True


def set_salvage_value(doc, method=None):
    """Keep Calculate Depreciation, Finance Books, and Salvage Value in sync with
    asset_type: Calculate Depreciation defaults on for every asset except a
    non-depreciable category or an uncapitalized Composite Asset, building Finance
    Books from the Asset Category defaults (like the "Set Finance Book" button) when
    missing, and Salvage Value defaults to 1 (0 for a Composite Asset until it's
    submitted - see set_composite_asset_salvage_value_on_submit).
    """
    if not _should_calculate_depreciation(doc):
        doc.calculate_depreciation = 0
        doc.finance_books = []
        return

    doc.calculate_depreciation = 1

    if not doc.get("finance_books") and doc.item_code and doc.asset_category:
        from erpnext.assets.doctype.asset.asset import get_item_details

        for row in get_item_details(doc.item_code, doc.asset_category, doc.net_purchase_amount):
            doc.append("finance_books", row)

    composite = _is_composite_asset(doc)
    target = 0 if composite else 1

    # erpnext requires expected_value_after_useful_life < net_purchase_amount
    # (asset.py: validate_asset_finance_books), so skip whenever the target value
    # wouldn't satisfy that - net_purchase_amount may simply not be entered yet.
    if flt(target) >= flt(doc.net_purchase_amount):
        return

    for row in doc.get("finance_books") or []:
        if composite or not row.expected_value_after_useful_life:
            row.expected_value_after_useful_life = target


def set_composite_asset_salvage_value_on_submit(doc, method=None):
    """Composite Asset: Salvage Value becomes 1 once the asset is submitted."""
    if not _is_composite_asset(doc):
        return

    if flt(1) >= flt(doc.net_purchase_amount):
        return

    for row in doc.get("finance_books") or []:
        row.expected_value_after_useful_life = 1
