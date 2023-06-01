import json
import os
import folium
import geopandas
import pandas
import requests
from flask import Flask, render_template, request
from shapely.geometry import Point

# default starting point Los Angeles
default_latitude, default_longitude = 34.04919, -118.24799
k_number_default = 5
crs_routing_format = "EPSG:4326"
crs_map_format = "EPSG:3857"
api_ORS_key = "5b3ce3597851110001cf62483a64689c0c234ddab368b092813c9dce"
by_bike = "cycling-regular"
by_foot = "foot-walking"


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


def create_local_html_map(dataframe, poslat, poslong, k_nearest, destlat=0.0, destlong=0.0,
                          route_coordinates=geopandas.GeoDataFrame()):

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

    if not (destlat and destlong) == 0:
        folium.Marker(location=[destlat, destlong],
                      popup=f'Postition:\nlat: {destlat}\nlong: {destlong}',
                      tooltip='My Position Destination',
                      icon=folium.Icon(color='black', icon="user")
                      ).add_to(m)
        folium.PolyLine(locations=route_coordinates, color='blue', weight=3).add_to(m)

        df_nearest_route = get_nearest_dataframe(dataframe, destlong, destlat, k_nearest)
        df_nearest = pandas.concat([df_nearest, df_nearest_route])
        print("-------------------Combined Dataframe-------------------")
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
    save_map(m)

    return df_nearest, m


def get_nearest_dataframe(dataframe, poslong, poslat, k_nearest):
    # my_position_point = Point(poslong, poslat)
    # Convert the point to the needed crs system
    # my_position_point = geopandas.GeoSeries([my_position_point], crs="EPSG:4326").to_crs("EPSG:3857").iloc[0]
    my_position_point = create_point(poslat, poslong, crs_routing_format, crs_map_format)
    # Create a geodataframe only with necessary columns
    gdf = dataframe.loc[:, ('kioskId', 'name', 'addressStreet', 'addressCity', 'addressState', 'addressZipCode',
                            'latitude', 'longitude', 'geometry')]

    # Reproject the 'geometry' column to the desired CRS format
    gdf['geometry'] = gdf['geometry'].to_crs(crs_map_format)

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


# def find_route(source_lat, source_long, dest_lat, dest_long, travel_type):
#    # create points in "EPSG:4326"
#    start_point = create_point(source_lat, source_long, crs_map_format, crs_routing_format)
#    end_point = create_point(dest_lat, dest_long, crs_map_format, crs_routing_format)
#    north_lat = 34.224313
#    south_lat = 33.906345
#    east_long = -118.180111
#    west_long = -118.529665
#    graph = osmnx.graph_from_bbox(north_lat, south_lat, east_long, west_long, network_type=travel_type, simplify=True)
#    print("Graph_success")
#    #new
#    start_point = (source_lat, source_long)
#    end_point = (dest_lat, dest_long)
#    #find nearest nodes
#    n_source = osmnx.distance.nearest_nodes(graph, source_long, source_lat, return_dist=True)
#    n_dest = osmnx.distance.nearest_nodes(graph, dest_long, dest_lat, return_dist=True)
#    osmnx_route = networkx.shortest_path(graph, n_source, n_dest, 'length')
#
#    edge_lengths = osmnx.utils_graph.get_route_edge_attributes(
#                    graph, osmnx_route, 'length')
#    route_len_m = sum(edge_lengths)
#    print(route_len_m)
#    return route_len_m

def find_route(source_lat, source_long, dest_lat, dest_long, travel_type):
    route_folder = "routes"
    data_file = os.path.join(route_folder, "geo_data_route.json")
    #
    if not os.path.exists(route_folder):
        os.makedirs(route_folder)

    headers = {
        'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8',
    }
    call = requests.get(
        f'https://api.openrouteservice.org/v2/directions/{travel_type}?api_key={api_ORS_key}&start={source_long},{source_lat}&end={dest_long},{dest_lat}',
        headers=headers)

    data = json.loads(call.text)
    # Save the data to a file
    with open(data_file, "w") as file:
        json.dump(data, file)
    #
    print(" Route Data saved successfully.")
    #
    #
    route_folder = "routes"
    data_file = os.path.join(route_folder, "geo_data_route.json")
    with open(data_file, 'r') as f:
        geojson_data = json.load(f)

    coordinates = geojson_data['features'][0]['geometry']['coordinates']

    return coordinates


def create_point(lat, long, crs_in, crs_out):
    point = Point(long, lat)
    point = geopandas.GeoSeries([point], crs=crs_in)
    point = point.to_crs(crs_out)
    print(f'Point from {crs_in} to {crs_out}: from {lat} , {long} to {point.iloc[0]}')
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


def request_lat_long(in_put):
    out_put = request.form.get(in_put)
    if out_put:
        out_put = float(out_put)
    else:
        out_put = 0.0
    return out_put


def run_map_viewer():
    app = Flask(__name__)

    @app.route('/', methods=['GET', 'POST'])
    def index():
        df = create_dataframe()
        gdf = df
        if request.method == 'POST':

            # Get float inputs from Website
            latitude = request_lat_long('latitude')
            longitude = request_lat_long('longitude')
            dest_latitude = request_lat_long('destLat')
            dest_longitude = request_lat_long('destLong')

            # Get int inputs from Website
            rankings = request.form.get('rankings')
            rankings = int(rankings) if rankings else 3
            drop_if_number = request.form.get('available_pieces')
            drop_if_number = int(drop_if_number) if drop_if_number else 1
            # Get Checkbox from Website
            search_bikes = request.form.get('searchBike') == 'on'
            search_docks = request.form.get('searchDocks') == 'on'

            # prepare Task1
            if search_bikes:
                df = select_bikes(df, drop_if_number)
            # prepare Task2
            if search_docks:
                df = select_docks(df, drop_if_number)
            if dest_longitude and dest_latitude:
                print("________________________ROUTING STARTED________________________")
                rankings = 1
                travel_mode = by_bike
                route_coordinates = find_route(latitude, longitude, dest_latitude, dest_longitude, travel_mode)
                print("________________________ROUTING END________________________")
                gdf, m = create_local_html_map(df, latitude or default_latitude, longitude or default_longitude,
                                               rankings, dest_latitude, dest_longitude, route_coordinates)
            else:
                gdf, m = create_local_html_map(df, latitude or default_latitude, longitude or default_longitude,
                                               rankings)

            return render_template('index.html', latitude=latitude, longitude=longitude,
                                   search_bikes=search_bikes, search_docks=search_docks,
                                   df_html=gdf.to_html(index=False))

        gdf, m = create_local_html_map(df, default_latitude, default_longitude, k_number_default)

        return render_template('index.html', latitude=default_latitude, longitude=default_longitude,
                               df_html=gdf.to_html(index=False))

    if __name__ == '__main__':
        app.run(debug=True)


run_map_viewer()
