import os
import pytest
from exporter import (
    export_to_csv,
    export_to_excel,
    export_to_amocrm_csv,
    export_to_bitrix24_csv,
    export_to_hubspot_csv,
    export_to_vcard,
    export_to_json,
    generate_outreach_email,
    generate_cold_calling_script
)

SAMPLE_LEAD = {
    "id": 1,
    "inn": "7736207543",
    "company_name": 'ООО "ЯНДЕКС"',
    "dm_full_name": "Худавердян Тигран Оганесович",
    "dm_title": "Управляющий директор",
    "dm_role_level": "C-Level",
    "dm_email": "t.khudaverdyan@yandex.ru",
    "email_status": "valid_mx",
    "dm_phone": "+74957397000",
    "dm_phone_type": "office",
    "phone_carrier": "ПАО Ростелеком",
    "phone_timezone": "MSK (UTC+3)",
    "website": "yandex.ru",
    "region": "г. Москва",
    "confidence_score": 95,
    "source": "egrul"
}


def test_export_to_csv(tmp_path):
    p = str(tmp_path / "leads.csv")
    export_to_csv([SAMPLE_LEAD], p)
    assert os.path.exists(p)
    with open(p, "rb") as f:
        content = f.read()
    # UTF-8 BOM
    assert content.startswith(b'\xef\xbb\xbf')


def test_export_to_excel(tmp_path):
    p = str(tmp_path / "leads.xlsx")
    export_to_excel([SAMPLE_LEAD], p)
    assert os.path.exists(p)
    assert os.path.getsize(p) > 1000


def test_export_to_amocrm(tmp_path):
    p = str(tmp_path / "amo.csv")
    export_to_amocrm_csv([SAMPLE_LEAD], p)
    assert os.path.exists(p)


def test_export_to_bitrix24(tmp_path):
    p = str(tmp_path / "b24.csv")
    export_to_bitrix24_csv([SAMPLE_LEAD], p)
    assert os.path.exists(p)


def test_export_to_hubspot(tmp_path):
    p = str(tmp_path / "hubspot.csv")
    export_to_hubspot_csv([SAMPLE_LEAD], p)
    assert os.path.exists(p)


def test_export_to_vcard(tmp_path):
    p = str(tmp_path / "contact.vcf")
    export_to_vcard([SAMPLE_LEAD], p)
    assert os.path.exists(p)
    with open(p, "r", encoding="utf-8") as f:
        content = f.read()
    assert "BEGIN:VCARD" in content
    assert "Худавердян" in content


def test_generate_outreach_email_templates():
    types = ["partnership", "sales", "demo", "procurement", "substitution", "event", "followup1", "followup2"]
    for t in types:
        draft = generate_outreach_email(SAMPLE_LEAD, offer_type=t)
        assert len(draft["subject"]) > 5
        assert len(draft["body"]) > 20
        assert "ЯНДЕКС" in draft["subject"] or "ЯНДЕКС" in draft["body"] or "Худавердян" in draft["body"] or "Тигран" in draft["body"]


def test_generate_cold_calling_script():
    script = generate_cold_calling_script(SAMPLE_LEAD)
    assert "gatekeeper_script" in script
    assert "intro_pitch" in script
    assert len(script["objections"]) >= 5
    assert "closing" in script
