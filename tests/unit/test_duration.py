import pytest

from auto_broll.core.duration import frames_duration, retime_speed_percent, split_half_open_segments


def test_frames_duration_uses_end_exclusive_contract():
    assert frames_duration(100, 160) == 60
    assert frames_duration(0, 1) == 1


@pytest.mark.parametrize(("start", "end"), [(10, 10), (11, 10), (-1, 10), (0, -1)])
def test_frames_duration_rejects_invalid_frame_ranges(start, end):
    with pytest.raises(ValueError):
        frames_duration(start, end)


@pytest.mark.parametrize(
    ("start", "duration", "count", "expected"),
    [
        (100, 202, 2, [(100, 201), (201, 302)]),
        (100, 203, 2, [(100, 202), (202, 303)]),
        (0, 100, 3, [(0, 34), (34, 67), (67, 100)]),
    ],
)
def test_split_half_open_segments_cover_range_without_gaps(start, duration, count, expected):
    segments = split_half_open_segments(start, duration, count)

    assert segments == expected
    assert sum(end - start for start, end in segments) == duration
    assert [segments[index][1] for index in range(len(segments) - 1)] == [
        segments[index][0] for index in range(1, len(segments))
    ]


@pytest.mark.parametrize(("duration", "count"), [(0, 1), (10, 0), (-1, 2)])
def test_split_half_open_segments_rejects_invalid_inputs(duration, count):
    with pytest.raises(ValueError):
        split_half_open_segments(0, duration, count)


def test_retime_speed_percent_uses_source_over_target():
    assert retime_speed_percent(195, 202) == pytest.approx(96.534653, rel=1e-6)
    assert retime_speed_percent(100, 200) == pytest.approx(50.0)
    assert retime_speed_percent(200, 100) is None
