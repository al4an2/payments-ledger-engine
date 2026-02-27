from payments_ledger.db.session import get_session_factory
from payments_ledger.adapters.db.uow import SqlAlchemyUnitOfWork
from payments_ledger.api.auth import get_client_id_auth


def get_uow():
    return SqlAlchemyUnitOfWork(get_session_factory())


get_client_id = get_client_id_auth
