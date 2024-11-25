# Uta-Net Lyrics Tagger

Downloads and writes lyrics for your audio files from www.uta-net.com

- (Add it to your path and) run it in the directory with your music
- Enjoy!

```
$ uta-net.py -h
usage: uta-net.py [-h] [-d DIRECTORY] [-u URL] [--per-file] [--by-title]

Add lyrics from uta-net.com to audio files.

options:
  -h, --help            show this help message and exit
  -d DIRECTORY, --directory DIRECTORY
                        Directory containing audio files (default: current directory)
  -u URL, --url URL     uta-net.com artist page URL (default: auto-detect)
  --per-file            Search for artist URL for each file individually
  --by-title            Try to find lyrics by title search for failed files
```

```
Using current directory: ...
Detected artist: 井上あずみ
Found artist: 井上あずみ (歌詞：71)
Artist URL: https://www.uta-net.com/artist/1864/
Found substring match: '風の谷のナウシカ(風の谷のナウシカ)' contains '風の谷のナウシカ'
Writing lyrics to '08 風の谷のナウシカ(風の谷のナウシカ).m4a'
--------------------
金色の花びら散らして
振り向けば　まばゆい草原
雲間から光が射せば
身体ごと宙に浮かぶの

やさしさは見えない翼ね
遠くからあなたが呼んでる
愛しあう人は誰でも
飛び方を知ってるものよ

風の谷のナウシカ　髪を軽くなびかせ
風の谷のナウシカ　眠る樹海を飛び超え
青空から舞い降りたら
やさしくつかまえて

花や木や小鳥の言葉を
あなたにも教えてあげたい
何故人は傷つけあうの
しあわせに小石を投げて

風の谷のナウシカ　白い霧が晴れたら
風の谷のナウシカ　手と手固く握って
大地けって翔び立つのよ
はるかな地平線

風の谷のナウシカ　眠る樹海を飛び超え
青空から舞い降りたら
やさしく抱きしめて
--------------------
Lyrics added to 08 風の谷のナウシカ(風の谷のナウシカ).m4a
Found substring match: 'いつも何度でも(千と千尋の神隠し)' contains 'いつも何度でも'
Writing lyrics to '09 いつも何度でも(千と千尋の神隠し).m4a'

...

Lyrics added to 10 さんぽ(となりのトトロ).m4a

All 14 files processed successfully!

```
