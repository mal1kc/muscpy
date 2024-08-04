from pprint import pprint
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
}
# ytdl_test_format_options = {
#     # "format": "bestaudio/best",
#     # "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
#     # "restrictfilenames": True,
#     "noplaylist": False,
#     "nocheckcertificate": True,
#     "ignoreerrors": False,
#     "logtostderr": False,
#     "quiet": False, # probably should be True but I want to see errors
#     # add plist item limit up to 100
#     "playlist_items": "1-100",
#     "no_warnings": True,
#     "default_search": "auto",
#     "source_address": "0.0.0.0",
#     "extract_flat": True,
#     "flat_playlist": True,
# }

# ytdlp_client = YoutubeDL(ytdl_test_format_options)

# def ytdlp_test(url):
#     with ytdlp_client:
#         result = ytdlp_client.extract_info(url, download=False)
#         return result
    

# def save_data_to_json(data, filename):
#     import json
#     with open(filename, 'w') as f:
#         json.dump(data, f, indent=4)

# if __name__ == "__main__":
#     url = "https://music.youtube.com/watch?v=2DOVyJGK5PA&list=RDAMVM8L__O1hElCE"
#     data = ytdlp_test(url)
#     save_data_to_json(data, "data.json")


def search_test():
    
    ytdl_search_options = {
        "noplaylist": True,
        "playlist_items": "1-5",
        "default_search": "https://music.youtube.com/search?q=",
        "extract_flat": True,
        "flat_playlist": True,
        **common_ytdl_options
    }

    with YoutubeDL(ytdl_search_options) as ydl:
        result = ydl.extract_info("ytsearch5:the boys finale ost", download=False)
        return result
    

if __name__ == "__main__":
    pprint(search_test())

