import requests
import os
import json
import folium
import geopandas
import pandas
from flask import Flask, render_template, request
from shapely.geometry import Point

# default starting point Los Angeles
default_latitude, default_longitude = 34.04919, -118.24799
k_number_default = 5
crs_code_format = "EPSG:3857"
drop_if_number = 8


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
            json_data = "data/geo_data.json"
            jsonfile = open(json_data)
            # geopanda dataframe
            dfgeo = geopandas.read_file(jsonfile)
            jsonfile.close()
            dfgeo.to_csv("data/geo_station_live.csv")
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


def create_dataframe():  # creates the Geodataframe and creates a csv
    json_data = "data/geo_data.json"
    jsonfile = open(json_data)
    # geopanda dataframe
    dfgeo = geopandas.read_file(jsonfile)
    jsonfile.close()
    dfgeo.to_csv("data/geo_station_live.csv")
    return dfgeo


# creates the csv files from json and returns geodataframe
# df = create_dataframe()


def create_local_html_map(dataframe, poslat, poslong, k_number):
    # Create a map centered at a specific location
    m = folium.Map(location=[poslat, poslong],
                   zoom_start=15,
                   control_scale=True,
                   crs='EPSG3857'
                   )
    k_nearest = int(k_number)
    # Add My Position marker to the map
    my_position = folium.Marker(location=[poslat, poslong],
                                popup=f'Postition:\nlat: {poslat}\nlong: {poslong}',
                                tooltip='My Position',
                                icon=folium.Icon(color='black', icon="user")
                                ).add_to(m)

    # Create a point of the current position
    my_position_point = Point(poslong, poslat)
    my_position_point = geopandas.GeoSeries([my_position_point], crs="EPSG:4326").to_crs("EPSG:3857").iloc[0]
    print(my_position_point)
    # Create a geodataframe only with necessary columns
    gdf = dataframe.loc[:, ('kioskId', 'name', 'addressStreet', 'addressCity', 'addressState', 'addressZipCode',
                            'latitude', 'longitude', 'geometry')]
    # Reproject the 'geometry' column to the desired CRS format
    gdf['geometry'] = gdf['geometry'].to_crs(crs_code_format)
    # Calculate the distances from the current position to all stations
    gdf['distance'] = gdf['geometry'].distance(my_position_point)
    gdf = gdf.sort_values(by='distance')

    # Find the k-nearest Station
    deleted_kiosk_id = []

    for num in range(k_nearest):
        spatial_index = gdf.sindex
        nearest_geometry = spatial_index.nearest(my_position_point, return_all=False)

        nearest_indicies = nearest_geometry.flatten()[:1]
        nearest_stations = gdf.iloc[nearest_indicies]
        deleted_kiosk_id.extend(nearest_stations['kioskId'].tolist())

        gdf = gdf.drop(gdf.index[nearest_indicies.tolist()])

    df_nearest = dataframe[dataframe['kioskId'].isin(deleted_kiosk_id)]
    print(df_nearest)

    # Add Station Markers to the map from the geodataframe
    for idx, row in dataframe.iterrows():
        long, lat = row['geometry'].x, row['geometry'].y

        if 'Active' in row['kioskPublicStatus'] and int(row['bikesAvailable']) > 5 and int(row['docksAvailable']) > 5:
            if row['kioskId'] in df_nearest['kioskId'].values:
                color = 'darkgreen'
            else:
                color = 'lightgreen'
            icon = 'ok-sign'
        elif 'Active' in row['kioskPublicStatus'] and int(row['bikesAvailable']) >= 2 and int(
                row['docksAvailable']) >= 2:
            if row['kioskId'] in df_nearest['kioskId'].values:
                color = 'darkblue'
            else:
                color = 'lightblue'
            icon = 'info-sign'
        elif 'Unavailable' in row['kioskPublicStatus'] or 'Active' in row['kioskPublicStatus']:
            if row['kioskId'] in df_nearest['kioskId'].values:
                color = 'darkred'
            else:
                color = 'lightred'
            icon = 'remove-sign'
        else:
            color = 'gray'
            icon = 'search'

        station_name = row['name']

        popup_html = """
        <b>Name:</b> {}<br>
        <b>ID:</b> {}<br>
        <b>Street:</b> {}<br>
        <b>Available Bikes:</b> {}<br>
        <b>Available Docks:</b> {}<br>
        <b>Status:</b> {}<br>
        <b>Opening hours:</b> {} am - {} pm<br>
        """.format(row['name'], row['kioskId'], row['addressStreet'], row['bikesAvailable'], row['docksAvailable'],
                   row['kioskPublicStatus'], row['openTime'], row['closeTime'])
        popup = folium.Popup(html=popup_html, max_width=250)
        station_marker = folium.Marker(location=[lat, long],
                                       tooltip=f'{station_name}',
                                       popup=popup,
                                       icon=folium.Icon(color=f'{color}',
                                                        icon=f'{icon}')
                                       ).add_to(m)

    # Add Clickable map that Copies lat and long to clipboard
    m.add_child(folium.ClickForLatLng())
    # Save the map as an HTML file
    map_file = 'templates/map.html'
    m.save(map_file)
    return df_nearest


def run_map_viewer():
    app = Flask(__name__)

    @app.route('/', methods=['GET', 'POST', 'ROUTE'])
    def index():
        df = create_dataframe()
        if request.method == 'POST':
            latitude = float(request.form['latitude'])
            longitude = float(request.form['longitude'])
            rankings = request.form.get('rankings')
            rankings = int(rankings) if rankings else 3
            dest_latitude = request.form.get('destLat')
            dest_longitude = request.form.get('destLong')
            search_bikes = request.form.get('searchBike') == 'on'
            search_docks = request.form.get('searchDocks') == 'on'

            if dest_longitude and dest_latitude:
                print("________________________ROUTING STARTED________________________")
                rankings = 1
            if search_bikes:
                df = df.loc[:, ('kioskId', 'name', 'addressStreet', 'addressCity', 'addressState', 'addressZipCode',
                                'bikesAvailable', 'classicBikesAvailable', 'smartBikesAvailable',
                                'electricBikesAvailable',
                                'docksAvailable', 'kioskPublicStatus', 'openTime', 'closeTime',
                                'latitude', 'longitude', 'geometry',)] \
                    .drop(df[df['bikesAvailable'] <= drop_if_number].index)
            elif search_docks:
                df = df.loc[:, ('kioskId', 'name', 'addressStreet', 'addressCity', 'addressState', 'addressZipCode',
                                'bikesAvailable', 'docksAvailable', 'kioskPublicStatus', 'openTime', 'closeTime',
                                'latitude', 'longitude', 'geometry',)] \
                    .drop(df[df['docksAvailable'] <= drop_if_number].index)

            gdf = create_local_html_map(df, latitude or default_latitude, longitude or default_longitude, rankings)

            return render_template('index.html', latitude=latitude, longitude=longitude,
                                   search_bikes=search_bikes, search_docks=search_docks,
                                   df_html=gdf.to_html(index=False))

        gdf = create_local_html_map(df, default_latitude, default_longitude, k_number_default)
        return render_template('index.html', latitude=default_latitude, longitude=default_longitude,
                               df_html=gdf.to_html(index=False))

    if __name__ == '__main__':
        app.run(debug=True)


run_map_viewer()
