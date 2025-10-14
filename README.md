# Geofy Historical Imagery API

FastAPI application for capturing historical satellite imagery from Google Earth using GEHistoricalImagery CLI tool.

## 🚀 Deployment to t3.xlarge CPU Server

### Server Specifications
- **Instance**: t3.xlarge
- **vCPUs**: 4
- **RAM**: 16GB
- **IP**: 18.215.180.51
- **Architecture**: CPU-optimized (no GPU)

---

## 📦 Quick Deployment

### 1. SSH into Server
```bash
ssh -i your-keypair.pem ubuntu@18.215.180.51
```

---

## 🔔 Webhooks & Callbacks

The API can notify your system when jobs complete or fail using webhooks. Provide a `callbackUrl` in the `POST /api/capture` request body. When the job finishes, we POST a JSON payload to your URL.

### Events
- `job.completed`
- `job.failed`

### Payload example
```json
{
  "jobId": "b3e7e7c2-1d0f-4a8c-9f1d-6f4d9d5a2c11",
  "status": "completed",
  "images": [{"year": 2021, "captureDate": "2021-07-01", "imageUrl": "...", "optimizedUrl": "...", "thumbnailUrl": "..."}],
  "aiAnalysis": {"changes_detected": [], "timeline": [], "summary": "..."}
}
```

### Request headers
- `Content-Type: application/json`
- `User-Agent: Geofy-Imagery-API/1.0 (+https://geofy.example)`
- `Geofy-Event: job.completed | job.failed`
- `Geofy-Delivery-Id: <uuid>`
- `Geofy-Timestamp: <unix-seconds>`
- `Geofy-Signature-Version: 1`
- `Geofy-Signature-Alg: HMAC-SHA256`
- `Geofy-Signature: t=<timestamp>,v1=<hex-digest>`

### Signature scheme
If `WEBHOOK_SIGNING_SECRET` is set, requests are signed with HMAC-SHA256.

1. Serialize the JSON body with compact separators.
2. Build base string: `b"t=<timestamp>.body=" + body_bytes`
3. Compute `HMAC_SHA256(secret, base_string)` and hex-encode.
4. Send as `Geofy-Signature` header with the timestamp.

Receiver validation checklist:
- Parse `Geofy-Signature` into `t` and `v1`
- Recompute signature over the raw request body
- Constant-time compare
- Enforce timestamp tolerance (recommend `±WEBHOOK_TOLERANCE_SECONDS`, default 300s)

### Retry policy
- Exponential backoff, up to `WEBHOOK_MAX_RETRIES` (default 5)
- Base backoff seconds: `WEBHOOK_BACKOFF_BASE_SECONDS` (default 2), delay = base * 2^attempt
- Timeout per attempt: `WEBHOOK_REQUEST_TIMEOUT_SECONDS` (default 30)
- We retry on network errors, `5xx`, and `429`; `4xx` are not retried
- If `Retry-After` header (seconds) is present, we honor it when larger than our computed backoff
- We add full jitter to backoff (random 0..delay) to avoid thundering herd

### Configuration (.env)
```env
WEBHOOK_SIGNING_SECRET=your_shared_secret
WEBHOOK_REQUEST_TIMEOUT_SECONDS=30
WEBHOOK_MAX_RETRIES=5
WEBHOOK_BACKOFF_BASE_SECONDS=2
WEBHOOK_TOLERANCE_SECONDS=300
WEBHOOK_USER_AGENT=Geofy-Imagery-API/1.0 (+https://geofy.example)
```

### Security best practices
- Use HTTPS for `callbackUrl`
- We validate `callbackUrl` to require `https`
- Verify HMAC signature and timestamp
- Return a 2xx quickly (store then process)
- Idempotently handle duplicate deliveries
- Rate limit by IP and validate source if applicable