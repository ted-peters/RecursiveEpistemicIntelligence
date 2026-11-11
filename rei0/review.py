"""Authenticated, signed *review decisions*, not automatic truth verification.

The HMAC key belongs to a trusted reviewing authority and MUST NOT be
provided to the untrusted LLM, embedded in a checkpoint, or committed to git.
For adversarial isolation, deploy issuance/verification outside the model process.
"""
from __future__ import annotations

from dataclasses import dataclass
import hmac
from hashlib import sha256
from typing import Any, Mapping

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives import serialization

from .models import Validation, canonical_json, require_utc


class ReviewError(ValueError):
    """A review was not validly authenticated or was not allowed."""


def _hex_digest(value: str, field: str) -> None:
    if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
        raise ReviewError(f'{field} must be a lowercase 64-character SHA-256 hex digest')


def _name(value: str, field: str, limit: int = 256) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ReviewError(f'{field} must be a nonempty string of at most {limit} characters')


@dataclass(frozen=True)
class ReviewReceipt:
    """Portable domain-separated HMAC-SHA256 attestation of one review decision.

    subject_digest commits to evidence, claim, link, source provenance, artifact
    hash, and active method; earlier decisions are linked via prior_signature.
    """
    key_id: str
    reviewer_id: str
    submission_id: str
    subject_digest: str
    decision: Validation
    reason: str
    issued_at: str
    decision_index: int
    prior_signature: str
    signature: str
    scheme: str = "hmac-sha256"

    def __post_init__(self) -> None:
        for key in ('key_id', 'reviewer_id', 'submission_id'):
            _name(getattr(self, key), key)
        _name(self.reason, 'reason', 2000)
        _hex_digest(self.subject_digest, 'subject_digest')
        if self.scheme not in ('hmac-sha256','ed25519'):
            raise ReviewError('unsupported review signature scheme')
        if (not isinstance(self.prior_signature,str) or
            len(self.prior_signature) not in (64,128) or
            any(c not in '0123456789abcdef' for c in self.prior_signature)):
            raise ReviewError('invalid prior signature')
        length = 64 if self.scheme == 'hmac-sha256' else 128
        if (not isinstance(self.signature,str) or len(self.signature) != length or
            any(c not in '0123456789abcdef' for c in self.signature)):
            raise ReviewError('invalid review signature')
        require_utc(self.issued_at)
        if not isinstance(self.decision, Validation) or self.decision == Validation.PENDING:
            raise ReviewError('invalid review decision')
        if type(self.decision_index) is not int or self.decision_index < 1:
            raise ReviewError('decision_index must be positive')

    def statement(self) -> dict[str, Any]:
        return {'schema_version': 'rei0.review.v1' if self.scheme == 'hmac-sha256' else 'rei0.review.v2', 'key_id': self.key_id,
                'reviewer_id': self.reviewer_id, 'submission_id': self.submission_id,
                'subject_digest': self.subject_digest, 'decision': self.decision.value,
                'reason': self.reason, 'issued_at': self.issued_at,
                'decision_index': self.decision_index, 'prior_signature': self.prior_signature}

    def to_dict(self) -> dict[str, Any]:
        return {**self.statement(), 'signature': self.signature}

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> ReviewReceipt:
        if not isinstance(value, dict) or set(value) != {
            'schema_version', 'key_id', 'reviewer_id', 'submission_id', 'subject_digest',
            'decision', 'reason', 'issued_at', 'decision_index', 'prior_signature', 'signature'
        } or value.get('schema_version') not in ('rei0.review.v1','rei0.review.v2'):
            raise ReviewError('invalid review receipt schema')
        try:
            return cls(key_id=value['key_id'], reviewer_id=value['reviewer_id'],
                       submission_id=value['submission_id'], subject_digest=value['subject_digest'],
                       decision=Validation(value['decision']), reason=value['reason'],
                       issued_at=value['issued_at'], decision_index=value['decision_index'],
                       prior_signature=value['prior_signature'], signature=value['signature'],
                       scheme='ed25519' if value['schema_version']=='rei0.review.v2' else 'hmac-sha256')
        except (ValueError, TypeError, KeyError) as exc:
            raise ReviewError(f'invalid review receipt: {exc}') from exc


def _mac(secret: bytes, statement: Mapping[str, Any]) -> str:
    return hmac.new(secret, b'REI-0.3-REVIEW\x00' + canonical_json(statement).encode('utf-8'), sha256).hexdigest()


def _secret(value: bytes) -> None:
    if not isinstance(value, bytes) or len(value) < 32:
        raise ReviewError('review secret must be at least 32 random bytes')


class ReviewIssuer:
    """Trusted signing capability. Restrict creation to a separate review process."""
    def __init__(self, key_id: str, reviewer_id: str, secret: bytes):
        _name(key_id, 'key_id'); _name(reviewer_id, 'reviewer_id')
        _secret(secret)
        self.key_id = key_id
        self.reviewer_id = reviewer_id
        self._secret = secret

    def issue(self, *, submission_id: str, subject_digest: str, decision: Validation,
              reason: str, issued_at: str, decision_index: int,
              prior_signature: str) -> ReviewReceipt:
        statement = {'schema_version': 'rei0.review.v1', 'key_id': self.key_id,
                     'reviewer_id': self.reviewer_id, 'submission_id': submission_id,
                     'subject_digest': subject_digest, 'decision': decision.value,
                     'reason': reason, 'issued_at': issued_at,
                     'decision_index': decision_index, 'prior_signature': prior_signature}
        signature = _mac(self._secret, statement)
        return ReviewReceipt.from_dict({**statement, 'signature': signature})


@dataclass(frozen=True)
class TrustedReviewer:
    reviewer_id: str
    secret: bytes
    can_verify: bool = True
    can_revoke: bool = True

    def __post_init__(self) -> None:
        _name(self.reviewer_id, 'reviewer_id')
        _secret(self.secret)
        if type(self.can_verify) is not bool or type(self.can_revoke) is not bool:
            raise ReviewError('permissions must be booleans')




class Ed25519ReviewIssuer:
    """Offline private-key signer; the verifier must never receive this object."""
    def __init__(self, key_id: str, reviewer_id: str, private_key: bytes):
        _name(key_id, 'key_id'); _name(reviewer_id, 'reviewer_id')
        if not isinstance(private_key, bytes) or len(private_key) != 32:
            raise ReviewError('Ed25519 seed must be 32 bytes')
        self.key_id, self.reviewer_id = key_id, reviewer_id
        self._key = Ed25519PrivateKey.from_private_bytes(private_key)

    @classmethod
    def generate(cls, key_id: str, reviewer_id: str) -> 'Ed25519ReviewIssuer':
        key = Ed25519PrivateKey.generate().private_bytes(
            serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
            serialization.NoEncryption())
        return cls(key_id, reviewer_id, key)

    def private_key_bytes(self) -> bytes:
        return self._key.private_bytes(serialization.Encoding.Raw,
                                       serialization.PrivateFormat.Raw,
                                       serialization.NoEncryption())

    def public_key_bytes(self) -> bytes:
        return self._key.public_key().public_bytes(serialization.Encoding.Raw,
                                                    serialization.PublicFormat.Raw)

    def issue(self, *, submission_id: str, subject_digest: str, decision: Validation,
              reason: str, issued_at: str, decision_index: int,
              prior_signature: str) -> ReviewReceipt:
        statement = {'schema_version': 'rei0.review.v2', 'key_id': self.key_id,
                     'reviewer_id': self.reviewer_id, 'submission_id': submission_id,
                     'subject_digest': subject_digest, 'decision': decision.value,
                     'reason': reason, 'issued_at': issued_at,
                     'decision_index': decision_index, 'prior_signature': prior_signature}
        signature = self._key.sign(b'REI-0.5-ED25519-REVIEW\x00' +
                                   canonical_json(statement).encode('utf-8')).hex()
        return ReviewReceipt.from_dict({**statement, 'signature':signature})


@dataclass(frozen=True)
class Ed25519TrustedReviewer:
    reviewer_id: str
    public_key: bytes
    can_verify: bool = True
    can_revoke: bool = True

    def __post_init__(self) -> None:
        _name(self.reviewer_id,'reviewer_id')
        if not isinstance(self.public_key,bytes) or len(self.public_key)!=32:
            raise ReviewError('Ed25519 public key must be 32 bytes')
        if type(self.can_verify) is not bool or type(self.can_revoke) is not bool:
            raise ReviewError('permissions must be booleans')
        Ed25519PublicKey.from_public_bytes(self.public_key)


class VerificationBoundary:
    """Fail-closed verifier with keys supplied independently of untrusted data.

    This is an authenticated application-layer gate, NOT an OS/process sandbox.
    Caller must protect the key registry and audit anchors outside this process.
    """
    def __init__(self, reviewers: Mapping[str, TrustedReviewer | Ed25519TrustedReviewer]):
        if not isinstance(reviewers, Mapping) or not reviewers:
            raise ReviewError('at least one trusted key is required')
        for key_id, record in reviewers.items():
            _name(key_id, 'key_id')
            if not isinstance(record, (TrustedReviewer,Ed25519TrustedReviewer)):
                raise ReviewError('invalid key registration')
        self._reviewers = dict(reviewers)

    def verify(self, receipt: ReviewReceipt) -> None:
        reviewer = self._reviewers.get(receipt.key_id)
        if reviewer is None:
            raise ReviewError('untrusted signing key')
        if reviewer.reviewer_id != receipt.reviewer_id:
            raise ReviewError('reviewer ID does not match authenticated key')
        if receipt.decision in (Validation.VERIFIED, Validation.REJECTED) and not reviewer.can_verify:
            raise ReviewError('key lacks review permission')
        if receipt.decision == Validation.REVOKED and not reviewer.can_revoke:
            raise ReviewError('key lacks revocation permission')
        if isinstance(reviewer, Ed25519TrustedReviewer):
            if receipt.scheme != 'ed25519':
                raise ReviewError('signature scheme does not match trusted key')
            try:
                Ed25519PublicKey.from_public_bytes(reviewer.public_key).verify(
                    bytes.fromhex(receipt.signature),
                    b'REI-0.5-ED25519-REVIEW\x00' + canonical_json(receipt.statement()).encode('utf-8'))
            except (InvalidSignature, ValueError) as exc:
                raise ReviewError('review authentication failed') from exc
        else:
            if receipt.scheme != 'hmac-sha256':
                raise ReviewError('signature scheme does not match trusted key')
            expected = _mac(reviewer.secret, receipt.statement())
            if not hmac.compare_digest(expected, receipt.signature):
                raise ReviewError('review authentication failed')
