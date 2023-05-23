import requests
import os
import json
import geopandas
import folium

url = "https://bikeshare.metro.net/stations/json"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64) AppleWebkit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36",
    "Referer": "https://bikeshare.metro.net/stations/",
}

data_folder = "data"
data_file = os.path.join(data_folder, "geo_data.json")

# Create the data folder if it doesn't exist
if not os.path.exists(data_folder):
    os.makedirs(data_folder)

try:
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        data = response.json()

        # Save the data to a file
        with open(data_file, "w") as file:
            json.dump(data, file)

        print("Data saved successfully.")
    else:
        if os.path.exists(data_file):
            # Load the data from the stored file
            with open(data_file, "r") as file:
                data = json.load(file)

            print("Failed to retrieve data. Using stored data.")
        else:
            print(f"Request failed with status code: {response.status_code}")
            print("No stored data available.")
except requests.exceptions.RequestException as e:
    if os.path.exists(data_file):
        # Load the data from the stored file
        with open(data_file, "r") as file:
            data = json.load(file)

        print("An error occurred. Using stored data.")
    else:
        print("An error occurred. No stored data available.")

import folium
import os

def create_local_html_map():
    # Create a map centered at a specific location
    m = folium.Map(location=[37.7749, -122.4194], zoom_start=13)

    # Add a marker to the map
    folium.Marker(location=[37.7749, -122.4194], popup="San Francisco").add_to(m)

    # Save the map as an HTML file
    map_file = 'map.html'
    m.save(map_file)

    # Get the absolute path of the HTML file
    abs_path = os.path.abspath(map_file)

    # Open the HTML file using the default web browser
    os.startfile(abs_path)


# Call the function to create and load the local HTML map
create_local_html_map()



