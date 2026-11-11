"""Ed25519 signatures, backwards-compatible HMAC and offline key files."""
import json
from pathlib import Path
import tempfile
import unittest
from rei0.models import Validation
from rei0.review import (Ed25519ReviewIssuer, Ed25519TrustedReviewer,
                         VerificationBoundary, ReviewReceipt, ReviewError,
                         ReviewIssuer, TrustedReviewer)
from rei0.service_cli import _run, add_args, load_trust, load_signer
import argparse


class EdReviewTests(unittest.TestCase):
    def setUp(self):
        self.signer=Ed25519ReviewIssuer.generate('ed-review','reviewer')
        self.boundary=VerificationBoundary({'ed-review':Ed25519TrustedReviewer(
            'reviewer',self.signer.public_key_bytes())})
    def receipt(self):
        return self.signer.issue(submission_id='example',subject_digest='a'*64,
            decision=Validation.VERIFIED,reason='I checked the original',
            issued_at='2026-11-10T19:00:00Z',decision_index=1,prior_signature='0'*64)
    def test_signed_receipt_verified_by_public_key(self):
        receipt=self.receipt()
        self.assertEqual(receipt.scheme,'ed25519')
        self.assertEqual(len(receipt.signature),128)
        self.boundary.verify(ReviewReceipt.from_dict(receipt.to_dict()))
    def test_tampering_rejected(self):
        r=self.receipt().to_dict();r['reason']='fabricated'
        with self.assertRaises(ReviewError):self.boundary.verify(ReviewReceipt.from_dict(r))
    def test_signature_corruption_rejected(self):
        r=self.receipt().to_dict();r['signature']='0'*128
        with self.assertRaises(ReviewError):self.boundary.verify(ReviewReceipt.from_dict(r))
    def test_unknown_key_rejected(self):
        other=Ed25519ReviewIssuer.generate('ed-review','reviewer')
        r=other.issue(submission_id='example',subject_digest='a'*64,
            decision=Validation.VERIFIED,reason='test',issued_at='2026-11-10T19:00:00Z',
            decision_index=1,prior_signature='0'*64)
        with self.assertRaises(ReviewError):self.boundary.verify(r)
    def test_invalid_public_key_fails(self):
        with self.assertRaises(ReviewError):Ed25519TrustedReviewer('reviewer',b'short')
    def test_wrong_scheme_rejected(self):
        h=ReviewIssuer('ed-review','reviewer',b'k'*32)
        r=h.issue(submission_id='example',subject_digest='a'*64,
           decision=Validation.VERIFIED,reason='legacy',issued_at='2026-11-10T19:00:00Z',
           decision_index=1,prior_signature='0'*64)
        with self.assertRaises(ReviewError): self.boundary.verify(r)
    def test_hmac_v1_still_accepted(self):
        issuer=ReviewIssuer('hmac','human',b'k'*32)
        boundary=VerificationBoundary({'hmac':TrustedReviewer('human',b'k'*32)})
        receipt=issuer.issue(submission_id='s',subject_digest='a'*64,
            decision=Validation.VERIFIED,reason='legacy',issued_at='2026-11-10T19:00:00Z',
            decision_index=1,prior_signature='0'*64)
        boundary.verify(ReviewReceipt.from_dict(receipt.to_dict()))
        self.assertEqual(receipt.to_dict()['schema_version'],'rei0.review.v1')
    def test_ed_key_generation_separates_private_and_public(self):
        with tempfile.TemporaryDirectory() as td:
            signer=Path(td)/'signer.json'; trust=Path(td)/'trust.json'
            p=argparse.ArgumentParser(); add_args(p)
            args=p.parse_args(['service-keygen-ed25519','--signer',str(signer),
                               '--trust',str(trust)])
            self.assertTrue(_run(args)['created'])
            self.assertIn('private_hex',signer.read_text())
            self.assertNotIn('private_hex',trust.read_text())
            self.assertNotIn('secret_hex',trust.read_text())
            public=load_trust(trust)
            issuer=load_signer(signer)
            r=issuer.issue(submission_id='s',subject_digest='a'*64,
                decision=Validation.VERIFIED,reason='operator',issued_at='2026-11-10T19:00:00Z',
                decision_index=1,prior_signature='0'*64)
            public.verify(r)
