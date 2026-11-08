__version__ = "0.0.1"

# Import to apply monkeypatches at app load time
try:
	# erpnext isn't importable while acc_egypt_cust is built before it (Frappe Cloud build order)
	from acc_egypt_cust.overrides import depreciation  # noqa: F401
except ImportError:
	pass
