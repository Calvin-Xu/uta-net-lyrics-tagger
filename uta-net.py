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
import argparse
from urllib.parse import quote

try:
    import argcomplete

    ARGCOMPLETE_AVAILABLE = True
except ImportError:
    ARGCOMPLETE_AVAILABLE = False


class LyricsTagger:
    def __init__(
        self,
        directory: Optional[str] = None,
        artist_url: Optional[str] = None,
        per_file_search: bool = False,
        single_file: Optional[str] = None,
    ):
        self.directory: str = self.get_directory_path(directory)
        self.single_file: Optional[str] = single_file
        self.audio_files: List[str] = self.get_audio_files()
        self.per_file_search = per_file_search
        self.artist_url: Optional[str] = (
            None if per_file_search else self.get_artist_url(artist_url)
        )
        self.song_entries: Dict[str, str] = (
            {}
            if per_file_search or self.artist_url is None
            else self.collect_song_entries()
        )

    def get_directory_path(self, directory: Optional[str] = None) -> str:
        """Get directory path from argument or use current directory."""
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

        if self.single_file:
            if not os.path.isfile(os.path.join(self.directory, self.single_file)):
                print(f"The specified file '{self.single_file}' does not exist.")
                sys.exit(1)
            if not self.single_file.lower().endswith(audio_extensions):
                print(
                    f"The specified file '{self.single_file}' is not a supported audio file."
                )
                sys.exit(1)
            return [self.single_file]

        audio_files = sorted(
            [
                f
                for f in os.listdir(self.directory)
                if f.lower().endswith(audio_extensions)
            ]
        )
        if not audio_files:
            print("No audio files found in directory.")
            sys.exit(1)
        return audio_files

    @staticmethod
    def find_best_match(
        search_term: str, candidates: List[str], threshold: float = 0.8
    ) -> Optional[tuple[str, float]]:
        """Find the best matching string from a list of candidates using fuzzy matching.

        Args:
            search_term: The string to search for
            candidates: List of strings to search through
            threshold: Minimum similarity ratio to consider a match (0-1)

        Returns:
            Tuple of (best matching string, similarity ratio) or None if no match found
        """
        best_match = None
        highest_ratio = 0
        substring_match = None

        for candidate in candidates:
            # Calculate similarity ratio
            ratio = difflib.SequenceMatcher(None, search_term, candidate).ratio()

            if ratio > highest_ratio and ratio >= threshold:
                highest_ratio = ratio
                best_match = candidate

            # Check for substring match if we haven't found a good match yet
            if not best_match and candidate in search_term:
                # If we find multiple substring matches, use the longest one
                if not substring_match or len(candidate) > len(substring_match):
                    substring_match = candidate

        # Use substring match if no better match was found
        if not best_match and substring_match:
            substring_ratio = difflib.SequenceMatcher(
                None, search_term, substring_match
            ).ratio()
            return substring_match, substring_ratio
        elif best_match:
            return best_match, highest_ratio

        return None

    def search_artist_url(self, artist_name: str) -> Optional[tuple[str, str, str]]:
        """Search for an artist on uta-net and return their URL and details."""
        # Get potential search terms
        search_terms = self.extract_search_terms(artist_name)

        best_match = None
        highest_ratio = 0

        # Try each search term until we find a confident match
        for search_term in search_terms:
            print(f"Trying artist search term: '{search_term}'")

            entries = self.get_artist_search_results(search_term)
            if not entries:
                continue

            artist_names = [entry[0] for entry in entries]
            entry_mapping = {entry[0]: entry for entry in entries}

            match_result = self.find_best_match(
                artist_name, artist_names, threshold=0.3
            )

            if match_result:
                matched_name, ratio = match_result
                if ratio > highest_ratio:
                    highest_ratio = ratio
                    matched_entry = entry_mapping[matched_name]
                    best_match = (matched_entry[1], matched_entry[0], matched_entry[2])

            if highest_ratio >= 0.3:
                break

        if best_match:
            artist_url, artist_name_found, song_count = best_match
            print(
                f"Best artist match (similarity: {highest_ratio:.2f}): {artist_name_found} ({song_count})"
            )
            return artist_url, artist_name_found, song_count

        return None

    def get_artist_url(self, url: Optional[str] = None) -> Optional[str]:
        """Get uta-net artist page URL from argument or auto-detect from audio files.
        Returns None if no artist URL found but title search might be possible."""
        if url and re.match(r"https?://www\.uta-net\.com/artist/\d+/?", url):
            return url

        if not self.audio_files:
            print("No audio files found in directory.")
            sys.exit(1)

        file_path = os.path.join(self.directory, self.audio_files[0])
        audio = mutagen.File(file_path, easy=True)
        if not audio or not audio.get("artist"):
            print(f"Could not read artist from {self.audio_files[0]}")
            return None

        artist_name = str(audio["artist"][0])
        print(f"Detected artist: {artist_name}")

        result = self.search_artist_url(artist_name)
        if not result:
            print(f"No results found for artist: {artist_name}")
            return None

        artist_url, artist_name_found, song_count = result
        print(f"Artist URL: {artist_url}")

        return artist_url

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

    @staticmethod
    def normalize_text(title: str) -> str:
        """Clean title by removing emojis, symbols, and punctuation"""
        title = unicodedata.normalize("NFKC", title)

        cleaned = ""
        for char in title:
            if unicodedata.category(char).startswith(("So", "Sm", "Sk", "Sc")):
                continue
            if unicodedata.category(char).startswith("P") and char not in "'.:()（）":
                continue
            cleaned += char

        return cleaned.lower().strip()

    def match_song_title(
        self, file_title: str, song_titles: List[str]
    ) -> Optional[str]:
        """Match the audio file's title with the collected song titles using fuzzy matching."""
        cleaned_file_title = self.normalize_text(file_title)
        cleaned_song_titles = [self.normalize_text(title) for title in song_titles]

        # Create mapping of cleaned titles to original titles
        title_mapping = dict(zip(cleaned_song_titles, song_titles))

        match_result = self.find_best_match(cleaned_file_title, cleaned_song_titles)

        if match_result:
            matched_clean_title, ratio = match_result
            original_title = title_mapping[matched_clean_title]
            print(
                f"Matched '{file_title}' to '{original_title}' (similarity: {ratio:.2f})"
            )
            return original_title

        return None

    def fetch_lyrics(self, song_url: str) -> str:
        """Fetch the lyrics from the song's page."""
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
            elif file_ext == ".flac":
                from mutagen.flac import FLAC

                audio = FLAC(file_path)
                audio["UNSYNCEDLYRICS"] = lyrics
                audio.save(file_path)
            elif file_ext == ".m4a" or file_ext == ".aac":
                # Handle M4A, ALAC, AAC (MP4 containers)
                from mutagen.mp4 import MP4

                audio = MP4(file_path)
                audio["\xa9lyr"] = lyrics
                audio.save(file_path)
            else:
                print(f"Unsupported file extension: {file_ext}")
                return

            print(f"Lyrics added to {os.path.basename(file_path)}")
        except Exception as e:
            print(f"Error adding lyrics to {os.path.basename(file_path)}: {str(e)}")

    def get_title_search_results(
        self, search_term: str
    ) -> Optional[List[tuple[str, str, str]]]:
        """Perform search and return list of (title, url, artist) tuples."""
        search_url = f"https://www.uta-net.com/search/?Keyword={quote(search_term)}&Aselect=2&Bselect=3"
        try:
            response = requests.get(search_url)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            song_entries = []
            total_pages = self.get_total_pages(soup)

            for page_num in range(1, total_pages + 1):
                if page_num > 1:
                    page_url = f"{search_url}&page={page_num}"
                    response = requests.get(page_url)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.content, "html.parser")

                rows = soup.select("tbody.songlist-table-body tr")
                for row in rows:
                    title_link = row.select_one("td.sp-w-100 a")
                    artist_link = row.select_one("td.sp-none a")
                    if not title_link or not artist_link:
                        continue

                    song_title = title_link.select_one(
                        "span.songlist-title"
                    ).text.strip()
                    song_artist = artist_link.text.strip()
                    song_url = f"https://www.uta-net.com{title_link['href']}"
                    song_entries.append((song_title, song_url, song_artist))

            return song_entries
        except requests.RequestException:
            return None

    def extract_search_terms(self, text: str, max_terms: int = 5) -> List[str]:
        """Extract multiple potential search terms from text, ordered by likelihood of success."""
        # First try: original text
        search_terms = [text]

        # Second try: full normalized text
        normalized = self.normalize_text(text)
        if not normalized:
            return [text.strip()[:10]]
        search_terms.append(normalized)

        # Third try: kanji sequences
        kanji_matches = list(re.finditer(r"[\u4e00-\u9fff]+", normalized))
        kanji_terms = sorted(
            [match.group() for match in kanji_matches], key=len, reverse=True
        )
        search_terms.extend(kanji_terms)

        # Fourth try: word-based substrings
        words = normalized.split()
        substrings = []
        for i in range(len(words)):
            for j in range(i + 1, len(words) + 1):
                substring = " ".join(words[i:j])
                if substring not in search_terms:
                    substrings.append(substring)

        # Sort substrings by length in descending order
        substrings.sort(key=len, reverse=True)
        search_terms.extend(substrings)

        # Return unique terms, limited to max_terms
        return list(dict.fromkeys(search_terms))[:max_terms]

    def get_lyrics_by_title_search(
        self, filename: str, file_path: str
    ) -> Optional[tuple[bool, str]]:
        """Try to find and fetch lyrics by searching the song title directly."""
        audio = mutagen.File(file_path, easy=True)
        if not audio or not audio.get("title"):
            return None

        title = str(audio["title"][0])
        artist = str(audio.get("artist", [""])[0])
        print(f"\nSearching for '{title}' by '{artist}'...")

        # Get potential search terms
        search_terms = self.extract_search_terms(title)

        best_match = None
        highest_ratio = 0

        # Try each search term until we find a confident match
        for search_term in search_terms:
            print(f"Trying search term: '{search_term}'")

            entries = self.get_title_search_results(search_term)
            if not entries:
                continue

            # Find best match among results
            for song_title, song_url, song_artist in entries:
                title_ratio = difflib.SequenceMatcher(
                    None, self.normalize_text(title), self.normalize_text(song_title)
                ).ratio()
                artist_ratio = difflib.SequenceMatcher(
                    None, self.normalize_text(artist), self.normalize_text(song_artist)
                ).ratio()

                combined_ratio = (0.3 * title_ratio) + (0.7 * artist_ratio)
                # print(f" - '{song_title}' by '{song_artist}': {combined_ratio:.2f}")

                if combined_ratio > highest_ratio:
                    highest_ratio = combined_ratio
                    best_match = (song_title, song_url, song_artist)
            # If we found a confident match, stop searching
            if highest_ratio >= 0.3:
                break

        if not best_match or highest_ratio < 0.3:
            return (False, f"No confident matches found for '{title}' by '{artist}'")

        matched_title, song_url, matched_artist = best_match
        print(
            f"\nBest match: '{matched_title}' by '{matched_artist}' (similarity: {highest_ratio:.2f})"
        )

        lyrics = self.fetch_lyrics(song_url)
        if not lyrics:
            return (False, f"No lyrics found for '{matched_title}'")

        print("-" * 20)
        print(lyrics)
        print("-" * 20)

        self.write_lyrics_to_file(file_path, lyrics)
        print(f"Successfully added lyrics to {filename} via title search")
        return (True, "Success")

    def process_audio_files(self, search_by_title_pass: bool = True) -> None:
        """Process each audio file in the directory to add lyrics."""
        failed_files = []

        for filename in self.audio_files:
            file_path = os.path.join(self.directory, filename)
            audio = mutagen.File(file_path, easy=True)
            if not audio:
                print(f"Could not open {filename}. Skipping.")
                failed_files.append((filename, "Could not open file"))
                continue

            # Handle per-file artist search if enabled
            if self.per_file_search:
                artist = audio.get("artist")
                if not artist:
                    print(f"No artist found for {filename}. Skipping.")
                    failed_files.append((filename, "No artist found"))
                    continue

                print(f"\nProcessing {filename} - Artist: {artist[0]}")
                result = self.search_artist_url(str(artist[0]))
                if not result:
                    print(f"No artist found for {artist[0]}. Skipping.")
                    failed_files.append((filename, f"No artist found for {artist[0]}"))
                    continue

                self.artist_url, artist_name_found, song_count = result
                print(f"Found artist: {artist_name_found} ({song_count})")
                self.song_entries = self.collect_song_entries()

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
            print("-" * 20)
            print(lyrics)
            print("-" * 20)

            try:
                self.write_lyrics_to_file(file_path, lyrics)
            except Exception as e:
                failed_files.append((filename, f"Error writing lyrics: {str(e)}"))

        # Try to process failed files by title search if enabled
        if search_by_title_pass and failed_files:
            print("\nAttempting to find lyrics by title search for failed files...")
            still_failed = []

            for filename, reason in failed_files:
                file_path = os.path.join(self.directory, filename)
                result = self.get_lyrics_by_title_search(filename, file_path)

                if result is None:
                    still_failed.append((filename, reason))
                elif not result[0]:  # If search failed
                    still_failed.append((filename, result[1]))
                # If search succeeded, file is not added to still_failed

            failed_files = still_failed

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
            print(f"\nAll {len(self.audio_files)} files processed successfully!")

    def get_artist_search_results(
        self, search_term: str
    ) -> Optional[List[tuple[str, str, str]]]:
        """Perform artist search and return list of (artist_name, url, song_count) tuples."""
        search_url = "https://www.uta-net.com/search/"
        params = {
            "target": "art",
            "type": "in",
            "keyword": search_term,
        }

        try:
            response = requests.get(search_url, params=params)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, "html.parser")

            artist_entries = []
            for row in soup.select("tbody.songlist-table-body tr"):
                artist_link = row.select_one("a")
                if not artist_link:
                    continue

                artist_name = artist_link.select_one("span.fw-bold").text.strip()
                song_count = artist_link.select_one("span.song-count").text.strip()
                artist_url = f"https://www.uta-net.com{artist_link['href']}"
                artist_entries.append((artist_name, artist_url, song_count))

            return artist_entries
        except requests.RequestException:
            return None


def path_completer(prefix, **kwargs):
    """Custom path completer for argcomplete"""
    if not ARGCOMPLETE_AVAILABLE:
        return []

    audio_extensions = (".mp3", ".flac", ".m4a", ".ogg", ".aac")
    directory = os.getcwd()
    files = []

    for f in os.listdir(directory):
        if os.path.isfile(f) and f.lower().endswith(audio_extensions):
            if not prefix or f.startswith(prefix):
                files.append(f)

    return sorted(files)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add lyrics from uta-net.com to audio files."
    )
    parser.add_argument(
        "-d",
        "--directory",
        help="Directory containing audio files (default: current directory)",
    )
    parser.add_argument(
        "-u", "--url", help="uta-net.com artist page URL (default: auto-detect)"
    )
    parser.add_argument(
        "--per-file",
        action="store_true",
        help="Search for artist URL for each file individually",
    )
    parser.add_argument(
        "--no-title-search",
        action="store_true",
        help="Disable searching by title for failed files",
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Process a single audio file (optionally supports tab completion)",
    ).completer = path_completer

    if ARGCOMPLETE_AVAILABLE:
        argcomplete.autocomplete(parser)

    args = parser.parse_args()

    tagger = LyricsTagger(
        directory=args.directory,
        artist_url=args.url,
        per_file_search=args.per_file,
        single_file=args.file,
    )
    tagger.process_audio_files(search_by_title_pass=not args.no_title_search)


if __name__ == "__main__":
    main()
