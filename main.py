# ________________Imports________________
from flask import Flask, render_template
from functions import *


# _______________________________________

# ________________VALUES________________
# default starting point Los Angeles
default_latitude, default_longitude = 34.04919, -118.24799
# default number of k_nearest stations
k_number_default = 5
# CRS format to calculate routing
crs_routing_format = "EPSG:4326"
# CRS format displaying on the Open Street Map
crs_map_format = "EPSG:3857"
browser_open = 1
# 2 types of Open Route Service Routing ( by foot and by bike)
by_bike = "cycling-regular"
by_foot = "foot-walking"
# ______________________________________


def run_map_viewer():
    """
        Runs the map viewer application using Flask.

        The function sets up a Flask web application and defines routes for handling user requests.
        It creates a GeoDataFrame from the retrieved GeoJSON data and initializes the map with default values.
        The function handles user inputs from the website, performs data filtering and routing tasks,
        and generates the HTML map to be rendered on the website.

        """

    app = Flask(__name__)

    @app.route('/favicon.ico')
    def ignore_favicon():
        return app.response_class(status=204)

    @app.route('/', methods=['GET', 'POST'])

    def index():

        # Create the initial GeoDataFrame
        df = create_dataframe()
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

            # Prepare Task 1: Filter stations by bike availability
            if search_bikes:
                print("Task 1:")
                df = select_bikes(df, drop_if_number)

            # Prepare Task 2: Filter stations by dock availability
            if search_docks:
                print("Task 2:")
                df = select_docks(df, drop_if_number)
            # Prepare Task 3: Routing from Source to Destination
            if dest_longitude and dest_latitude:
                print("Task 3:")
                print("________________________ROUTING STARTED________________________")
                # Perform routing tasks
                route_foot_start, route_bike, route_foot_end = full_route(df, latitude, longitude, dest_latitude,
                                                                          dest_longitude)
                print("__________________________ROUTING END__________________________")

                # Create the HTML map with routing information
                gdf, m = create_local_html_map(df, latitude or default_latitude, longitude or default_longitude,
                                               rankings, dest_latitude, dest_longitude, route_bike, route_foot_start,
                                               route_foot_end)
            else:
                # Create the HTML map with default values
                gdf, m = create_local_html_map(df, latitude or default_latitude, longitude or default_longitude,
                                               rankings)

            return render_template('index.html', latitude=latitude, longitude=longitude,
                                   search_bikes=search_bikes, search_docks=search_docks,
                                   df_html=gdf.to_html(index=False))

        # Create the HTML map with default values
        gdf, m = create_local_html_map(df, default_latitude, default_longitude, k_number_default)

        return render_template('index.html', latitude=default_latitude, longitude=default_longitude,
                               df_html=gdf.to_html(index=False))


    if __name__ == '__main__':
        open_browser()
        app.run(debug=True)




# retrieves the GeoJSon Stationdata
get_GeoJSON()
# run

run_map_viewer()
input("Press Enter to exit...")
