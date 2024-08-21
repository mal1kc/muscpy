# pyright: basic
from pprint import pprint
from typing import Any
from yt_dlp import YoutubeDL


common_ytdl_options = {
    "format": "bestaudio/best",
    "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "geo_bypass": True,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": False,
    "no_warnings": True,
    "source_address": "0.0.0.0",
    "default_search": "https://music.youtube.com/search?q=",
}

ytdl_search_options = {
    "noplaylist": True,
    "playlist_items": "1-5",
    "default_search": "https://music.youtube.com/search?q=",
    "extract_flat": True,
    "flat_playlist": True,
    **common_ytdl_options,
}


ytdl_glbl_format_options = {
    "noplaylist": False,
    "playlist_items": "1-100",
    "default_search": "auto",
    "extract_flat": True,
    "flat_playlist": True,
    **common_ytdl_options,
}


ytldl_single_url_options = {"noplaylist": True, **common_ytdl_options}


def save_data_to_json(data: Any, filename: str):
    import json

    with open(filename, "w") as f:
        json.dump(data, f, indent=4)


def search_extract():
    with YoutubeDL(ytdl_search_options) as ydl:
        result = ydl.extract_info("ytsearch5:the boys finale ost", download=False)
        return result


def extract_info_glbl_options(url: str) -> dict[str, Any] | None:
    with YoutubeDL(ytdl_glbl_format_options) as ydl:
        result = ydl.extract_info(url, download=False)
        return result


# track data with playlist
def pl_extract():
    url = "https://music.youtube.com/playlist?list=OLAK5uy_noi_byHFvSNxfA3GziKw2xKIIc9_EYtoE"
    return extract_info_glbl_options(url)


def pl_item_extract():
    url = "https://music.youtube.com/watch?v=g7RGN7MJR1s&list=OLAK5uy_noi_byHFvSNxfA3GziKw2xKIIc9_EYtoE"
    return extract_info_glbl_options(url)


def item_extract():
    url = "https://www.youtube.com/watch?v=5jKkLjh6K0Y"
    return extract_info_glbl_options(url)


if __name__ == "__main__":
    test_data_result = pl_extract()
    save_data_to_json(test_data_result, "./temp/pl_result.json")
    pprint(test_data_result)

    test_data_result = search_extract()

    save_data_to_json(test_data_result, "./temp/search_result.json")
    pprint(test_data_result)

    test_data_result = pl_item_extract()
    save_data_to_json(test_data_result, "./temp/pl_item_result.json")
    pprint(test_data_result)

    test_data_result = item_extract()
    save_data_to_json(test_data_result, "./temp/item_result.json")
    pprint(test_data_result)
