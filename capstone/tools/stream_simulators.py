"""
Event stream simulators for AgentFleet.

This module provides simulated event stream sources that generate realistic
events for testing and demonstration purposes.
"""

import random
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Iterator
from dataclasses import dataclass
import uuid


@dataclass
class StreamConfig:
    """Configuration for event stream simulators."""
    event_rate: float = 1.0  # Events per second
    burst_probability: float = 0.1  # Probability of burst events
    burst_size: int = 5  # Number of events in a burst


class TwitterStreamSimulator:
    """
    Simulates a Twitter-like social media event stream.
    
    Generates realistic tweets about various incident types including
    natural disasters, infrastructure issues, and public safety concerns.
    """
    
    # Tweet templates for different incident types
    TWEET_TEMPLATES = {
        "flooding": [
            "Major flooding reported in {location}! Water levels rising rapidly. #emergency",
            "Streets completely flooded in {location}. Cars stranded. Stay safe everyone!",
            "⚠️ Flash flood warning for {location}. Avoid downtown area. #flood #safety",
            "Unprecedented flooding in {location}. Emergency services overwhelmed.",
            "Water main break causing massive flooding in {location}. Multiple streets closed.",
        ],
        "fire": [
            "🔥 Large fire reported at {location}. Smoke visible from miles away.",
            "Breaking: Fire crews responding to major blaze in {location}. #fire",
            "Massive fire in {location}. Residents evacuating. Stay away from the area!",
            "Fire spreading rapidly in {location}. Multiple buildings affected.",
            "Emergency: Structure fire at {location}. Heavy smoke reported.",
        ],
        "power_outage": [
            "Power outage affecting {location}. Thousands without electricity.",
            "Blackout in {location}. Traffic lights down. Drive carefully!",
            "Major power outage in {location}. No ETA on restoration. #poweroutage",
            "Entire {location} area without power. Grid failure suspected.",
            "Rolling blackouts hitting {location}. Stay prepared!",
        ],
        "traffic": [
            "Major accident on {location}. Traffic at standstill. Avoid if possible.",
            "Multi-vehicle collision in {location}. Emergency services on scene.",
            "Traffic nightmare in {location}. Highway completely blocked.",
            "Serious accident in {location}. Expect major delays. #traffic",
            "Road closure in {location} due to accident. Find alternate routes.",
        ],
        "weather": [
            "Severe storm hitting {location}. Take shelter immediately!",
            "Tornado warning for {location}. Seek shelter now! #tornado #emergency",
            "Hurricane force winds in {location}. Stay indoors!",
            "Extreme weather alert for {location}. Dangerous conditions.",
            "Hailstorm damaging vehicles in {location}. Take cover!",
        ],
    }
    
    LOCATIONS = [
        "downtown", "Main Street", "the financial district", "the waterfront",
        "Highway 101", "Central Station", "the industrial park", "Oak Avenue",
        "the shopping district", "River Road", "the university campus", "Park Plaza",
    ]
    
    HASHTAGS = [
        "#emergency", "#breaking", "#alert", "#news", "#local",
        "#safety", "#warning", "#update", "#urgent", "#crisis",
    ]
    
    def __init__(self, config: Optional[StreamConfig] = None):
        """
        Initialize Twitter stream simulator.
        
        Args:
            config: Stream configuration (uses defaults if not provided)
        """
        self.config = config or StreamConfig()
        self.is_active = False
        self.event_count = 0
    
    def generate_event(self) -> Dict[str, Any]:
        """
        Generate a single simulated tweet event.
        
        Returns:
            Dictionary containing tweet data
        """
        incident_type = random.choice(list(self.TWEET_TEMPLATES.keys()))
        template = random.choice(self.TWEET_TEMPLATES[incident_type])
        location = random.choice(self.LOCATIONS)
        
        # Generate tweet content
        content = template.format(location=location)
        
        # Add random hashtags
        if random.random() > 0.5:
            content += " " + random.choice(self.HASHTAGS)
        
        # Generate metadata
        self.event_count += 1
        event = {
            "source": "twitter",
            "timestamp": datetime.utcnow().isoformat(),
            "content": content,
            "metadata": {
                "tweet_id": str(uuid.uuid4()),
                "user": f"user_{random.randint(1000, 9999)}",
                "retweets": random.randint(0, 500),
                "likes": random.randint(0, 1000),
                "incident_type": incident_type,
                "location": location,
                "verified_user": random.random() > 0.7,
            }
        }
        
        return event
    
    def stream(self, duration: Optional[float] = None) -> Iterator[Dict[str, Any]]:
        """
        Generate a continuous stream of tweet events.
        
        Args:
            duration: Optional duration in seconds (infinite if None)
            
        Yields:
            Tweet event dictionaries
        """
        self.is_active = True
        start_time = time.time()
        
        while self.is_active:
            # Check duration limit
            if duration and (time.time() - start_time) >= duration:
                break
            
            # Determine if this is a burst event
            is_burst = random.random() < self.config.burst_probability
            num_events = self.config.burst_size if is_burst else 1
            
            # Generate events
            for _ in range(num_events):
                yield self.generate_event()
            
            # Wait before next event
            if not is_burst:
                time.sleep(1.0 / self.config.event_rate)
            else:
                time.sleep(0.1)  # Small delay between burst events
        
        self.is_active = False
    
    def stop(self):
        """Stop the event stream."""
        self.is_active = False


class EmergencyFeedSimulator:
    """
    Simulates an emergency alert system feed.
    
    Generates official emergency alerts from government agencies,
    weather services, and emergency management systems.
    """
    
    ALERT_TEMPLATES = {
        "weather": [
            "SEVERE WEATHER ALERT: {severity} conditions expected in {location}. {action}",
            "WEATHER WARNING: {severity} weather system approaching {location}. {action}",
            "NATIONAL WEATHER SERVICE: {severity} alert for {location}. {action}",
        ],
        "evacuation": [
            "EVACUATION ORDER: Mandatory evacuation for {location}. {action}",
            "EMERGENCY EVACUATION: Residents of {location} must evacuate immediately. {action}",
            "EVACUATION NOTICE: {severity} situation in {location}. {action}",
        ],
        "hazmat": [
            "HAZMAT INCIDENT: Chemical spill reported in {location}. {action}",
            "HAZARDOUS MATERIALS ALERT: {severity} incident at {location}. {action}",
            "CHEMICAL EMERGENCY: Toxic substance release in {location}. {action}",
        ],
        "infrastructure": [
            "INFRASTRUCTURE FAILURE: {severity} damage to {location}. {action}",
            "CRITICAL INFRASTRUCTURE ALERT: System failure at {location}. {action}",
            "UTILITY EMERGENCY: Major outage affecting {location}. {action}",
        ],
        "public_safety": [
            "PUBLIC SAFETY ALERT: {severity} incident in {location}. {action}",
            "EMERGENCY NOTIFICATION: Active situation in {location}. {action}",
            "SAFETY WARNING: Dangerous conditions in {location}. {action}",
        ],
    }
    
    SEVERITY_LEVELS = ["CRITICAL", "HIGH", "MODERATE", "LOW"]
    
    ACTIONS = [
        "Shelter in place immediately",
        "Avoid the area",
        "Follow official instructions",
        "Monitor local news for updates",
        "Prepare for possible evacuation",
        "Stay indoors and secure windows",
        "Seek higher ground",
        "Move to designated safe zones",
    ]
    
    LOCATIONS = [
        "Zone A (Downtown)", "Zone B (North District)", "Zone C (South District)",
        "Sector 1", "Sector 2", "Sector 3", "County-wide", "City Center",
        "Industrial Zone", "Residential Area", "Coastal Region", "River Valley",
    ]
    
    AGENCIES = [
        "National Weather Service", "Emergency Management Agency",
        "Department of Public Safety", "Fire Department", "Police Department",
        "Environmental Protection Agency", "Public Health Department",
    ]
    
    def __init__(self, config: Optional[StreamConfig] = None):
        """
        Initialize emergency feed simulator.
        
        Args:
            config: Stream configuration (uses defaults if not provided)
        """
        self.config = config or StreamConfig(event_rate=0.5)  # Lower rate for emergency alerts
        self.is_active = False
        self.event_count = 0
    
    def generate_event(self) -> Dict[str, Any]:
        """
        Generate a single simulated emergency alert.
        
        Returns:
            Dictionary containing alert data
        """
        alert_type = random.choice(list(self.ALERT_TEMPLATES.keys()))
        template = random.choice(self.ALERT_TEMPLATES[alert_type])
        severity = random.choice(self.SEVERITY_LEVELS)
        location = random.choice(self.LOCATIONS)
        action = random.choice(self.ACTIONS)
        agency = random.choice(self.AGENCIES)
        
        # Generate alert content
        content = template.format(
            severity=severity,
            location=location,
            action=action
        )
        
        # Generate metadata
        self.event_count += 1
        event = {
            "source": "emergency",
            "timestamp": datetime.utcnow().isoformat(),
            "content": content,
            "metadata": {
                "alert_id": f"ALERT-{uuid.uuid4().hex[:8].upper()}",
                "agency": agency,
                "severity": severity,
                "alert_type": alert_type,
                "location": location,
                "expires": (datetime.utcnow() + timedelta(hours=2)).isoformat(),
                "priority": 1 if severity in ["CRITICAL", "HIGH"] else 2,
            }
        }
        
        return event
    
    def stream(self, duration: Optional[float] = None) -> Iterator[Dict[str, Any]]:
        """
        Generate a continuous stream of emergency alerts.
        
        Args:
            duration: Optional duration in seconds (infinite if None)
            
        Yields:
            Emergency alert dictionaries
        """
        self.is_active = True
        start_time = time.time()
        
        while self.is_active:
            # Check duration limit
            if duration and (time.time() - start_time) >= duration:
                break
            
            # Generate event
            yield self.generate_event()
            
            # Wait before next event
            time.sleep(1.0 / self.config.event_rate)
        
        self.is_active = False
    
    def stop(self):
        """Stop the event stream."""
        self.is_active = False


class SensorDataSimulator:
    """
    Simulates IoT sensor data streams.
    
    Generates sensor readings from various monitoring systems including
    environmental sensors, infrastructure monitors, and safety systems.
    """
    
    SENSOR_TYPES = {
        "water_level": {
            "unit": "meters",
            "normal_range": (0.5, 2.0),
            "alert_threshold": 3.0,
            "critical_threshold": 4.0,
        },
        "temperature": {
            "unit": "celsius",
            "normal_range": (15, 30),
            "alert_threshold": 40,
            "critical_threshold": 50,
        },
        "air_quality": {
            "unit": "AQI",
            "normal_range": (0, 50),
            "alert_threshold": 150,
            "critical_threshold": 300,
        },
        "seismic": {
            "unit": "magnitude",
            "normal_range": (0, 2.0),
            "alert_threshold": 4.0,
            "critical_threshold": 6.0,
        },
        "pressure": {
            "unit": "kPa",
            "normal_range": (95, 105),
            "alert_threshold": 90,
            "critical_threshold": 85,
        },
        "radiation": {
            "unit": "μSv/h",
            "normal_range": (0.05, 0.2),
            "alert_threshold": 1.0,
            "critical_threshold": 5.0,
        },
    }
    
    LOCATIONS = [
        "Sensor-A1", "Sensor-A2", "Sensor-B1", "Sensor-B2",
        "Sensor-C1", "Sensor-C2", "Monitor-01", "Monitor-02",
        "Station-North", "Station-South", "Station-East", "Station-West",
    ]
    
    def __init__(self, config: Optional[StreamConfig] = None):
        """
        Initialize sensor data simulator.
        
        Args:
            config: Stream configuration (uses defaults if not provided)
        """
        self.config = config or StreamConfig(event_rate=2.0)  # Higher rate for sensor data
        self.is_active = False
        self.event_count = 0
        self.sensor_states = {}  # Track sensor values for continuity
    
    def generate_event(self) -> Dict[str, Any]:
        """
        Generate a single simulated sensor reading.
        
        Returns:
            Dictionary containing sensor data
        """
        sensor_type = random.choice(list(self.SENSOR_TYPES.keys()))
        sensor_config = self.SENSOR_TYPES[sensor_type]
        location = random.choice(self.LOCATIONS)
        sensor_id = f"{location}-{sensor_type}"
        
        # Get or initialize sensor state
        if sensor_id not in self.sensor_states:
            # Start with normal value
            min_val, max_val = sensor_config["normal_range"]
            self.sensor_states[sensor_id] = random.uniform(min_val, max_val)
        
        # Simulate value drift (mostly normal, occasionally anomalous)
        current_value = self.sensor_states[sensor_id]
        
        if random.random() < 0.05:  # 5% chance of anomaly
            # Generate anomalous reading
            if random.random() < 0.5:
                value = random.uniform(
                    sensor_config["alert_threshold"],
                    sensor_config["critical_threshold"]
                )
            else:
                value = sensor_config["critical_threshold"] * random.uniform(1.0, 1.5)
        else:
            # Normal drift
            min_val, max_val = sensor_config["normal_range"]
            drift = random.uniform(-0.1, 0.1) * (max_val - min_val)
            value = max(min_val, min(max_val, current_value + drift))
        
        self.sensor_states[sensor_id] = value
        
        # Determine status
        if value >= sensor_config["critical_threshold"]:
            status = "CRITICAL"
        elif value >= sensor_config["alert_threshold"]:
            status = "ALERT"
        else:
            status = "NORMAL"
        
        # Generate content message
        content = f"{sensor_type.replace('_', ' ').title()} reading: {value:.2f} {sensor_config['unit']} at {location}"
        if status != "NORMAL":
            content += f" - {status} THRESHOLD EXCEEDED"
        
        # Generate metadata
        self.event_count += 1
        event = {
            "source": "sensor",
            "timestamp": datetime.utcnow().isoformat(),
            "content": content,
            "metadata": {
                "sensor_id": sensor_id,
                "sensor_type": sensor_type,
                "location": location,
                "value": value,
                "unit": sensor_config["unit"],
                "status": status,
                "reading_id": str(uuid.uuid4()),
                "calibration_date": (datetime.utcnow() - timedelta(days=random.randint(1, 90))).isoformat(),
            }
        }
        
        return event
    
    def stream(self, duration: Optional[float] = None) -> Iterator[Dict[str, Any]]:
        """
        Generate a continuous stream of sensor readings.
        
        Args:
            duration: Optional duration in seconds (infinite if None)
            
        Yields:
            Sensor reading dictionaries
        """
        self.is_active = True
        start_time = time.time()
        
        while self.is_active:
            # Check duration limit
            if duration and (time.time() - start_time) >= duration:
                break
            
            # Generate event
            yield self.generate_event()
            
            # Wait before next event
            time.sleep(1.0 / self.config.event_rate)
        
        self.is_active = False
    
    def stop(self):
        """Stop the event stream."""
        self.is_active = False
