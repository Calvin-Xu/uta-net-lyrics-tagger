#!/usr/bin/env python3

import os
import re
import sys
from typing import Dict, List, Optional
import requests
from bs4 import BeautifulSoup
import mutagen
from mutagen.id3 import ID3, USLT, ID3NoHeaderError
import difflib
import unicodedata


class LyricsTagger:
    def __init__(self):
        self.directory: str = self.get_directory_path()
        self.audio_files: List[str] = self.get_audio_files()
        self.artist_url: str = self.get_artist_url()
        self.song_entries: Dict[str, str] = self.collect_song_entries()

    def get_directory_path(self) -> str:
        """Prompt the user for a directory path or use current directory."""
        directory = input(
            "Please enter the directory path (press Enter for current directory): "
        ).strip()

        # If no input, use current working directory
        if not directory:
            directory = os.getcwd()
            print(f"Using current directory: {directory}")

        if not os.path.isdir(directory):
            print("The provided path is not a valid directory.")
            sys.exit(1)

        return directory

    def get_audio_files(self) -> List[str]:
        """Get the list of audio files in the directory."""
        audio_extensions = (".mp3", ".flac", ".m4a", ".ogg", ".aac")
        audio_files = [
            f
            for f in os.listdir(self.directory)
            if f.lower().endswith(audio_extensions)
        ]
        if not audio_files:
            print("No audio files found in directory.")
            sys.exit(1)
        return audio_files

    def get_artist_url(self) -> str:
        """Get uta-net artist page URL from user input or auto-detect from audio files."""
        url = input(
            "Please enter the uta-net.com artist page URL (skip for auto-detect): "
        ).strip()

        # If URL is provided and valid, use it
        if url and re.match(r"https?://www\.uta-net\.com/artist/\d+/?", url):
            return url

        # If no valid URL provided, try to auto-detect artist
        if not self.audio_files:
            print("No audio files found in directory.")
            sys.exit(1)

        # Get artist from first audio file
        file_path = os.path.join(self.directory, self.audio_files[0])
        audio = mutagen.File(file_path, easy=True)
        if not audio or not audio.get("artist"):
            print(f"Could not read artist from {self.audio_files[0]}")
            sys.exit(1)

        artist_name = str(audio["artist"][0])
        print(f"Detected artist: {artist_name}")

        # Search for artist on uta-net
        search_url = "https://www.uta-net.com/search/"
        params = {"target": "art", "type": "in", "keyword": artist_name}

        try:
            response = requests.get(search_url, params=params)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            # Find first artist result
            artist_row = soup.select_one("tbody.songlist-table-body tr")
            if not artist_row:
                print(f"No results found for artist: {artist_name}")
                sys.exit(1)

            artist_link = artist_row.select_one("a")
            if not artist_link:
                print(f"Could not find artist link for: {artist_name}")
                sys.exit(1)

            artist_url = f"https://www.uta-net.com{artist_link['href']}"
            artist_name_found = artist_link.select_one("span.fw-bold").text.strip()
            song_count = artist_link.select_one("span.song-count").text.strip()

            print(f"Found artist: {artist_name_found} ({song_count})")
            print(f"Artist URL: {artist_url}")

            return artist_url

        except Exception as e:
            print(f"Error searching for artist: {str(e)}")
            sys.exit(1)

    def get_total_pages(self, soup: BeautifulSoup) -> int:
        """Extract the total number of pages from the artist page."""
        page_info = soup.find(
            "div", class_="col-7 col-lg-3 text-start text-lg-end d-none d-lg-block"
        )
        if page_info:
            match = re.search(r"全(\d+)ページ中", page_info.text)
            if match:
                return int(match.group(1))
        return 1

    def collect_song_entries(self) -> Dict[str, str]:
        """Collect song titles and their corresponding URLs from the artist's page."""
        song_entries = {}
        response = requests.get(self.artist_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        total_pages = self.get_total_pages(soup)

        for page_num in range(1, total_pages + 1):
            if page_num > 1:
                page_url = f"{self.artist_url.rstrip('/')}/0/{page_num}/"
                response = requests.get(page_url)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, "html.parser")

            rows = soup.select("tbody.songlist-table-body tr")
            for row in rows:
                title_span = row.select_one("td.sp-w-100 a span.songlist-title")
                a_tag = row.select_one("td.sp-w-100 a")

                if not title_span or not a_tag:
                    continue

                song_title = title_span.get_text(strip=True)
                song_link = a_tag["href"]
                full_song_url = f"https://www.uta-net.com{song_link}"
                song_entries[song_title] = full_song_url

        if not song_entries:
            print("No songs found for the given artist.")
            sys.exit(1)

        return song_entries

    def clean_title(self, title: str) -> str:
        """Clean title by removing emojis, symbols, and punctuation"""
        # Normalize unicode (e.g., full-width to half-width for Latin chars and numbers)
        title = unicodedata.normalize("NFKC", title)

        cleaned = ""
        for char in title:
            if unicodedata.category(char).startswith(("So", "Sm", "Sk", "Sc", "P")):
                continue
            cleaned += char

        return cleaned.lower().strip()

    def match_song_title(
        self, file_title: str, song_titles: List[str]
    ) -> Optional[str]:
        """Match the audio file's title with the collected song titles using fuzzy matching."""
        SIMILARITY_THRESHOLD = 0.8  # Adjust this value between 0 and 1

        cleaned_file_title = self.clean_title(file_title)
        best_match = None
        highest_ratio = 0
        substring_match = None

        for song_title in song_titles:
            cleaned_song_title = self.clean_title(song_title)

            # Calculate similarity ratio
            ratio = difflib.SequenceMatcher(
                None, cleaned_file_title, cleaned_song_title
            ).ratio()

            if ratio > highest_ratio and ratio >= SIMILARITY_THRESHOLD:
                highest_ratio = ratio
                best_match = song_title

            # Check for substring match if we haven't found a good match yet
            if not best_match and cleaned_song_title in cleaned_file_title:
                # If we find multiple substring matches, use the longest one
                if not substring_match or len(cleaned_song_title) > len(
                    self.clean_title(substring_match)
                ):
                    substring_match = song_title

        # Use substring match if no better match was found
        if not best_match and substring_match:
            best_match = substring_match
            print(f"Found substring match: '{file_title}' contains '{best_match}'")
        elif best_match:
            print(
                f"Matched '{file_title}' to '{best_match}' (similarity: {highest_ratio:.2f})"
            )

        return best_match

    def fetch_lyrics(self, song_url: str) -> str:
        """Fetch the lyrics from the song's page, handling <br> tags correctly."""
        response = requests.get(song_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        lyrics_div = soup.find("div", id="kashi_area")
        if lyrics_div:
            # Replace <br> tags with newlines
            for br in lyrics_div.find_all("br"):
                br.replace_with("\n")
            lyrics = lyrics_div.get_text()
            # Replace multiple consecutive newlines with two newlines
            lyrics = re.sub(r"\n{2,}", "\n\n", lyrics)
            lyrics = lyrics.strip()
            return lyrics
        return ""

    def write_lyrics_to_file(self, file_path: str, lyrics: str) -> None:
        """Write the lyrics to the audio file's lyrics tag."""
        file_ext = os.path.splitext(file_path)[1].lower()

        try:
            if file_ext == ".mp3":
                try:
                    tags = ID3(file_path)
                except ID3NoHeaderError:
                    tags = ID3()
                    tags.save(file_path)
                # Remove existing USLT frames to avoid duplication
                tags.delall("USLT")
                ulyrics = USLT(
                    encoding=3, lang="jpn", desc="Unsynced lyrics", text=lyrics
                )
                tags.add(ulyrics)
                tags.save(file_path)
            else:
                # Handle M4A, ALAC, AAC (MP4 containers)
                from mutagen.mp4 import MP4

                audio = MP4(file_path)
                audio["\xa9lyr"] = lyrics
                audio.save(file_path)

            print(f"Lyrics added to {os.path.basename(file_path)}")
        except Exception as e:
            print(f"Error adding lyrics to {os.path.basename(file_path)}: {str(e)}")

    def process_audio_files(self) -> None:
        """Process each audio file in the directory to add lyrics."""
        failed_files = []

        for filename in self.audio_files:
            file_path = os.path.join(self.directory, filename)
            audio = mutagen.File(file_path, easy=True)
            if not audio:
                print(f"Could not open {filename}. Skipping.")
                failed_files.append((filename, "Could not open file"))
                continue

            title = audio.get("title")
            if not title:
                print(f"No title found for {filename}. Skipping.")
                failed_files.append((filename, "No title found"))
                continue

            file_title = str(title[0])
            matched_title = self.match_song_title(
                file_title, list(self.song_entries.keys())
            )

            if not matched_title:
                print(f"No matching song found for '{file_title}'.")
                failed_files.append(
                    (filename, f"No matching song found for '{file_title}'")
                )
                continue

            song_url = self.song_entries[matched_title]
            lyrics = self.fetch_lyrics(song_url)

            if not lyrics:
                print(f"No lyrics found for '{matched_title}'.")
                failed_files.append(
                    (filename, f"No lyrics found for '{matched_title}'")
                )
                continue

            print(f"Writing lyrics to '{filename}'")
            print("-" * 10)
            print(lyrics)
            print("-" * 10)

            try:
                self.write_lyrics_to_file(file_path, lyrics)
            except Exception as e:
                failed_files.append((filename, f"Error writing lyrics: {str(e)}"))

        # Print summary at the end
        if failed_files:
            print("\nSummary of files that failed:")
            print("-" * 50)
            for filename, reason in failed_files:
                print(f"• {filename}: {reason}")
            print(
                f"\nTotal: {len(failed_files)} file(s) failed out of {len(self.audio_files)}"
            )
        else:
            print("\nAll files processed successfully!")


def main() -> None:
    tagger = LyricsTagger()
    tagger.process_audio_files()


if __name__ == "__main__":
    main()
