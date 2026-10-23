# Phone OTP Authentication

> Verified against commit `f972117` on 2026-10-23.
> Parent: [index.md](index.md)

> **Status: NOT YET IMPLEMENTED IN THIS COMMIT.**
> This doc describes a planned feature as documented in team notes. At commit
> `f972117`, no OTP, Twilio, Redis, or auth code exists in the repository.
> `Backend/main.py` does not include an auth router, `Backend/requirements.txt`
> lists neither `redis` nor `httpx` nor `twilio`, and the frontend has no signup
> page.
>
> The sections below define the target design so a future implementer can match
> it against the existing team spec. All references to "endpoint lives at…" or
> "handler at…" are **planned**, not actual.

## Design Overview
Phone-based OTP (One-Time Password) over SMS for retail-investor signup. The user
submits an Indian 10-digit mobile number, receives a 6-digit code via SMS, and types
it back to prove ownership. The code is single-use with a 5-minute TTL.

## Planned Endpoints

### `POST /auth/send-phone-otp`
Request:
```json
{ "phone": "9876543210" }
```
Behavior:
- Validate: exactly 10 digits.
- Generate a 6-digit decimal OTP (e.g. `random.randint(100000, 999999)`).
- Store in Redis: key `otp:phone:{phone}`, value = OTP string, TTL 300 seconds (5 min).
- Send via Twilio SMS REST API using `httpx` (planned):
  - URL: `https://api.twilio.com/2010-04-01/Accounts/{ACCOUNT_SID}/Messages.json`
  - Body: `From=TWILIO_SMS_FROM`, `To=+91{phone}`, `Body=Your StockAIVerse OTP is {otp}. Valid for 5 minutes. Do not share this with anyone.`
  - Basic auth with `(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)`.
- Response: `200` → `{ "status": "ok" }`. The OTP is never echoed back.

Error cases:
- Invalid phone format → `400` with reason.
- Redis unreachable → `503`.
- Twilio call fails → `502` with Twilio error summary; the Redis key is still written to allow retry via the same number *(design choice to confirm during implementation)*.

### `POST /auth/verify-phone-otp`
Request:
```json
{ "phone": "9876543210", "otp": "123456" }
```
Behavior:
- Read `otp:phone:{phone}` from Redis.
- Key missing / expired → `400` with `"OTP expired or not sent"`.
- Mismatch → `400` with `"Invalid OTP"`.
- Match → `DEL` the key (one-time use), return `200` → `{ "verified": true }`.

## Redis Keys
| Key | Value | TTL | Written by | Read by |
|---|---|---|---|---|
| `otp:phone:{phone}` | 6-digit OTP string | 300 s | `send-phone-otp` | `verify-phone-otp` |

A single Redis instance is sufficient — any eviction-safe DB index is fine.

## Twilio SMS Message
Fixed template:
```
Your StockAIVerse OTP is XXXXXX. Valid for 5 minutes. Do not share this with anyone.
```

## Frontend Flow (planned, not present in this commit)
Signup page:
1. Phone input prefixed with `+91`, numeric-only, max length 10.
2. **Send OTP** button → `POST /auth/send-phone-otp`. On success, start a 60-second resend cooldown and reveal the OTP input.
3. OTP input accepts 6 digits (numeric only).
4. **Verify** button → `POST /auth/verify-phone-otp`. On success, mark the phone as verified (checkmark); on failure show one of:
   - "Invalid OTP"
   - "OTP expired or not sent"
   - a generic network-error message
5. The signup form's submit button stays disabled until phone verification succeeds.

Where it will live (suggested, matching existing structure):
- `Frontend/src/pages/Signup.tsx` (new)
- A new route `/signup` in `Frontend/src/App.tsx`
- API methods added under `api.auth.sendOtp(phone)` and `api.auth.verifyOtp(phone, otp)` in `Frontend/src/api/client.ts`

## Required Environment Variables
To be added to `Backend/.env` (file does not yet exist):
```
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_SMS_FROM=+1XXXXXXXXXX
REDIS_URL=redis://localhost:6379/0
```

## Dependencies to Add
Not yet in `Backend/requirements.txt`:
- `redis` (Python client)
- `httpx` (async HTTP client for Twilio call)
- `python-dotenv` *(optional, to load `.env`)*

## Current Blocker
Even on completion of the code, live OTP delivery requires valid Twilio credentials.
Without the three `TWILIO_*` env vars the SMS send step fails and the user never
receives a code.

## Debugging Guide (post-implementation)
| Symptom | Likely cause | Where to look |
|---|---|---|
| `send-phone-otp` returns `502` | Twilio credentials missing or wrong | `Backend/.env`; Twilio console delivery logs |
| User receives no SMS, API returns `200` | Twilio accepted but downstream block (carrier filter, trial account restriction) | Twilio console |
| `verify-phone-otp` always returns "expired or not sent" | Clock skew between app and Redis TTL, or Redis is a different instance between send/verify | `redis-cli KEYS otp:phone:*` immediately after send |
| OTP is accepted twice | `DEL` was skipped — regression on the verify handler | `verify-phone-otp` handler |

## Known Gaps
- **Nothing is coded yet.** This doc exists so that when the feature lands, the design intent is captured and reviewable. The audit of code vs. doc will be done on the first implementation PR.
- No rate limiting is specified — a production implementation must cap sends per phone per hour (and per IP) to prevent SMS billing abuse.
- No persistent user model is specified. The verify endpoint returns `verified: true` but does not mint a session, cookie, or JWT. A follow-up design is needed to attach the verified phone to a user record.
