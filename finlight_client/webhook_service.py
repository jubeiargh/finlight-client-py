import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Optional
from .models import Article


SIGNATURE_PREFIX = "sha256="
REPLAY_ATTACK_TOLERANCE_SECONDS = 5 * 60  # 5 minutes


class WebhookVerificationError(Exception):
    """Raised when webhook verification fails.

    This can occur due to invalid signatures, expired timestamps,
    or malformed payloads.
    """
    pass


class WebhookService:
    """Service for securely receiving and verifying webhook events from Finlight.

    Webhooks provide real-time notifications when new articles are published.
    This service handles HMAC signature verification and replay attack protection.
    """

    @staticmethod
    def construct_event(
        raw_body: str,
        signature: str,
        endpoint_secret: str,
        timestamp: Optional[str] = None
    ) -> Article:
        """Constructs and verifies a webhook event from raw request data.

        Verifies the HMAC-SHA256 signature to ensure the webhook came from Finlight
        and hasn't been tampered with. Optionally validates the timestamp to prevent
        replay attacks (5 minute tolerance window).

        Args:
            raw_body: The raw request body as a string (must be unparsed)
            signature: The signature from the X-Webhook-Signature header
            endpoint_secret: Your webhook endpoint secret from the Finlight dashboard
            timestamp: Optional timestamp from the X-Webhook-Timestamp header for replay protection

        Returns:
            Article: The verified and parsed article object

        Raises:
            WebhookVerificationError: If verification fails

        Example:
            >>> # Flask webhook endpoint
            >>> @app.route('/webhook', methods=['POST'])
            >>> def webhook():
            ...     raw_body = request.get_data(as_text=True)
            ...     signature = request.headers.get('X-Webhook-Signature')
            ...     timestamp = request.headers.get('X-Webhook-Timestamp')
            ...
            ...     try:
            ...         article = WebhookService.construct_event(
            ...             raw_body, signature, os.getenv('WEBHOOK_SECRET'), timestamp
            ...         )
            ...         print(f"New article: {article.title}")
            ...         return '', 200
            ...     except WebhookVerificationError:
            ...         return '', 400
        """
        normalized_signature = WebhookService._normalize_signature(signature)
        
        WebhookService._verify_signature(
            raw_body, normalized_signature, endpoint_secret, timestamp
        )
        
        if timestamp:
            WebhookService._verify_timestamp(timestamp)
        
        return WebhookService._parse_payload(raw_body)
    
    @staticmethod
    def _normalize_signature(signature: str) -> str:
        """Remove the sha256= prefix from the signature if present."""
        return signature.replace(SIGNATURE_PREFIX, "")
    
    @staticmethod
    def _verify_signature(
        payload: str,
        signature: str,
        secret: str,
        timestamp: Optional[str] = None
    ) -> None:
        """Verify the webhook signature."""
        if timestamp:
            expected_signature = WebhookService._compute_signature_with_timestamp(
                payload, secret, timestamp
            )
        else:
            expected_signature = WebhookService._compute_signature(payload, secret)
        
        if not WebhookService._secure_compare(signature, expected_signature):
            raise WebhookVerificationError("Invalid webhook signature")
    
    @staticmethod
    def _verify_timestamp(timestamp: str) -> None:
        """Verify the timestamp is within allowed tolerance."""
        try:
            webhook_time = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        except ValueError:
            raise WebhookVerificationError("Invalid timestamp format")
        
        current_time = datetime.now(timezone.utc)
        time_difference = abs((current_time - webhook_time).total_seconds())
        
        if time_difference > REPLAY_ATTACK_TOLERANCE_SECONDS:
            raise WebhookVerificationError("Webhook timestamp outside allowed tolerance")
    
    @staticmethod
    def _parse_payload(raw_body: str) -> Article:
        """Parse the JSON payload and validate it as an Article."""
        try:
            raw_data = json.loads(raw_body)
            return Article.model_validate(raw_data)
        except json.JSONDecodeError:
            raise WebhookVerificationError("Invalid JSON payload")
        except Exception as e:
            raise WebhookVerificationError(f"Invalid article data: {str(e)}")
    
    @staticmethod
    def _compute_signature_with_timestamp(
        payload: str,
        secret: str,
        timestamp: str
    ) -> str:
        """Compute signature with timestamp."""
        message = f"{timestamp}.{payload}"
        return WebhookService._compute_signature(message, secret)
    
    @staticmethod
    def _compute_signature(payload: str, secret: str) -> str:
        """Compute HMAC SHA256 signature."""
        return hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    @staticmethod
    def _secure_compare(a: str, b: str) -> bool:
        """Perform constant-time string comparison."""
        return hmac.compare_digest(a, b)