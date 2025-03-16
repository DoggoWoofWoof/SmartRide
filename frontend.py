import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from geopy.distance import geodesic
from geopy.geocoders import Nominatim

# Initialize geocoder
geolocator = Nominatim(user_agent="ride_share_app")

# Set page config
st.set_page_config(
    page_title="RideShare Pro",
    page_icon="🚗",
    layout="wide"
)

# Mock data for ride assignments
MOCK_RIDES = [
    {"start": "Indiranagar", "end": "Koramangala", "duration": 1},
    {"start": "Koramangala", "end": "HSR Layout", "duration": 2},
    {"start": "HSR Layout", "end": "Whitefield", "duration": 1},
    {"start": "Whitefield", "end": "Indiranagar", "duration": 3},
    {"start": "Koramangala", "end": "BTM Layout", "duration": 5},
    {"start": "BTM Layout", "end": "Indiranagar", "duration": 2},
    {"start": "HSR Layout", "end": "Indiranagar", "duration": 1},
    {"start": "Whitefield", "end": "Koramangala", "duration": 4},
    {"start": "Koramangala", "end": "Indiranagar", "duration": 2},
    {"start": "Indiranagar", "end": "BTM Layout", "duration": 3}
]

# Hardcoded data
DRIVERS = {
    "driver1": {
        "username": "john_doe",
        "home_location": "Indiranagar, Bangalore",
        "work_hours": {"start": "09:00", "end": "18:00"},
        "preferred_areas": ["Indiranagar", "Koramangala", "HSR Layout"],
        "rating": 4.8,
        "peak_hour_rides": {
            "completed": 15,
            "required": 20
        },
        "current_ride": None,
        "assigned_rides": [],
        "current_location": "Indiranagar"
    },
    "driver2": {
        "username": "jane_smith",
        "home_location": "Koramangala, Bangalore",
        "work_hours": {"start": "08:00", "end": "17:00"},
        "preferred_areas": ["Koramangala", "BTM Layout", "Marathahalli"],
        "rating": 4.9,
        "peak_hour_rides": {
            "completed": 22,
            "required": 20
        },
        "current_ride": None,
        "assigned_rides": [],
        "current_location": "Koramangala"
    }
}

# Initialize session state
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.user_type = None
    st.session_state.user_data = None
    st.session_state.assigned_rides = {}

def assign_rides(drivers, rides):
    """Assign rides to drivers based on preferences and optimization rules"""
    assignments = {driver_id: [] for driver_id in drivers.keys()}
    current_locations = {driver_id: drivers[driver_id]["current_location"] for driver_id in drivers.keys()}
    
    for ride in rides:
        best_driver = None
        best_score = -1
        
        for driver_id, driver in drivers.items():
            if len(assignments[driver_id]) >= 5:  # Limit rides per driver
                continue
                
            if ride["start"] != current_locations[driver_id]:
                continue
                
            score = 0
            # Preference matching
            if ride["end"] in driver["preferred_areas"]:
                score += 10
                
            # End of day optimization
            current_time = datetime.strptime(datetime.now().strftime("%H:%M"), "%H:%M")
            end_time = datetime.strptime(driver["work_hours"]["end"], "%H:%M")
            time_diff = (end_time - current_time).total_seconds() / 3600
            
            if 0 <= time_diff <= 2 and ride["end"] in driver["home_location"]:
                score += 15
                
            if score > best_score:
                best_score = score
                best_driver = driver_id
        
        if best_driver:
            assignments[best_driver].append(ride)
            current_locations[best_driver] = ride["end"]
            
    return assignments

def calculate_route_segments(start_location, end_location):
    """Calculate intermediate points for long-distance ride segmentation"""
    # Hardcoded segments for demonstration
    segments = {
        ("Indiranagar", "Whitefield"): ["Indiranagar", "Marathahalli", "Whitefield"],
        ("Koramangala", "Hebbal"): ["Koramangala", "Indiranagar", "Hebbal"],
        ("HSR Layout", "Yeshwantpur"): ["HSR Layout", "Koramangala", "Indiranagar", "Yeshwantpur"]
    }
    
    for (start, end), route in segments.items():
        if start_location.lower() in start.lower() and end_location.lower() in end.lower():
            return route
    
    return [start_location, end_location]

def is_peak_hour():
    """Check if current time is during peak hours (7-10 AM or 4-7 PM)"""
    current_time = datetime.now().time()
    morning_peak = (7 <= current_time.hour < 10)
    evening_peak = (16 <= current_time.hour < 19)
    return morning_peak or evening_peak

def calculate_driver_score(driver_data, pickup_location, dropoff_location):
    """Calculate driver score based on various factors"""
    score = 0
    
    # Check if location is in preferred areas
    if pickup_location in driver_data['preferred_areas']:
        score += 10
        
    # Check end-of-day optimization
    current_time = datetime.strptime(datetime.now().strftime("%H:%M"), "%H:%M")
    end_time = datetime.strptime(driver_data['work_hours']['end'], "%H:%M")
    time_diff = (end_time - current_time).total_seconds() / 3600
    
    if 0 <= time_diff <= 2:  # Last 2 hours of shift
        if dropoff_location in driver_data['home_location']:
            score += 15
            
    # Check peak hour commitment
    if is_peak_hour() and driver_data['peak_hour_rides']['completed'] < driver_data['peak_hour_rides']['required']:
        score += 8
        
    return score

def driver_dashboard():
    st.title("Driver Dashboard 🚗")
    
    # Select driver for demonstration
    selected_driver = st.selectbox("Select Driver", list(DRIVERS.keys()))
    driver_data = DRIVERS[selected_driver]
    
    # Update work preferences
    st.header("Update Work Preferences")
    col1, col2 = st.columns(2)
    
    with col1:
        home_location = st.text_input("Home Location", value=driver_data['home_location'])
        work_start = st.time_input("Work Start Time", datetime.strptime(driver_data['work_hours']['start'], "%H:%M"))
        work_end = st.time_input("Work End Time", datetime.strptime(driver_data['work_hours']['end'], "%H:%M"))
        
    with col2:
        preferred_areas = st.multiselect(
            "Preferred Areas (Max 5)",
            ["Indiranagar", "Koramangala", "HSR Layout", "BTM Layout", "Whitefield", "Marathahalli"],
            default=driver_data['preferred_areas'],
            max_selections=5
        )
        
        peak_hour_slots = st.multiselect(
            "Preferred Peak Hour Slots",
            ["Morning (7-10 AM)", "Evening (4-7 PM)"]
        )
    
    if st.button("Update Preferences"):
        st.success("Preferences updated successfully!")
    
    # Ride Assignments Section
    st.header("Ride Assignments")
    if st.button("Get New Assignments"):
        assignments = assign_rides(DRIVERS, MOCK_RIDES)
        st.session_state.assigned_rides = assignments
        st.success("New rides assigned!")
        
    if hasattr(st.session_state, 'assigned_rides') and selected_driver in st.session_state.assigned_rides:
        for ride in st.session_state.assigned_rides[selected_driver]:
            st.info(f"🚗 {ride['start']} → {ride['end']} (Duration: {ride['duration']} hours)")
    
    # Active Ride Section
    st.header("Active Ride")
    if driver_data['current_ride']:
        ride_data = driver_data['current_ride']
        st.info(f"Current ride: {ride_data['pickup']} → {ride_data['dropoff']}")
        
        if st.button("Complete Ride"):
            accept_return = st.checkbox("Accept return ride from drop-off location?")
            if accept_return:
                st.success("We'll notify you of matching return rides!")
            st.success("Ride completed successfully!")
            
    # Earnings & Incentives Section
    st.header("Earnings & Incentives")
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Peak Hour Progress")
        peak_rides = driver_data['peak_hour_rides']
        required = peak_rides['required']
        completed = peak_rides['completed']
        
        progress = completed / required
        st.progress(progress)
        st.write(f"Completed: {completed}/{required} peak hour rides")
        
    with col2:
        st.subheader("Bonus Status")
        if completed > required:
            bonus = (completed - required) * 50  # ₹50 bonus per extra peak ride
            st.success(f"Extra Peak Ride Bonus: ₹{bonus}")
        else:
            remaining = required - completed
            st.info(f"Complete {remaining} more peak rides for bonus!")

def passenger_dashboard():
    st.title("Passenger Dashboard 🚕")
    
    # Book a Ride
    st.header("Book a Ride")
    col1, col2 = st.columns(2)
    
    with col1:
        pickup = st.text_input("Pickup Location", "Indiranagar")
        
    with col2:
        dropoff = st.text_input("Drop-off Location", "Whitefield")
        
    if st.button("Check Route"):
        if pickup and dropoff:
            segments = calculate_route_segments(pickup, dropoff)
            
            if len(segments) > 2:
                st.info("This is a long-distance ride. We'll split it into segments for better service!")
                for i, segment in enumerate(segments[:-1]):
                    st.write(f"Segment {i+1}: {segment} → {segments[i+1]}")
                    
            available_drivers = [d for d in DRIVERS.values() if not d['current_ride']]
            if available_drivers:
                st.success(f"Found {len(available_drivers)} available drivers!")
                
                # Score and sort drivers
                scored_drivers = []
                for driver in available_drivers:
                    score = calculate_driver_score(driver, pickup, dropoff)
                    scored_drivers.append((score, driver))
                
                scored_drivers.sort(reverse=True)
                
                # Display top 3 drivers
                st.subheader("Recommended Drivers")
                for score, driver in scored_drivers[:3]:
                    st.write(f"Driver: {driver['username']} (Rating: {driver['rating']})")
                    
                if st.button("Book Now"):
                    st.success("Ride booked successfully!")
            else:
                st.error("No drivers available at the moment. Please try again later.")

def main():
    if not st.session_state.logged_in:
        st.title("Welcome to RideShare Pro 🚗")
        
        # Login/Signup Section
        login_type = st.radio("Select User Type", ["Driver", "Passenger"])
        
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login")
            
            if submitted:
                st.session_state.logged_in = True
                st.session_state.user_type = login_type.lower()
                st.session_state.user_data = DRIVERS.get("driver1") if login_type == "Driver" else {}
                st.success("Login successful!")
                st.rerun()
    else:
        # Show appropriate dashboard based on user type
        if st.session_state.user_type == "driver":
            driver_dashboard()
        else:
            passenger_dashboard()
        
        if st.sidebar.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.user_type = None
            st.session_state.user_data = None
            st.rerun()

if __name__ == "__main__":
    main()