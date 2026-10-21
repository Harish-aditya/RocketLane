"""All scenarios are simulated; this script never places calls."""
from pathlib import Path
from app.store import Store
from app.services import DemoServices
from app.workflow import Workflow


def main():
    body = Path('examples/deal.txt').read_text()
    for label, answer, email in [
        ('Enterprise', 'Enterprise', body), ('Growth', 'Growth', body),
        ('Missing field', 'Enterprise', body.replace('Customer Name: Acme Labs', '')),
        ('No answer', 'unresolved', body), ('Ambiguous', 'probably Enterprise', body),
    ]:
        services = DemoServices(answer)
        store = Store(':memory:')
        flow = Workflow(store, services)
        run = flow.ingest(label, email)
        for _ in range(12):
            run = flow.step(run['id'])
        print(f'{label:16} -> {run["state"]:10} calls={services.calls} projects={services.projects} channels={services.channels}')


if __name__ == '__main__':
    main()
