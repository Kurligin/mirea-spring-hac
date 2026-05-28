from sqlalchemy import text


async def test_db_engine_pings(db):
    result = await db.execute(text("SELECT 1"))
    assert result.scalar() == 1
