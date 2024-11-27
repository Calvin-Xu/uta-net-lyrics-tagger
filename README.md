# Uta-Net Lyrics Tagger

Downloads and writes lyrics for your audio files from www.uta-net.com

- (Add it to your path and) run it in the directory with your music
- Enjoy!

```
$ uta-net.py -h
usage: uta-net.py [-h] [-d DIRECTORY] [-u URL] [--per-file] [--no-title-search]

Add lyrics from uta-net.com to audio files.

options:
  -h, --help            show this help message and exit
  -d DIRECTORY, --directory DIRECTORY
                        Directory containing audio files (default: current directory)
  -u URL, --url URL     uta-net.com artist page URL (default: auto-detect)
  --per-file            Search for artist URL for each file individually
  --no-title-search     Disable searching by title for failed files
```

```
Using current directory: [...]
Detected artist: 下川みくに
Best artist match (similarity: 1.00): 下川みくに
Found artist: 下川みくに (歌詞：110)
Artist URL: https://www.uta-net.com/artist/1966/
Matched '水の星へ愛をこめて' to '水の星に愛をこめて' (similarity: 0.89)
Writing lyrics to '1-01 下川みくに - 水の星へ愛をこめて.m4a'
--------------------
蒼く眠る水の星にそっと
口づけして生命(いのち)の火を灯(とも)すひとよ
時間(とき)という金色のさざ波は
宇宙(あおぞら)の唇に生まれた吐息ね
[...]
--------------------
Lyrics added to 1-01 下川みくに - 水の星へ愛をこめて.m4a
Matched 'all the way' to 'all the way' (similarity: 1.00)
Writing lyrics to '2-04 下川みくに - all the way.m4a'
[...]
No matching song found for '輪舞－revolution－'.
[...]
Attempting to find lyrics by title search for failed files...

Searching for '輪舞－revolution－' by '下川みくに feat. 浦嶋りんこ'...
Initial search failed, trying with kanji substring: 輪舞
Best match: '輪舞～revolution～ Feat.浦嶋りんこ' by '下川みくに' (similarity: 0.55)
--------------------
潔く　カッコ良く　生きて行こう…
たとえ2人離ればなれになっても…
Take my revolution
[...]
--------------------
Lyrics added to 1-07 下川みくに feat. 浦嶋りんこ - 輪舞－revolution－.m4a
Successfully added lyrics to 1-07 下川みくに feat. 浦嶋りんこ - 輪舞－revolution－.m4a via title search

All 22 files processed successfully!
```
