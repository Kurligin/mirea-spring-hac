from app.bot.catalog_filter import CatalogFilter, DEFAULT_TOKEN
from app.models.event import EventFormat, EventType


def test_default_filter_encodes_to_dashes():
    f = CatalogFilter()
    assert f.encode() == DEFAULT_TOKEN
    assert f.is_default


def test_encode_decode_round_trip_full():
    f = CatalogFilter(
        category=EventType.MASTER_CLASS, date="week", format=EventFormat.OFFLINE
    )
    assert f.encode() == "mwf"
    f2 = CatalogFilter.decode("mwf")
    assert f2 == f


def test_decode_garbage_yields_default():
    assert CatalogFilter.decode("zzz") == CatalogFilter()
    assert CatalogFilter.decode("too long") == CatalogFilter()
    assert CatalogFilter.decode("") == CatalogFilter()
    assert CatalogFilter.decode(None) == CatalogFilter()  # type: ignore[arg-type]


def test_decode_partial_keeps_known_chars():
    f = CatalogFilter.decode("mz-")  # category=m valid, date=z bad→all, format=- all
    assert f.category == EventType.MASTER_CLASS
    assert f.date == "all"
    assert f.format is None


def test_with_methods_replace_one_dimension():
    f = CatalogFilter(category=EventType.MASTER_CLASS, date="week", format=None)
    assert f.with_category(None).category is None
    assert f.with_date("today").date == "today"
    assert f.with_format(EventFormat.ONLINE).format == EventFormat.ONLINE


def test_summary_ru_omits_default_dims():
    assert CatalogFilter().summary_ru() == ""
    assert CatalogFilter(category=EventType.OPEN_DAY).summary_ru() == "День открытых дверей"
    f = CatalogFilter(category=EventType.MASTER_CLASS, date="week", format=EventFormat.OFFLINE)
    assert f.summary_ru() == "Мастер-класс · На этой неделе · Очно"
