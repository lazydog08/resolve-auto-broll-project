import pytest

from auto_broll.core.override import parse_override_csv


def test_parse_override_csv_normalizes_shot_ids(tmp_path):
    override_file = tmp_path / "overrides.csv"
    override_file.write_text(
        "shot_id,path\n"
        "C1,/broll/manual/C001.mov\n"
        "镜头002,/broll/manual/C002.mov\n",
        encoding="utf-8",
    )

    assert parse_override_csv(str(override_file), pad_width=3) == {
        "1": "/broll/manual/C001.mov",
        "2": "/broll/manual/C002.mov",
    }


@pytest.mark.parametrize(
    "contents",
    [
        "shot_id\nC001\n",
        "shot_id,path\n,/broll/C001.mov\n",
        "shot_id,path\nshot abc,/broll/C001.mov\n",
        "shot_id,path\nC001,\n",
        "shot_id,path\nC001,/broll/C001.mov,extra\n",
    ],
)
def test_parse_override_csv_rejects_malformed_rows(tmp_path, contents):
    override_file = tmp_path / "bad_overrides.csv"
    override_file.write_text(contents, encoding="utf-8")

    with pytest.raises(ValueError):
        parse_override_csv(str(override_file), pad_width=3)
