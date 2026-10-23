import subprocess
from pathlib import Path

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


def test_fetch_vehicles_includes_certified_preowned():
    vehicles = pc.fetch_vehicles("PS2")

    cycle_states = {v["vehicleDetails"]["cycleState"] for v in vehicles}
    assert cycle_states == {"PreOwned", "CertifiedPreOwned"}


def test_report_lists_each_model_in_its_own_section():
    result = subprocess.run(
        [str(SCRIPT)], capture_output=True, text=True, check=True
    )
    assert result.stderr == ""

    sections = {}
    current = None
    for line in result.stdout.splitlines():
        if line.startswith("Polestar "):
            current = line
            sections[current] = []
        elif line.strip():
            assert current is not None, f"vehicle listed before any model header: {line}"
            sections[current].append(line)

    headers = list(sections)
    assert [h.split(" (")[0] for h in headers] == [
        "Polestar 2",
        "Polestar 3",
        "Polestar 4",
    ]
    for header, slug in zip(headers, ["polestar-2/", "polestar-3/", "polestar-4-coupe/"]):
        lines = sections[header]
        assert header.endswith(f"({len(lines)})")
        assert lines, f"no vehicles listed under {header}"
        assert all(slug in line for line in lines)
