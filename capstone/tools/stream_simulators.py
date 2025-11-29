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
            "Breaking: Flooding confirmed in {location} after heavy rainfall. Multiple homes damaged.",
            "Floodwaters have risen unexpectedly in {location}, causing widespread damage to infrastructure.",
            "Local authorities announced evacuation orders for {location} due to rising floodwaters.",
            "Severe flooding occurred in {location} overnight, affecting hundreds of residents.",
            "Emergency services stated that flooding in {location} is the worst in decades.",
            "Flash flooding happened in {location} within minutes, catching residents off guard.",
            "Flood situation in {location} has resulted in multiple road closures and power outages.",
            "Rescue teams are working to evacuate stranded residents in {location} flood zone.",
            "Meteorologists confirmed that more rain is expected in {location}, worsening flood conditions.",
            "Community centers in {location} have been opened as temporary shelters for flood victims.",
            "Flood damage assessment underway in {location}, with preliminary reports showing extensive property loss.",
            "Volunteers are being mobilized to assist with flood relief efforts in {location}.",
            "Insurance companies reporting surge in claims from {location} flood-affected areas.",
            "Flood warning systems activated across {location} as water levels continue to rise.",
            "Agricultural areas in {location} severely affected by flooding, threatening crop yields.",
            "Drainage systems overwhelmed in {location}, leading to urban flooding throughout the city.",
            "Environmental agency stated that floodwaters in {location} may contain hazardous materials.",
        ],
        "fire": [
            "🔥 Large fire reported at {location}. Smoke visible from miles away.",
            "Breaking: Fire crews responding to major blaze in {location}. #fire",
            "Massive fire in {location}. Residents evacuating. Stay away from the area!",
            "Fire spreading rapidly in {location}. Multiple buildings affected.",
            "Emergency: Structure fire at {location}. Heavy smoke reported.",
            "Wildfire confirmed burning out of control in {location} hills. Evacuation orders issued.",
            "Fire officials announced that the blaze in {location} has consumed hundreds of acres.",
            "Multiple fire trucks dispatched to {location} after explosion reported at industrial site.",
            "Firefighter injuries confirmed in {location} warehouse fire incident.",
            "Authorities stated that cause of {location} fire is under investigation.",
            "Brush fire occurred near {location}, threatening nearby residential areas.",
            "Fire damage assessment shows extensive structural damage in {location} business district.",
            "Emergency evacuation underway in {location} as wildfire approaches city limits.",
            "Fire crews working tirelessly to contain blaze in {location} forested area.",
            "Air quality alerts issued for {location} due to smoke from ongoing fire.",
            "Fire hydrant system damaged in {location}, complicating firefighting efforts.",
            "Historic building lost in {location} fire, community mourns cultural loss.",
            "Fire investigators confirmed arson as cause of {location} apartment complex fire.",
            "Volunteer firefighters injured while battling blaze in {location} rural area.",
            "Power lines down in {location} after fire damaged electrical infrastructure.",
            "Fire department announced new safety measures for {location} industrial zone.",
            "Smoke inhalation cases reported at {location} fire, medical teams responding.",
        ],
        "power_outage": [
            "Power outage affecting {location}. Thousands without electricity.",
            "Blackout in {location}. Traffic lights down. Drive carefully!",
            "Major power outage in {location}. No ETA on restoration. #poweroutage",
            "Entire {location} area without power. Grid failure suspected.",
            "Rolling blackouts hitting {location}. Stay prepared!",
            "Utility company confirmed widespread power outage in {location} after transformer explosion.",
            "Emergency services reported increased calls in {location} due to power outage complications.",
            "Power restoration efforts ongoing in {location}, but full service may take hours.",
            "Hospital backup generators activated in {location} after power failure reported.",
            "Traffic accidents increased in {location} following power outage at major intersections.",
            "Water treatment plant in {location} affected by power outage, issuing boil water advisory.",
            "Business owners in {location} reporting significant losses due to extended power outage.",
            "Utility crews stated that severe weather damaged transmission lines serving {location}.",
            "Schools closed in {location} after power outage affected heating and lighting systems.",
            "Generator sales surge in {location} as residents prepare for potential extended outages.",
            "Power company announced rolling blackouts will continue in {location} through the weekend.",
            "Communication towers down in {location}, affecting cell phone service during outage.",
            "Food spoilage reported in {location} as refrigeration systems fail during power outage.",
            "Emergency shelters opened in {location} for residents without power or heat.",
            "Power restoration prioritized for hospitals and critical infrastructure in {location}.",
            "Utility company investigating if cyberattack caused power outage in {location}.",
            "Solar panel installations seeing increased interest in {location} after power outage.",
        ],
        "traffic": [
            "Major accident on {location}. Traffic at standstill. Avoid if possible.",
            "Multi-vehicle collision in {location}. Emergency services on scene.",
            "Traffic nightmare in {location}. Highway completely blocked.",
            "Serious accident in {location}. Expect major delays. #traffic",
            "Road closure in {location} due to accident. Find alternate routes.",
            "Fatal accident reported on {location}, investigation underway at the scene.",
            "Traffic congestion in {location} worsened after multi-car pileup occurred during rush hour.",
            "Emergency responders confirmed multiple injuries in {location} highway accident.",
            "Police stated that weather conditions may have contributed to {location} traffic incident.",
            "Road debris cleanup ongoing in {location} after truck accident caused hazardous conditions.",
            "Commuter frustration mounting in {location} as traffic delays exceed two hours.",
            "Public transportation system affected in {location} following bridge closure due to accident.",
            "Traffic patterns rerouted in {location} while authorities investigate serious collision.",
            "Witnesses reported seeing the accident happen in {location} moments before emergency crews arrived.",
            "Road rage incident escalated to physical altercation on {location}, police investigating.",
            "Construction zone accident in {location} resulted in worker injuries and lane closures.",
            "Traffic camera footage reviewed to determine cause of {location} intersection collision.",
            "Ambulance services overwhelmed in {location} responding to multiple traffic accidents.",
            "School zone safety concerns raised after child injured in {location} crosswalk incident.",
            "Insurance claims expected to rise following major traffic accident in {location}.",
            "Traffic enforcement increased in {location} after spike in accident reports.",
            "Public outcry grows over dangerous intersection in {location} following fatal accident.",
        ],
        "weather": [
            "Severe storm hitting {location}. Take shelter immediately!",
            "Tornado warning for {location}. Seek shelter now! #tornado #emergency",
            "Hurricane force winds in {location}. Stay indoors!",
            "Extreme weather alert for {location}. Dangerous conditions.",
            "Hailstorm damaging vehicles in {location}. Take cover!",
            "Meteorologists confirmed severe weather system developing near {location}, potential tornadoes reported.",
            "Emergency management announced state of emergency for {location} due to extreme weather conditions.",
            "Weather service stated that unprecedented storm system approaching {location} from the west.",
            "Severe weather outbreak occurred in {location}, with multiple tornadoes confirmed touching down.",
            "Storm damage assessment shows widespread destruction across {location} communities.",
            "Rescue operations underway in {location} after flash flooding resulted from intense rainfall.",
            "National Guard deployed to {location} to assist with weather-related emergency response.",
            "Weather experts stated that climate patterns may be contributing to increased severe weather in {location}.",
            "Powerful wind gusts reported in {location}, causing structural damage and downed trees.",
            "Coastal areas in {location} under evacuation orders as hurricane makes landfall.",
            "Emergency shelters at capacity in {location} as residents flee from approaching storm system.",
            "Weather radar shows intense thunderstorm activity developing over {location}, lightning strikes confirmed.",
            "Agricultural losses reported in {location} after hailstorm destroyed crops across farming regions.",
            "Search and rescue teams deployed in {location} after landslide occurred during heavy rains.",
            "Weather service issued red flag warning for {location} due to extreme fire danger conditions.",
            "Winter storm warning for {location} as freezing temperatures and snow expected to cause hazardous travel.",
            "Heat wave emergency declared in {location} as temperatures exceeded dangerous levels for extended period.",
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
            "METEOROLOGICAL AGENCY CONFIRMED: Tornado touchdown reported in {location}. {action}",
            "WEATHER EMERGENCY: Severe thunderstorm confirmed in {location} with damaging winds. {action}",
            "CLIMATE CENTER ANNOUNCED: Extreme heat wave affecting {location}. {action}",
            "FLOOD WARNING: Major flooding occurred in {location} river basin. {action}",
            "WEATHER SERVICE STATED: Hurricane-force winds confirmed in {location}. {action}",
            "STORM SYSTEM: Severe weather outbreak resulted in multiple emergencies across {location}. {action}",
            "WINTER WEATHER: Heavy snowfall reported in {location} causing dangerous travel conditions. {action}",
            "LIGHTNING THREAT: Multiple lightning strikes confirmed in {location} area. {action}",
            "COASTAL WARNING: Storm surge flooding confirmed along {location} coastline. {action}",
            "WILDFIRE WEATHER: Extreme fire danger conditions reported in {location}. {action}",
            "ATMOSPHERIC RIVER: Intense rainfall confirmed in {location} causing flash flooding. {action}",
            "ICE STORM: Freezing rain reported in {location} creating hazardous conditions. {action}",
            "DUST STORM: Severe dust conditions confirmed in {location} reducing visibility. {action}",
            "WIND ADVISORY: Gale-force winds reported in {location} causing structural damage. {action}",
            "AVALANCHE WARNING: Snow conditions in {location} mountains deemed unstable. {action}",
            "TSUNAMI WARNING: Seismic event resulted in tsunami threat for {location} coastal areas. {action}",
            "HEAT INDEX: Extreme heat confirmed in {location} with heat-related illnesses reported. {action}",
            "FROST WARNING: Record low temperatures expected in {location} affecting infrastructure. {action}",
            "AIR QUALITY: Smoke from wildfires affecting {location} air quality to hazardous levels. {action}",
        ],
        "evacuation": [
            "EVACUATION ORDER: Mandatory evacuation for {location}. {action}",
            "EMERGENCY EVACUATION: Residents of {location} must evacuate immediately. {action}",
            "EVACUATION NOTICE: {severity} situation in {location}. {action}",
            "MANDATORY EVACUATION: Fire threat confirmed in {location}. All residents must evacuate. {action}",
            "EVACUATION SHELTERS: Emergency shelters opened for {location} residents affected by disaster. {action}",
            "HURRICANE EVACUATION: Storm surge threat confirmed for {location} coastal areas. {action}",
            "CHEMICAL PLUME: Hazardous materials release reported in {location}. Evacuate immediately. {action}",
            "FLOOD EVACUATION: Rising waters confirmed in {location} requiring immediate evacuation. {action}",
            "WILDFIRE EVACUATION: Fire front approaching {location} communities. Evacuate now. {action}",
            "TORNADO WARNING: Multiple tornadoes confirmed in {location} area. Seek shelter. {action}",
            "STRUCTURAL FAILURE: Building damage reported in {location} requiring evacuation of surrounding area. {action}",
            "CONTAMINATION: Biological agent detected in {location}. Immediate evacuation required. {action}",
            "LANDSLIDE RISK: Geological instability confirmed in {location} hills. Evacuate immediately. {action}",
            "UTILITY EXPLOSION: Gas main rupture reported in {location}. Evacuate one-mile radius. {action}",
            "RADIOLOGICAL THREAT: Nuclear incident confirmed in {location}. Evacuate to safe zones. {action}",
            "PANDEMIC QUARANTINE: Disease outbreak confirmed in {location}. Mandatory isolation enforced. {action}",
            "TERRORIST THREAT: Security incident reported in {location}. Evacuate and shelter in place. {action}",
            "BRIDGE COLLAPSE: Structural failure confirmed in {location} requiring evacuation of transportation routes. {action}",
            "DAM FAILURE: Water release confirmed from {location} dam. Downstream evacuation required. {action}",
            "AIRPORT EMERGENCY: Aircraft incident reported at {location}. Evacuate terminal area. {action}",
            "PORT CLOSURE: Security threat confirmed at {location} port facilities. Evacuate immediately. {action}",
            "STADIUM EVACUATION: Structural concerns reported in {location} venue. Evacuate all occupants. {action}",
        ],
        "hazmat": [
            "HAZMAT INCIDENT: Chemical spill reported in {location}. {action}",
            "HAZARDOUS MATERIALS ALERT: {severity} incident at {location}. {action}",
            "CHEMICAL EMERGENCY: Toxic substance release in {location}. {action}",
            "CHEMICAL RELEASE: Industrial accident reported in {location} releasing toxic fumes. {action}",
            "RADIOLOGICAL EVENT: Radiation leak confirmed in {location} facility. {action}",
            "BIOLOGICAL HAZARD: Pathogen exposure reported in {location} laboratory. {action}",
            "GAS LEAK: Natural gas pipeline rupture confirmed in {location}. {action}",
            "EXPLOSION HAZARD: Chemical storage explosion reported in {location} industrial park. {action}",
            "CONTAMINATION: Water supply contamination confirmed in {location}. {action}",
            "TOXIC SMOKE: Fire resulted in hazardous smoke release in {location}. {action}",
            "AMMONIA LEAK: Refrigeration system failure reported in {location}. {action}",
            "CHLORINE RELEASE: Water treatment facility incident in {location}. {action}",
            "FUEL SPILL: Tanker accident resulted in fuel spill in {location} waterway. {action}",
            "ASBESTOS EXPOSURE: Building demolition resulted in asbestos release in {location}. {action}",
            "MERCURY SPILL: Laboratory accident reported in {location} with mercury contamination. {action}",
            "PESTICIDE DRIFT: Agricultural spraying resulted in chemical drift affecting {location}. {action}",
            "NAPALM LEAK: Military facility incident reported in {location}. {action}",
            "ACID SPILL: Manufacturing accident resulted in acid release in {location}. {action}",
            "SARIN DETECTION: Nerve agent confirmed in {location} public area. {action}",
            "METH LAB: Illegal drug lab explosion reported in {location} residential area. {action}",
            "FENTANYL CONTAMINATION: Drug manufacturing facility compromised in {location}. {action}",
            "ELECTRICAL ARC: Transformer explosion resulted in chemical release in {location}. {action}",
        ],
        "infrastructure": [
            "INFRASTRUCTURE FAILURE: {severity} damage to {location}. {action}",
            "CRITICAL INFRASTRUCTURE ALERT: System failure at {location}. {action}",
            "UTILITY EMERGENCY: Major outage affecting {location}. {action}",
            "BRIDGE COLLAPSE: Structural failure confirmed in {location} causing multiple injuries. {action}",
            "POWER GRID: System failure reported in {location} affecting millions. {action}",
            "WATER SYSTEM: Main pipe burst confirmed in {location} causing flooding and service loss. {action}",
            "COMMUNICATIONS: Network failure reported in {location} disrupting emergency services. {action}",
            "TRANSPORTATION: Major train derailment confirmed in {location} with hazardous materials. {action}",
            "BUILDING COLLAPSE: Structural failure reported in {location} high-rise building. {action}",
            "TUNNEL FLOOD: Underground transit system flooded in {location} after dam failure. {action}",
            "AIRPORT FAILURE: Runway collapse reported in {location} affecting air traffic. {action}",
            "PORT DAMAGE: Tsunami resulted in major damage to {location} port facilities. {action}",
            "DAM BREACH: Structural failure confirmed in {location} dam threatening downstream areas. {action}",
            "SUBWAY: Electrical fire reported in {location} subway system causing service disruption. {action}",
            "HOSPITAL: Power failure in {location} hospital affecting life-support systems. {action}",
            "SCHOOL: Structural damage reported in {location} school building requiring immediate evacuation. {action}",
            "FIRE STATION: Fire at {location} fire station affecting emergency response capabilities. {action}",
            "POLICE: Communications failure reported at {location} police headquarters. {action}",
            "MILITARY: Base security breach confirmed in {location} requiring immediate response. {action}",
            "NUCLEAR PLANT: Cooling system failure reported in {location} nuclear facility. {action}",
            "OIL REFINERY: Explosion and fire confirmed at {location} oil refinery with multiple injuries. {action}",
            "GAS PLANT: Processing facility failure in {location} affecting regional gas supply. {action}",
        ],
        "public_safety": [
            "PUBLIC SAFETY ALERT: {severity} incident in {location}. {action}",
            "EMERGENCY NOTIFICATION: Active situation in {location}. {action}",
            "SAFETY WARNING: Dangerous conditions in {location}. {action}",
            "SHOOTING: Active shooter reported in {location}. Shelter in place immediately. {action}",
            "BOMB THREAT: Explosive device reported in {location} public area. {action}",
            "HOSTAGE: Barricade situation confirmed in {location} with armed suspect. {action}",
            "RIOT: Civil unrest reported in {location} with property damage and injuries. {action}",
            "TERRORISM: Terrorist attack confirmed in {location} with multiple casualties reported. {action}",
            "KIDNAPPING: Child abduction reported in {location} with suspect at large. {action}",
            "SUICIDE: Individual threatening self-harm on {location} bridge. {action}",
            "FIGHT: Large-scale brawl reported in {location} entertainment district. {action}",
            "STABBING: Multiple stabbing victims reported in {location} alleyway. {action}",
            "ROBBERY: Armed robbery in progress at {location} bank. {action}",
            "ARSON: Deliberately set fire reported in {location} residential neighborhood. {action}",
            "RAPE: Sexual assault reported in {location} parking lot with suspect fleeing. {action}",
            "DRUG OVERDOSE: Multiple overdoses reported in {location} club requiring medical attention. {action}",
            "HUMAN TRAFFICKING: Suspected trafficking operation discovered in {location} with multiple victims. {action}",
            "CHILD ENDANGERMENT: Neglect case reported in {location} home with multiple children affected. {action}",
            "DOMESTIC VIOLENCE: Violent incident reported in {location} residence with weapons involved. {action}",
            "CULT INCIDENT: Mass suicide reported in {location} compound with law enforcement responding. {action}",
            "PRISON BREAK: Multiple inmates escaped from {location} correctional facility with manhunt underway. {action}",
            "CYBER ATTACK: Government systems in {location} compromised affecting public safety infrastructure. {action}",
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
        "humidity": {
            "unit": "percent",
            "normal_range": (30, 70),
            "alert_threshold": 85,
            "critical_threshold": 95,
        },
        "wind_speed": {
            "unit": "km/h",
            "normal_range": (0, 20),
            "alert_threshold": 60,
            "critical_threshold": 100,
        },
        "visibility": {
            "unit": "meters",
            "normal_range": (1000, 10000),
            "alert_threshold": 200,
            "critical_threshold": 50,
        },
        "co2_level": {
            "unit": "ppm",
            "normal_range": (400, 1000),
            "alert_threshold": 1500,
            "critical_threshold": 2000,
        },
        "noise_level": {
            "unit": "decibels",
            "normal_range": (40, 60),
            "alert_threshold": 85,
            "critical_threshold": 100,
        },
        "vibration": {
            "unit": "mm/s",
            "normal_range": (0, 2),
            "alert_threshold": 5,
            "critical_threshold": 10,
        },
        "chemical_sensor": {
            "unit": "mg/m³",
            "normal_range": (0, 1),
            "alert_threshold": 5,
            "critical_threshold": 10,
        },
        "light_level": {
            "unit": "lux",
            "normal_range": (100, 10000),
            "alert_threshold": 50,
            "critical_threshold": 5,
        },
        "soil_moisture": {
            "unit": "percent",
            "normal_range": (20, 60),
            "alert_threshold": 80,
            "critical_threshold": 95,
        },
        "gas_concentration": {
            "unit": "ppm",
            "normal_range": (0, 50),
            "alert_threshold": 200,
            "critical_threshold": 500,
        },
        "structural_stress": {
            "unit": "MPa",
            "normal_range": (0, 50),
            "alert_threshold": 80,
            "critical_threshold": 100,
        },
        "water_quality": {
            "unit": "NTU",
            "normal_range": (0, 5),
            "alert_threshold": 20,
            "critical_threshold": 50,
        },
        "energy_consumption": {
            "unit": "kW",
            "normal_range": (100, 500),
            "alert_threshold": 800,
            "critical_threshold": 1000,
        },
        "occupancy_count": {
            "unit": "people",
            "normal_range": (0, 50),
            "alert_threshold": 100,
            "critical_threshold": 150,
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