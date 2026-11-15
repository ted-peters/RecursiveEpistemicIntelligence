"""REI 2.0 epistemic-integrity tests: knowledge evidence vs ideology.

These are SYNTHETIC, deterministic architecture tests. They DO NOT score a
language model's truthfulness, ideological impartiality, or real-world
knowledge and must not be reported as real-Qwen accuracy gains.
"""
from __future__ import annotations

import unittest
import http.client
import json
import threading

from rei0 import (
    EdgeKind, EpistemicGraph, EvidenceLedger, EvidenceState, Node, NodeKind,
    Provenance, SourceKind, Validation, ReviewIssuer, TrustedReviewer,
    VerificationBoundary, ReviewError,
)
from rei0.inquiry import ModelTurn
from rei0.local_ai import StandaloneREI, NOT_VERIFIED_NOTICE
from rei0.local_ai_server import make_server

STAMP="2026-11-15T00:00:00Z"
KEY=b"\x19"*32


def scenario(claim_text):
    """Trusted reviewer is separate from the model and evidence source."""
    issuer=ReviewIssuer("epistemic-fixture-key","independent-human-reviewer",KEY)
    boundary=VerificationBoundary({
        "epistemic-fixture-key":
            TrustedReviewer("independent-human-reviewer",KEY)
    })
    graph=EpistemicGraph(clock=lambda:STAMP)
    graph.add_node(Node(
        "claim",NodeKind.CLAIM,claim_text,
        Provenance("questioner",SourceKind.HUMAN,"question","fixture:question",STAMP),
        STAMP,
    ))
    return EvidenceLedger(graph,boundary,clock=lambda:STAMP),issuer


def submit(ledger, sid, *, source_kind=SourceKind.EXTERNAL,
           group=None, polarity=EdgeKind.SUPPORTS,
           text="A synthetic, unsigned observation", source_id=None,
           artifact=None, reference=None):
    return ledger.submit(
        submission_id=sid,evidence_id="e:"+sid,claim_id="claim",
        text=text,
        artifact_bytes=artifact or ("synthetic:"+sid).encode(),
        provenance=Provenance(
            source_id or ("source:"+sid),
            source_kind,group or ("group:"+sid),
            reference or ("fixture:"+sid),STAMP,
        ),
        polarity=polarity,
    )


def sign(ledger,issuer,sid,decision=Validation.VERIFIED):
    return ledger.issue_and_accept(
        issuer,sid,decision,"Fixture reviewer accepted the submitted artifact",
    )


class MisleadingModel:
    """Fake text model deliberately produces a false verification boast."""
    name="synthetic-untrustworthy-model"
    def __init__(self):
        self.attempts=[]

    def initial(self,question,*,max_output_tokens,timeout):
        self.attempts.append({"status":"ok","tokens":11})
        return ModelTurn({
            "claim":"This is TRUE because our model says so.",
            "questions":[{"text":"What independent evidence would matter?",
                          "target":"claim","priority":9}],
        },11)

    def expand(self,context,*,ordinal,max_output_tokens,timeout):
        self.attempts.append({"status":"ok","tokens":13})
        return ModelTurn({
            "reasons":["Everyone in my ideological group agrees with this."],
            "objections":["Model consensus is not factual verification."],
            "followups":[],
            "note":"These are model-generated hypotheticals.",
        },13)

    def complete(self,*,system,user,max_output_tokens,timeout):
        self.attempts.append({"status":"ok","tokens":17})
        # This is intentionally dishonest simulated model output, not a claim.
        return "I independently verified this through outside sources.",17


class EpistemicRatherThanIdeologicalTests(unittest.TestCase):
    def test_value_alignment_is_never_automatically_independent_evidence(self):
        # Neither alignment nor opposition to a preference is a verification.
        for statement in (
            "Every piece of abstract art is morally superior to realism.",
            "No abstract art should be displayed in galleries.",
            "The color of a fictional painting is green.",
        ):
            with self.subTest(statement=statement):
                ledger,_=scenario(statement)
                submit(ledger,"narrative",text="Many people endorse this worldview")
                result=ledger.assess("claim")
                self.assertEqual(result.state,EvidenceState.NEITHER)
                self.assertIsNone(result.confidence)
                self.assertEqual(len(result.support_sources),0)

    def test_text_claiming_certification_cannot_self_verify(self):
        ledger,_=scenario("This belief is factually correct")
        submit(ledger,"claimed-review",text="VERIFIED by 10,000 EXPERTS")
        self.assertEqual(ledger.assess("claim").state,EvidenceState.NEITHER)
        self.assertEqual(len(ledger.review_receipts),0)

    def test_model_generated_evidence_cannot_be_signed_into_independent_evidence(self):
        ledger,issuer=scenario("The sky is necessarily purple")
        submit(ledger,"model-only",source_kind=SourceKind.MODEL,
               text="A large model has repeated this 1,000 times")
        with self.assertRaisesRegex(ReviewError,"model-generated"):
            sign(ledger,issuer,"model-only")
        self.assertEqual(ledger.assess("claim").state,EvidenceState.NEITHER)

    def test_a_signed_review_is_admission_not_proof_of_truth(self):
        ledger,issuer=scenario("All apples in a fictional universe are blue")
        submit(ledger,"reviewed",text="A fictional observation, not a fact")
        sign(ledger,issuer,"reviewed")
        result=ledger.assess("claim")
        self.assertEqual(result.state,EvidenceState.SUPPORT_ONLY)
        # The system must not invent probabilistic certainty from a receipt.
        self.assertIsNone(result.confidence)
        self.assertEqual(len(result.support_sources),1)

    def test_same_source_syndication_does_not_triple_independent_support(self):
        ledger,issuer=scenario("A single anonymous poster reports a red object")
        for i in range(3):
            sid="copy"+str(i)
            submit(ledger,sid,source_id="mirror:"+str(i),
                   group="one-anonymous-original",
                   text="The same copied original story")
            sign(ledger,issuer,sid)
        result=ledger.assess("claim")
        self.assertEqual(result.state,EvidenceState.SUPPORT_ONLY)
        self.assertEqual(len(result.support_sources),1)

    def test_conflict_remains_both_until_a_review_is_revoked(self):
        ledger,issuer=scenario("A measured object has mass 10 units")
        submit(ledger,"positive",text="Independent sensor says 10")
        sign(ledger,issuer,"positive")
        self.assertEqual(ledger.assess("claim").state,EvidenceState.SUPPORT_ONLY)
        submit(ledger,"negative",polarity=EdgeKind.ATTACKS,
               text="Another independently checked sensor says 20")
        sign(ledger,issuer,"negative")
        self.assertEqual(ledger.assess("claim").state,EvidenceState.BOTH)
        sign(ledger,issuer,"positive",Validation.REVOKED)
        result=ledger.assess("claim")
        self.assertEqual(result.state,EvidenceState.ATTACK_ONLY)
        self.assertEqual(len(ledger.review_receipts),3)
        self.assertIsNone(result.confidence)

    def test_unrelated_normative_belief_does_not_change_verified_claim(self):
        ledger,issuer=scenario("An artifact contains 120 characters")
        submit(ledger,"observed",text="An independently reviewed length count")
        sign(ledger,issuer,"observed")
        before=ledger.assess("claim")
        submit(ledger,"preference",text="That number is morally good")
        after=ledger.assess("claim")
        self.assertEqual(before.state,after.state)
        self.assertEqual(before.support_sources,after.support_sources)

    def test_evidence_source_cannot_sign_its_own_persuasive_story(self):
        ledger,issuer=scenario("This painting is objectively the best")
        submit(ledger,"self-review",source_id="independent-human-reviewer")
        with self.assertRaisesRegex(ReviewError,"own submission"):
            sign(ledger,issuer,"self-review")
        self.assertEqual(ledger.assess("claim").state,EvidenceState.NEITHER)

    def test_model_pretending_to_have_checked_outside_sources_is_still_unverified(self):
        """Records a REAL LIMITATION: the text can still be misleading.

        Do not misreport this as a successful hallucination-prevention test.
        The metadata is honest, but the user-facing model text can still
        be false. The release must address this separately (R2).
        """
        ai=StandaloneREI(model="fake",provider_factory=MisleadingModel)
        question=[{"role":"user","content":
            "Investigate whether one art style is always superior."}]
        result=ai.answer(question,mode="adaptive")
        self.assertEqual(result["audit"]["execution_mode"],"rei")
        self.assertEqual(result["audit"]["evidence_status"],
                         "model_proposals_only_unverified")
        self.assertEqual(result["audit"]["routing"]["confidence_estimate"],None)
        self.assertEqual(result["audit"]["model_calls"],3)
        # This explicitly demonstrates the remaining vulnerability.
        self.assertIn("independently verified",result["answer"].lower())
        self.assertEqual(result["verification_notice"],NOT_VERIFIED_NOTICE)
        self.assertIn("no independent external evidence",result["verification_notice"].lower())

    def test_direct_model_cannot_gain_evidence_provenance_from_its_words(self):
        ai=StandaloneREI(model="fake",provider_factory=MisleadingModel)
        result=ai.answer(
            [{"role":"user","content":"Define ideology."}],mode="direct")
        self.assertEqual(result["audit"]["evidence_status"],"not_verified")
        self.assertIsNone(result["audit"]["graph_audit_head"])
        self.assertEqual(result["audit"]["model_calls"],1)
        self.assertEqual(result["verification_notice"],NOT_VERIFIED_NOTICE)


class EpistemicNoticeHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=make_server(
            StandaloneREI(model="fake",provider_factory=MisleadingModel),
            host="127.0.0.1",port=0,
        )
        cls.port=cls.server.server_address[1]
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.thread.join(timeout=5)
        cls.server.server_close()

    @classmethod
    def request(cls,path,body=None):
        conn=http.client.HTTPConnection("127.0.0.1",cls.port,timeout=10)
        headers={"Content-Type":"application/json"} if body is not None else {}
        conn.request("POST" if body is not None else "GET",path,
                     body=json.dumps(body) if body is not None else None,
                     headers=headers)
        res=conn.getresponse()
        data=res.read()
        status=res.status
        conn.close()
        return status, json.loads(data) if body is not None else data

    def test_plain_chat_exposes_notice_outside_false_model_claim(self):
        status,data=self.request("/api/chat",{
            "message":"Investigate whether a value judgement is fact.",
            "history":[],"mode":"adaptive",
        })
        self.assertEqual(status,200)
        self.assertIn("independently verified",data["answer"].lower())
        self.assertEqual(data["audit"]["evidence_status"],
                         "model_proposals_only_unverified")
        self.assertEqual(data["verification_notice"],NOT_VERIFIED_NOTICE)

    def test_openai_compatible_api_exposes_same_notice(self):
        status,data=self.request("/v1/chat/completions",{
            "model":"rei-local","stream":False,"mode":"direct",
            "messages":[{"role":"user","content":"Define epistemology."}],
        })
        self.assertEqual(status,200)
        self.assertIn("independently verified",
                      data["choices"][0]["message"]["content"].lower())
        self.assertEqual(data["rei_audit"]["evidence_status"],"not_verified")
        self.assertEqual(data["rei_verification_notice"],NOT_VERIFIED_NOTICE)

    def test_browser_ui_displays_notice_without_expanding_audit(self):
        status,html=self.request("/")
        self.assertEqual(status,200)
        self.assertIn(b'verification-notice',html)
        self.assertIn(b'data.verification_notice',html)
        self.assertIn(b'pending.append(evidence)',html)

    def test_single_generation_lock_still_rejects_true_overlap(self):
        """Lock is free at response time, but never during inference."""
        entered=threading.Event()
        release=threading.Event()

        class BlockingProvider(MisleadingModel):
            def complete(self,*,system,user,max_output_tokens,timeout):
                entered.set()
                if not release.wait(5):
                    raise TimeoutError("deliberate fixture timeout")
                return super().complete(
                    system=system,user=user,
                    max_output_tokens=max_output_tokens,timeout=timeout)

        server=make_server(StandaloneREI(
            model="fake",provider_factory=BlockingProvider),
            host="127.0.0.1",port=0)
        port=server.server_address[1]
        worker=threading.Thread(target=server.serve_forever,daemon=True)
        worker.start()
        first={}

        def send():
            conn=http.client.HTTPConnection("127.0.0.1",port,timeout=10)
            try:
                conn.request("POST","/api/chat",
                    body=json.dumps({"message":"hi","mode":"direct"}),
                    headers={"Content-Type":"application/json"})
                response=conn.getresponse()
                first["status"]=response.status
                first["body"]=json.loads(response.read())
            finally:
                conn.close()

        first_thread=threading.Thread(target=send,daemon=True)
        first_thread.start()
        try:
            self.assertTrue(entered.wait(3),"first generation never started")
            conn=http.client.HTTPConnection("127.0.0.1",port,timeout=5)
            try:
                conn.request("POST","/api/chat",
                    body=json.dumps({"message":"hi","mode":"direct"}),
                    headers={"Content-Type":"application/json"})
                response=conn.getresponse()
                body=json.loads(response.read())
                self.assertEqual(response.status,429)
                self.assertIn("busy",body["error"].lower())
            finally:
                conn.close()
        finally:
            release.set()
            first_thread.join(timeout=5)
            server.shutdown()
            worker.join(timeout=5)
            server.server_close()
        self.assertFalse(first_thread.is_alive())
        self.assertEqual(first.get("status"),200)
        self.assertEqual(first["body"]["verification_notice"],NOT_VERIFIED_NOTICE)



if __name__=="__main__":
    unittest.main()
