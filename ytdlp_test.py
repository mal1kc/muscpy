from yt_dlp import YoutubeDL

ytdl_test_format_options = {
    # "format": "bestaudio/best",
    # "outtmpl": "%(extractor)s-%(id)s-%(title)s.%(ext)s",
    # "restrictfilenames": True,
    "noplaylist": False,
    "nocheckcertificate": True,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": False, # probably should be True but I want to see errors
    # add plist item limit up to 100
    "playlist_items": "1-100",
    "no_warnings": True,
    "default_search": "auto",
    "source_address": "0.0.0.0",
    "extract_flat": True,
    "flat_playlist": True,
}

ytdlp_client = YoutubeDL(ytdl_test_format_options)

def ytdlp_test(url):
    with ytdlp_client:
        result = ytdlp_client.extract_info(url, download=False)
        return result
    

def save_data_to_json(data, filename):
    import json
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

if __name__ == "__main__":
    url = "https://music.youtube.com/watch?v=2DOVyJGK5PA&list=RDAMVM8L__O1hElCE"
    data = ytdlp_test(url)
    save_data_to_json(data, "data.json")