"""Bounded polling cycles; run exactly one worker per business database."""
import time
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def single_worker(database):
    """OS-released lock survives hard process termination without a stale PID file."""
    if database == ':memory:':
        yield
        return
    with Path(database + '.worker.lock').open('a+b') as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b'0')
            handle.flush()
        handle.seek(0)
        try:
            import os
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise RuntimeError('Another worker already owns this database') from exc
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == 'nt':
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def cycle(flow, gmail=None):
    ingested = []
    email_results = []
    errors = []
    if gmail is not None:
        try:
            for message_id, body in gmail.messages():
                run = flow.ingest(message_id, body)
                ingested.append(run['id'])
                email_results.append({'message_id': message_id, 'run_id': run['id'],
                                      'intake_result': 'existing_opportunity' if run['message_id'] != message_id else 'received',
                                      'state': run['state']})
        except Exception:
            # Intake/provider failure must not starve already accepted runs.
            errors.append('Gmail intake failed; check credentials, message shape, and provider availability')
            with flow.store.transaction():
                flow.store.event({'id': 'worker'}, 'intake_error', errors[-1])
    ids = [row['id'] for row in flow.store.db.execute(
        "SELECT id FROM runs WHERE state NOT IN ('complete','rejected','escalated','reconcile','customer_invite_manual')"
    )]
    results = []
    for run_id in ids:
        try:
            results.append(flow.run(run_id))
        except Exception:
            # A failed node leaves its durable intent for reconciliation next cycle.
            # Do not expose provider response bodies or block other customer runs.
            with flow.store.transaction():
                flow.store.event({'id': run_id}, 'worker_error',
                                 'Unexpected graph node error; inspect run; pending writes reconcile next cycle')
            results.append({'id': run_id, 'state': 'worker_error'})
    mode = ('real_gmail_and_slack_simulated_voice_project' if getattr(flow.services,'real_slack',False)
            else 'real_gmail_simulated_downstream' if gmail is not None and getattr(flow.services, 'simulated', False)
            else 'live' if gmail is not None else 'demo')
    flow.store.heartbeat(mode, errors)
    return {'ingested': ingested, 'email_results': email_results, 'runs': results, 'errors': errors}


def serve(flow, gmail=None, interval=15, once=False, emit=print):
    if not 1 <= interval <= 60:
        raise ValueError('Worker interval must be between 1 and 60 seconds')
    with single_worker(flow.store.path):
        while True:
            emit(cycle(flow, gmail))
            if once:
                return
            time.sleep(interval)
