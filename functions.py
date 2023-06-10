import json
import os
import folium
import geopandas
import pandas
import requests
from flask import request
from shapely.geometry import Point

# CRS format to calculate routing
crs_routing_format = "EPSG:4326"
# CRS format displaying on the Open Street Map
crs_map_format = "EPSG:3857"
# Api key for the Open Route Service
api_ORS_key = "5b3ce3597851110001cf62483a64689c0c234ddab368b092813c9dce"

# 2 types of Open Route Service Routing ( by foot and by bike)
by_bike = "cycling-regular"
by_foot = "foot-walking"


def get_GeoJSON():
    """
        Retrieves GeoJSON data from the Metro Bike Share LA website and saves it locally.

        The function sends a request to the website, saves the retrieved data as a JSON file,
        and creates a GeoPandas dataframe from the JSON file. It also saves the data in a CSV file.

    """
    # create a request to Metro Bike Share LA for retrieving data:
    # url contains the link to the website
    url = "https://bikeshare.metro.net/stations/json"
    # a header with user credentials is needed for the request, otherwise the request gets blocked from the website
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64) AppleWebkit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.63 Safari/537.36",
        "Referer": "https://bikeshare.metro.net/stations/",
    }
    # creating a folder to save the request
    data_folder = "data"
    data_file = os.path.join(data_folder, "geo_data.json")
    # Create the data folder if it doesn't exist
    if not os.path.exists(data_folder):
        os.makedirs(data_folder)

    try:
        # send the request and catch the response
        response = requests.get(url, headers=headers)
        # if the response is ok save the data
        if response.status_code == 200:
            data = response.json()

            # Save the data to a json file
            with open(data_file, "w") as file:
                json.dump(data, file)
            print("Data saved successfully.")

            dfgeo = create_dataframe()
            dfgeo.to_csv("data/geo_station_live.csv")

        else:  # e.g. response.status_code 404

            if os.path.exists(data_file):
                # Load the data from an previous stored file
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


def create_dataframe():
    """
        Creates a GeoPandas DataFrame (GeoDataFrame) from a GeoJSON file and saves it as a CSV file.

        Returns:
        - dfgeo: GeoPandas DataFrame containing the data from the GeoJSON file.

        """
    # open json file
    json_data = "data/geo_data.json"
    jsonfile = open(json_data)
    # creates a GeoDataFrame
    dfgeo = geopandas.read_file(jsonfile)
    jsonfile.close()
    # creates a csv file out of the GeoDataFrame
    dfgeo.to_csv("data/geo_station_live.csv")
    return dfgeo


def create_local_html_map(dataframe, poslat, poslong, k_nearest, destlat=0.0, destlong=0.0,
                          route_coordinates_bybike=None, route_foot_start=None, route_foot_end=None):
    """
        Creates a local HTML map with markers for the user's current position, destination (if provided),
        and nearest stations from the given dataframe. It also draws routes for walking and cycling with the Metro Bike.

        Args:
            dataframe: The input dataframe containing station data.
            poslat: The latitude of the user's current position.
            poslong: The longitude of the user's current position.
            k_nearest: The number of nearest stations to retrieve.
            destlat: The latitude of the destination position (default: 0.0).
            destlong: The longitude of the destination position (default: 0.0).
            route_coordinates_bybike: List of coordinates for the cycling route (default: None).
            route_foot_start: List of coordinates for the walking route start (default: None).
            route_foot_end: List of coordinates for the walking route end (default: None).

        Returns:
            df_nearest: The dataframe containing the k_nearest stations from the user's current position and destination.
            m: The folium map object.
        """

    if route_foot_end is None:
        route_foot_end = []

    if route_foot_start is None:
        route_foot_start = []

    if route_coordinates_bybike is None:
        route_coordinates_bybike = []

    # creating a map centered to the Position of LA, Map Format CRS is: EPSG:3857
    m = folium.Map(location=[poslat, poslong],
                   zoom_start=15,
                   control_scale=True,
                   crs='EPSG3857'
                   )

    # Add a Marker of the User's current Position add a popup and a hint showing the current lat and long coordinates
    folium.Marker(location=[poslat, poslong],
                  popup=f'Postition:\nlat: {poslat}\nlong: {poslong}', tooltip='My Position',
                  icon=folium.Icon(color='black', icon="user")).add_to(m)

    # returns a dataframe containing the k_nearest stations from the Users current lat and long coordinates
    df_nearest = get_nearest_dataframe(dataframe, poslong, poslat, k_nearest)
    # if a destination is selected create a second Maker showing the position of the destinations lat and long coordinates
    if not (destlat and destlong) == 0:
        folium.Marker(location=[destlat, destlong],
                      popup=f'Postition:\nlat: {destlat}\nlong: {destlong}',
                      tooltip='My Position Destination',
                      icon=folium.Icon(color='black', icon="user", prefix='fa')
                      ).add_to(m)

        # creates a line from point to point out of an list of coordinates
        # red is the line for walking, while blue is the line for cycling with the Metro Bike
        folium.PolyLine(locations=route_foot_start, color='red', weight=4).add_to(m)
        folium.PolyLine(locations=route_coordinates_bybike, color='blue', weight=4).add_to(m)
        folium.PolyLine(locations=route_foot_end, color='red', weight=4).add_to(m)
        # search for the destinations k_nearest stations and add them to the existing dataframe
        df_nearest_route = get_nearest_dataframe(dataframe, destlong, destlat, k_nearest)
        df_nearest = pandas.concat([df_nearest, df_nearest_route])

    # Add a Marker for every Station
    for idx, row in dataframe.iterrows():
        long, lat = row['geometry'].x, row['geometry'].y

        # retrieves the right color and icon for a user friendlier interface
        color, icon = icon_color(row, df_nearest)
        # creates a Marker with the color and the icon and also adds a Popup with necessary station information
        station_marker = create_markers(row, lat, long, color, icon)
        # adds the created marker to the map
        station_marker.add_to(m)

    # Add Clickable map that Copies lat and long to clipboard
    m.add_child(folium.ClickForLatLng())

    # Save the map as an HTML file
    save_map(m)

    return df_nearest, m


def get_nearest_dataframe(dataframe, poslong, poslat, k_nearest):
    """
    Retrieves the nearest data points in a dataframe based on the given position.

    Args:
        dataframe: The input dataframe containing data points.
        poslong: The longitude of the current position.
        poslat: The latitude of the current position.
        k_nearest: The number of nearest neighbors to retrieve.

    Returns:
        df_nearest: The dataframe containing the k_nearest neighbors to the current position.
    """

    # create a Geometric Point of the current position
    my_position_point = create_point(poslat, poslong, crs_routing_format, crs_map_format)
    # Create a  temporary geodataframe only with necessary columns
    gdf = dataframe.loc[:, ('kioskId', 'name', 'addressStreet', 'addressCity', 'addressState', 'addressZipCode',
                            'latitude', 'longitude', 'geometry')]

    # Reproject the 'geometry' column to the desired CRS format
    gdf['geometry'] = gdf['geometry'].to_crs(crs_map_format)

    # Calculate the distances from the current position to all stations
    gdf['distance'] = gdf['geometry'].distance(my_position_point)

    # sort the Dataframe by distances
    gdf = gdf.sort_values(by='distance')

    # creates a new dataframe where the KioskID matches the KioskID from the distance sorted Dataframe, containing
    df_nearest = dataframe[dataframe['kioskId'].isin(gdf['kioskId'].head(k_nearest))]

    return df_nearest


def icon_color(row, df_nearest):
    """
        Determines the color and icon for a station marker based on its status and availability.

        Args:
            row (Series): The row containing station information.
            df_nearest (DataFrame): The dataframe containing the nearest stations.

        Returns:
            color (str): The color for the station marker.
            icon (str): The icon for the station marker.
        """
    # station is active and has enough available bikes and docks
    if 'Active' in row['kioskPublicStatus'] and int(row['bikesAvailable']) > 5 and int(row['docksAvailable']) > 5:
        # the nearest stations are highlighted
        if row['kioskId'] in df_nearest['kioskId'].values:
            color = 'darkgreen'
        else:
            color = 'green'
        icon = 'bicycle'

    # station is active and has some bikes and docks
    elif 'Active' in row['kioskPublicStatus'] and int(row['bikesAvailable']) >= 2 and int(
            row['docksAvailable']) >= 2:
        # the nearest stations are highlighted
        if row['kioskId'] in df_nearest['kioskId'].values:
            color = 'darkblue'
        else:
            color = 'blue'
        icon = 'bicycle'

    # Station is unavailable or active but has low or no availability of bikes and docks
    elif 'Unavailable' in row['kioskPublicStatus'] or 'Active' in row['kioskPublicStatus']:
        # the nearest stations are highlighted
        if row['kioskId'] in df_nearest['kioskId'].values:
            color = 'darkred'
        else:
            color = 'red'
        icon = 'bicycle'

    # anything else, (error handling)
    else:
        color = 'gray'
        icon = 'magnifying-glass'

    return color, icon


def create_markers(row, lat, long, color, icon):
    """
        Creates a marker for a station on the map.

        Args:
            row (Series): The row containing station information.
            lat (float): The latitude of the station.
            long (float): The longitude of the station.
            color (str): The color for the marker.
            icon (str): The icon for the marker.

        Returns:
            Marker: The marker for the station.
        """

    station_name = row['name']

    # create HTML content for the marker's popup
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

    # Create a popup for the marker with the HTML content
    popup = folium.Popup(html=popup_html, max_width=250)

    # Create the marker with the specified location, tooltip, popup, color, and icon
    station_marker = folium.Marker(location=[lat, long],
                                   tooltip=f'{station_name}',
                                   popup=popup,
                                   icon=folium.Icon(color=f'{color}',
                                                    icon=f'{icon}', prefix='fa')
                                   )
    return station_marker


def save_map(m):
    """
        Saves the map as an HTML file.

        Args:
            m (Map): The map object to be saved.
        """
    map_file = 'templates/map.html'
    m.save(map_file)


def find_route(source_lat, source_long, dest_lat, dest_long, travel_type):
    """
        Finds a route between the source and destination coordinates using the OpenRouteService API.

        Args:
            source_lat (float): The latitude of the source location.
            source_long (float): The longitude of the source location.
            dest_lat (float): The latitude of the destination location.
            dest_long (float): The longitude of the destination location.
            travel_type (str): The type of travel ('foot', 'bike', 'car', etc.).

        Returns:
            list: A list of reversed coordinates representing the route.
        """

    # create folder, saving the route
    route_folder = "routes"
    data_file = os.path.join(route_folder, f'geo_data_route_{travel_type}.json')
    if not os.path.exists(route_folder):
        os.makedirs(route_folder)

    # header for the request
    headers = {
        'Accept': 'application/json, application/geo+json, application/gpx+xml, img/png; charset=utf-8',
    }

    # make a request to the OpenRouteService API to get the route data
    call = requests.get(
        f'https://api.openrouteservice.org/v2/directions/{travel_type}?api_key={api_ORS_key}&start={source_long},{source_lat}&end={dest_long},{dest_lat}',
        headers=headers)

    data = json.loads(call.text)

    # Save the route data to a file
    with open(data_file, "w") as file:
        json.dump(data, file)

    route_folder = "routes"
    data_file = os.path.join(route_folder, f'geo_data_route_{travel_type}.json')
    with open(data_file, 'r') as f:
        geojson_data = json.load(f)

    # Extract the coordinates from the route data
    coordinates = geojson_data['features'][0]['geometry']['coordinates']

    # Reverse the order of coordinates (longitude, latitude) to (latitude, longitude)
    reversed_coordinates = [(coord[1], coord[0]) for coord in coordinates]

    return reversed_coordinates


def create_point(lat, long, crs_in, crs_out):
    """
        Creates a geometric point with the specified latitude and longitude, and reprojects it to the desired CRS.

        Args:
            lat (float): The latitude of the point.
            long (float): The longitude of the point.
            crs_in (str): The CRS (Coordinate Reference System) of the input point.
            crs_out (str): The desired CRS for the output point.

        Returns:
            shapely.geometry.Point: The reprojected point in the desired CRS.
        """
    # Create a point with the given latitude and longitude
    point = Point(long, lat)

    # Create a GeoSeries with the point and assign the input CRS
    point = geopandas.GeoSeries([point], crs=crs_in)

    # Reproject the point to the desired CRS
    point = point.to_crs(crs_out)
    print(f'Point from {crs_in} to {crs_out}: from {lat} , {long} to {point.iloc[0]}')

    return point.iloc[0]


def select_bikes(df, drop_numbers):
    """
        Selects data points from a dataframe based on the number of available bikes.

        Args:
            df (pandas.DataFrame): The input dataframe containing data points.
            drop_numbers (int): The threshold number of available bikes. Data points with fewer available bikes will be dropped.

        Returns:
            pandas.DataFrame: The dataframe containing the selected data points with sufficient available bikes.
        """

    # select the necessary columns from the dataframe and drop the data points where the number is too low
    df = df.loc[:, ('kioskId', 'name', 'addressStreet', 'addressCity', 'addressState', 'addressZipCode',
                    'bikesAvailable', 'classicBikesAvailable', 'smartBikesAvailable',
                    'electricBikesAvailable',
                    'docksAvailable', 'kioskPublicStatus', 'openTime', 'closeTime',
                    'latitude', 'longitude', 'geometry',)] \
        .drop(df[df['bikesAvailable'] <= drop_numbers].index)

    return df


def select_docks(df, drop_numbers):
    """
        Selects data points from a dataframe based on the number of available docks.

        Args:
            df (pandas.DataFrame): The input dataframe containing data points.
            drop_numbers (int): The threshold number of available docks. Data points with fewer available docks will be dropped.

        Returns:
            pandas.DataFrame: The dataframe containing the selected data points with sufficient available docks.
        """

    # select the necessary columns from the dataframe and drop the data points where the number is to low
    df = df.loc[:, ('kioskId', 'name', 'addressStreet', 'addressCity', 'addressState', 'addressZipCode',
                    'bikesAvailable', 'docksAvailable', 'kioskPublicStatus', 'openTime', 'closeTime',
                    'latitude', 'longitude', 'geometry',)] \
        .drop(df[df['docksAvailable'] <= drop_numbers].index)

    return df


def request_lat_long(in_put):
    """
        Retrieves latitude or longitude value from the input form data.

        Args:
            in_put (str): The input parameter to retrieve from the form data.

        Returns:
            float: The retrieved latitude or longitude value. If not found, returns 0.0.
    """
    # get the value from the form data
    out_put = request.form.get(in_put)

    # conversion to float if exist
    if out_put:
        out_put = float(out_put)
    else:
        out_put = 0.0

    return out_put


def full_route(df, s_lat, s_long, d_lat, d_long):
    """
        Calculates the full route from the source position to the destination position using bike and foot.

        Args:
            df (DataFrame): The input dataframe containing station data.
            s_lat (float): The latitude of the source position.
            s_long (float): The longitude of the source position.
            d_lat (float): The latitude of the destination position.
            d_long (float): The longitude of the destination position.

        Returns:
            tuple: A tuple containing the route segments:
                - start_to_station (list): The route from the source position to the nearest start station by foot.
                - s_station_to_d_station (list): The route from the start station to the destination station by bike.
                - d_station_to_end (list): The route from the destination station to the destination position by foot.
        """

    # only the nearest stations and min availability = 1
    ranking = 1

    # delete stations with no availability
    df = select_bikes(df, ranking)
    df = select_docks(df, ranking)

    # Distance from source position to start station
    df_start_station = get_nearest_dataframe(df, s_long, s_lat, ranking)
    s_station_lat = df_start_station.loc[:, ('latitude')].item()
    s_station_long = df_start_station.loc[:, ('longitude')].item()
    start_to_station = find_route(s_lat, s_long, s_station_lat, s_station_long, by_foot)

    # Distance from start station to end station
    df_end_station = get_nearest_dataframe(df, d_long, d_lat, ranking)
    d_station_lat = df_end_station.loc[:, ('latitude')].item()
    d_station_long = df_end_station.loc[:, ('longitude')].item()
    s_station_to_d_station = find_route(s_station_lat, s_station_long, d_station_lat, d_station_long, by_bike)

    # Distance from end station to destination position
    d_station_to_end = find_route(d_station_lat, d_station_long, d_lat, d_long, by_foot)

    return start_to_station, s_station_to_d_station, d_station_to_end
