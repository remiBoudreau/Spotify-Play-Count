import requests
import json
from bs4 import BeautifulSoup
import pandas as pd
import os
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration variables
API_TOKEN_URL = "https://accounts.spotify.com/api/token"
SEARCH_API_URL = "https://api.spotify.com/v1/search"
TOP_TRACKS_API_URL = "https://api-partner.spotify.com/pathfinder/v1/query"
AUDIO_FEATURES_API_URL = "https://api.spotify.com/v1/audio-features/"
TRACK_DETAILS_API_URL = "https://api.spotify.com/v1/tracks/"

# Function to obtain access token from Spotify API
def get_access_token(client_id, client_secret):
    """
    Obtains access token from Spotify API.
    """
    data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    }
    response = requests.post(API_TOKEN_URL, data=data)

    if response.status_code == 200:
        data = response.json()
        return data.get("access_token")
    else:
        logger.error("Failed to obtain access token: %s", response.text)
        return None

# Function to get artist information from Spotify API
def get_artist_info(artist_name, access_token):
    """
    Gets the artist ID, followers count, popularity, and genres for the given artist name.
    """
    params = {"q": artist_name, "type": "artist", "limit": 1}  # Limiting to only one artist
    headers = {"Authorization": "Bearer " + access_token}
    response = requests.get(SEARCH_API_URL, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()
        artist_info = extract_artist_info(data)
        if artist_info:
            return artist_info
        else:
            logger.warning("Artist '%s' not found or missing necessary information.", artist_name)
            return None
    else:
        logger.error("Failed to fetch data for artist: %s", artist_name)
        return None

# Function to extract artist information from Spotify API response
def extract_artist_info(data):
    """
    Extracts artist ID, followers count, popularity, and genres from Spotify API response.
    """
    artists = data.get("artists", {}).get("items", [])
    if artists:
        artist = artists[0]
        artist_id = artist.get("id")
        followers = artist.get("followers", {}).get("total", 0)
        popularity = artist.get("popularity", 0)
        genres = artist.get("genres", [])
        return {"artist_id": artist_id, "followers": followers, "popularity": popularity, "genres": genres}
    else:
        return None

# Function to obtain client token from Spotify website
def get_client_token():
    """
    Obtains client token from Spotify website.
    """
    response = requests.get("https://open.spotify.com/")

    if response.status_code == 200:
        soup = BeautifulSoup(response.content, 'html.parser')
        script_tags = soup.find_all('script')
        for script in script_tags:
            if "accessToken" in script.text:
                start_index = script.text.find("accessToken") + len("accessToken\":\"")
                end_index = script.text.find("\"", start_index)
                client_token = script.text[start_index:end_index]
                return client_token
        else:
            logger.error("Client token not found in page source.")
            return None
    else:
        logger.error("Failed to fetch client token: %s", response.text)
        return None

# Function to fetch top tracks for a given artist ID
def fetch_top_tracks(client_token, artist_id, access_token):
    """
    Fetches top tracks for a given artist ID.
    """
    headers = {"Authorization": f"Bearer {client_token}"}
    variables = json.dumps({"uri": f"spotify:artist:{artist_id}", "locale": "", "includePrerelease": True})
    extensions = json.dumps({"persistedQuery": {"version": 1, "sha256Hash": "da986392124383827dc03cbb3d66c1de81225244b6e20f8d78f9f802cc43df6e"}})
    params = {
        "operationName": "queryArtistOverview",
        "variables": variables,
        "extensions": extensions
    }

    response = requests.get(TOP_TRACKS_API_URL, headers=headers, params=params)

    if response.status_code == 200:
        data = response.json()
        top_tracks = data.get("data", {}).get("artistUnion", {}).get("discography", {}).get("topTracks", {}).get("items", [])
        return top_tracks
    else:
        logger.error("Failed to fetch top tracks: %s", response.text)
        return []

# Function to fetch audio features for a given song ID
def song_audio_features_by_id(access_token, song_id):
    """
    Searches for a song by its ID.
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{AUDIO_FEATURES_API_URL}{song_id}", headers=headers)

    if response.status_code == 200:
        song_data = response.json()
        return song_data
    else:
        logger.error("Failed to fetch song features: %s", response.text)
        return {}

# Function to extract specific information from the track info
def extract_track_data(track_info):
    """
    Extracts specific information from the track info.
    """
    danceability = track_info.get('danceability', 0)
    energy = track_info.get('energy', 0)
    acousticness = track_info.get('acousticness', 0)

    return danceability, energy, acousticness

# Function to get the popularity of a track by its ID
def get_track_popularity(access_token, track_id):
    """
    Fetches the popularity of a track by its ID.
    """
    headers = {"Authorization": f"Bearer {access_token}"}
    response = requests.get(f"{TRACK_DETAILS_API_URL}{track_id}", headers=headers)

    if response.status_code == 200:
        track_data = response.json()
        popularity = track_data.get("popularity", 0)
        return popularity
    else:
        logger.error("Failed to fetch track popularity: %s", response.text)
        return 0  # Return 0 as default if failed to fetch popularity

# Function to convert data from artists_data (JSONL format) to CSV with specified headers
def jsonl_to_csv(artists_data, output_csv_path):
    """
    Convert data from artists_data (JSONL format) to CSV with specified headers.
    """
    headers = ['name', 'followers', 'popularity', 'genres', 'tracks']

    # Convert dictionaries to string as a single column for tracks
    for artist_info in artists_data:
        artist_info['tracks'] = json.dumps(artist_info['tracks'])

    # Create DataFrame from artists_data
    df = pd.DataFrame(artists_data, columns=headers)

    # Export DataFrame to CSV
    df.to_csv(output_csv_path, index=False)
    logger.info("CSV exported to %s", output_csv_path)

# Main function to orchestrate the process
def main(csv_file_path, client_id, client_secret):
    """
    Main function to orchestrate the process.
    """
    # Read artist names from CSV file
    artist_names = pd.read_csv(csv_file_path)['Performer 1 Name'].tolist()

    # Get access token
    access_token = get_access_token(client_id, client_secret)
    if not access_token:
        logger.error("Failed to obtain access token. Exiting.")
        return

    # Get client token
    client_token = get_client_token()
    if not client_token:
        logger.error("Failed to obtain client token. Exiting.")
        return

    artists_data = []
    for artist_name in artist_names:
        logger.info("Processing artist: %s", artist_name)
        artist_info = get_artist_info(artist_name, access_token)
        if artist_info:
            top_tracks = fetch_top_tracks(client_token, artist_info['artist_id'], access_token)
            tracks_data = []
            for track in top_tracks[:5]:
                track_data = {}

                song_id = track.get("track", {}).get("id")
                track_data['track_name'] = track.get("track", {}).get("name")
                track_data['popularity'] = get_track_popularity(access_token, song_id)
                track_data['track_number'] = track.get("track", {}).get("playcount")

                song_features = song_audio_features_by_id(access_token, song_id)
                track_data['danceability'], track_data['energy'], track_data['acousticness'] = extract_track_data(song_features)

                tracks_data.append(track_data)

            artists_data.append({
                'name': artist_name,
                'followers': artist_info['followers'],
                'popularity': artist_info['popularity'],
                'genres': artist_info['genres'],
                'tracks': tracks_data,
            })
    return artists_data

if __name__ == "__main__":
    csv_file_path = "bandname.csv" 
    CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
    CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
    output_csv_path = "artist_top_tracks.csv" 
    artists_data = main(csv_file_path, CLIENT_ID, CLIENT_SECRET)
    if artists_data:
        jsonl_to_csv(artists_data, output_csv_path)
    else:
        logger.error("No artist data found. Exiting.")
