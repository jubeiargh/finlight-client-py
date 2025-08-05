import hashlib
import hmac
import json
import unittest
from datetime import datetime, timedelta, timezone

from finlight_client.webhook_service import (
    WebhookService,
    WebhookVerificationError,
)
from finlight_client.models import Article


class TestWebhookService(unittest.TestCase):
    def setUp(self):
        self.endpoint_secret = "test_secret_key"
        self.valid_payload = {
            "link": "https://example.com/article",
            "title": "Test Article",
            "publishDate": "2024-01-01T00:00:00Z",
            "source": "example.com",
            "language": "en",
            "sentiment": "positive",
            "confidence": "0.95",
            "summary": "This is a test article",
            "companies": [
                {
                    "companyId": 1,
                    "confidence": "0.90",
                    "name": "Apple Inc.",
                    "ticker": "AAPL",
                    "exchange": "NASDAQ"
                }
            ]
        }
    
    def create_signature(self, payload: str, secret: str, timestamp: str = None) -> str:
        """Helper to create valid signatures."""
        if timestamp:
            message = f"{timestamp}.{payload}"
        else:
            message = payload
        
        return hmac.new(
            secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def test_verify_and_construct_event_with_valid_signature_and_timestamp(self):
        """Test successful verification with signature and timestamp."""
        raw_body = json.dumps(self.valid_payload)
        timestamp = datetime.now(timezone.utc).isoformat()
        signature = f"sha256={self.create_signature(raw_body, self.endpoint_secret, timestamp)}"
        
        article = WebhookService.construct_event(
            raw_body, signature, self.endpoint_secret, timestamp
        )
        
        # Verify it's an Article instance
        self.assertIsInstance(article, Article)
        
        # Verify basic fields
        self.assertEqual(article.title, self.valid_payload["title"])
        self.assertEqual(article.link, self.valid_payload["link"])
        
        # Verify date conversion: string -> datetime
        self.assertIsInstance(article.publishDate, datetime)
        self.assertEqual(article.publishDate.isoformat(), self.valid_payload["publishDate"].replace('Z', '+00:00'))
        
        # Verify confidence conversion: string -> float
        self.assertIsInstance(article.confidence, float)
        self.assertEqual(article.confidence, 0.95)
        
        # Verify company confidence conversion: string -> float
        self.assertEqual(len(article.companies), 1)
        self.assertIsInstance(article.companies[0].confidence, float)
        self.assertEqual(article.companies[0].confidence, 0.90)
    
    def test_verify_and_construct_event_with_valid_signature_without_timestamp(self):
        """Test successful verification without timestamp."""
        raw_body = json.dumps(self.valid_payload)
        signature = f"sha256={self.create_signature(raw_body, self.endpoint_secret)}"
        
        article = WebhookService.construct_event(
            raw_body, signature, self.endpoint_secret
        )
        
        self.assertIsInstance(article, Article)
        self.assertEqual(article.title, self.valid_payload["title"])
        self.assertIsInstance(article.confidence, float)
        self.assertEqual(article.confidence, 0.95)
    
    def test_signature_without_prefix(self):
        """Test signature without sha256= prefix."""
        raw_body = json.dumps(self.valid_payload)
        timestamp = datetime.now(timezone.utc).isoformat()
        signature = self.create_signature(raw_body, self.endpoint_secret, timestamp)
        
        article = WebhookService.construct_event(
            raw_body, signature, self.endpoint_secret, timestamp
        )
        
        self.assertIsInstance(article, Article)
        self.assertEqual(article.title, self.valid_payload["title"])
        self.assertIsInstance(article.publishDate, datetime)
    
    def test_invalid_signature_raises_error(self):
        """Test that invalid signature raises error."""
        raw_body = json.dumps(self.valid_payload)
        timestamp = datetime.now(timezone.utc).isoformat()
        invalid_signature = "sha256=invalid_signature"
        
        with self.assertRaises(WebhookVerificationError) as context:
            WebhookService.construct_event(
                raw_body, invalid_signature, self.endpoint_secret, timestamp
            )
        
        self.assertEqual(str(context.exception), "Invalid webhook signature")
    
    def test_mismatched_secret_raises_error(self):
        """Test that mismatched secret raises error."""
        raw_body = json.dumps(self.valid_payload)
        timestamp = datetime.now(timezone.utc).isoformat()
        wrong_secret = "wrong_secret"
        signature = f"sha256={self.create_signature(raw_body, wrong_secret, timestamp)}"
        
        with self.assertRaises(WebhookVerificationError) as context:
            WebhookService.construct_event(
                raw_body, signature, self.endpoint_secret, timestamp
            )
        
        self.assertEqual(str(context.exception), "Invalid webhook signature")
    
    def test_expired_timestamp_raises_error(self):
        """Test that expired timestamp raises error."""
        raw_body = json.dumps(self.valid_payload)
        old_timestamp = (datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat()
        signature = f"sha256={self.create_signature(raw_body, self.endpoint_secret, old_timestamp)}"
        
        with self.assertRaises(WebhookVerificationError) as context:
            WebhookService.construct_event(
                raw_body, signature, self.endpoint_secret, old_timestamp
            )
        
        self.assertEqual(
            str(context.exception), "Webhook timestamp outside allowed tolerance"
        )
    
    def test_timestamp_within_tolerance(self):
        """Test timestamp within 5 minute tolerance."""
        raw_body = json.dumps(self.valid_payload)
        recent_timestamp = (datetime.now(timezone.utc) - timedelta(minutes=4)).isoformat()
        signature = f"sha256={self.create_signature(raw_body, self.endpoint_secret, recent_timestamp)}"
        
        article = WebhookService.construct_event(
            raw_body, signature, self.endpoint_secret, recent_timestamp
        )
        
        self.assertIsInstance(article, Article)
        self.assertEqual(article.title, self.valid_payload["title"])
        self.assertIsInstance(article.publishDate, datetime)
    
    def test_invalid_json_payload_raises_error(self):
        """Test that invalid JSON raises error."""
        raw_body = "invalid json"
        signature = f"sha256={self.create_signature(raw_body, self.endpoint_secret)}"
        
        with self.assertRaises(WebhookVerificationError) as context:
            WebhookService.construct_event(
                raw_body, signature, self.endpoint_secret
            )
        
        self.assertEqual(str(context.exception), "Invalid JSON payload")
    
    def test_complex_payload(self):
        """Test handling of complex payload with various data types."""
        complex_payload = {
            "link": "https://example.com/complex-article",
            "title": "Complex Article with Multiple Companies",
            "publishDate": "2024-01-01T12:30:00Z",
            "source": "financial-news.com",
            "language": "en",
            "sentiment": "neutral",
            "confidence": "0.85",
            "summary": "A comprehensive analysis of market trends",
            "images": ["https://example.com/image1.jpg", "https://example.com/image2.jpg"],
            "content": "Full article content here...",
            "companies": [
                {
                    "companyId": 1,
                    "confidence": "0.95",
                    "country": "US",
                    "exchange": "NASDAQ",
                    "industry": "Technology",
                    "sector": "Software",
                    "name": "Apple Inc.",
                    "ticker": "AAPL",
                    "isin": "US0378331005",
                    "openfigi": "BBG000B9XRY4"
                },
                {
                    "companyId": 2,
                    "confidence": "0.88",
                    "name": "Microsoft Corporation",
                    "ticker": "MSFT"
                }
            ]
        }
        
        raw_body = json.dumps(complex_payload)
        signature = f"sha256={self.create_signature(raw_body, self.endpoint_secret)}"
        
        article = WebhookService.construct_event(
            raw_body, signature, self.endpoint_secret
        )
        
        self.assertIsInstance(article, Article)
        self.assertEqual(article.title, complex_payload["title"])
        self.assertEqual(len(article.companies), 2)
        
        # Verify confidence type conversions
        self.assertIsInstance(article.confidence, float)
        self.assertEqual(article.confidence, 0.85)
        self.assertIsInstance(article.companies[0].confidence, float)
        self.assertEqual(article.companies[0].confidence, 0.95)
        self.assertIsInstance(article.companies[1].confidence, float)
        self.assertEqual(article.companies[1].confidence, 0.88)
        
        # Verify date conversion
        self.assertIsInstance(article.publishDate, datetime)
    
    def test_case_sensitive_signatures(self):
        """Test that signatures are case-sensitive."""
        raw_body = json.dumps(self.valid_payload)
        signature = f"sha256={self.create_signature(raw_body, self.endpoint_secret)}"
        upper_case_signature = signature.upper()
        
        with self.assertRaises(WebhookVerificationError):
            WebhookService.construct_event(
                raw_body, upper_case_signature, self.endpoint_secret
            )
    
    def test_invalid_timestamp_format_raises_error(self):
        """Test that invalid timestamp format raises error."""
        raw_body = json.dumps(self.valid_payload)
        invalid_timestamp = "not-a-timestamp"
        signature = f"sha256={self.create_signature(raw_body, self.endpoint_secret, invalid_timestamp)}"
        
        with self.assertRaises(WebhookVerificationError) as context:
            WebhookService.construct_event(
                raw_body, signature, self.endpoint_secret, invalid_timestamp
            )
        
        self.assertEqual(str(context.exception), "Invalid timestamp format")


if __name__ == "__main__":
    unittest.main()