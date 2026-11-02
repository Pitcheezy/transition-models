"""Verify exact source allowlisting and extraction from observed page content."""

import pytest

from src.data.mlb_sources import media_urls, validate_mlb_url


@pytest.mark.parametrize(
    "url",
    [
        "http://mlb.com/video",
        "https://mlb.com.attacker.test/a.mp4",
        "https://attacker.test/mlb.com/a.mp4",
        "file:///video.mp4",
        "https://user:pass@mlb.com/a.mp4",
        "https://mlb.com:8080/a",
    ],
)
def test_non_mlb_sources_rejected(url):
    with pytest.raises(ValueError):
        validate_mlb_url(url)


def test_media_extraction_is_deduplicated_and_ignores_unrelated_hosts():
    page = '<source src="https://sporty-clips.mlb.com/a.mp4">' * 2
    page += '<source src="https://other.test/evil.mp4">'
    assert media_urls(page) == ["https://sporty-clips.mlb.com/a.mp4"]


def test_single_quoted_attribute_does_not_leak_into_the_url():
    page = "<video src='https://sporty-clips.mlb.com/a.mp4?t=1'></video>"
    assert media_urls(page) == ["https://sporty-clips.mlb.com/a.mp4?t=1"]


def test_an_html_encoded_apostrophe_in_the_path_is_kept():
    page = '<source src="https://sporty-clips.mlb.com/o&#39;neil.mp4">'
    assert media_urls(page) == ["https://sporty-clips.mlb.com/o'neil.mp4"]


def test_single_quoted_js_literals_are_not_merged_into_one_url():
    clip = "https://sporty-clips.mlb.com/abc.mp4"
    page = f"<script>var m={{poster:'https://img.mlb.com/p.jpg',src:'{clip}',type:'video/mp4'}};</script>"
    assert media_urls(page) == [clip]
    other_host = page.replace("img.mlb.com", "img.mlbstatic.net")
    assert media_urls(other_host) == [clip]


def test_no_invented_media_url():
    assert media_urls('<video src="blob:1234">') == []
