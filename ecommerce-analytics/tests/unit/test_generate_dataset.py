from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "python" / "ingest"))
import generate_dataset


def test_dataset_window_ends_today_and_spans_two_years():
    """The generator should produce a rolling two-year window ending today."""
    assert generate_dataset.END_DATE.date() == datetime.now().date()
    assert (generate_dataset.END_DATE - generate_dataset.START_DATE).days >= 730
