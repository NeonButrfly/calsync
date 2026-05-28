from sqlalchemy import create_engine, inspect

from calsync.models import Base


def test_metadata_exposes_expected_tables() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    tables = set(inspect(engine).get_table_names())

    assert "apple_calendar_connections" in tables
    assert "appointments" in tables
    assert "appointment_external_links" in tables
    assert "audit_entries" in tables
