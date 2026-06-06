from auto_broll.core.filename_parser import DEFAULT_PATTERN
from auto_broll.core.indexer import build_index


def test_build_index_groups_recursive_files_by_normalized_shot_id(tmp_path):
    root = tmp_path / "broll"
    nested = root / "nested"
    nested.mkdir(parents=True)
    first = root / "C001.mov"
    second = nested / "20260605_C001_take2.mp4"
    third = nested / "C002.mov"
    ignored = nested / "CARD_0007.mov"
    for path in [first, second, third, ignored]:
        path.write_text("fixture")

    index = build_index([str(root)], DEFAULT_PATTERN, pad_width=3)

    assert [candidate.path for candidate in index["1"]] == sorted([str(first), str(second)])
    assert index["1"][0].shot_id == "1"
    assert index["1"][0].shot_id_raw == "001"
    assert index["1"][0].shot_id_canonical == "1"
    assert index["1"][0].filename == "C001.mov"
    assert [candidate.path for candidate in index["2"]] == [str(third)]
    assert "7" not in index


def test_build_index_accepts_direct_file_paths_and_ignores_unmatched_names(tmp_path):
    matched = tmp_path / "C003.mov"
    ignored = tmp_path / "CAM2_take1.mov"
    matched.write_text("fixture")
    ignored.write_text("fixture")

    index = build_index([str(matched), str(ignored)], DEFAULT_PATTERN, pad_width=3)

    assert list(index) == ["3"]
    assert index["3"][0].path == str(matched)


def test_build_index_groups_c888_and_c0888_under_same_canonical_id(tmp_path):
    first = tmp_path / "C888.MP4"
    second = tmp_path / "20260101_C0888.mov"
    for path in [first, second]:
        path.write_text("fixture")

    index = build_index([str(first), str(second)], DEFAULT_PATTERN, pad_width=3)

    assert [candidate.path for candidate in index["888"]] == sorted([str(first), str(second)])
