import requests
import os
import json
import folium
import geopandas
import pandas
from flask import Flask, render_template, request
def get_GeoJSON():
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
# retrieves the GeoJSon from the Metro Bike Station Website
get_GeoJSON()

json_data = "data/geo_data.json"
jsonfile = open(json_data)
# geopanda dataframe
dfgeo = geopandas.read_file(jsonfile)
# convert to pada dataframe
df = dfgeo.drop(columns='geometry')
jsonfile.close()
dfgeo.to_csv("data/geo_station_live.csv")
df.to_csv("data/station_live.csv")

def create_local_html_map():
    # Create a map centered at a specific location
    m = folium.Map(location=[34.04919, -118.24799], zoom_start=10)

    # Add a marker to the map
    folium.Marker(location=[34.04919, -118.24799], popup="Los Angeles").add_to(m)

    # Save the map as an HTML file
    map_file = 'templates/map.html'
    m.save(map_file)

## Call the function to create and load the local HTML map
create_local_html_map()



def run_map_viewer():
    app = Flask(__name__)

    @app.route('/', methods=['GET', 'POST'])
    def index():
        if request.method == 'POST':
            latitude = request.form['latitude']
            longitude = request.form['longitude']
            return render_template('index.html', latitude=latitude, longitude=longitude)
        return render_template('index.html')

    if __name__ == '__main__':
        app.run(debug=True)

if __name__ == '__main__':
    run_map_viewer()
