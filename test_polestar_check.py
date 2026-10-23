import collections
import copy
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


def test_report_lists_each_model_in_its_own_section():
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

    headers = list(sections)
    assert [h.split(" (")[0] for h in headers] == [
        "Polestar 2",
        "Polestar 3",
        "Polestar 4",
    ]
    for header, slug in zip(
        headers, ["polestar-2/", "polestar-3/", "polestar-4-coupe/"]
    ):
        lines = sections[header]
        assert header.endswith(f"({len(lines)})")
        assert all(slug in line for line in lines)


STOCK_CODES = ["359", "814"]


@pytest.fixture(scope="module")
def dealers():
    return pc.fetch_dealers()


def test_fetch_dealers_returns_us_dealers_with_partner_ids(dealers):
    assert len(dealers) > 1
    assert all(d["partnerId"].startswith("6US") and d["name"] for d in dealers)


def test_fetch_new_vehicles_pages_through_every_result(dealers):
    # Find a dealer with at least 2 cars, then fetch it again 1 car per page
    everything = pc.fetch_new_vehicles(dealers, STOCK_CODES)
    counts = collections.Counter(c["dealer"]["partnerId"] for c in everything)
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
