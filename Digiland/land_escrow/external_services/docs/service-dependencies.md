# Service Dependencies

## Payment Providers

### Paystack

Paystack is the primary payment gateway for the Digiland platform, serving the Nigerian and broader African market. It handles card payments, bank transfers, and mobile money through a single integration. Paystack's REST API uses Bearer-token authentication with a secret key, and all monetary amounts are specified in kobo (the smallest currency unit for NGN). The adapter implements all five `PaymentProvider` methods: `initialize_payment` (creates a transaction and returns a checkout URL), `verify_payment` (confirms transaction completion), `transfer` (initiates a recipient transfer), `refund` (issues a full or partial refund), and `get_balance` (retrieves the merchant balance). Paystack supports idempotency through the `reference` parameter, which the adapter passes on every call. The adapter also handles Paystack-specific error codes, including the `429` rate-limit response which includes a `Retry-After` header. Paystack's webhook integration delivers real-time transaction status updates, which the ESL validates using HMAC-SHA256 signatures. The typical latency for Paystack API calls is 500-1500ms, and the adapter sets a 30-second timeout for payment operations and a 10-second timeout for balance queries. Configuration requires `PAYSTACK_SECRET_KEY` and optionally `PAYSTACK_BASE_URL` and `PAYSTACK_CALLBACK_URL`.

### Stripe

Stripe serves as the secondary payment provider, handling international card payments and bank transfers. The adapter uses the official `stripe` Python SDK, which is lazy-imported to avoid a hard dependency at module level. Stripe's PaymentIntent API is used for payment initialisation, providing a `client_secret` that the frontend uses to confirm the payment. The adapter maps ESL operations to Stripe's API: `initialize_payment` creates a PaymentIntent, `verify_payment` retrieves a PaymentIntent, `transfer` creates a Transfer, `refund` creates a Refund, and `get_balance` retrieves the Stripe Balance. Stripe's idempotency is handled through the `idempotency_key` parameter, which the adapter sets to the Digiland reference by default. The adapter requires `STRIPE_API_KEY` in Django settings. Stripe's webhook integration provides real-time event notifications for payment status changes, which the ESL validates using Stripe's signature scheme. Stripe's SDK handles automatic retries for transient errors internally, so the ESL's circuit breaker complements rather than duplicates Stripe's built-in resilience.

### M-Pesa (Daraja)

M-Pesa integration is critical for the Kenyan market, where mobile money is the dominant payment method. The adapter wraps the existing `core.services.payment.DarajaAPI` class, which handles the Safaricom Daraja API's STK Push (customer-initiated), B2C (business-to-customer), and C2B (customer-to-business) flows. The adapter maps `initialize_payment` to `stk_push`, `verify_payment` to `query_stk_status`, `transfer` to `b2c_payment`, and `refund` to `reverse_transaction`. M-Pesa's API uses OAuth2 for authentication with consumer key/secret credentials, and the DarajaAPI class manages token refresh internally. The adapter requires `DARAJA_CONSUMER_KEY`, `DARAJA_CONSUMER_SECRET`, `DARAJA_SHORTCODE`, and `DARAJA_PASSKEY` in Django settings. M-Pesa's callback URLs receive asynchronous payment confirmations, which the ESL processes through its webhook infrastructure. The typical latency for STK Push is 2-5 seconds, as it involves the customer's phone interaction.

### Bank Transfer

Bank transfer integration is handled through the KCB Bank Open Banking API adapter. This supports direct bank-to-bank fund transfers, account balance checks, and transaction status queries for Kenyan shilling transactions. The adapter wraps the `core.services.kcb` module and maps its functions to the ESL `PaymentProvider` interface. The KCB API uses OAuth2 with client credentials, and the adapter manages token lifecycle. Configuration requires `KCB_CLIENT_ID`, `KCB_CLIENT_SECRET`, and optionally `KCB_API_BASE_URL`, `KCB_SANDBOX`, `KCB_COMPANY_CODE`, and `KCB_PLATFORM_ACCOUNT`.

## Email Providers

### SendGrid

SendGrid is the primary transactional email provider, used for payment confirmations, parcel listing notifications, escrow status updates, and user onboarding emails. The adapter implements the `EmailProvider` interface using SendGrid's v3 REST API with Bearer-token authentication. It supports single sends (`send`), template-based sends (`send_template`) using SendGrid dynamic templates, and bulk sends (`send_bulk`) with personalisation for each recipient. The adapter tracks delivery through SendGrid's `X-Message-Id` response header, which can be correlated with SendGrid webhook events for delivery and bounce tracking. SendGrid's rate limits are generous (up to 100 emails per second on Pro plans), but the adapter respects the `429` response and raises `RateLimitExceededError`. Configuration requires `SENDGRID_API_KEY`. SendGrid webhook integration provides real-time delivery, bounce, and spam report events.

### Mailgun

Mailgun serves as the fallback email provider, offering similar capabilities to SendGrid with a slightly different API design. The adapter uses Mailgun's REST API with HTTP Basic authentication (API key as the password). Mailgun excels at high-volume batch sending and provides robust email validation capabilities. The adapter supports single sends, template sends (using Mailgun's stored templates), and bulk sends. Mailgun's webhook system provides detailed delivery and bounce notifications, which the ESL processes through its webhook verification pipeline.

## SMS Providers

### Twilio

Twilio is the primary SMS provider for international messaging, supporting delivery to over 200 countries. The adapter implements the `SmsProvider` interface using Twilio's REST API with Account SID and Auth Token authentication. It supports single sends (`send`), bulk sends (`send_bulk`), and delivery status checks (`get_delivery_status`). Twilio provides detailed delivery status information (queued, sent, delivered, undelivered, failed) and supports alphanumeric sender IDs in supported countries. The adapter handles Twilio's rate limiting (which varies by destination and sender type) and raises appropriate exceptions. Configuration requires `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN`.

### Africa's Talking

Africa's Talking is the SMS provider for the African market, offering competitive pricing and high delivery rates for African phone numbers. The adapter implements the `SmsProvider` interface using Africa's Talking REST API with API-key authentication. It supports single sends, bulk sends, and delivery status checks. Africa's Talking also provides USSD and voice capabilities, which are available through the adapter's `**kwargs` passthrough. The adapter requires `AFRICAS_TALKING_API_KEY` and `AFRICAS_TALKING_USERNAME` in Django settings. Africa's Talking's mobile-originated (MO) messages are received via webhook and processed through the ESL's webhook infrastructure.

## Storage Providers

### Amazon S3

Amazon S3 is the primary object storage provider, used for document storage (title deeds, survey plans, identity documents), parcel images, and report archives. The adapter implements the `StorageProvider` interface using the boto3 SDK (lazy-imported). It supports upload, download, delete, pre-signed URL generation, and object listing. The adapter uses server-side encryption (AES-256) by default and supports versioning for compliance-sensitive documents. Pre-signed URLs are generated with configurable expiration (default 3600 seconds) for temporary access without requiring AWS credentials. Configuration requires `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME`, and `AWS_S3_REGION_NAME`.

### Cloudflare R2

Cloudflare R2 serves as the secondary object storage provider, offering S3-compatible API without egress fees. The adapter implements the `StorageProvider` interface using the same boto3 SDK with R2's S3-compatible endpoint. R2 is particularly cost-effective for frequently accessed documents and images. Configuration requires `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, and `R2_ENDPOINT_URL`.

### Google Cloud Storage

Google Cloud Storage is available as a tertiary storage option, used primarily for deployments running on Google Cloud Platform. The adapter uses the `google-cloud-storage` Python SDK (lazy-imported) and implements the full `StorageProvider` interface. GCS offers strong consistency and fine-grained IAM controls, making it suitable for compliance-sensitive workloads. Configuration requires a service account key file or workload identity federation.

## AI Providers

### OpenAI

OpenAI is the primary AI/LLM provider, used for chat completions (buyer-seller negotiation assistance, document summarisation), embeddings (semantic search over parcel listings), and token counting (cost estimation). The adapter implements the `AIProvider` interface using the OpenAI Python SDK (lazy-imported). It supports `chat_completion` (with streaming and function calling options), `generate_embedding` (using the `text-embedding-3-small` model by default), `count_tokens` (using the `tiktoken` library), and `get_available_models`. The adapter tracks token usage and creates `CostRecord` entries for billing and cost management. OpenAI's rate limits are enforced per-organisation and per-model, and the adapter raises `RateLimitExceededError` when limits are hit. Configuration requires `OPENAI_API_KEY`.

### Anthropic

Anthropic is the secondary AI provider, offering the Claude family of models. The adapter implements the `AIProvider` interface using Anthropic's Python SDK (lazy-imported). Claude models are used for tasks requiring longer context windows and more nuanced reasoning, such as contract analysis and compliance review. The adapter supports chat completions with the Messages API, embeddings (when available), token counting, and model listing. Configuration requires `ANTHROPIC_API_KEY`.

### Google Gemini

Google Gemini is available as a tertiary AI provider, particularly for deployments integrated with Google Cloud. The adapter implements the `AIProvider` interface using the Google Generative AI SDK. Gemini models offer multimodal capabilities (text, image, video understanding) that can be leveraged for parcel image analysis and document OCR. Configuration requires `GOOGLE_AI_API_KEY` or Google Cloud service account credentials.
