from datetime import datetime, timedelta
import random
from collections import deque
from functools import lru_cache
import requests
from math import radians, sin, cos, sqrt, atan2
import math

# Constants for incentives and earnings
BASE_RATE_PER_KM = 10  # Base rate per kilometer in INR
PEAK_HOUR_MULTIPLIER = 1.5  # Multiplier for peak hour rides
FIXED_INCENTIVE = 50  # Fixed incentive for each ride in INR
CARPOOL_BONUS = 20  # Bonus for carpooled rides in INR

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
        self.total_earnings = 0  # Track total earnings
        self.total_distance = 0  # Track total distance traveled

# Ride class
class Ride:
    def __init__(self, start, end, duration, arrival_time, is_carpooled=False):
        self.start = start
        self.end = end
        self.duration = duration  # Duration in hours
        self.arrival_time = arrival_time  # Arrival time of the ride
        self.is_assigned = False  # Track ride assignment status
        self.is_carpooled = is_carpooled  # Track if the ride is carpooled
        self.distance = 0  # Distance in meters

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
        "X-Goog-FieldMask": "routes.duration,routes.distanceMeters,routes.polyline,routes.legs.polyline,routes.legs.steps.polyline"
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
    # Convert latitude and longitude from degrees to radians
    lat1, lon1 = map(math.radians, start)
    lat2, lon2 = map(math.radians, end)

    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    # Earth's radius in kilometers
    R = 6371.0  
    return R * c  # Distance in kilometers

# Function to decode a polyline
def decode_polyline(polyline):
    try:
        from polyline import decode
        return decode(polyline)
    except ImportError:
        print("Error: polyline library not installed. Install it using `pip install polyline`.")
        return None

# Function to reverse geocode coordinates to an address
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
                print(f"Error: No address found for coordinates ({lat}, {lon}).")
                return None
        else:
            print(f"Error: API request failed with status code {response.status_code}.")
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

# Function to check if two rides can be carpooled
def can_carpool(ride1, ride2):
    # Check if the rides share a common start or end point
    if ride1.start == ride2.start or ride1.end == ride2.end:
        # Check if the arrival times are within the duration of each other
        time_diff = abs((datetime.combine(datetime.today(), ride1.arrival_time) - 
                         datetime.combine(datetime.today(), ride2.arrival_time)).total_seconds() / 3600)
        if time_diff <= ride1.duration or time_diff <= ride2.duration:
            # Check if the total distance of the merged ride is <= 20 km
            merged_distance = get_haversine_distance(ride1.start, ride2.end)
            if merged_distance <= 20000:  # 20 km in meters
                return True
    return False

# Function to merge two rides into a carpooled ride
def merge_rides(ride1, ride2):
    # Determine the common start or end point
    if ride1.start == ride2.start:
        start = ride1.start
        end = ride1.end if ride1.duration > ride2.duration else ride2.end
    else:
        start = ride1.end if ride1.duration > ride2.duration else ride2.end
        end = ride1.end if ride1.duration > ride2.duration else ride2.end
    
    # Calculate the total duration
    total_duration = max(ride1.duration, ride2.duration)
    
    # Determine the arrival time
    arrival_time = ride1.arrival_time if ride1.duration > ride2.duration else ride2.arrival_time
    
    # Create the merged ride
    merged_ride = Ride(start, end, total_duration, arrival_time, is_carpooled=True)
    
    return merged_ride

# Generate random rides with dynamic durations and arrival times
def generate_random_rides(locations, num_rides):
    rides = []
    location_keys = list(locations.keys())
    
    # Generate regular rides
    for _ in range(num_rides - 8):  # Reserve 8 rides for carpooling
        start, end = random.sample(location_keys, 2)  # Ensure start and end are different
        while start == end:  # Avoid rides like "home to home"
            start, end = random.sample(location_keys, 2)
        
        # Calculate duration, distance, and polyline
        duration, distance, _ = get_route(locations[start], locations[end])
        if duration and distance:
            # Assign a random arrival time between 8:00 AM and 6:00 PM
            arrival_time = datetime.strptime(f"{random.randint(8, 17)}:{random.randint(0, 59)}", "%H:%M").time()
            ride = Ride(locations[start], locations[end], duration, arrival_time)
            ride.distance = distance
            
            # Check if the ride needs to be split (distance > 20 km)
            if distance > 20000:  # 20 km in meters
                print(f"Splitting ride from {ride.start} to {ride.end} (Distance: {distance / 1000:.2f} km)")
                split_result = split_ride(ride)
                if split_result:
                    rides.extend(split_result)
                else:
                    rides.append(ride)
            else:
                rides.append(ride)
    
    # Generate 8 rides that can be carpooled
    for _ in range(4):  # Create 4 pairs of carpooled rides
        start, end1, end2 = random.sample(location_keys, 3)  # Ensure start and ends are different
        duration1, distance1, _ = get_route(locations[start], locations[end1])
        duration2, distance2, _ = get_route(locations[start], locations[end2])
        
        if duration1 and duration2:
            # Assign arrival times within the same time window
            arrival_time = datetime.strptime(f"{random.randint(8, 17)}:{random.randint(0, 59)}", "%H:%M").time()
            ride1 = Ride(locations[start], locations[end1], duration1, arrival_time)
            ride1.distance = distance1
            ride2 = Ride(locations[start], locations[end2], duration2, arrival_time)
            ride2.distance = distance2
            
            # Merge the rides
            merged_ride = merge_rides(ride1, ride2)
            merged_ride.distance = distance1 + distance2
            rides.append(merged_ride)
            print(f"Merged ride from {merged_ride.start} to {merged_ride.end} (Duration: {merged_ride.duration:.2f} hours, Arrival Time: {merged_ride.arrival_time})")
    
    return rides

# Check if a driver can handle a ride
def can_handle_ride(driver, ride):
    current_datetime = datetime.combine(datetime.today(), driver.current_time)
    end_datetime = datetime.combine(datetime.today(), datetime.strptime(str(driver.work_hours[1]), "%H").time())
    
    ride_arrival_datetime = datetime.combine(datetime.today(), ride.arrival_time)
    
    if ride_arrival_datetime < current_datetime:
        # Skip this ride if it's already past the arrival time
        return False
    
    travel_time, _, _ = get_route(driver.current_location, ride.start)
    if not travel_time:
        return False
    
    departure_time = ride_arrival_datetime - timedelta(hours=travel_time)
    if current_datetime < departure_time:
        current_datetime = departure_time
    
    ride_completion_time = current_datetime + timedelta(hours=travel_time + ride.duration)
    
    # Allow drivers to extend their shift by up to 1 hour if needed
    if ride_completion_time > end_datetime + timedelta(hours=1):
        return False
    
    return True

# Assign rides to drivers using dynamic assignment with distance-based optimization
def assign_rides_to_drivers(drivers, rides):
    ride_queue = deque(sorted(rides, key=lambda x: x.arrival_time))  # Sort rides by arrival time (FCFS)
    
    while ride_queue:
        ride = ride_queue.popleft()  # Get the earliest ride
        best_driver = None
        min_total_time = float('inf')
        
        # Find the best driver for the ride
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
            assign_ride(best_driver, ride)
        else:
            print(f"No suitable driver found for ride from {ride.start} to {ride.end}.")
            # Log unassigned rides for manual assignment
            ride.is_assigned = False

# Assign a ride to a driver
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
    
    # Calculate earnings for the ride
    distance_km = ride.distance / 1000
    earnings = distance_km * BASE_RATE_PER_KM
    
    # Apply peak hour multiplier
    if 7 <= ride.arrival_time.hour <= 10 or 17 <= ride.arrival_time.hour <= 20:
        earnings *= PEAK_HOUR_MULTIPLIER
    
    # Add fixed incentive
    earnings += FIXED_INCENTIVE
    
    # Add carpool bonus if applicable
    if ride.is_carpooled:
        earnings += CARPOOL_BONUS
    
    driver.total_earnings += earnings
    driver.total_distance += distance_km
    
    print(f"Driver {driver.name} assigned ride:")
    print(f"  From {ride.start} to {ride.end} (Distance: {distance_km:.2f} km, Duration: {ride.duration:.2f} hours)")
    print(f"  Earnings: INR {earnings:.2f}")
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

# Input: Real-world locations in Bangalore (as addresses)
locations = {
    "Home1": "Indiranagar, Bangalore",
    "Home2": "Koramangala, Bangalore",
    "Home3": "Whitefield, Bangalore",
    "Home4": "Jayanagar, Bangalore",
    "Home5": "Marathahalli, Bangalore",
    "Office": "Manyata Tech Park, Bangalore",
    "Mall": "Mantri Square Mall, Sampige Road, Malleswaram, Bangalore",
    "Airport": "Kempegowda International Airport, KIAL Rd, Devanahalli, Bangalore",
    "Park": "Cubbon Park, Kasturba Road, Sampangi Rama Nagar, Bangalore",
    "Restaurant": "Toit Brewpub, Indiranagar, Bangalore",
    "Hospital": "Manipal Hospital, HAL Airport Road, Bangalore",
    "School": "Bishop Cotton Boys' School, St. Mark's Road, Bangalore",
    "Market": "KR Market, Kalasipalya, Bangalore"
}

# Drivers
drivers = [
    Driver("Driver1", locations["Home1"], [locations["Office"]], (8, 18)),  # Extended work hours
    Driver("Driver2", locations["Home2"], [locations["Park"]], (9, 19)),   # Extended work hours
    Driver("Driver3", locations["Home3"], [locations["Mall"]], (8, 17)),
    Driver("Driver4", locations["Home4"], [locations["Airport"]], (10, 20)),
    Driver("Driver5", locations["Home5"], [locations["Restaurant"]], (9, 18))
]

# Generate random rides with dynamic durations and arrival times
rides = generate_random_rides(locations, 20)  # Generate 20 random rides
print("Generated Rides:")
for ride in rides:
    _, distance, _ = get_route(ride.start, ride.end)
    print(f"  From {ride.start} to {ride.end} (Distance: {distance / 1000:.2f} km, Duration: {ride.duration:.2f} hours, Arrival Time: {ride.arrival_time})")

# Print preferred areas for each driver
for driver in drivers:
    print(f"Driver {driver.name} preferred areas: {driver.preferred_areas}")

# Set initial locations
drivers[0].current_location = locations["Home1"]
drivers[1].current_location = locations["Home2"]
drivers[2].current_location = locations["Home3"]
drivers[3].current_location = locations["Home4"]
drivers[4].current_location = locations["Home5"]

# Assign rides to drivers
assign_rides_to_drivers(drivers, rides)

## Add this function to check if a driver is near home
def is_near_home(driver):
    travel_time, _, _ = get_route(driver.current_location, driver.home_location)
    if travel_time is not None and travel_time <= 1:  # Within 1 hour of home
        return True
    return False

# Summary of driver locations and earnings
print("\n### Driver Locations and Earnings Summary ###")
for driver in drivers:
    near_home = "Yes" if is_near_home(driver) else "No"
    print(f"{driver.name} is currently at {driver.current_location}. Near home: {near_home}")
    print(f"  Total Earnings: INR {driver.total_earnings:.2f}")
    print(f"  Total Distance Traveled: {driver.total_distance:.2f} km")

# Summary of unassigned rides
unassigned_rides = [ride for ride in rides if not ride.is_assigned]
if unassigned_rides:
    print("\n### Unassigned Rides ###")
    for ride in unassigned_rides:
        _, distance, _ = get_route(ride.start, ride.end)
        print(f"  From {ride.start} to {ride.end} (Distance: {distance / 1000:.2f} km, Duration: {ride.duration:.2f} hours, Arrival Time: {ride.arrival_time})")
else:
    print("\nAll rides have been assigned.")