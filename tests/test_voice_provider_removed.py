from pathlib import Path

import pytest

from app.services import DemoServices, IntegrationError, LiveServices
from app.store import Store
from app.workflow import Workflow


def test_live_telephone_operations_fail_closed():
    for method, value in [('call', {'customer_name': 'Acme'}), ('outcome', 'old-provider-call')]:
        with pytest.raises(IntegrationError):
            getattr(LiveServices(), method)(value)


def test_legacy_real_confirmation_cannot_be_simulated(tmp_path):
    store = Store(tmp_path / 'voice.db')
    flow = Workflow(store, DemoServices('Growth'))
    try:
        run = flow.ingest('legacy', Path('examples/minimal_deal.txt').read_text())
        with store.transaction():
            run['voice_mode'] = 'real'
            store.save(run)
        assert flow.run(run['id'])['state'] == 'validated'
        assert flow.services.calls == 0
    finally:
        flow.close()
        store.db.close()
