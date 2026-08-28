import pytest
from core.harvester import UniversalB2BHarvester


def test_universal_harvester_enrichment():
    harvester = UniversalB2BHarvester()
    comp = harvester.harvest_company("7736207543")

    assert comp is not None
    assert comp.inn == "7736207543"
    assert comp.name == 'ООО "ЯНДЕКС"'
    assert comp.solvency_score is not None
    assert comp.solvency_score > 0
    assert len(comp.decision_makers) >= 1


def test_universal_harvester_batch():
    harvester = UniversalB2BHarvester()
    results = harvester.harvest_batch(["7736207543", "7707083893"])
    assert len(results) == 2
