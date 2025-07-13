import yt_dlp

def download_video(url, output_template="%(title)s.%(ext)s", progress_hook=None):
    ydl_opts = {
        'outtmpl': output_template,
        'format': 'bestvideo+bestaudio/best',
        'merge_output_format': 'mp4',
        'concurrent_fragment_downloads': 10,
        'progress_hooks': [progress_hook] if progress_hook else [],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
