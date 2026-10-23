import collections
import copy
import re
import subprocess
from pathlib import Path

import pytest

import polestar_check as pc

SCRIPT = Path(__file__).parent / "polestar_check.py"


def test_vehicle_url_uses_each_models_product_page_slug():
    assert (
        pc.vehicle_url("PS2", "abc")
        == "https://www.polestar.com/us/preowned-cars/product/polestar-2/abc"
    )
    assert (
        pc.vehicle_url("PS3", "abc")
        == "https://www.polestar.com/us/preowned-cars/product/polestar-3/abc"
    )
    assert (
        pc.vehicle_url("PS4", "abc")
        == "https://www.polestar.com/us/preowned-cars/product/polestar-4-coupe/abc"
    )


def test_stock_url_matches_site_format():
    car = {
        "pno34": "814PAPB0E13137300P04300      00000221001XCBL11XPILOT",
        "modelYear": "2026",
        "startStructureWeek": "202617",
        "dealer": {"partnerId": "6US6631"},
    }
    assert pc.stock_url("PS4", car) == (
        "https://www.polestar.com/us/stock-cars/polestar-4-coupe/"
        "814PAPB0E13137300P04300%20%20%20%20%20%2000000221001XCBL11XPILOT/"
        "?year=2026&structureweek=202617&partnerid=6US6631"
    )


def test_fetch_vehicles_pages_through_every_result():
    # 19 PS3s at the time of writing; a page size of 5 forces several pages
    # including a partial final page.
    vehicles = pc.fetch_vehicles("PS3", limit=5)
    single_page = pc.fetch_vehicles("PS3", limit=500)

    ids = [v["id"] for v in vehicles]
    assert len(single_page) > 5
    assert len(ids) == len(set(ids))
    assert set(ids) == {v["id"] for v in single_page}


def test_fetch_vehicles_returns_every_listing_that_is_not_new():
    # Query with no cycle-state filter so certified pre-owned stock (most PS2s
    # at the time of writing) can't be silently dropped by fetch_vehicles.
    unfiltered = copy.deepcopy(pc.GQL_QUERY)
    unfiltered["variables"].update(
        carModel="PS2", limit=500, equalFilters=[], excludeFilters=[]
    )
    listings = pc.check_polestar(unfiltered)["data"]["searchVehicleAds"]["vehicleAds"]
    not_new = {v["id"] for v in listings if v["vehicleDetails"]["cycleState"] != "New"}

    vehicles = pc.fetch_vehicles("PS2")

    assert not_new
    assert {v["id"] for v in vehicles} == not_new


@pytest.fixture(scope="module")
def report():
    result = subprocess.run(
        # --quiet keeps uv's own install messages out of stderr on a cold cache
        ["uv", "run", "--quiet", str(SCRIPT)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stderr == ""

    sections = {}
    current = None
    for line in result.stdout.splitlines():
        if line.startswith("Polestar "):
            current = line
            sections[current] = []
        elif line.strip():
            assert (
                current is not None
            ), f"vehicle listed before any model header: {line}"
            sections[current].append(line)
    return sections


def test_report_lists_each_model_in_its_own_section(report):
    headers = list(report)
    assert [h.split(" (")[0] for h in headers] == [
        "Polestar 2",
        "Polestar 3",
        "Polestar 4",
    ]
    for header, slug in zip(
        headers, ["polestar-2/", "polestar-3/", "polestar-4-coupe/"]
    ):
        lines = report[header]
        assert header.endswith(f"({len(lines)})")
        assert all(slug in line for line in lines)


def test_report_sections_are_sorted_cheapest_first(report):
    for header, lines in report.items():
        prices = [
            int(re.search(r"\$([\d,]+)", line).group(1).replace(",", ""))
            for line in lines
        ]
        assert prices == sorted(prices), header


def test_report_lists_every_new_car_under_its_model(report, new_cars):
    for (car_model, model), header in zip(pc.MODELS.items(), report):
        expected = sum(
            1
            for car in new_cars
            if pc.feature(car, "Model")["code"] == model.get("pno3")
        )
        actual = sum(line.startswith("New") for line in report[header])
        assert actual == expected, car_model


def test_report_tags_every_line(report):
    for lines in report.values():
        assert all(line.startswith(("New", "CPO", "Pre-owned")) for line in lines)


STOCK_CODES = ["359", "814"]


@pytest.fixture(scope="module")
def dealers():
    return pc.fetch_dealers()


def test_fetch_dealers_returns_us_dealers_with_partner_ids(dealers):
    assert len(dealers) > 1
    assert all(d["partnerId"].startswith("6US") and d["name"] for d in dealers)


@pytest.fixture(scope="module")
def new_cars(dealers):
    return pc.fetch_new_vehicles(dealers, STOCK_CODES)


def test_fetch_new_vehicles_pages_through_every_result(dealers, new_cars):
    # Find a dealer with at least 2 cars, then fetch it again 1 car per page
    counts = collections.Counter(c["dealer"]["partnerId"] for c in new_cars)
    partner_id, count = counts.most_common(1)[0]
    if count < 2:
        pytest.skip("no dealer currently lists 2+ new cars")
    dealer = [d for d in dealers if d["partnerId"] == partner_id]

    one_per_page = pc.fetch_new_vehicles(dealer, STOCK_CODES, page_size=1)

    assert len(one_per_page) == count


def test_fetch_new_vehicles_warns_and_skips_failing_dealer(capsys):
    bogus = {"partnerId": "BOGUS", "name": "Nowhere", "city": "Nowhere"}

    assert pc.fetch_new_vehicles([bogus], STOCK_CODES) == []

    err = capsys.readouterr().err
    assert err.startswith("warning: Nowhere: ")
    assert err.count("\n") == 1
