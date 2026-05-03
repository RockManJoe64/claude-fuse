import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))

import tempfile
import os

from common import read_new_jsonl


def test_read_new_jsonl_reads_all_from_zero():
    """Reading from offset 0 returns all records and final offset."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        f.write(json.dumps({"id": 1}) + "\n")
        f.write(json.dumps({"id": 2}) + "\n")
        path = f.name

    try:
        records, new_offset = read_new_jsonl(path, offset=0)
        assert len(records) == 2
        assert records[0]["id"] == 1
        assert records[1]["id"] == 2
        assert new_offset > 0
    finally:
        os.unlink(path)


def test_read_new_jsonl_reads_incrementally():
    """Reading from mid-file offset returns only new records."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        f.write(json.dumps({"id": 1}) + "\n")
        f.write(json.dumps({"id": 2}) + "\n")
        path = f.name

    try:
        # First read all to get offset
        records, offset = read_new_jsonl(path, offset=0)
        assert len(records) == 2

        # Append more data
        with open(path, 'a') as f:
            f.write(json.dumps({"id": 3}) + "\n")

        # Read from offset
        records, new_offset = read_new_jsonl(path, offset=offset)
        assert len(records) == 1
        assert records[0]["id"] == 3
        assert new_offset > offset
    finally:
        os.unlink(path)


def test_read_new_jsonl_empty_file():
    """Empty file returns empty records and offset 0."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        path = f.name

    try:
        records, offset = read_new_jsonl(path, offset=0)
        assert records == []
        assert offset == 0
    finally:
        os.unlink(path)


def test_read_new_jsonl_skips_invalid_json():
    """Invalid JSON lines are skipped gracefully."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False) as f:
        f.write(json.dumps({"id": 1}) + "\n")
        f.write("not json\n")
        f.write(json.dumps({"id": 2}) + "\n")
        path = f.name

    try:
        records, offset = read_new_jsonl(path, offset=0)
        assert len(records) == 2
        assert records[0]["id"] == 1
        assert records[1]["id"] == 2
    finally:
        os.unlink(path)
