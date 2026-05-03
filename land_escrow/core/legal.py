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
            "in equal shares."
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

SELLER_TRANSACTION_LAWS = [
    {
        "title": "Constitution of Kenya \u2013 Article 40",
        "citation": "Article 40(1)-(3)",
        "official_url": "https://new.kenyalaw.org/akn/ke/act/2010/constitution",
        "applies_to": "Seller\u2019s right to own and dispose of property",
        "summary": (
            "Every person has the right to acquire and own property in any part of Kenya. "
            "The State shall not deprive a person of property except in accordance with the Constitution. "
            "The seller must demonstrate lawful ownership before disposition."
        ),
        "required": True,
    },
    {
        "title": "Land Registration Act \u2013 Transfer Obligations",
        "citation": "Cap. 300, sections 36-43",
        "official_url": "https://new.kenyalaw.org/akn/ke/act/2012/3/eng%402022-12-31",
        "applies_to": "Seller\u2019s obligation to execute and register the transfer",
        "summary": (
            "The seller must execute the prescribed transfer instrument and ensure it is filed "
            "with the Registrar. No disposition takes effect until it is registered; the seller "
            "bears the duty to cooperate in registration."
        ),
        "required": True,
    },
    {
        "title": "Land Act \u2013 Disclosure Requirements",
        "citation": "No. 6 of 2012, section 56",
        "official_url": "https://new.kenyalaw.org/akn/ke/act/2012/6",
        "applies_to": "Seller\u2019s duty of disclosure before sale",
        "summary": (
            "The seller must disclose all material facts about the land, including existing "
            "encumbrances, charges, caveats, and any pending disputes or litigation that may "
            "affect the buyer\u2019s enjoyment of the property."
        ),
        "required": True,
    },
    {
        "title": "Matrimonial Property Act \u2013 Spousal Consent",
        "citation": "Cap. 152, section 12",
        "official_url": "https://new.kenyalaw.org/akn/ke/act/2013/49",
        "applies_to": "Sale of matrimonial property",
        "summary": (
            "Where the land being sold is matrimonial property, the seller must obtain written "
            "and informed consent from their spouse before alienation, leasing, or mortgaging."
        ),
        "required": False,
    },
    {
        "title": "Stamp Duty Act \u2013 Seller Obligations",
        "citation": "Cap. 480",
        "official_url": "https://new.kenyalaw.org/akn/ke/act/1958/31/eng%402025-07-01",
        "applies_to": "Tax obligations on the transfer instrument",
        "summary": (
            "The seller is responsible for ensuring that the conveyancing instruments are "
            "properly stamped. Failure to stamp may result in penalties and the Registrar "
            "refusing to register the transfer."
        ),
        "required": True,
    },
    {
        "title": "Land Control Act \u2013 Board Consent",
        "citation": "Cap. 302, section 6",
        "official_url": "https://new.kenyalaw.org/akn/ke/act/1967/34/eng%402022-12-31",
        "applies_to": "Sale of agricultural or controlled land",
        "summary": (
            "If the land is agricultural or otherwise controlled, the seller must obtain "
            "consent from the Land Control Board before the sale can proceed."
        ),
        "required": False,
    },
]

SELLER_TRANSACTION_CHECKLIST = [
    "Confirm you have good and marketable title, free from undisclosed encumbrances.",
    "Obtain spousal consent if the land is matrimonial property.",
    "Disclose all known disputes, caveats, or charges affecting the property.",
    "Execute and sign the transfer instrument (Form 33) in the presence of a witness.",
    "Ensure stamp duty obligations are met before filing the transfer.",
    "Obtain Land Control Board consent if the land is agricultural or controlled.",
    "Cooperate fully with the buyer and the platform agent during verification.",
]

KENYAN_LAND_DOCUMENTS = [
    {
        "title": "Sale Agreement",
        "key": "sale_agreement",
        "description": "The binding contract outlining the terms, price, and conditions of the land sale.",
        "content": (
            "THIS AGREEMENT is made between the SELLER and the BUYER as detailed in the transaction breakdown.\n\n"
            "1. The Seller agrees to sell and the Buyer agrees to purchase the described parcel of land.\n"
            "2. The purchase price shall be the agreed Escrow amount, paid in full upon successful verification.\n"
            "3. The Seller warrants that they have good and marketable title to the property, free from all encumbrances.\n"
            "4. Both parties agree to abide by the Digiland platform terms and the Laws of Kenya."
        ),
        "required": True,
    },
    {
        "title": "Transfer of Land (Form 33)",
        "key": "transfer_form",
        "description": "The statutory instrument used to legally transfer the title at the Lands Registry.",
        "content": (
            "REPUBLIC OF KENYA\nTHE LAND REGISTRATION ACT\n\n"
            "I/We, the SELLER, in consideration of the sum paid to me/us by the BUYER, "
            "HEREBY TRANSFER to the BUYER all my/our rights, title, and interest in the referenced parcel of land.\n\n"
            "By signing below, the Buyer acknowledges receipt of the transfer and agrees to be bound by the registered encumbrances (if any)."
        ),
        "required": True,
    },
    {
        "title": "Spousal / Family Consent",
        "key": "consent_form",
        "description": "Statutory consent required for the sale of matrimonial or family land.",
        "content": (
            "REPUBLIC OF KENYA\nMATRIMONIAL PROPERTY ACT\n\n"
            "I hereby give my free and voluntary consent to the sale, transfer, or alienation of the referenced parcel of land. "
            "I confirm that I have been fully informed of the transaction and understand its implications on our family/matrimonial rights."
        ),
        "required": False,
    },
]

JOINT_KENYAN_LAND_DOCUMENTS = KENYAN_LAND_DOCUMENTS + [
    {
        "title": "Joint Ownership Agreement",
        "key": "joint_agreement",
        "description": "Specifies the terms of co-ownership for the joint buyers.",
        "content": (
            "We, the CO-BUYERS, hereby agree to jointly purchase and hold the referenced parcel of land.\n\n"
            "1. Ownership shall be held in the shares proportionate to our respective contributions as detailed in the joint breakdown.\n"
            "2. We consent to the appointment of the Group Leader to act on our behalf in platform communications.\n"
            "3. No co-owner shall dispose of their share without offering the right of first refusal to the other co-owners."
        ),
        "required": True,
    }
]
