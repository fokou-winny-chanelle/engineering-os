# Fixtures for core/scaffold/security/semgrep.yml (semgrep --test). Not executed.
import hmac

import jwt
import stripe
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()


def jwt_cases(token, key):
    # ruleid: eos-jwt-verify-disabled
    jwt.decode(token, options={"verify_signature": False})
    # ruleid: eos-jwt-verify-disabled
    jwt.decode(token, key, algorithms=["HS256", "none"])
    # ok: eos-jwt-verify-disabled
    return jwt.decode(token, key, algorithms=["RS256"], audience="api", issuer="https://issuer")


def compare_cases(signature, expected, token_hash, stored):
    # ruleid: eos-non-constant-time-compare
    if signature == expected:
        return True
    # ruleid: eos-non-constant-time-compare
    if token_hash != stored:
        return False
    # ok: eos-non-constant-time-compare
    if signature == "":
        return False
    # ok: eos-non-constant-time-compare
    return hmac.compare_digest(signature, expected)


# ruleid: eos-webhook-without-signature-check
@app.post("/webhooks/payments")
async def unsafe_webhook(request: Request):
    event = await request.json()
    return {"ok": event["id"]}


# ok: eos-webhook-without-signature-check
@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    event = stripe.Webhook.construct_event(payload, request.headers["stripe-signature"], "whsec")
    return {"ok": event["id"]}


# ok: eos-webhook-without-signature-check
@app.post("/webhooks/momo")
async def momo_webhook(request: Request):
    body = await request.body()
    verify_hex_hmac(b"k", body, request.headers.get("x-signature"))  # noqa: F821
    return {"ok": True}


def verified(request: Request):
    return True


# ok: eos-webhook-without-signature-check
@app.post("/webhooks/other")
async def dep_webhook(request: Request, ok: bool = Depends(verified)):
    return {"ok": ok}


# ok: eos-webhook-without-signature-check
@app.get("/webhooks/health")
async def health():
    return {"ok": True}


# ruleid: eos-py-cors-wildcard-credentials
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True)
# ok: eos-py-cors-wildcard-credentials
app.add_middleware(CORSMiddleware, allow_origins=["https://app.example.com"], allow_credentials=True)
