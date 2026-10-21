from pathlib import Path
import pytest
from app.services import DemoServices,LiveServices,UncertainWrite
from app import services as service_module
from app.store import Store
from app.workflow import Workflow

BODY=Path('examples/minimal_deal.txt').read_text()


def test_customer_invitation_precedes_topic_and_welcome_and_never_repeats():
    service=DemoServices();flow=Workflow(Store(':memory:'),service)
    try:
        run=flow.run(flow.ingest('customer',BODY)['id'])
        assert run['state']=='complete'
        assert run['customer_invitation']['status']=='simulated'
        assert service.customer_invitations==[(run['channel_id'],run['deal']['contact_email'])]
        events=[e['action'] for e in flow.store.events(run['id'])]
        assert events.index('add_member_result')<events.index('customer_invite_intent')<events.index('topic_intent')<events.index('welcome_intent')
        flow.run(run['id'])
        assert len(service.customer_invitations)==1
    finally:
        flow.close()


def test_manual_invitation_waits_for_matching_operator_receipt():
    service=DemoServices()
    service.invite_customer=lambda channel,email:{'status':'manual_required','email':email,'reason':'Admin must invite'}
    flow=Workflow(Store(':memory:'),service)
    try:
        run=flow.run(flow.ingest('customer',BODY)['id'])
        assert run['state']=='customer_invite_manual' and service.welcomes==0
        flow.run(run['id']);assert service.welcomes==0
        with pytest.raises(ValueError):
            flow.record_customer_invite(run['id'],'someoneelse@acme.example','invitation_sent','I123','Verified')
        flow.record_customer_invite(run['id'],run['deal']['contact_email'],'invitation_sent','I123','Administrator checked the invitation email')
        completed=flow.run(run['id'])
        assert completed['state']=='complete'
        assert completed['customer_invitation']['status']=='invitation_sent'
    finally:
        flow.close()


def test_uncertain_invite_requires_reconciliation_without_resend():
    class Timeout(DemoServices):
        def invite_customer(self,channel,email):
            self.customer_invitations.append((channel,email))
            raise UncertainWrite('timeout')
    service=Timeout();flow=Workflow(Store(':memory:'),service)
    try:
        run=flow.run(flow.ingest('customer',BODY)['id'])
        assert run['state']=='reconcile' and run['pending_action']=='customer_invite'
        flow.run(run['id']);assert len(service.customer_invitations)==1
        flow.reconcile(run['id'],'customer_invited','Verified Slack invitation email','I123')
        run=flow.run(run['id'])
        assert run['state']=='complete' and len(service.customer_invitations)==1
        assert run['customer_invitation']['status']=='invitation_sent'
    finally:
        flow.close()


def test_existing_member_resolved_by_email(monkeypatch):
    monkeypatch.setenv('SLACK_BOT_TOKEN','test-token')
    sent=[]
    def request(method,url,headers,payload=None):
        sent.append((method,url,payload))
        if method=='GET':
            return {'ok':True,'user':{'id':'U123'}}
        return {'ok':False,'error':'already_in_channel'}
    monkeypatch.setattr(service_module,'request',request)
    r=LiveServices().invite_customer('C123','customer@acme.example')
    assert r['status']=='member_added' and r['user_id']=='U123'
    assert sent[0][0]=='GET' and 'users.lookupByEmail?' in sent[0][1]
    assert sent[1][2]=={'channel':'C123','users':'U123'}


def test_connect_email_invitation_and_manual_fallback(monkeypatch):
    monkeypatch.setenv('SLACK_BOT_TOKEN','test-token')
    monkeypatch.setenv('SLACK_CUSTOMER_INVITE_MODE','connect')
    sent=[]
    def request(method,url,headers,payload=None):
        sent.append(payload)
        return {'ok':False,'error':'users_not_found'} if method=='GET' else {'ok':True,'invite_id':'I123'}
    monkeypatch.setattr(service_module,'request',request)
    assert LiveServices().invite_customer('C123','customer@acme.example')['status']=='invitation_sent'
    assert sent[-1]=={'channel':'C123','emails':['customer@acme.example'],'external_limited':True}
    monkeypatch.setenv('SLACK_CUSTOMER_INVITE_MODE','manual')
    sent.clear()
    assert LiveServices().invite_customer('C123','customer@acme.example')['status']=='manual_required'
    assert len(sent)==1


def test_paid_or_permission_restriction_does_not_claim_invitation_sent(monkeypatch):
    monkeypatch.setenv('SLACK_BOT_TOKEN','test-token')
    monkeypatch.setenv('SLACK_CUSTOMER_INVITE_MODE','connect')
    monkeypatch.setattr(service_module,'request',lambda method,*args,**kwargs:
                        {'ok':False,'error':'users_not_found' if method=='GET' else 'not_paid'})
    assert LiveServices().invite_customer('C123','customer@acme.example')['status']=='manual_required'


def test_retry_after_permission_fix_reuses_channel_and_team():
    service=DemoServices()
    service.invite_customer=lambda channel,email:{'status':'manual_required','email':email,'reason':'Missing permission'}
    flow=Workflow(Store(':memory:'),service)
    try:
        run=flow.run(flow.ingest('customer',BODY)['id'])
        channel=run['channel_id']
        service.invite_customer=lambda channel,email:{'status':'member_added','email':email,'user_id':'U444'}
        flow.retry_customer_invite(run['id'])
        result=flow.run(run['id'])
        assert result['state']=='complete' and result['channel_id']==channel
        assert service.channels==service.projects==1 and len(service.invitation_calls)==3
        with pytest.raises(ValueError):
            flow.retry_customer_invite(run['id'])
    finally:
        flow.close()


def test_simulated_worker_cannot_finish_real_slack_customer_step():
    class Hybrid(DemoServices):
        real_slack=True
        def invite_customer(self,channel,email):
            return {'status':'manual_required','email':email,'reason':'Missing permission'}
    store=Store(':memory:');flow=Workflow(store,Hybrid())
    try:
        run=flow.run(flow.ingest('hybrid',BODY)['id'])
        assert run['slack_mode']=='real_slack_demo'
        flow.retry_customer_invite(run['id'])
        other_service=DemoServices();other=Workflow(store,other_service)
        try:
            assert other.run(run['id'])['state']=='team_added'
            assert other_service.customer_invitations==[] and other_service.welcomes==0
        finally:
            other.close()
    finally:
        flow.close()
