import logging
from typing import Any

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.database.session import get_db
from app.models import User
from app.services.user_service import (
    create_user_for_auth,
    find_user_by_auth_id,
)

logger = logging.getLogger("pcma.security")

bearer_scheme = HTTPBearer()


async def validate_access_token(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict[str, Any]:
    token = credentials.credentials

    token_exists = bool(token)
    token_length = len(token) if token else 0
    parts = token.split(".") if token else []
    is_jwt = len(parts) == 3

    logger.info("auth_diagnostics token_exists=%s length=%d is_jwt=%s", token_exists, token_length, is_jwt)

    if is_jwt:
        try:
            unverified_header = jwt.get_unverified_header(token)
            unverified_payload = jwt.decode(
                token,
                options={
                    "verify_signature": False,
                    "verify_aud": False,
                    "verify_iss": False,
                    "verify_exp": False,
                },
            )
            logger.info(
                "auth_diagnostics_jwt header_alg=%s header_kid=%s claim_iss=%s claim_aud=%s claim_exp=%s claim_azp=%s",
                unverified_header.get("alg"),
                unverified_header.get("kid"),
                unverified_payload.get("iss"),
                unverified_payload.get("aud"),
                unverified_payload.get("exp"),
                unverified_payload.get("azp"),
            )
        except Exception as err:
            logger.warning("auth_diagnostics_unverified_parse_failed error=%s", type(err).__name__)

    try:
        unverified_header = jwt.get_unverified_header(token)

        key_id = unverified_header.get("kid")
        algorithm = unverified_header.get("alg")

        if not key_id:
            logger.warning("auth_validation_failed_missing_kid")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token",
            )

        if algorithm != "RS256":
            logger.warning("auth_validation_failed_invalid_algorithm alg=%s", algorithm)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token algorithm",
            )

        async with httpx.AsyncClient() as client:
            response = await client.get(
                settings.auth_jwks_url,
                timeout=5.0,
            )

        response.raise_for_status()

        jwks = response.json()

        matching_key = next(
            (
                key
                for key in jwks["keys"]
                if key.get("kid") == key_id
            ),
            None,
        )

        if matching_key is None:
            logger.warning("auth_validation_failed_matching_key_not_found kid=%s", key_id)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Unable to find token signing key",
            )

        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(
            matching_key
        )

        payload = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=settings.auth_audience,
            issuer=settings.auth_issuer_url,
        )

        return payload

    except HTTPException:
        raise

    except jwt.ExpiredSignatureError:
        logger.warning("auth_validation_failed_expired_signature")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired",
        )

    except jwt.InvalidAudienceError:
        logger.warning("auth_validation_failed_invalid_audience expected=%s", settings.auth_audience)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token audience",
        )

    except jwt.InvalidIssuerError:
        logger.warning("auth_validation_failed_invalid_issuer expected=%s", settings.auth_issuer_url)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token issuer",
        )

    except jwt.InvalidTokenError as err:
        logger.warning("auth_validation_failed_invalid_token error_type=%s", type(err).__name__)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token",
        )

    except (httpx.HTTPError, KeyError, ValueError) as err:
        logger.warning("auth_validation_failed_http_or_key_error error_type=%s", type(err).__name__)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unable to validate access token",
        )


async def get_current_user(
    payload: dict[str, Any] = Depends(validate_access_token),
    db: AsyncSession = Depends(get_db),
) -> User:
    auth_id = payload.get("sub")

    if not auth_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token does not contain a user identifier",
        )

    user = await find_user_by_auth_id(
        db=db,
        auth_id=auth_id,
    )

    if user is None:
        user = await create_user_for_auth(
            db=db,
            auth_id=auth_id,
        )

    return user