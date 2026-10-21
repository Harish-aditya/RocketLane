import pytest
from app.dashboard import read_checkpoints
from app.store import Store


def test_checkpoint_log_pagination_filter_and_empty(tmp_path):
    path = tmp_path/'log.db'
    store = Store(path)
    assert read_checkpoints(path) == {'items': [], 'total': 0, 'next_cursor': None}
    for i in range(120):
        store.record_checkpoint({'configurable': {'thread_id': 'one' if i%2 else 'two'}},
                                {'id': str(i), 'channel_values': {'run': {'state': 'confirmed'}}}, {'step':i})
    first = read_checkpoints(path)
    second = read_checkpoints(path,before=first['next_cursor'])
    assert first['total'] == 120 and len(first['items']) == 50
    assert len(second['items']) == 50
    assert {r['event_id'] for r in first['items']}.isdisjoint(r['event_id'] for r in second['items'])
    filtered = read_checkpoints(path,'one')
    assert filtered['total'] == 60
    assert all(r['run_id']=='one' for r in filtered['items'])
    assert read_checkpoints(path,'missing')['items'] == []
    with pytest.raises(ValueError):
        read_checkpoints(path,before=-1)
