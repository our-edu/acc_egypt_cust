from frappe import _


def get_dashboard_data(data):
	"""Add the Purchase Invoice the asset was bought on to the Asset Connections tab."""
	data.setdefault("internal_links", {})["Purchase Invoice"] = "purchase_invoice"

	transactions = data.setdefault("transactions", [])
	if any("Purchase Invoice" in group.get("items", []) for group in transactions):
		return data

	transactions.append({"label": _("Purchase"), "items": ["Purchase Invoice"]})
	return data
