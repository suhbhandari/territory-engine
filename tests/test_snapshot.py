import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("snapshot", Path(__file__).parent.parent / "scripts" / "snapshot.py")
snapshot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(snapshot)


def setup(tmp_path, monkeypatch):
    raw = tmp_path / "outputs" / "raw"
    raw.mkdir(parents=True)
    (raw / "signals_raw.csv").write_text("entity_id,signals_fetched_at\n1,2026-10-09T01:00:00\n")
    (raw / "accounts_raw.csv").write_text("entity_id\n1\n")
    monkeypatch.setattr(snapshot, "ROOT", tmp_path)
    monkeypatch.setattr(snapshot, "RAW", raw)
    return raw


def test_copies_then_moves_signals_only_when_the_copy_is_identical(tmp_path, monkeypatch):
    raw = setup(tmp_path, monkeypatch)
    assert snapshot.default_label() == "2026-10-09"
    assert snapshot.main("2026-10-09", fresh_signals=True) == 0
    kept = raw / "runs" / "2026-10-09"
    assert (kept / "signals_raw.csv").exists() and (kept / "accounts_raw.csv").exists()
    assert not (raw / "signals_raw.csv").exists()
    assert (raw / "accounts_raw.csv").exists()


def test_refuses_to_overwrite_a_different_snapshot(tmp_path, monkeypatch):
    raw = setup(tmp_path, monkeypatch)
    snapshot.main("x", fresh_signals=False)
    (raw / "accounts_raw.csv").write_text("entity_id\n2\n")
    assert snapshot.main("x", fresh_signals=True) == 1
    assert (raw / "signals_raw.csv").exists()  # nothing moved
