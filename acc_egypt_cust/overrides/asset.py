import frappe
from frappe.utils import flt


def _is_composite_asset(doc):
    return doc.asset_type == "Composite Asset"


def _is_capitalized(doc):
    return flt(doc.net_purchase_amount) > 0


def _capitalized_value(doc):
    if doc.is_new():
        return 0
    return flt(
        frappe.db.sql(
            """select sum(total_value) from `tabAsset Capitalization`
            where target_asset=%s and docstatus=1""",
            doc.name,
        )[0][0]
    )


def sync_composite_asset_value(doc):
    # Asset Capitalization writes net_purchase_amount straight to the db
    # (update_target_asset), so a form still holding the pre-capitalization 0
    # would wipe it on save. Re-derive it from the submitted capitalizations.
    if not _is_composite_asset(doc) or doc.docstatus != 0:
        return
    value = _capitalized_value(doc)
    if value:
        doc.net_purchase_amount = value
        doc.purchase_amount = value


def _is_non_depreciable_category(doc):
    # "Non-depreciable" is read off the Item's own Asset Category (Item.asset_category),
    # not the Asset's asset_category field, which can be blank or diverge from the item.
    if not doc.item_code:
        return False
    item_asset_category = frappe.db.get_value("Item", doc.item_code, "asset_category")
    if not item_asset_category:
        return False
    return bool(frappe.db.get_value("Asset Category", item_asset_category, "non_depreciable_category"))


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
    missing, and an empty Salvage Value defaults to the Asset Category's
    custom_default_salvage_value (draft or submitted, Composite Asset included).

    custom_stop_auto_calculate_depreciation lets a user with permlevel 1 access opt
    an asset out of this auto-marking entirely, leaving Calculate Depreciation and
    Finance Books exactly as manually set - except a non-depreciable category still
    forces Calculate Depreciation off, since erpnext rejects that combination outright.
    """
    sync_composite_asset_value(doc)

    if doc.get("custom_stop_auto_calculate_depreciation") and not _is_non_depreciable_category(doc):
        return

    if not _should_calculate_depreciation(doc):
        doc.calculate_depreciation = 0
        doc.finance_books = []
        return

    doc.calculate_depreciation = 1

    if not doc.get("finance_books") and doc.item_code and doc.asset_category:
        from erpnext.assets.doctype.asset.asset import get_item_details

        for row in get_item_details(doc.item_code, doc.asset_category, doc.net_purchase_amount):
            doc.append("finance_books", row)

    default_salvage_value = _get_default_salvage_value(doc)
    if not default_salvage_value:
        return

    # erpnext requires expected_value_after_useful_life < net_purchase_amount
    # (asset.py: validate_asset_finance_books), so skip whenever the default
    # wouldn't satisfy that - net_purchase_amount may simply not be entered yet.
    if default_salvage_value >= flt(doc.net_purchase_amount):
        return

    for row in doc.get("finance_books") or []:
        if not row.expected_value_after_useful_life:
            row.expected_value_after_useful_life = default_salvage_value


def _get_default_salvage_value(doc):
    """Default Salvage Value configured on the Asset's Asset Category
    (custom_default_salvage_value). 0 when unset, meaning leave Salvage Value alone."""
    if not doc.asset_category:
        return 0
    return flt(frappe.db.get_value("Asset Category", doc.asset_category, "custom_default_salvage_value"))


def cancel_unscheduled_depreciation_entries(doc, method=None):
    """erpnext's Asset cancel only cancels the depreciation entries linked to the active
    depreciation schedule. Entries posted on disposal (e.g. Asset Capitalization submit) and
    their reversals (posted on its cancel) aren't linked to any schedule, so they'd keep the
    asset linked and block the cancel. Cancel them too, newest first so a reversal is
    cancelled before the entry it reverses."""
    entries = frappe.db.sql(
        """select distinct je.name from `tabJournal Entry` je
        join `tabJournal Entry Account` jea on jea.parent = je.name
        where jea.reference_type = 'Asset' and jea.reference_name = %s
            and je.voucher_type = 'Depreciation Entry' and je.docstatus = 1
        order by je.creation desc""",
        doc.name,
        pluck=True,
    )
    for name in entries:
        frappe.get_doc("Journal Entry", name).cancel()
