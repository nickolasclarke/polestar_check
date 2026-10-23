#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "requests",
# ]
# ///

import copy

import requests

# Polestar's carModel codes, mapped to display name and product page URL slug
MODELS = {
    "PS2": {"name": "Polestar 2", "url_slug": "polestar-2"},
    "PS3": {"name": "Polestar 3", "url_slug": "polestar-3"},
    "PS4": {"name": "Polestar 4", "url_slug": "polestar-4-coupe"},
}

GQL_QUERY = {
    "query": """
        query SearchVehicleAds(
        $carModel: CarModel!
        $market: String!
        $region: String
        $offset: Int!
        $limit: Int!
        $sortOrder: SortOrder2!
        $sortProperty: SortProperty!
        $equalFilters: [EqualFilter!]
        $excludeFilters: [ExcludeFilter!]
        ) {
        searchVehicleAds(
            carModel: $carModel
            market: $market
            region: $region
            offset: $offset
            limit: $limit
            sortOrder: $sortOrder
            sortProperty: $sortProperty
            equalFilters: $equalFilters
            excludeFilters: $excludeFilters
        ) {
            metadata {
            limit
            offset
            resultCount
            totalCount
            }
            vehicleAds {
            id
            firstTimeRegistration
            price {
                retail
                dealer
            }
            partnerLocation {
                city
                name
            }
            mileageInfo {
                distance
                metric
            }
            vehicleDetails {
                vin
                cycleState
                interior {
                labels {
                    label
                }
                thumbnail {
                    url
                }
                }
                vehicleImages {
                url
                rawUrl
                }
                modelDetails {
                modelYear
                model
                edition
                }
                rangeInformation {
                value
                }
                drivetrainInfo {
                label
                }
                pilotPackage {
                labels {
                    label
                }
                }
                plusPackage {
                labels {
                    label
                }
                }
                exterior {
                code
                labels {
                    label
                }
                }
                performancePackage {
                code
                labels {
                    label
                }
                }
                previousOwners
                previousOwner
                previousUsage
                accidentFree
                emissionSticker
                vehicleAdExtras {
                id
                type
                items {
                    id
                    title
                    image
                    articleNumber
                    __typename
                }
                }
            }
            }
        }
        }
        """,
    "variables": {
        "carModel": "PS2",
        "market": "us",
        "offset": 0,
        "limit": 100,
        "sortOrder": "Ascending",
        "sortProperty": "Price",
        # multiple filters of the same type are OR'd together
        "equalFilters": [
            {"filterType": "CycleState", "value": "PreOwned"},
            {"filterType": "CycleState", "value": "CertifiedPreOwned"},
        ],
        "excludeFilters": [{"filterType": "CycleState", "value": "New"}],
    },
}


def check_polestar(query: dict = GQL_QUERY):
    """
    Get the latest used car stock from Polestar's graphql API
    """
    url = "https://pc-api.polestar.com/eu-north-1/partner-rm-tool/public/"

    headers = {
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.5",
        "Content-Type": "application/json",
        "Connection": "keep-alive",
        "Host": "pc-api.polestar.com",
        "Origin": "https://www.polestar.com",
        "Referer": "https://www.polestar.com/",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:123.0) Gecko/20100101 Firefox/123.0",
    }

    data = {
        "query": query["query"].replace("\n", " "),
        "variables": query["variables"],
    }
    response = requests.post(
        url,
        headers=headers,
        json=data,
    )
    return response.json()


def fetch_vehicles(car_model: str, limit: int = 100) -> list[dict]:
    """
    Get every listed vehicle of a model, paging through results
    """
    query = copy.deepcopy(GQL_QUERY)
    query["variables"].update(carModel=car_model, limit=limit)
    vehicles = []
    while True:
        query["variables"]["offset"] = len(vehicles)
        search = check_polestar(query)["data"]["searchVehicleAds"]
        vehicles.extend(search["vehicleAds"])
        # stop on an empty page too, so a miscounted total can't loop forever
        if (
            len(vehicles) >= search["metadata"]["resultCount"]
            or not search["vehicleAds"]
        ):
            return vehicles


def vehicle_url(car_model: str, vehicle_id: str) -> str:
    slug = MODELS[car_model]["url_slug"]
    return f"https://www.polestar.com/us/preowned-cars/product/{slug}/{vehicle_id}"


def replace_labels(vehicle: dict):
    for key, value in vehicle.items():
        if isinstance(value, dict):
            replace_labels(value)
        # if key == "labels":
        #     vehicle[key] = value[0]["label"]
        #     break
        if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
            if all([k for v in value for k in v.keys()]):
                common_value = list(value[0].values())[0]
                vehicle[key] = common_value
    return vehicle


def pretty_print_vehicle_results(car_model: str, vehicle: dict):
    url = vehicle_url(car_model, vehicle["id"])
    dealer_price = vehicle["price"]["dealer"]
    retail_price = vehicle["price"]["retail"]
    m_year = vehicle["vehicleDetails"]["modelDetails"]["modelYear"]
    mileage = vehicle["mileageInfo"]["distance"]
    m_unit = vehicle["mileageInfo"]["metric"]
    city = vehicle["partnerLocation"]["city"]
    range = vehicle["vehicleDetails"]["rangeInformation"]
    print(
        f"${dealer_price:<6,} ({retail_price:,}) - {m_year} {mileage:<6} {m_unit} - range: {range} mi - {city:<15} {url}"
    )


if __name__ == "__main__":
    for car_model, model in MODELS.items():
        vehicles = [replace_labels(vehicle) for vehicle in fetch_vehicles(car_model)]
        print(f"{model['name']} ({len(vehicles)})")
        for vehicle in vehicles:
            pretty_print_vehicle_results(car_model, vehicle)
        print()
