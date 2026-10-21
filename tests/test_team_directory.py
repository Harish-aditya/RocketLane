import pytest
from app.store import Store
from app.team_directory import seed, team, escalation


def test_seed_repeat_preserves_member_changes():
    store = Store(':memory:')
    assert len(seed(store)) == 13
    with store.transaction():
        store.db.execute("UPDATE team_members SET active=0 WHERE member_id='mock-csm-01'")
    assert len(seed(store)) == 13
    assert len(team(store, 'Enterprise')) == 12
    assert all(r['slack_user_id'] is None and r['is_mock'] for r in seed(store))


def test_plan_and_escalation_routing():
    store = Store(':memory:')
    seed(store)
    assert sum(r['role'] == 'CSM' for r in team(store, 'Enterprise')) == 10
    assert escalation(store, 'Growth', 0) == []
    assert escalation(store, 'Growth', 1)[0]['role'] == 'Project Manager'
    assert escalation(store, 'Enterprise', 3)[0]['role'] == 'Project Manager'
    assert escalation(store, 'Enterprise', 4)[0]['role'] == 'Project Owner'
    assert escalation(store, 'Enterprise', 4, completed=True) == []
    with pytest.raises(ValueError):
        team(store, 'the expensive one')
    with pytest.raises(ValueError, match='Mock'):
        team(store, 'Enterprise', live=True)
