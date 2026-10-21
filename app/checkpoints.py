"""Mirror every committed LangGraph checkpoint into the dashboard event ledger."""
from langgraph.checkpoint.sqlite import SqliteSaver


class LoggedSqliteSaver(SqliteSaver):
    def __init__(self, connection, store):
        super().__init__(connection)
        self.store = store

    def put(self, config, checkpoint, metadata, new_versions):
        result = super().put(config, checkpoint, metadata, new_versions)
        self.store.record_checkpoint(config, checkpoint, metadata)
        return result
