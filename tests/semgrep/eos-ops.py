import logging

logger = logging.getLogger(__name__)
log = logging.getLogger("app")


def handler(request, user, password, token_count, payment):
    # ruleid: eos-log-secret
    logger.info("login attempt %s %s", user.id, password)
    # ruleid: eos-log-secret
    logger.debug(f"calling provider with {user.api_key}")
    # ruleid: eos-log-secret
    log.warning("headers: %s", request.headers["Authorization"])
    # ruleid: eos-log-secret
    logger.info("refreshed", extra={"tok": user.refresh_token})
    # ok: eos-log-secret
    logger.info("tokens used: %d", token_count)
    # ok: eos-log-secret
    logger.info("login ok", extra={"user_id": user.id, "has_token": bool(user.refresh_token)})
    # ruleid: eos-log-personal-data
    logger.info("payment for %s", user.msisdn)
    # ruleid: eos-log-personal-data
    logger.error(f"could not email {user.email}")
    # ok: eos-log-personal-data
    logger.info("payment %s for user %s", payment.id, user.id)
    # ruleid: eos-log-request-body
    logger.info("webhook body %s", request.get_json())
    # ruleid: eos-log-request-body
    logger.debug("form: %s", request.form)
    # ok: eos-log-request-body
    logger.info("webhook event %s", request.get_json()["event_id"])
