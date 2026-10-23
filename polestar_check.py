#!/usr/bin/env -S uv run
# /// script
# requires-python = ">=3.14"
# dependencies = [
#     "requests",
# ]
# ///

import copy
import sys
from urllib.parse import quote

import requests

PREOWNED_API_URL = "https://pc-api.polestar.com/eu-north-1/partner-rm-tool/public/"
STOCK_API_URL = "https://pc-api.polestar.com/eu-north-1/preconfigured-cars/"

# Polestar's carModel codes, mapped to display name and product/stock page URL slugs
MODELS = {
    "PS2": {"name": "Polestar 2", "url_slug": "polestar-2"},
    "PS3": {
        "name": "Polestar 3",
        "url_slug": "polestar-3",
        "stock_slug": "polestar-3",
        "pno3": "359",
    },
    "PS4": {
        "name": "Polestar 4",
        "url_slug": "polestar-4-coupe",
        "stock_slug": "polestar-4-coupe",
        "pno3": "814",
    },
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

DEALERS_QUERY = {
    "query": """
        query Dealers {
        getAllRetailersFunction(marketMappingCode: "us", source: Preconfigured) {
            partnerId
            name
            city
        }
        }
        """,
    "variables": {},
}

STOCK_QUERY = {
    "query": """
        query NewStock(
        $filters: [FilterValueGroupInput]!
        $pagination: PaginationInput
        $partnerId: String
        ) {
        vehicles: filteredStockCars(
            market: "us"
            includeValidFilters: false
            filters: $filters
            pagination: $pagination
            partnerId: $partnerId
            customerType: "B2C"
            source: Preconfigured
        ) {
            pagination {
            totalRecords
            }
            filterResults {
            pno34
            modelYear
            startStructureWeek
            content {
                featureType
                code
                name
            }
            cashPriceData {
                discounted {
                totals {
                    grandTotal {
                    paymentTotal {
                        paymentTotalPrice {
                        value
                        }
                    }
                    }
                }
                }
                listPrice {
                totals {
                    grandTotal {
                    paymentTotal {
                        paymentTotalPrice {
                        value
                        }
                    }
                    }
                }
                }
            }
            }
        }
        }
        """,
    "variables": {},
}


def check_polestar(query: dict = GQL_QUERY, url: str = PREOWNED_API_URL):
    """
    Get the latest used car stock from Polestar's graphql API
    """
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


def fetch_dealers() -> list[dict]:
    """
    Get every US dealer that can list new stock
    """
    return check_polestar(DEALERS_QUERY, STOCK_API_URL)["data"][
        "getAllRetailersFunction"
    ]


def fetch_new_vehicles(
    dealers: list[dict], pno3_codes: list[str], page_size: int = 100
) -> list[dict]:
    """
    Get every new car of the given models from each dealer, paging through
    results. A dealer the API rejects is reported on stderr and skipped.
    """
    query = copy.deepcopy(STOCK_QUERY)
    # the type 4 filter group selects cars by model code
    model_filter = {
        "filterTypeId": "4",
        "filterValues": [{"value": c, "featureCode": c} for c in pno3_codes],
    }
    query["variables"]["filters"] = [model_filter]
    vehicles = []
    for dealer in dealers:
        query["variables"]["partnerId"] = dealer["partnerId"]
        dealer_vehicles = []
        while True:
            query["variables"]["pagination"] = {
                "pageNo": len(dealer_vehicles) // page_size + 1,
                "pageSize": page_size,
            }
            response = check_polestar(query, STOCK_API_URL)
            if "errors" in response:
                print(
                    f"warning: {dealer['name']}: {response['errors'][0]['message']}",
                    file=sys.stderr,
                )
                dealer_vehicles = []
                break
            stock = response["data"]["vehicles"]
            dealer_vehicles.extend(stock["filterResults"])
            # stop on an empty page too, so a miscounted total can't loop forever
            if (
                len(dealer_vehicles) >= stock["pagination"]["totalRecords"]
                or not stock["filterResults"]
            ):
                break
        vehicles.extend({**v, "dealer": dealer} for v in dealer_vehicles)
    return vehicles


def vehicle_url(car_model: str, vehicle_id: str) -> str:
    slug = MODELS[car_model]["url_slug"]
    return f"https://www.polestar.com/us/preowned-cars/product/{slug}/{vehicle_id}"


def stock_url(car_model: str, car: dict) -> str:
    slug = MODELS[car_model]["stock_slug"]
    pno34 = quote(car["pno34"])
    return (
        f"https://www.polestar.com/us/stock-cars/{slug}/{pno34}/"
        f"?year={car['modelYear']}&structureweek={car['startStructureWeek']}"
        f"&partnerid={car['dealer']['partnerId']}"
    )


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
