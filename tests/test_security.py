"""
Security-focused tests for trial-randomizer.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import warnings
from agents.base import AuditTrail, PHIGuard, SecurityException, assert_no_phi
from trial_randomizer.state import rng_state_from_json, load_state, save_state


class TestPHIGuard:
    """Tests for PHI outbound guard functionality."""

    def test_mrn_detection(self):
        with pytest.raises(SecurityException):
            PHIGuard.assert_no_phi("Patient MRN-12345678")

    def test_ssn_detection(self):
        with pytest.raises(SecurityException):
            PHIGuard.assert_no_phi("SSN: 123-45-6789")

    def test_phone_detection(self):
        with pytest.raises(SecurityException):
            PHIGuard.assert_no_phi("Call 555-123-4567")

    def test_email_detection(self):
        with pytest.raises(SecurityException):
            PHIGuard.assert_no_phi("Email: patient@example.com")

    def test_clean_text_passes(self):
        PHIGuard.assert_no_phi("Analytical assay specimen KEY-001 optimal")

    def test_empty_text_passes(self):
        PHIGuard.assert_no_phi("")

    def test_redact_phi(self):
        result = PHIGuard.redact_phi("Patient MRN-12345678 has SSN 123-45-6789")
        assert "REDACTED_IDENTIFIER" in result
        assert "MRN" not in result
        assert "123-45-6789" not in result


class TestAuditTrail:
    """Tests for HMAC-SHA256 audit trail functionality."""

    def test_audit_trail_integrity(self):
        trail = AuditTrail(secret_key="test-key-123")
        trail.log("test_actor", "test_tier", "TEST_EVENT", {"data": "value1"})
        trail.log("test_actor", "test_tier", "TEST_EVENT", {"data": "value2"})
        assert trail.verify_integrity() is True

    def test_audit_trail_tamper_detection(self):
        trail = AuditTrail(secret_key="test-key-123")
        trail.log("test_actor", "test_tier", "TEST_EVENT", {"data": "value1"})
        trail.log("test_actor", "test_tier", "TEST_EVENT", {"data": "value2"})
        # Tamper with the first entry
        trail.logs[0]["payload_hash"] = "tampered_hash"
        assert trail.verify_integrity() is False

    def test_audit_trail_chain_tampering(self):
        trail = AuditTrail(secret_key="test-key-123")
        trail.log("test_actor", "test_tier", "TEST_EVENT", {"data": "value1"})
        trail.log("test_actor", "test_tier", "TEST_EVENT", {"data": "value2"})
        # Tamper with the chain linkage
        trail.logs[1]["prev_hash"] = "broken_chain"
        assert trail.verify_integrity() is False

    def test_audit_trail_signature_verification(self):
        trail = AuditTrail(secret_key="test-key-123")
        trail.log("test_actor", "test_tier", "TEST_EVENT", {"data": "value1"})
        # Tamper with the signature
        trail.logs[0]["current_hash"] = "invalid_signature"
        assert trail.verify_integrity() is False

    def test_audit_trail_empty(self):
        trail = AuditTrail(secret_key="test-key-123")
        assert trail.verify_integrity() is True

    def test_audit_trail_phi_blocking(self):
        trail = AuditTrail(secret_key="test-key-123")
        with pytest.raises(SecurityException):
            trail.log("test_actor", "test_tier", "TEST_EVENT", {"data": "MRN-12345678"})

    def test_random_key_generation_without_env(self):
        """Test that a random key is generated when AUDIT_SECRET_KEY is not set."""
        import os
        # Remove the env var if it exists
        original = os.environ.pop("AUDIT_SECRET_KEY", None)
        try:
            with warnings.catch_warnings(record=True) as w:
                warnings.simplefilter("always")
                trail = AuditTrail()
                assert len(w) == 1
                assert "AUDIT_SECRET_KEY not set" in str(w[0].message)
        finally:
            # Restore the env var
            if original is not None:
                os.environ["AUDIT_SECRET_KEY"] = original


class TestRngStateValidation:
    """Tests for RNG state JSON validation."""

    def test_valid_rng_state(self):
        result = rng_state_from_json([1, [123, 456, 789], None])
        assert result == (1, (123, 456, 789), None)

    def test_invalid_rng_state_length(self):
        with pytest.raises(ValueError, match="Invalid RNG state format"):
            rng_state_from_json([1, [123]])

    def test_invalid_rng_state_type(self):
        with pytest.raises(ValueError, match="Invalid RNG state format"):
            rng_state_from_json("not a list")

    def test_invalid_internal_state(self):
        with pytest.raises(ValueError, match="internal state must be a list"):
            rng_state_from_json([1, "not a list", None])
