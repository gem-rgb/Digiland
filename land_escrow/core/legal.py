"""Reusable legal references for land purchase and transfer workflows."""

LAND_TRANSACTION_LAWS = [
    {
        "title": "Law of Contract Act",
        "citation": "Cap. 23, section 3(3)",
        "official_url": "https://new.kenyalaw.org/akn/ke/act/1960/43",
        "applies_to": "All land sale agreements",
        "summary": (
            "A contract for the disposition of an interest in land should be in writing, "
            "signed by all parties, and attested by a witness who was present at signing."
        ),
        "required": True,
    },
    {
        "title": "Land Registration Act",
        "citation": "Cap. 300, sections 36, 37 and 43",
        "official_url": "https://new.kenyalaw.org/akn/ke/act/2012/3/eng%402022-12-31",
        "applies_to": "Transfer and registration of title",
        "summary": (
            "Transfers are completed through the prescribed instrument, filing, and "
            "registration of the transferee as proprietor; the disposition does not take effect "
            "until registration."
        ),
        "required": True,
    },
    {
        "title": "Land Control Act",
        "citation": "Cap. 302, section 6",
        "official_url": "https://new.kenyalaw.org/akn/ke/act/1967/34/eng%402022-12-31",
        "applies_to": "Agricultural land or other controlled transactions",
        "summary": (
            "Sales, transfers, leases, mortgages, exchanges, partitions, or other dealings in "
            "controlled agricultural land require consent from the relevant Land Control Board."
        ),
        "required": False,
    },
    {
        "title": "Stamp Duty Act",
        "citation": "Cap. 480",
        "official_url": "https://new.kenyalaw.org/akn/ke/act/1958/31/eng%402025-07-01",
        "applies_to": "Conveyancing instruments and transfer documents",
        "summary": (
            "Transfer documents must be duly stamped before they can move through the "
            "registration process."
        ),
        "required": True,
    },
    {
        "title": "Matrimonial Property Act",
        "citation": "Cap. 152, section 12",
        "official_url": "https://new.kenyalaw.org/akn/ke/act/2013/49",
        "applies_to": "Land that is matrimonial property",
        "summary": (
            "Where the property is matrimonial property, written and informed spousal consent "
            "is required before alienation or mortgaging."
        ),
        "required": False,
    },
    {
        "title": "Constitution of Kenya",
        "citation": "Articles 40 and 60",
        "official_url": "https://new.kenyalaw.org/akn/ke/act/2010/constitution",
        "applies_to": "Property rights and land policy",
        "summary": (
            "The Constitution protects the right to property and sets the core principles for "
            "land management, access, transparency, and sustainable administration."
        ),
        "required": True,
    },
]

LAND_TRANSACTION_CHECKLIST = [
    "Confirm buyer and seller identity before signing.",
    "Use a written agreement signed by all parties and witnessed at signing.",
    "Check whether the land is agricultural or otherwise controlled before transfer.",
    "Obtain Land Control Board consent where the transaction is controlled land.",
    "Ensure stamp duty and registration steps are completed before final transfer.",
    "Check spousal consent requirements where the land is matrimonial property.",
]

JOINT_LAND_TRANSACTION_LAWS = [
    {
        "title": "Law of Contract Act",
        "citation": "Cap. 23, section 3(3)",
        "official_url": "https://new.kenyalaw.org/akn/ke/act/1960/43",
        "applies_to": "All joint land sale contracts",
        "summary": (
            "A land-disposition contract must be in writing, signed by all parties, and attested "
            "by a witness present at signing."
        ),
        "required": True,
    },
    {
        "title": "Land Registration Act",
        "citation": "Cap. 300, section 91",
        "official_url": "https://new.kenyalaw.org/akn/ke/act/2012/3/eng%402022-12-31",
        "applies_to": "Joint tenancy and tenancy in common",
        "summary": (
            "Co-ownership is recognised under Kenyan land law. For a transfer to two or more people, "
            "the register must show whether the owners are joint tenants or tenants in common, and if "
            "the transfer does not specify the nature of the rights, the presumption is tenancy in common "
            "in equal shares. Current Kenyan law limits new joint tenancies to spouses or cases allowed by court, "
            "so group buyers should normally use tenancy in common with stated shares."
        ),
        "required": True,
    },
    {
        "title": "Land Registration Act",
        "citation": "Cap. 300, section 92",
        "official_url": "https://new.kenyalaw.org/akn/ke/act/2012/3/eng%402022-12-31",
        "applies_to": "Copies of title for each co-buyer",
        "summary": (
            "Each co-tenant is entitled to a copy of the title. The register also records the co-ownership "
            "details so every member can confirm the registered interest."
        ),
        "required": False,
    },
    {
        "title": "Land Registration Act",
        "citation": "Cap. 300, section 93",
        "official_url": "https://new.kenyalaw.org/akn/ke/act/2012/3/eng%402022-12-31",
        "applies_to": "Spouses buying for co-ownership and use",
        "summary": (
            "Where a spouse acquires land during marriage for the co-ownership and use of both spouses, "
            "the property is treated as matrimonial property and the Matrimonial Property Act applies."
        ),
        "required": False,
    },
    {
        "title": "Land Control Act",
        "citation": "Cap. 302, section 6",
        "official_url": "https://new.kenyalaw.org/akn/ke/act/1967/34",
        "applies_to": "Agricultural or controlled land",
        "summary": (
            "Sales, transfers, leases, mortgages, exchanges, partitions, or other dealings in "
            "controlled agricultural land require Land Control Board consent."
        ),
        "required": False,
    },
    {
        "title": "Stamp Duty Act",
        "citation": "Cap. 480, section 5",
        "official_url": "https://new.kenyalaw.org/akn/ke/act/1958/31",
        "applies_to": "Transfer instruments and conveyancing documents",
        "summary": (
            "Conveyancing instruments that relate to land in Kenya are chargeable with stamp duty "
            "and must be duly stamped before registration."
        ),
        "required": True,
    },
    {
        "title": "Matrimonial Property Act",
        "citation": "Cap. 152, section 12",
        "official_url": "https://new.kenyalaw.org/akn/ke/act/2013/49",
        "applies_to": "Joint purchases that are matrimonial property",
        "summary": (
            "If the property is matrimonial property, written and informed spousal consent is "
            "required before alienation, leasing, or mortgaging."
        ),
        "required": False,
    },
    {
        "title": "Constitution of Kenya",
        "citation": "Articles 40 and 60",
        "official_url": "https://new.kenyalaw.org/akn/ke/act/2010/constitution",
        "applies_to": "Property rights and land policy",
        "summary": (
            "The Constitution protects the right to own property individually or in association "
            "with others, and requires equitable, efficient, transparent, and sustainable land management."
        ),
        "required": True,
    },
]

JOINT_LAND_TRANSACTION_CHECKLIST = [
    "Identify all co-buyers and confirm the ownership shares before signing.",
    "For a group purchase, register the property as tenants in common unless the buyers are spouses or have court leave for joint tenancy.",
    "Confirm whether the land is agricultural or otherwise controlled before transfer.",
    "Obtain Land Control Board consent where the transaction is controlled land.",
    "Stamp and register the transfer instrument before completion.",
    "Check spousal consent requirements where any co-buyer or seller is married and the land is matrimonial property.",
]

JOINT_PAYMENT_GUIDANCE = [
    "Record the joint bank account name, number, and branch before payment is initiated.",
    "Use the bank account mandate signed by the listed co-buyers as the source of payment authority.",
    "If the group prefers M-Pesa instead of bank transfer, split contributions can still be sent by member.",
]
