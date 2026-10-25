frappe.query_reports["Employee Assets Custody"] = {
    filters: [
        {
            fieldname: "company",
            label: __("Company"),
            fieldtype: "Link",
            options: "Company"
        },

        {
            fieldname: "employee",
            label: __("Employee"),
            fieldtype: "Link",
            options: "Employee"
        },

        {
            fieldname: "asset",
            label: __("Asset"),
            fieldtype: "Link",
            options: "Asset"
        }
    ]
};
