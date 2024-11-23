from dataclasses import dataclass
import json
import argparse
import requests
import re

GENERAL_AMENITIES = ["outdoor pool", "indoor pool", "business center", "childcare", "wifi", "dry cleaning", "breakfast"]
ROOM_AMENITIES = ["aircon", "tv", "coffee machine", "kettle", "hair dryer", "iron", "bathtub"]

@dataclass
class Hotel:
    id: str
    destination_id: str
    name: str
    description: str
    location: dict
    amenities: dict
    images: dict
    booking_conditions: list[str]


class BaseSupplier:
    def endpoint(self):
        """URL to fetch supplier data"""

    def parse(self, obj: dict) -> Hotel:
        """Parse supplier-provided data into Hotel object"""

    def fetch(self):
        url = self.endpoint()
        resp = requests.get(url)
        return [self.parse(dto) for dto in resp.json()]


class Acme(BaseSupplier):
    @staticmethod
    def endpoint():
        return 'https://5f2be0b4ffc88500167b85a0.mockapi.io/suppliers/acme'

    @staticmethod
    def parse(dto: dict) -> Hotel:
        # Split facilities into general and room-specific amenities
        def parse_amenities(facilities):
            """Categorize facilities into general and room-specific amenities."""
            general = []
            room = []
            for amenity in facilities:
                formatted = camel_to_snake_case(amenity.strip())
                if formatted in GENERAL_AMENITIES:
                    general.append(formatted)
                if formatted in ROOM_AMENITIES:
                    room.append(formatted)
            return {"general": general, "room": room}

        address = (dto["Address"] or "").strip()
        if dto["PostalCode"] and dto["PostalCode"] not in address:
            address = f"{address}, {dto['PostalCode']}"

        # Merge the address and PostalCode
        return Hotel(
            id=dto["Id"],
            destination_id=dto["DestinationId"],
            name=dto["Name"],
            description=dto["Description"] or "",
            location={
                "lat": dto["Latitude"],
                "lng": dto["Longitude"],
                "address": address,
                "city": dto["City"],
                "country": dto["Country"],
            },
            amenities=parse_amenities(dto["Facilities"] or []),
            images={"rooms": [], "site": [], "amenities": []},
            booking_conditions=[]
        )



class Paperflies(BaseSupplier):
    @staticmethod
    def endpoint():
        return 'https://5f2be0b4ffc88500167b85a0.mockapi.io/suppliers/paperflies'

    @staticmethod
    def parse(dto: dict) -> Hotel:
        location = dto.get("location", {})
        return Hotel(
            id=dto["hotel_id"],
            destination_id=dto["destination_id"],
            name=dto["hotel_name"],
            description=dto["details"] or "",
            location={
                "lat": None,
                "lng": None,
                "address": location.get("address"),
                "city": None,
                "country": location.get("country"),
            },
            amenities=dto["amenities"] or {"general": [], "room": []},
            images={
                "rooms": [
                    {"link": img["link"], "description": img["caption"]}
                    for img in (dto["images"] or {}).get("rooms", [])
                ],
                "site": [
                    {"link": img["link"], "description": img["caption"]}
                    for img in (dto["images"] or {}).get("site", [])
                ],
                "amenities": []
            },
            booking_conditions=dto.get("booking_conditions", [])
        )



class Patagonia(BaseSupplier):
    @staticmethod
    def endpoint():
        return 'https://5f2be0b4ffc88500167b85a0.mockapi.io/suppliers/patagonia'

    @staticmethod
    def parse(dto: dict) -> Hotel:
        def parse_amenities(amenities):
            #Categorize amenities into general and room-specific.

            return {
                "general": [a.lower().strip() for a in amenities if a.lower().strip() in GENERAL_AMENITIES],
                "room": [a.lower().strip() for a in amenities if a.lower().strip() in ROOM_AMENITIES],
            }
        return Hotel(
            id=dto["id"],
            destination_id=dto["destination"],
            name=dto["name"],
            description=dto["info"] or "",
            location={
                "lat": dto["lat"],
                "lng": dto["lng"],
                "address": dto["address"],
                "city": None,
                "country": None,
            },
            amenities=parse_amenities(dto["amenities"] or []),
            images={
                "rooms": [
                    {"link": img["url"], "description": img["description"]}
                    for img in (dto["images"] or {}).get("rooms", [])
                ],
                "site": [],
                "amenities": [
                    {"link": img["url"], "description": img["description"]}
                    for img in (dto["images"] or {}).get("amenities", [])
                ]
            },
            booking_conditions=[]
        )

def camel_to_snake_case(s):
    return re.sub(r'(?<!^)([A-Z])', r' \1', s).lower()
    
class HotelsService:
    def __init__(self):
        self.hotels = {}

    def merge_and_save(self, supplier_data):
        """Merge hotel data from multiple suppliers."""
        for hotel in supplier_data:
            if hotel.id not in self.hotels:
                self.hotels[hotel.id] = hotel

            else:
                existing = self.hotels[hotel.id]
                # Merge fields, ensuring no duplicates

                existing.name = hotel.name or existing.name

                #Take the description that is longer
                if len(existing.description)<len(hotel.description):
                    existing.description = hotel.description
                
                newLocation = {
                    k: v for k,v in hotel.location.items()
                    if not existing.location[k] and hotel.location[k]
                }
                
                existing.location={
                    **existing.location,
                    **newLocation
                }
                
 
                existing.amenities["general"]=list(set(existing.amenities["general"]+hotel.amenities["general"]))
                existing.amenities["room"]=list(set(existing.amenities["room"]+hotel.amenities["room"]))


                existing.images ={
                    k: existing.images[k] + [
                        img for img in hotel.images[k] if img not in existing.images[k]
                    ]
                    for k in existing.images.keys()
                }

                existing.booking_conditions = list(set(existing.booking_conditions+hotel.booking_conditions))

    def find(self, hotel_ids, destination_ids):
        """Filter hotels by hotel_ids and destination_ids."""
        filtered = [
            hotel for hotel in self.hotels.values()
            if (not hotel_ids or hotel.id in hotel_ids) and
               (not destination_ids or str(hotel.destination_id) in destination_ids)
        ]
        return filtered


def fetch_hotels(hotel_ids, destination_ids):
    # Fetch data from all suppliers
    suppliers = [
        Acme(),
        Paperflies(),
        Patagonia()
    ]
    all_supplier_data = []
    for supp in suppliers:
        all_supplier_data.extend(supp.fetch())

    # Merge all the data and save it in-memory
    svc = HotelsService()
    svc.merge_and_save(all_supplier_data)

    # Fetch filtered data
    filtered = svc.find(hotel_ids, destination_ids)

    # Convert to JSON format
    return json.dumps([hotel.__dict__ for hotel in filtered], indent=2)


def main():
    parser = argparse.ArgumentParser()
    
    parser.add_argument("hotel_ids", type=str, help="Hotel IDs")
    parser.add_argument("destination_ids", type=str, help="Destination IDs")
    
    # Parse the arguments
    args = parser.parse_args()
    
    hotel_ids = args.hotel_ids
    destination_ids = args.destination_ids
    
    result = fetch_hotels(hotel_ids, destination_ids)
    print(result)

if __name__ == "__main__":
    main()