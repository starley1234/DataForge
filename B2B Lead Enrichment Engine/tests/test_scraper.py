import pytest
from bs4 import BeautifulSoup
from core.scraper import WebsiteScraper


def test_extract_emails():
    scraper = WebsiteScraper()
    text = "Напишите нам на pr@company.ru или info@company.ru. Игнорировать fake@example.com и icon@2x.png."
    emails = scraper._extract_emails(text, "company.ru")
    assert "pr@company.ru" in emails
    assert "info@company.ru" in emails
    assert "fake@example.com" not in emails
    assert "icon@2x.png" not in emails


def test_extract_phones():
    scraper = WebsiteScraper()
    text = "Контакты: +7 (495) 739-70-00, доп. 8 (800) 200-00-00, прямой +7 926 555-44-33."
    phones = scraper._extract_phones(text)
    formatted = [p["formatted"] for p in phones]
    assert "+74957397000" in formatted
    assert "+78002000000" in formatted
    assert "+79265554433" in formatted


def test_extract_requisites():
    scraper = WebsiteScraper()
    text = 'ООО "Вектор". ИНН 7707083893, ОГРН 1027700132195, КПП 773601001.'
    reqs = scraper._extract_requisites(text)
    assert reqs["inn"] == "7707083893"
    assert reqs["ogrn"] == "1027700132195"
    assert reqs["kpp"] == "773601001"


def test_extract_person_cards():
    scraper = WebsiteScraper()
    html = """
    <div class="team-members">
        <div class="member-card">
            <h4>Семенов Игорь Владимирович</h4>
            <div class="position">Генеральный директор</div>
            <p>Email: i.semenov@corp.ru</p>
        </div>
        <div class="person-item">
            <h4>Кузнецова Елена Павловна</h4>
            <div class="title">Коммерческий директор</div>
            <p>Телефон: +7 495 111-22-33</p>
        </div>
    </div>
    """
    soup = BeautifulSoup(html, "html.parser")
    persons = scraper._extract_persons(soup, "https://corp.ru/team")
    assert len(persons) == 2
    names = [p["full_name"] for p in persons]
    assert "Семенов Игорь Владимирович" in names
    assert "Кузнецова Елена Павловна" in names
