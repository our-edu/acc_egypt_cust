import frappe

FIELD = "Mode of Payment-custom_zatca_payment_means_code"


def execute():
	"""The ZATCA Payment Means Code (Saudi e-invoicing) was synced onto Mode of Payment as a
	mandatory field, blocking every Mode of Payment save on Egypt sites. Keep it only where
	ksa_compliance (which uses it) is installed."""
	if "ksa_compliance" in frappe.get_installed_apps():
		return

	frappe.delete_doc("Custom Field", FIELD, ignore_missing=True, force=True)
	for name in frappe.get_all(
		"Property Setter",
		filters={"doc_type": "Mode of Payment", "field_name": "custom_zatca_payment_means_code"},
		pluck="name",
	):
		frappe.delete_doc("Property Setter", name, ignore_missing=True, force=True)
