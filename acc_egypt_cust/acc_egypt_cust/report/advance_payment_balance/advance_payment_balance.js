frappe.query_reports["Advance Payment Balance"] = {
    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company",
            reqd: 1
        },

        {
            fieldname: "party_type",
            label: __("Party Type"),
            fieldtype: "Select",
            options: "Customer\nSupplier",
            reqd: 1,
            default: "Customer"
        },

        {
            fieldname: "party",
            label: __("Party"),
            fieldtype: "Dynamic Link",
            options: "party_type"
        },

        {
            fieldname: "advance_account",
            label: __("Advance Account"),
            fieldtype: "Link",
            options: "Account"
        },

        {
            fieldname: "from_date",
            label: __("From Date"),
            fieldtype: "Date"
        },

        {
            fieldname: "to_date",
            label: __("To Date"),
            fieldtype: "Date"
        }
    ]
};