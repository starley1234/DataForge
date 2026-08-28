#!/usr/bin/env python3
"""
Скрипт генерации полного B2B Sales Pack (серия писем, скрипт звонка, vCard) для ЛПР.

Примеры использования:
    python3 scripts/generate_sales_pack.py --lead-id 1
    python3 scripts/generate_sales_pack.py --inn 7707083893 --out-dir sales_kit
"""

import sys
import os
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from rich.panel import Panel
from engine import EnrichmentEngine
from exporter import generate_outreach_email, generate_cold_calling_script, export_to_vcard

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Генератор B2B Sales Pack для менеджера по продажам")
    parser.add_argument("--lead-id", type=int, help="ID контакта ЛПР в базе данных")
    parser.add_argument("--inn", type=str, help="ИНН компании для поиска и формирования пакета")
    parser.add_argument("--out-dir", type=str, default="sales_pack", help="Папка для сохранения файлов")
    parser.add_argument("--sender-name", type=str, default="[Ваше Имя]")
    parser.add_argument("--sender-company", type=str, default="[Ваша Компания]")
    parser.add_argument("--sender-title", type=str, default="[Ваша Должность]")
    parser.add_argument("--sender-phone", type=str, default="[Ваш Телефон]")

    args = parser.parse_args()
    engine = EnrichmentEngine()

    lead = None
    if args.lead_id:
        lead = engine.get_lead_by_id(args.lead_id)
    elif args.inn:
        leads = engine.get_all_leads(query=args.inn.strip())
        if leads:
            lead = leads[0]
        else:
            comp = engine.fetch_and_enrich(args.inn.strip())
            if comp:
                leads = engine.get_all_leads(query=comp.inn)
                if leads:
                    lead = leads[0]

    if not lead:
        console.print("[red]Контакт ЛПР не найден. Укажите существующий --lead-id или --inn.[/red]")
        sys.exit(1)

    os.makedirs(args.out_dir, exist_ok=True)

    console.print(Panel(
        f"[bold]Компания:[/bold] [cyan]{lead['company_name']}[/cyan] (ИНН: {lead['inn']})\n"
        f"[bold]ЛПР:[/bold] [magenta]{lead['dm_full_name']}[/magenta] ([yellow]{lead['dm_title']}[/yellow])\n"
        f"[bold]Email:[/bold] [green]{lead['dm_email'] or '—'}[/green] ({lead['email_status']})\n"
        f"[bold]Телефон:[/bold] [cyan]{lead['dm_phone'] or '—'}[/cyan] ({lead.get('phone_carrier', '')})\n"
        f"[bold]Пояс и время:[/bold] {lead.get('phone_timezone', 'MSK')}",
        title="[bold green]Формирование B2B Sales Pack[/bold green]"
    ))

    # 1. Генерация 8 шаблонов холодных писем
    email_types = [
        ("01_partnership.txt", "partnership", "Стратегическое партнерство"),
        ("02_sales_pitch.txt", "sales", "B2B Продажи и оптимизация"),
        ("03_demo_pilot.txt", "demo", "Демо-доступ и пилот"),
        ("04_procurement.txt", "procurement", "Снабжение и закупки"),
        ("05_import_substitution.txt", "substitution", "Импортозамещение"),
        ("06_event_invitation.txt", "event", "Приглашение на круглый стол"),
        ("07_followup1.txt", "followup1", "Follow-up 1 (Напоминание)"),
        ("08_breakup.txt", "followup2", "Follow-up 2 (Breakup)")
    ]

    for fname, otype, desc in email_types:
        draft = generate_outreach_email(
            lead,
            offer_type=otype,
            sender_name=args.sender_name,
            sender_company=args.sender_company,
            sender_title=args.sender_title,
            sender_phone=args.sender_phone
        )
        filepath = os.path.join(args.out_dir, fname)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"Тема: {draft['subject']}\n")
            f.write(f"Кому: {draft['recipient_email']}\n")
            f.write("="*60 + "\n\n")
            f.write(draft['body'] + "\n")

    # 2. Скрипт холодного звонка
    script = generate_cold_calling_script(lead)
    script_path = os.path.join(args.out_dir, "00_cold_calling_script.txt")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(f"СЦЕНАРИЙ ХОЛОДНОГО ЗВОНКА: {lead['dm_full_name']} ({lead['company_name']})\n")
        f.write("="*60 + "\n\n")
        f.write("1. СЕКРЕТАРСКИЙ БАРЬЕР:\n")
        f.write(script['gatekeeper_script'] + "\n\n")
        f.write("2. ОТКРЫТИЕ РАЗГОВОРА С ЛПР (30-sec HOOK):\n")
        f.write(script['intro_pitch'] + "\n\n")
        f.write("3. ОТРАБОТКА ВОЗРАЖЕНИЙ:\n")
        for obj in script['objections']:
            f.write(f"• {obj['objection']}\n  -> {obj['answer']}\n\n")
        f.write("4. ЗАКРЫТИЕ НА ВСТРЕЧУ:\n")
        f.write(script['closing'] + "\n")

    # 3. vCard файл
    vcard_path = os.path.join(args.out_dir, f"contact_{lead['id']}.vcf")
    export_to_vcard([lead], vcard_path)

    console.print(f"[bold green]✓ B2B Sales Pack успешно сформирован в директории: [cyan]{args.out_dir}/[/cyan][/bold green]")
    console.print(f"  • Файлов сгенерировано: [bold]10[/bold] (8 писем, 1 скрипт звонка, 1 vCard)")


if __name__ == "__main__":
    main()
