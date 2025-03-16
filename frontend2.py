from datetime import datetime, timedelta
import random
from collections import deque
from functools import lru_cache
import requests
from math import radians, sin, cos, sqrt, atan2
import streamlit as st
import pandas as pd

# Driver class
class Driver:
    def __init__(self, name, home_location, preferred_areas, work_hours):
        self.name = name
        self.home_location = home_location
        self.preferred_areas = preferred_areas
        self.work_hours = work_hours
        self.current_location = home_location
        self.current_time = datetime.strptime(str(work_hours[0]), "%H").time()
        self.assigned_rides = []
        self.is_available = True  # Track driver availability

# Ride class
class Ride:
    def __init__(self, start, end, duration, arrival_time):
        self.start = start
        self.end = end
        self.duration = duration  # Duration in hours
        self.arrival_time = arrival_time  # Arrival time of the ride
        self.is_assigned = False  # Track ride assignment status

# Fetch route, travel time, and distance between two locations using Google Maps Directions API
@lru_cache(maxsize=1024)
def get_route(start, end):
    if start == end:
        return 0, 0, None  # If start and end are the same, distance and duration are 0

    API_KEY = "AIzaSyChR3PEV_4WI_GC930ZeWPPFJYLSoOjJpQ"  # Replace with your actual API key
    url = "https://routes.googleapis.com/directions/v2:computeRoutes"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.polyline"
    }
    
    payload = {
        "origin": {
            "address": start
        },
        "destination": {
            "address": end
        },
        "travelMode": "DRIVE"
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code == 200:
            data = response.json()
            if "routes" in data and len(data["routes"]) > 0:
                route = data["routes"][0]
                duration = int(route["duration"][:-1])  # Remove 's' and convert to int
                distance = route["distanceMeters"]
                polyline = route["polyline"]["encodedPolyline"]
                return duration / 3600, distance, polyline  # Convert seconds to hours
            else:
                print(f"Error: No route found from {start} to {end}. Response: {data}")
                # Fallback to Haversine distance
                return get_haversine_distance(start, end), None, None
        else:
            print(f"Error: API request failed with status code {response.status_code}. Response: {response.text}")
            # Fallback to Haversine distance
            return get_haversine_distance(start, end), None, None
    except Exception as e:
        print(f"Error: Failed to connect to Google Maps API. {e}")
        # Fallback to Haversine distance
        return get_haversine_distance(start, end), None, None

# Function to calculate the Haversine distance between two points
def haversine(lat1, lon1, lat2, lon2):
    R = 6371  # Earth radius in km
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return R * c * 1000  # Distance in meters

# Function to get Haversine distance as fallback
def get_haversine_distance(start, end):
    # Dummy coordinates for demonstration purposes
    start_coords = (12.9716, 77.5946)  # Example: Bangalore coordinates
    end_coords = (13.0827, 80.2707)    # Example: Chennai coordinates
    return haversine(start_coords[0], start_coords[1], end_coords[0], end_coords[1])

# Function to decode a polyline string into coordinates
def decode_polyline(polyline_str):
    index, lat, lng = 0, 0, 0
    coordinates = []
    changes = {'latitude': 0, 'longitude': 0}

    # Coordinates have variable length when encoded, so keep track of index
    while index < len(polyline_str):
        # Gather latitude changes
        shift, result = 0, 0
        while True:
            byte = ord(polyline_str[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if not byte >= 0x20:
                break
        changes['latitude'] += ~(result >> 1) if (result & 1) else (result >> 1)

        # Gather longitude changes
        shift, result = 0, 0
        while True:
            byte = ord(polyline_str[index]) - 63
            index += 1
            result |= (byte & 0x1F) << shift
            shift += 5
            if not byte >= 0x20:
                break
        changes['longitude'] += ~(result >> 1) if (result & 1) else (result >> 1)

        # Append the coordinates
        coordinates.append((changes['latitude'] / 100000.0, changes['longitude'] / 100000.0))

    return coordinates

# Function to reverse geocode latitude and longitude coordinates into an address
def reverse_geocode(lat, lon):
    API_KEY = "AIzaSyChR3PEV_4WI_GC930ZeWPPFJYLSoOjJpQ"  # Replace with your actual API key
    url = f"https://maps.googleapis.com/maps/api/geocode/json?latlng={lat},{lon}&key={API_KEY}"
    
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if "results" in data and len(data["results"]) > 0:
                return data["results"][0]["formatted_address"]
            else:
                print(f"Error: No address found for coordinates ({lat}, {lon}). Response: {data}")
                return None
        else:
            print(f"Error: API request failed with status code {response.status_code}. Response: {response.text}")
            return None
    except Exception as e:
        print(f"Error: Failed to connect to Google Maps API. {e}")
        return None

# Function to split a ride into two segments
def split_ride(ride):
    start = ride.start
    end = ride.end
    
    # Get the route from start to end
    duration, distance, polyline = get_route(start, end)
    if not duration or not distance or not polyline:
        print(f"Error: Unable to fetch route for ride from {start} to {end}.")
        return None
    
    # Decode the polyline to get the list of coordinates
    coordinates = decode_polyline(polyline)
    if not coordinates:
        print(f"Error: Unable to decode polyline for ride from {start} to {end}.")
        return None
    
    # Find the midpoint (halfway along the route)
    midpoint_distance = distance / 2
    accumulated_distance = 0
    midpoint_address = None
    for i in range(len(coordinates) - 1):
        lat1, lon1 = coordinates[i]
        lat2, lon2 = coordinates[i + 1]
        segment_distance = haversine(lat1, lon1, lat2, lon2)
        accumulated_distance += segment_distance
        if accumulated_distance >= midpoint_distance:
            # Reverse geocode the midpoint coordinates to get an address
            midpoint_address = reverse_geocode(lat2, lon2)
            if not midpoint_address:
                print(f"Error: Unable to reverse geocode midpoint coordinates ({lat2}, {lon2}).")
                return None
            break
    
    if not midpoint_address:
        print(f"Error: Unable to find midpoint for ride from {start} to {end}.")
        return None
    
    # Calculate travel time for each segment
    start_to_mid_duration, start_to_mid_distance, _ = get_route(start, midpoint_address)
    mid_to_end_duration, mid_to_end_distance, _ = get_route(midpoint_address, end)
    
    if not start_to_mid_duration or not mid_to_end_duration:
        print(f"Error: Unable to calculate durations for split ride segments.")
        return None
    
    # Log the split ride details
    print(f"Split ride from {start} to {end} (Total Distance: {distance / 1000:.2f} km):")
    print(f"  Segment 1: {start} to {midpoint_address} (Distance: {start_to_mid_distance / 1000:.2f} km, Duration: {start_to_mid_duration:.2f} hours)")
    print(f"  Segment 2: {midpoint_address} to {end} (Distance: {mid_to_end_distance / 1000:.2f} km, Duration: {mid_to_end_duration:.2f} hours)")
    
    # Create two new rides
    ride1 = Ride(start, midpoint_address, start_to_mid_duration, ride.arrival_time)
    ride2 = Ride(midpoint_address, end, mid_to_end_duration,
                 (datetime.combine(datetime.today(), ride.arrival_time) + timedelta(hours=start_to_mid_duration)).time())
    
    return ride1, ride2

# Function to merge all rides with the same start and end points
def merge_all_rides(rides):
    merged_rides = []  # List to store merged rides
    ride_dict = {}  # Dictionary to group rides by start and end points
    
    # Group rides by start and end points
    for ride in rides:
        key = (ride.start, ride.end)
        if key in ride_dict:
            ride_dict[key].append(ride)
        else:
            ride_dict[key] = [ride]
    
    # Merge rides with the same start and end points
    for key, ride_list in ride_dict.items():
        if len(ride_list) > 1:
            # Merge all rides in the list into a single ride
            combined_ride = ride_list[0]
            for ride in ride_list[1:]:
                combined_ride.duration += ride.duration
                combined_ride.arrival_time = min(combined_ride.arrival_time, ride.arrival_time)
            merged_rides.append(combined_ride)
        else:
            # Add the single ride to the merged list
            merged_rides.append(ride_list[0])
    
    return merged_rides

# Function to check if a driver can handle a ride
def can_handle_ride(driver, ride):
    """
    Check if a driver can handle a ride based on their availability, work hours, and proximity to the ride's start location.
    """
    # Convert driver's current time and work hours to datetime for easier calculations
    current_datetime = datetime.combine(datetime.today(), driver.current_time)
    end_datetime = datetime.combine(datetime.today(), datetime.strptime(str(driver.work_hours[1]), "%H").time())
    
    # Convert ride's arrival time to datetime
    ride_arrival_datetime = datetime.combine(datetime.today(), ride.arrival_time)
    
    # Check if the ride's arrival time is before the driver's current time
    if ride_arrival_datetime < current_datetime:
        return False  # Skip this ride if it's already past the arrival time
    
    # Calculate travel time from driver's current location to ride start
    travel_time, _, _ = get_route(driver.current_location, ride.start)
    if not travel_time:
        return False  # Unable to calculate travel time
    
    # Calculate departure time (ride arrival time minus travel time)
    departure_time = ride_arrival_datetime - timedelta(hours=travel_time)
    
    # If the driver is not yet at the departure location, update the current time
    if current_datetime < departure_time:
        current_datetime = departure_time
    
    # Calculate ride completion time
    ride_completion_time = current_datetime + timedelta(hours=travel_time + ride.duration)
    
    # Check if the ride can be completed within the driver's work hours (with a 1-hour buffer)
    if ride_completion_time > end_datetime + timedelta(hours=1):
        return False  # Driver cannot complete the ride within their work hours
    
    return True  # Driver can handle the ride

# Function to assign rides to drivers
def assign_rides_to_drivers(drivers, rides):
    ride_queue = deque(sorted(rides, key=lambda x: x.arrival_time))  # Sort rides by arrival time (FCFS)
    
    while ride_queue:
        ride = ride_queue.popleft()  # Get the earliest ride
        
        # Assign the ride to the best driver
        best_driver = None
        min_total_time = float('inf')
        
        for driver in drivers:
            if not driver.is_available or not can_handle_ride(driver, ride):
                continue
            
            # Calculate travel time from driver's current location to ride start
            travel_time, _, _ = get_route(driver.current_location, ride.start)
            
            # Calculate total time (waiting + travel + ride duration)
            current_datetime = datetime.combine(datetime.today(), driver.current_time)
            ride_arrival_datetime = datetime.combine(datetime.today(), ride.arrival_time)
            
            # If driver arrives early, calculate waiting time
            waiting_time = max(0, (ride_arrival_datetime - current_datetime).total_seconds() / 3600)
            
            # Total time = waiting_time + travel_time + ride.duration
            total_time = waiting_time + travel_time + ride.duration
            
            # Prioritize preferred areas
            if ride.start in driver.preferred_areas:
                total_time *= 0.7  # 30% priority boost
            if ride.end in driver.preferred_areas:
                total_time *= 0.8  # 20% priority boost
            
            # Choose the driver with the minimum total time
            if total_time < min_total_time:
                min_total_time = total_time
                best_driver = driver
        
        if best_driver:
            # Assign the ride to the best driver
            assign_ride(best_driver, ride)
        else:
            print(f"No suitable driver found for ride from {ride.start} to {ride.end}.")
            # Log unassigned rides for manual assignment
            ride.is_assigned = False

# Function to assign a ride to a driver
def assign_ride(driver, ride):
    travel_time, _, _ = get_route(driver.current_location, ride.start)
    if not travel_time:
        return
    
    # Convert driver's current time to datetime for easier calculations
    current_datetime = datetime.combine(datetime.today(), driver.current_time)
    end_datetime = datetime.combine(datetime.today(), datetime.strptime(str(driver.work_hours[1]), "%H").time())
    
    ride_arrival_datetime = datetime.combine(datetime.today(), ride.arrival_time)
    
    # If there's a gap between the driver's current time and the ride's arrival time, wait
    waiting_time = max(0, (ride_arrival_datetime - current_datetime).total_seconds() / 3600)
    if waiting_time > 0:
        print(f"Driver {driver.name} is waiting from {current_datetime.time()} to {ride.arrival_time}.")
        current_datetime = ride_arrival_datetime  # Corrected variable name
    
    # Calculate departure time
    departure_time = ride_arrival_datetime - timedelta(hours=travel_time)
    if current_datetime < departure_time:
        current_datetime = departure_time
    
    # Assign the ride to the driver
    driver.assigned_rides.append(ride)
    driver.current_location = ride.end
    driver.current_time = (current_datetime + timedelta(hours=travel_time + ride.duration)).time()
    ride.is_assigned = True
    print(f"Driver {driver.name} assigned ride:")
    print(f"  From {ride.start} to {ride.end} (Duration: {ride.duration:.2f} hours)")
    print(f"  Travel time: {travel_time:.2f} hours")
    print(f"  Arrival time: {ride.arrival_time}")
    print(f"  Current time: {driver.current_time}")
    
    # Move closer to home in the last hour of the shift
    if (datetime.combine(datetime.today(), datetime.strptime(str(driver.work_hours[1]), "%H").time()) - 
        (datetime.combine(datetime.today(), driver.current_time))) <= timedelta(hours=1):
        print(f"Driver {driver.name} is moving closer to home.")
        home_travel_time, _, _ = get_route(driver.current_location, driver.home_location)
        if home_travel_time:
            if home_travel_time <= 1:  # Ensure home travel time fits within the last hour
                driver.current_location = driver.home_location
                driver.current_time = (datetime.combine(datetime.today(), driver.current_time) + 
                                       timedelta(hours=home_travel_time)).time()
                print(f"Driver {driver.name} reached home at {driver.current_time}.")
            else:
                print(f"Driver {driver.name} cannot return home within work hours.")
    
    # Mark driver as available for reassignment
    driver.is_available = True

# Hardcoded input of 20 rides
rides = [
    # Rides for splitting (long-distance rides > 20 km)
    Ride("Jayanagar, Bangalore", "Kempegowda International Airport, KIAL Rd, Devanahalli, Bangalore", 1.5, datetime.strptime("15:00", "%H:%M").time()),
    Ride("Marathahalli, Bangalore", "Kempegowda International Airport, KIAL Rd, Devanahalli, Bangalore", 1.8, datetime.strptime("16:00", "%H:%M").time()),
    Ride("Whitefield, Bangalore", "Jayanagar, Bangalore", 1.2, datetime.strptime("14:00", "%H:%M").time()),
    Ride("Kempegowda International Airport, KIAL Rd, Devanahalli, Bangalore", "Koramangala, Bangalore", 1.6, datetime.strptime("17:00", "%H:%M").time()),

    # Rides for merging (identical start and end points)
    Ride("KR Market, Kalasipalya, Bangalore", "Mantri Square Mall, Sampige Road, Malleswaram, Bangalore", 0.5, datetime.strptime("10:00", "%H:%M").time()),
    Ride("KR Market, Kalasipalya, Bangalore", "Mantri Square Mall, Sampige Road, Malleswaram, Bangalore", 0.5, datetime.strptime("11:00", "%H:%M").time()),
    Ride("Manyata Tech Park, Bangalore", "Koramangala, Bangalore", 0.8, datetime.strptime("12:00", "%H:%M").time()),
    Ride("Manyata Tech Park, Bangalore", "Koramangala, Bangalore", 0.8, datetime.strptime("13:00", "%H:%M").time()),
    Ride("Indiranagar, Bangalore", "Marathahalli, Bangalore", 0.7, datetime.strptime("09:00", "%H:%M").time()),
    Ride("Indiranagar, Bangalore", "Marathahalli, Bangalore", 0.7, datetime.strptime("10:00", "%H:%M").time()),

    # Regular rides (no splitting or merging)
    Ride("Marathahalli, Bangalore", "Manyata Tech Park, Bangalore", 0.6, datetime.strptime("08:00", "%H:%M").time()),
    Ride("Koramangala, Bangalore", "Jayanagar, Bangalore", 0.4, datetime.strptime("09:00", "%H:%M").time()),
    Ride("Whitefield, Bangalore", "Cubbon Park, Kasturba Road, Sampangi Rama Nagar, Bangalore", 0.9, datetime.strptime("11:00", "%H:%M").time()),
    Ride("Cubbon Park, Kasturba Road, Sampangi Rama Nagar, Bangalore", "Marathahalli, Bangalore", 0.7, datetime.strptime("12:00", "%H:%M").time()),
    Ride("Manipal Hospital, HAL Airport Road, Bangalore", "Mantri Square Mall, Sampige Road, Malleswaram, Bangalore", 0.5, datetime.strptime("13:00", "%H:%M").time()),
    Ride("Bishop Cotton Boys' School, St. Mark's Road, Bangalore", "Jayanagar, Bangalore", 0.3, datetime.strptime("14:00", "%H:%M").time()),
    Ride("Toit Brewpub, Indiranagar, Bangalore", "KR Market, Kalasipalya, Bangalore", 0.6, datetime.strptime("15:00", "%H:%M").time()),
    Ride("Jayanagar, Bangalore", "Toit Brewpub, Indiranagar, Bangalore", 0.6, datetime.strptime("16:00", "%H:%M").time()),
    Ride("Koramangala, Bangalore", "Whitefield, Bangalore", 0.8, datetime.strptime("17:00", "%H:%M").time()),
    Ride("Mantri Square Mall, Sampige Road, Malleswaram, Bangalore", "Cubbon Park, Kasturba Road, Sampangi Rama Nagar, Bangalore", 0.4, datetime.strptime("18:00", "%H:%M").time()),
]

# Drivers
drivers = [
    Driver("Driver1", "Indiranagar, Bangalore", ["Indiranagar, Bangalore", "Marathahalli, Bangalore"], (8, 18)),
    Driver("Driver2", "Koramangala, Bangalore", ["Koramangala, Bangalore", "Jayanagar, Bangalore"], (9, 19)),
    Driver("Driver3", "Whitefield, Bangalore", ["Whitefield, Bangalore", "Marathahalli, Bangalore"], (8, 17)),
    Driver("Driver4", "Jayanagar, Bangalore", ["Jayanagar, Bangalore", "KR Market, Kalasipalya, Bangalore"], (10, 20)),
    Driver("Driver5", "Marathahalli, Bangalore", ["Marathahalli, Bangalore", "Manyata Tech Park, Bangalore"], (9, 18))
]

# Split long-distance rides
split_rides = []
for ride in rides:
    _, distance, _ = get_route(ride.start, ride.end)
    if distance and distance > 20000:  # Split rides longer than 20 km
        split_result = split_ride(ride)
        if split_result:
            split_rides.extend(split_result)
        else:
            split_rides.append(ride)
    else:
        split_rides.append(ride)

# Merge rides with the same start and end points
merged_rides = merge_all_rides(split_rides)

# Assign merged rides to drivers
assign_rides_to_drivers(drivers, merged_rides)

# Streamlit Dashboard
def create_streamlit_dashboard(drivers, merged_rides):
    """
    Create a Streamlit dashboard displaying driver ride assignments.
    """
    # Set up Streamlit app
    st.set_page_config(
        page_title="Driver Assignment Dashboard",
        page_icon="🚗",
        layout="wide",
    )
    
    st.title("🚗 Driver Assignment Dashboard")
    st.write("View assigned rides and driver status")
    
    # Summary metrics
    total_rides = sum(len(driver.assigned_rides) for driver in drivers)
    total_drivers = len(drivers)
    avg_rides = total_rides / total_drivers if total_drivers > 0 else 0
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Drivers", total_drivers)
    col2.metric("Total Assigned Rides", total_rides)
    col3.metric("Avg. Rides per Driver", f"{avg_rides:.1f}")
    
    # Driver-specific tables
    st.header("Driver Assignments")
    
    for driver in drivers:
        with st.expander(f"Driver: {driver.name} (Home: {driver.home_location})", expanded=True):
            if driver.assigned_rides:
                # Create data for this driver's rides
                driver_data = []
                
                for ride in driver.assigned_rides:
                    # Calculate travel time from driver's location to ride start
                    travel_time, _, _ = get_route(driver.current_location, ride.start)
                    
                    # Calculate waiting time (if any)
                    ride_arrival_datetime = datetime.combine(datetime.today(), ride.arrival_time)
                    current_datetime = datetime.combine(datetime.today(), driver.current_time)
                    waiting_time = max(0, (ride_arrival_datetime - current_datetime).total_seconds() / 3600)
                    
                    # Calculate end time after completing the ride
                    end_time = (ride_arrival_datetime + timedelta(hours=ride.duration)).time()
                    
                    driver_data.append({
                        "Initial Destination": ride.start,
                        "Final Destination": ride.end,
                        "Arrival Time": ride.arrival_time.strftime("%H:%M"),
                        "End Time": end_time.strftime("%H:%M"),
                        "Travel Duration (hrs)": f"{travel_time:.2f}",
                        "Home Location": driver.home_location,
                        "Home Reaching Time": (datetime.combine(datetime.today(), driver.current_time) + 
                                              timedelta(hours=travel_time + ride.duration)).time().strftime("%H:%M")
                    })
                
                if driver_data:
                    df = pd.DataFrame(driver_data)
                    st.table(df)
            else:
                st.write("No rides assigned to this driver.")
    
    # Unassigned rides
    unassigned_rides = [ride for ride in merged_rides if not ride.is_assigned]
    if unassigned_rides:
        st.header("Unassigned Rides")
        unassigned_data = []
        for ride in unassigned_rides:
            _, distance, _ = get_route(ride.start, ride.end)
            unassigned_data.append({
                "From": ride.start,
                "To": ride.end,
                "Distance (km)": f"{distance / 1000:.2f}",
                "Duration (hrs)": f"{ride.duration:.2f}",
                "Arrival Time": ride.arrival_time.strftime("%H:%M")
            })
        
        if unassigned_data:
            st.table(pd.DataFrame(unassigned_data))
    else:
        st.success("All rides have been assigned!")

# Run the Streamlit dashboard
if __name__ == "__main__":
    create_streamlit_dashboard(drivers, merged_rides)