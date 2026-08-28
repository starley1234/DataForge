import os
import pytest
from exporter import (
    export_to_csv,
    export_to_excel,
    export_to_amocrm_csv,
    export_to_bitrix24_csv,
    export_to_json,
    generate_outreach_email
)

SAMPLE_LEAD = {
    "id": 1,
    "inn": "7736207543",
    "company_name": 'ООО "ЯНДЕКС"',
    "dm_full_name": "Худавердян Тигран Оганесович",
    "dm_title": "Управляющий директор",
    "dm_email": "t.khudaverdyan@yandex.ru",
    "email_status": "valid_mx",
    "dm_phone": "+74957397000",
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
    # Проверяем наличие UTF-8 BOM
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


def test_export_to_json(tmp_path):
    p = str(tmp_path / "leads.json")
    export_to_json([SAMPLE_LEAD], p)
    assert os.path.exists(p)


def test_generate_outreach_email():
    draft = generate_outreach_email(SAMPLE_LEAD, "sales")
    assert "t.khudaverdyan@yandex.ru" in draft["recipient_email"]
    assert "Тигран Оганесович" in draft["body"]
    assert "ЯНДЕКС" in draft["subject"]
