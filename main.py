import requests
import os
import json
import folium
import geopandas
import pandas
from flask import Flask, render_template, request
from shapely.geometry import Point
import osmnx as ox
import networkx as nx

# default starting point Los Angeles
default_latitude, default_longitude = 34.04919, -118.24799
k_number_default = 5
crs_code_format = "EPSG:3857"


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

            # create a save csv file
            dfgeo = geopandas.read_file(jsonfile)
            jsonfile.close()
            dfgeo.to_csv("data/geo_station_live.csv")

        else:  # e.g. response.status_code 404

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


def create_local_html_map(dataframe, poslat, poslong, k_nearest):

    # Create a map centered at a specific location
    m = folium.Map(location=[poslat, poslong],
                   zoom_start=15,
                   control_scale=True,
                   crs='EPSG3857'
                   )

    # Add My Position marker to the map
    my_position = folium.Marker(location=[poslat, poslong],
                                popup=f'Postition:\nlat: {poslat}\nlong: {poslong}',
                                tooltip='My Position',
                                icon=folium.Icon(color='black', icon="user")
                                ).add_to(m)

    # returns a dataframe containing the k_nearest stations
    df_nearest = get_nearest_dataframe(dataframe, poslong, poslat, k_nearest)

    print(df_nearest)

    # Add Station Markers to the map from the Geo dataframe
    for idx, row in dataframe.iterrows():
        long, lat = row['geometry'].x, row['geometry'].y

        # retrieves right color and icon
        color, icon = icon_color(row, df_nearest)
        # creates marker for map
        station_marker = create_markers(row, lat, long, color, icon)
        # add marker to map
        station_marker.add_to(m)

    # Add Clickable map that Copies lat and long to clipboard
    m.add_child(folium.ClickForLatLng())

    # Save the map as an HTML file
    # map_file = 'templates/map.html'
    # m.save(map_file)
    save_map(m)
    return df_nearest, m


def get_nearest_dataframe(dataframe, poslong, poslat, k_nearest):
    my_position_point = Point(poslong, poslat)
    # Convert the point to the needed crs system
    my_position_point = geopandas.GeoSeries([my_position_point], crs="EPSG:4326").to_crs("EPSG:3857").iloc[0]

    # Create a geodataframe only with necessary columns
    gdf = dataframe.loc[:, ('kioskId', 'name', 'addressStreet', 'addressCity', 'addressState', 'addressZipCode',
                            'latitude', 'longitude', 'geometry')]

    # Reproject the 'geometry' column to the desired CRS format
    gdf['geometry'] = gdf['geometry'].to_crs(crs_code_format)

    # Calculate the distances from the current position to all stations
    gdf['distance'] = gdf['geometry'].distance(my_position_point)
    # sort the Dataframe by distances and get the k_nearest neighbours
    gdf = gdf.sort_values(by='distance')
    df_nearest = dataframe[dataframe['kioskId'].isin(gdf['kioskId'].head(k_nearest))]

    return df_nearest


def icon_color(row, df_nearest):
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
    return color, icon


def create_markers(row, lat, long, color, icon):
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
                                   )
    return station_marker


def save_map(m):
    map_file = 'templates/map.html'
    m.save(map_file)


def find_route(start_point, end_point, travel_type):
    place_name = 'Los Angeles, California, USA'

    graph = ox.graph_from_place(place_name, network_type=travel_type)

    orig_node = ox.distance.nearest_nodes(graph, start_point.x, start_point.y)
    dest_node = ox.distance.nearest_nodes(graph, end_point.x, end_point.y)

    route = nx.shortest_path(graph, orig_node, dest_node, weight="length")

    route_coordinates = [(graph.nodes[node]["y"], graph.nodes[node]["x"]) for node in route]

    return route_coordinates


def create_point(lat, long):
    point = Point(long, lat)
    point = geopandas.GeoSeries([point], crs='EPSG:3857')
    point = point.to_crs('EPSG:4326')
    # point = geopandas.GeoSeries([point], crs="EPSG:4326").to_crs("EPSG:3857").iloc[0]
    print(point)
    return point.iloc[0]


def select_bikes(df, drop_numbers):
    df = df.loc[:, ('kioskId', 'name', 'addressStreet', 'addressCity', 'addressState', 'addressZipCode',
                    'bikesAvailable', 'classicBikesAvailable', 'smartBikesAvailable',
                    'electricBikesAvailable',
                    'docksAvailable', 'kioskPublicStatus', 'openTime', 'closeTime',
                    'latitude', 'longitude', 'geometry',)] \
        .drop(df[df['bikesAvailable'] <= drop_numbers].index)
    return df


def select_docks(df, drop_numbers):
    df = df.loc[:, ('kioskId', 'name', 'addressStreet', 'addressCity', 'addressState', 'addressZipCode',
                    'bikesAvailable', 'docksAvailable', 'kioskPublicStatus', 'openTime', 'closeTime',
                    'latitude', 'longitude', 'geometry',)] \
        .drop(df[df['docksAvailable'] <= drop_numbers].index)
    return df


def run_map_viewer():
    app = Flask(__name__)

    @app.route('/', methods=['GET', 'POST'])
    def index():
        df = create_dataframe()
        if request.method == 'POST':
            # Get inputs from Website
            latitude = float(request.form['latitude'])
            longitude = float(request.form['longitude'])
            rankings = request.form.get('rankings')
            rankings = int(rankings) if rankings else 3
            dest_latitude = request.form.get('destLat')
            dest_longitude = request.form.get('destLong')
            search_bikes = request.form.get('searchBike') == 'on'
            search_docks = request.form.get('searchDocks') == 'on'
            drop_if_number = request.form.get('available_pieces')
            drop_if_number = int(drop_if_number) if drop_if_number else 1

            if dest_longitude and dest_latitude:
                print("________________________ROUTING STARTED________________________")
                rankings = 1
                travel_mode = "bike"
                source_point = create_point(latitude, longitude)
                dest_point = create_point(dest_latitude, dest_longitude)
                route_coordinates = find_route(source_point, dest_point, travel_mode)
                print(route_coordinates)
                gdf, m = create_local_html_map(df, latitude or default_latitude, longitude or default_longitude,
                                               rankings)
                folium.PolyLine(locations=route_coordinates, color='blue', weight=3).add_to(m)
                save_map(m)
                print("________________________ROUTING END________________________")

            # prepare Task1
            if search_bikes:
                df = select_bikes(df, drop_if_number)
            # prepare Task2
            elif search_docks:
                df = select_docks(df, drop_if_number)

            gdf, m = create_local_html_map(df, latitude or default_latitude, longitude or default_longitude, rankings)

            return render_template('index.html', latitude=latitude, longitude=longitude,
                                   search_bikes=search_bikes, search_docks=search_docks,
                                   df_html=gdf.to_html(index=False))

        gdf, m = create_local_html_map(df, default_latitude, default_longitude, k_number_default)
        return render_template('index.html', latitude=default_latitude, longitude=default_longitude,
                               df_html=gdf.to_html(index=False))

    if __name__ == '__main__':
        app.run(debug=True)


run_map_viewer()
