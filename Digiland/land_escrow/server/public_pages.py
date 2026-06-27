"""Reusable content payloads for public marketing pages rendered through the React shell."""

from __future__ import annotations


def _section(title: str, body: str, *, kicker: str | None = None, bullets: list[str] | None = None, actions: list[dict[str, str]] | None = None):
    section = {
        'title': title,
        'body': body,
    }
    if kicker:
        section['kicker'] = kicker
    if bullets:
        section['bullets'] = bullets
    if actions:
        section['actions'] = actions
    return section


def _page(
    page_key: str,
    title: str,
    subtitle: str,
    *,
    kicker: str,
    badge: str,
    sections: list[dict[str, object]] | None = None,
    content_key: str | None = None,
    actions: list[dict[str, str]] | None = None,
):
    page = {
        'page_key': page_key,
        'title': title,
        'subtitle': subtitle,
        'badge': badge,
        'actions': actions or [],
    }
    if content_key:
        page['content_key'] = content_key
    if sections is not None:
        page['content'] = {
            'hero': {
                'kicker': kicker,
                'title': title,
                'subtitle': subtitle,
                'badge': badge,
            },
            'sections': sections,
        }
    return page


PUBLIC_PAGES = {
    'about': _page(
        'about',
        'Built for secure land transfers in Kenya',
        'Digiland combines verified parcel workflows, escrow settlement, and joint ownership support in one platform.',
        kicker='About Digiland',
        badge='Public overview',
        content_key='about',
    ),
    'architecture': _page(
        'architecture',
        'A compact, auditable platform design',
        'The app keeps the Django backend in charge of business rules while React handles the presentation layer.',
        kicker='Architecture',
        badge='System design',
        content_key='architecture',
    ),
    'investors': _page(
        'investors',
        'A focused land transaction product',
        'Digiland targets a narrow workflow with high trust requirements: parcel verification, contract signing, and escrow payment.',
        kicker='Investors',
        badge='Growth story',
        content_key='investors',
    ),
    'terms': _page(
        'terms',
        'Platform usage terms',
        'These pages summarise how the Digiland workflow is intended to be used.',
        kicker='Terms',
        badge='Legal',
        content_key='terms',
    ),
    'privacy': _page(
        'privacy',
        'Privacy and data handling',
        'The platform stores only what it needs to manage escrow, verification, and support workflows.',
        kicker='Privacy',
        badge='Data policy',
        content_key='privacy',
    ),
    'sell': _page(
        'sell',
        'Sell with confidence',
        'List verified land, price it accurately, and move into escrow when a buyer is ready.',
        kicker='Seller tools',
        badge='Marketplace',
        sections=[
            _section(
                'Prepare the listing',
                'Use the parcel workflow to upload documents, capture location details, and keep the sale visible to qualified buyers.',
                bullets=[
                    'Verified parcel review before the listing goes live',
                    'Clear size, location, and land-use details',
                    'Price guidance from the estimator before you publish',
                ],
            ),
            _section(
                'Protect the transaction',
                'Once the buyer is ready, the platform moves the deal into signed contract and escrow steps so both sides have a traceable workflow.',
                bullets=[
                    'Digital contract signing',
                    'Escrow-backed settlement',
                    'Audit trail for each status change',
                ],
            ),
            _section(
                'Close faster',
                'The seller journey is designed to reduce back-and-forth and keep every action visible to the team handling the transaction.',
            ),
        ],
        actions=[
            {'label': 'Browse parcels', 'href': '/parcels/', 'tone': 'outline'},
            {'label': 'Estimate value', 'href': '/price-prediction/', 'tone': 'secondary'},
        ],
    ),
    'escrow': _page(
        'escrow',
        'Escrow protection',
        'Funds stay protected until documents, signatures, and transfer checks are complete.',
        kicker='Trust layer',
        badge='Protected settlement',
        sections=[
            _section(
                'How it works',
                'Buyer funds are held safely while the contract, verification, and settlement steps are checked in order.',
                bullets=[
                    'Deposit funds into a controlled escrow flow',
                    'Complete contract and verification checks',
                    'Release only after the agreed conditions are met',
                ],
            ),
            _section(
                'Why it matters',
                'A structured escrow path reduces payment risk and gives both parties a clear status trail during the sale.',
            ),
        ],
        actions=[
            {'label': 'Read legal acts', 'href': '/escrow-acts/', 'tone': 'outline'},
            {'label': 'View transactions', 'href': '/transactions/', 'tone': 'secondary'},
        ],
    ),
    'virtual-cities': _page(
        'virtual-cities',
        'Virtual cities',
        'Model emerging districts and growth corridors before the market fully catches up.',
        kicker='Planning',
        badge='Future districts',
        sections=[
            _section(
                'Map the market',
                'Explore corridors, growth belts, and premium zones as if they were living districts inside the platform.',
                bullets=[
                    'Visualise demand around major hubs',
                    'Track cluster behaviour across counties',
                    'Compare established and emerging markets',
                ],
            ),
            _section(
                'Use the signal',
                'Virtual district thinking helps the team separate long-term expansion zones from short-lived spikes in search activity.',
            ),
        ],
        actions=[
            {'label': 'Open recommendations', 'href': '/recommendations/', 'tone': 'outline'},
            {'label': 'Price estimator', 'href': '/price-prediction/', 'tone': 'secondary'},
        ],
    ),
    'ai-agents': _page(
        'ai-agents',
        'AI agents',
        'Automate valuation, routing, document review, and support handoffs.',
        kicker='Automation',
        badge='Smart workflows',
        sections=[
            _section(
                'Valuation assistant',
                'The estimator combines location context with parcel traits so the search flow can guide the user before they submit the form.',
            ),
            _section(
                'Review and support',
                'Agents can triage support cases, parcel checks, and approval queues without losing auditability.',
                bullets=[
                    'Prioritised support handling',
                    'Location-aware responses',
                    'Deterministic status transitions',
                ],
            ),
        ],
        actions=[
            {'label': 'Open support', 'href': '/support/', 'tone': 'outline'},
            {'label': 'Run estimator', 'href': '/price-prediction/', 'tone': 'secondary'},
        ],
    ),
    'analytics': _page(
        'analytics',
        'Land analytics',
        'Track demand, pricing, and listing performance across the marketplace.',
        kicker='Insights',
        badge='Trend view',
        sections=[
            _section(
                'Market trends',
                'Review county activity, listing engagement, and the areas that attract the highest-intent buyers.',
                bullets=[
                    'Demand patterns by county and constituency',
                    'Comparable price signals around each parcel',
                    'Better context for the valuation engine',
                ],
            ),
            _section(
                'Operational metrics',
                'Use analytics to see which listings perform, where buyers stop, and where the workflow needs attention.',
            ),
        ],
        actions=[
            {'label': 'View recommendations', 'href': '/recommendations/', 'tone': 'outline'},
            {'label': 'Open finance', 'href': '/dashboard/finance/', 'tone': 'secondary'},
        ],
    ),
    'dev-tools': _page(
        'dev-tools',
        'Development tools',
        'Integrations, APIs, and workflow building blocks for teams that need to extend the platform.',
        kicker='Integrations',
        badge='Developer surface',
        sections=[
            _section(
                'API-first flow',
                'The platform exposes a public price prediction endpoint, operational APIs, and internal workflow services for agents and admins.',
                bullets=[
                    'JSON endpoints for pricing and reference data',
                    'Structured responses for UI integration',
                    'Auth-aware endpoints for internal workflows',
                ],
            ),
            _section(
                'Build and embed',
                'Use the React shell and Django views together to add new features without rewriting the whole app.',
            ),
        ],
        actions=[
            {'label': 'API reference', 'href': '/api-reference/', 'tone': 'outline'},
            {'label': 'Price API', 'href': '/api/v1/price-prediction/', 'tone': 'secondary'},
        ],
    ),
    'nft-assets': _page(
        'nft-assets',
        'NFT assets',
        'Prepare for tokenized provenance and digital ownership experiences.',
        kicker='Roadmap',
        badge='Digital assets',
        sections=[
            _section(
                'Provenance layer',
                'Digital ownership can carry parcel history, document provenance, and metadata for future transfer workflows.',
            ),
            _section(
                'Future readiness',
                'The current platform keeps the legal and workflow layer separate so tokenized experiences can be added later without disrupting escrow.',
            ),
        ],
        actions=[
            {'label': 'Platform story', 'href': '/about/', 'tone': 'outline'},
            {'label': 'Legal terms', 'href': '/terms/', 'tone': 'secondary'},
        ],
    ),
    'docs': _page(
        'docs',
        'Documentation',
        'A quick guide to the platform, workflows, and public endpoints.',
        kicker='Reference',
        badge='Docs hub',
        sections=[
            _section(
                'Getting started',
                'Learn the core user journeys: browse parcels, estimate value, sign the contract, and complete escrow.',
                bullets=[
                    'Marketplace discovery',
                    'Land value estimation',
                    'Escrow and settlement flow',
                ],
            ),
            _section(
                'What to read next',
                'Use the support and API pages when you need implementation detail or help with a specific workflow.',
            ),
        ],
        actions=[
            {'label': 'API reference', 'href': '/api-reference/', 'tone': 'outline'},
            {'label': 'Help center', 'href': '/help/', 'tone': 'secondary'},
        ],
    ),
    'api-reference': _page(
        'api-reference',
        'API reference',
        'The endpoints used by the web app and automation workflows.',
        kicker='Reference',
        badge='JSON endpoints',
        sections=[
            _section(
                'Public pricing API',
                'The price prediction service exposes county lists, location search, and prediction requests through a single public endpoint.',
                bullets=[
                    '/api/v1/price-prediction/',
                    '/api/v1/price-prediction/?action=locations',
                    '/api/v1/price-prediction/?action=constituencies',
                ],
            ),
            _section(
                'Operational APIs',
                'Authenticated endpoints cover parcel workflows, support, transactions, and analytics used across the app.',
            ),
        ],
        actions=[
            {'label': 'Open pricing API', 'href': '/api/v1/price-prediction/', 'tone': 'outline'},
            {'label': 'Browse app', 'href': '/parcels/', 'tone': 'secondary'},
        ],
    ),
    'blog': _page(
        'blog',
        'Blog and updates',
        'Product notes, platform releases, and market commentary.',
        kicker='Updates',
        badge='Newsroom',
        sections=[
            _section(
                'Release notes',
                'Track changes to the marketplace, estimator, and escrow flow as the platform evolves.',
            ),
            _section(
                'Market commentary',
                'Use the blog to explain how location signals, demand patterns, and land-use context affect pricing.',
            ),
        ],
        actions=[
            {'label': 'About Digiland', 'href': '/about/', 'tone': 'outline'},
            {'label': 'Contact the team', 'href': '/contact/', 'tone': 'secondary'},
        ],
    ),
    'help': _page(
        'help',
        'Help center',
        'Find quick answers or open a support ticket when you need help.',
        kicker='Support',
        badge='Help desk',
        sections=[
            _section(
                'How to get started',
                'If you are new to the platform, start with the marketplace, then use the estimator to narrow down pricing.',
                bullets=[
                    'Browse verified parcels',
                    'Run a location estimate',
                    'Open support if anything is unclear',
                ],
            ),
            _section(
                'When to contact support',
                'Reach support for account issues, document questions, or transaction concerns.',
            ),
        ],
        actions=[
            {'label': 'Open support', 'href': '/support/', 'tone': 'outline'},
            {'label': 'Read terms', 'href': '/terms/', 'tone': 'secondary'},
        ],
    ),
    'community': _page(
        'community',
        'Community',
        'Connect with buyers, sellers, and agents around verified land transactions.',
        kicker='Network',
        badge='Community space',
        sections=[
            _section(
                'Buyer community',
                'Buyers can compare notes on location trends, escrow flow, and due diligence habits.',
            ),
            _section(
                'Seller and agent network',
                'Sellers and agents can collaborate around listings, pricing, and verification discipline.',
            ),
        ],
        actions=[
            {'label': 'Create account', 'href': '/accounts/signup/', 'tone': 'outline'},
            {'label': 'Open support', 'href': '/support/', 'tone': 'secondary'},
        ],
    ),
    'careers': _page(
        'careers',
        'Careers',
        'Join the team building trusted land commerce tooling in Kenya.',
        kicker='Hiring',
        badge='Work with us',
        sections=[
            _section(
                'What we look for',
                'We value people who can work across product, operations, and engineering while keeping trust and clarity first.',
            ),
            _section(
                'How to apply',
                'Reach out with a short summary of what you have built and how you would improve land workflows.',
            ),
        ],
        actions=[
            {'label': 'Contact us', 'href': '/contact/', 'tone': 'outline'},
            {'label': 'About Digiland', 'href': '/about/', 'tone': 'secondary'},
        ],
    ),
    'press': _page(
        'press',
        'Press',
        'Media resources, announcements, and company background.',
        kicker='Media',
        badge='Press room',
        sections=[
            _section(
                'Company facts',
                'Digiland combines verified land listings, escrow discipline, and pricing intelligence in one workflow.',
            ),
            _section(
                'Press inquiries',
                'Use the contact page for interviews, quotes, or product background requests.',
            ),
        ],
        actions=[
            {'label': 'Contact us', 'href': '/contact/', 'tone': 'outline'},
            {'label': 'About Digiland', 'href': '/about/', 'tone': 'secondary'},
        ],
    ),
    'partners': _page(
        'partners',
        'Partners',
        'Work with Digiland on integrations, distribution, and market expansion.',
        kicker='Business',
        badge='Partnerships',
        sections=[
            _section(
                'Who we partner with',
                'The platform fits property teams, verification vendors, legal partners, and distribution networks that need trusted land workflows.',
            ),
            _section(
                'Integration paths',
                'Partners can connect through the API layer, the public estimator, or the workflow surfaces used by staff.',
            ),
        ],
        actions=[
            {'label': 'Contact us', 'href': '/contact/', 'tone': 'outline'},
            {'label': 'API reference', 'href': '/api-reference/', 'tone': 'secondary'},
        ],
    ),
    'contact': _page(
        'contact',
        'Contact',
        'Reach the team for partnerships, support, or operational questions.',
        kicker='Reach out',
        badge='Get in touch',
        sections=[
            _section(
                'Support channel',
                'Use the support page for account issues, workflow questions, and transaction help.',
            ),
            _section(
                'Partnership and press',
                'Use this page when you need to discuss integrations, media requests, or general platform information.',
            ),
        ],
        actions=[
            {'label': 'Open support', 'href': '/support/', 'tone': 'outline'},
            {'label': 'Browse marketplace', 'href': '/parcels/', 'tone': 'secondary'},
        ],
    ),
    'cookies': _page(
        'cookies',
        'Cookie policy',
        'How we use browser storage and related data on the platform.',
        kicker='Privacy',
        badge='Cookie notice',
        sections=[
            _section(
                'What is stored',
                'Cookies and related browser storage help keep sessions secure and the UI responsive during navigation.',
            ),
            _section(
                'How to manage cookies',
                'You can clear browser storage from your browser settings if you want to reset the local session state.',
            ),
        ],
        actions=[
            {'label': 'Privacy policy', 'href': '/privacy/', 'tone': 'outline'},
            {'label': 'Terms', 'href': '/terms/', 'tone': 'secondary'},
        ],
    ),
}
