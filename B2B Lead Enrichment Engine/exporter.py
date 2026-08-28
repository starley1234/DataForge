import json
import pandas as pd
from typing import List, Dict, Any, Optional
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from translit import split_russian_name, get_salutation


def export_to_csv(leads: List[Dict[str, Any]], filepath: str) -> str:
    """Экспорт в CSV в кодировке UTF-8 с BOM (utf-8-sig) для корректного открытия в Excel на Windows."""
    df = pd.DataFrame(leads)
    df.to_csv(filepath, index=False, encoding="utf-8-sig")
    return filepath


def export_to_excel(leads: List[Dict[str, Any]], filepath: str) -> str:
    """
    Профессиональный экспорт в Excel (.xlsx) с оформлением:
    - Фирменный стиль заголовков (темно-синий фон, белый шрифт)
    - Закрепление верхней строки
    - Включение автофильтра
    - Автоматический расчет оптимальной ширины колонок
    - Цветовая подсветка статусов email и скоринга
    """
    if not leads:
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Лиды B2B"
        ws.append(["Нет данных"])
        wb.save(filepath)
        return filepath

    # Человекочитаемые заголовки колонок
    column_mappings = [
        ("inn", "ИНН"),
        ("company_name", "Организация"),
        ("dm_full_name", "ФИО ЛПР"),
        ("dm_title", "Должность"),
        ("dm_role_level", "Уровень ЛПР"),
        ("dm_email", "Корпоративный Email"),
        ("email_status", "Статус Email"),
        ("dm_phone", "Телефон"),
        ("dm_phone_type", "Тип телефона"),
        ("website", "Сайт"),
        ("region", "Регион"),
        ("okved_name", "Отрасль / ОКВЭД"),
        ("confidence_score", "Скоринг доверия"),
        ("source", "Источник данных"),
        ("lead_status", "Статус в CRM"),
        ("notes", "Примечания")
    ]

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "B2B Лиды и ЛПР"

    # Стили
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    border_thin = Side(border_style="thin", color="E2E8F0")
    cell_border = Border(left=border_thin, right=border_thin, top=border_thin, bottom=border_thin)

    fill_even = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
    fill_odd = PatternFill(start_color="FFFFFF", end_color="FFFFFF", fill_type="solid")

    # Подсветка статусов
    fill_valid = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
    font_valid = Font(name="Calibri", size=10, bold=True, color="166534")

    fill_warn = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
    font_warn = Font(name="Calibri", size=10, bold=True, color="92400E")

    fill_invalid = PatternFill(start_color="FEE2E2", end_color="FEE2E2", fill_type="solid")
    font_invalid = Font(name="Calibri", size=10, bold=True, color="991B1B")

    # Запись строки заголовков
    headers = [label for _, label in column_mappings]
    ws.append(headers)
    ws.row_dimensions[1].height = 28

    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align
        cell.border = cell_border

    # Запись строк с данными
    keys = [k for k, _ in column_mappings]
    for r_idx, lead in enumerate(leads, start=2):
        row_values = []
        for k in keys:
            val = lead.get(k)
            if k == "confidence_score" and val is not None:
                val = f"{val}%"
            elif val is None or val == "":
                val = "—"
            row_values.append(val)
        ws.append(row_values)
        ws.row_dimensions[r_idx].height = 20

        # Чередование цвета строк и подсветка
        row_fill = fill_even if r_idx % 2 == 0 else fill_odd
        for c_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=r_idx, column=c_idx)
            cell.border = cell_border
            cell.alignment = Alignment(vertical="center")
            cell.fill = row_fill

            # Подсветка колонки Статус Email
            if keys[c_idx - 1] == "email_status":
                status = str(cell.value).lower()
                if "valid" in status or "verified" in status:
                    cell.fill = fill_valid
                    cell.font = font_valid
                elif "generated" in status:
                    cell.fill = fill_warn
                    cell.font = font_warn
                elif "invalid" in status or "no_mx" in status or "disposable" in status:
                    cell.fill = fill_invalid
                    cell.font = font_invalid

    # Автоподбор ширины колонок
    for col in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col[0].column)
        for cell in col:
            val = str(cell.value or "")
            if len(val) > max_len:
                max_len = len(val)
        ws.column_dimensions[col_letter].width = min(40, max(max_len + 3, 12))

    # Закрепление шапки и автофильтр
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{len(leads) + 1}"

    wb.save(filepath)
    return filepath


def export_to_json(leads: List[Dict[str, Any]], filepath: str) -> str:
    """Экспорт в форматированный JSON с сохранением русских символов."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(leads, f, ensure_ascii=False, indent=2)
    return filepath


def export_to_amocrm_csv(leads: List[Dict[str, Any]], filepath: str) -> str:
    """
    Экспорт в CSV для импорта в amoCRM (стандартные колонки сделок и контактов).
    """
    amo_rows = []
    for l in leads:
        amo_rows.append({
            "Название сделки": f"{l.get('company_name', 'B2B')} — {l.get('dm_title', 'ЛПР')}",
            "Компания": l.get("company_name", ""),
            "Основной контакт": l.get("dm_full_name", ""),
            "Должность": l.get("dm_title", ""),
            "Рабочий e-mail": l.get("dm_email", ""),
            "Рабочий телефон": l.get("dm_phone", ""),
            "Сайт": l.get("website", ""),
            "Город/Регион": l.get("region", ""),
            "ИНН": l.get("inn", ""),
            "Этап сделки": "Первичный контакт",
            "Примечание": f"Email статус: {l.get('email_status')}, Скоринг: {l.get('confidence_score')}%, Источник: {l.get('source')}"
        })

    df = pd.DataFrame(amo_rows)
    df.to_csv(filepath, index=False, encoding="utf-8-sig")
    return filepath


def export_to_bitrix24_csv(leads: List[Dict[str, Any]], filepath: str) -> str:
    """
    Экспорт в CSV для прямого импорта в Битрикс24 (сущность Лид).
    """
    b24_rows = []
    for l in leads:
        last, first, middle = split_russian_name(l.get("dm_full_name", ""))
        b24_rows.append({
            "Название лида": f"Лид: {l.get('company_name')} ({l.get('dm_full_name')})",
            "Имя": first,
            "Фамилия": last,
            "Отчество": middle,
            "Компания": l.get("company_name", ""),
            "Должность": l.get("dm_title", ""),
            "E-mail": l.get("dm_email", ""),
            "Рабочий телефон": l.get("dm_phone", ""),
            "Сайт": l.get("website", ""),
            "Источник": "B2B Lead Enrichment Engine",
            "Статус": "Не обработан",
            "Комментарий": f"ИНН: {l.get('inn')}, ОКВЭД: {l.get('okved_name')}, Доверие: {l.get('confidence_score')}%"
        })

    df = pd.DataFrame(b24_rows)
    df.to_csv(filepath, index=False, encoding="utf-8-sig")
    return filepath


def generate_outreach_email(lead: Dict[str, Any], offer_type: str = "partnership") -> Dict[str, str]:
    """
    Генерирует готовый персонализированный шаблон холодного B2B-письма в деловом стиле РФ.
    """
    full_name = lead.get("dm_full_name", "")
    comp_name = lead.get("company_name", "Ваша организация")
    title = lead.get("dm_title", "Руководитель")
    email = lead.get("dm_email", "")

    salutation = get_salutation(full_name, formal=True)

    if offer_type == "sales":
        subject = f"Сотрудничество с {comp_name} // оптимизация B2B процессов"
        body = f"""{salutation}

Меня зовут [Ваше Имя], компания [Ваша Компания].

Обращаюсь к Вам как к {title.lower()} {comp_name}. Мы специализируемся на внедрении передовых B2B-решений для предприятий Вашей отрасли.

Изучив профиль {comp_name}, мы видим высокий потенциал для сокращения операционных издержек и масштабирования поставок. Подобный кейс мы недавно реализовали для аналогичного лидера рынка, увеличив эффективность на 24%.

Будет ли у Вас возможность уделить 10-15 минут на этой неделе (например, в четверг в 11:00 или 15:00) для краткого ознакомительного онлайн-звонка?

С уважением,
[Ваше Имя]
[Ваша Должность], [Ваша Компания]
Телефон: [Ваш Телефон]
Сайт: [Ваш Сайт]"""

    elif offer_type == "demo":
        subject = f"Демо-доступ для команды {comp_name}"
        body = f"""{salutation}

Пишу Вам, поскольку Вы руководите ключевыми направлениями в {comp_name}.

Мы разработали технологическое решение, которое помогает автоматизировать рутинные процессы и повысить результативность команды. 

Предлагаем организовать персональную 15-минутную демонстрацию системы с разбором специфики {comp_name}, а также предоставить бесплатный пилотный доступ на 14 дней.

Подскажите, пожалуйста, в какой день Вам было бы удобно провести встречу в Zoom или Telegram?

С уважением,
[Ваше Имя]
[Ваша Компания]"""

    else:  # partnership
        subject = f"Предложение о партнерстве с {comp_name}"
        body = f"""{salutation}

Обращаюсь к Вам по вопросу стратегического взаимодействия с {comp_name}.

Наша компания реализует комплексные B2B-проекты. Мы видим отличные точки соприкосновения и взаимную синергию между нашими продуктами и масштабом Вашего бизнеса.

Хотели бы направить краткую презентацию концепции партнерства и обсудить взаимовыгодные форматы сотрудничества.

Буду признателен за обратную связь или подсказку, с кем из Ваших коллег было бы целесообразно созвониться по данному вопросу.

С уважением,
[Ваше Имя]
[Ваша Компания]"""

    return {
        "recipient_email": email,
        "recipient_name": full_name,
        "subject": subject,
        "body": body
    }
