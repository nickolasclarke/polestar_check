#!/usr/bin/python3

import requests

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
        "equalFilters": [{"filterType": "CycleState", "value": "PreOwned"}],
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
    return (
        response.json()
    )  # TODO getting a 504 request timeout. check later, or dig back into the API. Perhaps we need to break up the query into smaller chunks


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


def pretty_print_vehicle_results(vehicle: dict):
    url = (
        f"https://www.polestar.com/us/preowned-cars/product/polestar-2/{vehicle['id']}"
    )
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


# Build product page link with the following:
# https://www.polestar.com/us/preowned-cars/product/polestar-2/<INSERT ID HERE> vehicleAds.id

if __name__ == "__main__":
    res = check_polestar()
    if res["data"]["searchVehicleAds"]["metadata"]["resultCount"] > 0:
        vehicles = res["data"]["searchVehicleAds"]["vehicleAds"]
        # page through reults if there are more than the limit
        if (
            res["data"]["searchVehicleAds"]["metadata"]["resultCount"]
            > res["data"]["searchVehicleAds"]["metadata"]["limit"]
        ):
            for i in range(
                1,
                res["data"]["searchVehicleAds"]["metadata"]["resultCount"]
                // res["data"]["searchVehicleAds"]["metadata"]["limit"],
            ):
                GQL_QUERY["variables"]["offset"] = (
                    i * res["data"]["searchVehicleAds"]["metadata"]["limit"]
                )
                res = check_polestar()
                vehicles.extend(res["data"]["searchVehicleAds"]["vehicleAds"])
        vehicles = [replace_labels(vehicle) for vehicle in vehicles]
        for vehicle in vehicles:
            pretty_print_vehicle_results(vehicle)
