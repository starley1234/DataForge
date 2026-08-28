#!/usr/bin/env python3
"""
Скрипт прямого обогащения компании по веб-сайту / корпоративному домену.

Примеры использования:
    python3 scripts/enrich_domain.py sberbank.ru
    python3 scripts/enrich_domain.py kaspersky.ru --export-excel kaspersky_leads.xlsx
"""

import sys
import os
import argparse
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from engine import EnrichmentEngine
from sources.tech_stack import TechStackDetector
from exporter import export_to_excel, export_to_csv, export_to_vcard

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Обогащение организации по корпоративному сайту / домену")
    parser.add_argument("domains", nargs="+", help="Один или несколько доменов (например: sberbank.ru ozon.ru)")
    parser.add_argument("--export-excel", type=str, help="Путь для сохранения Excel файла (.xlsx)")
    parser.add_argument("--export-csv", type=str, help="Путь для сохранения CSV файла")
    parser.add_argument("--json", action="store_true", help="Вывести результат в формате JSON")

    args = parser.parse_args()
    engine = EnrichmentEngine()
    all_leads = []

    for dom in args.domains:
        clean_dom = dom.strip().lower()
        if not args.json:
            console.print(f"[bold cyan]Краулинг сайта и анализ контактов: {clean_dom}...[/bold cyan]")

        comp = engine.enrich_by_domain(clean_dom, verify_emails=True)
        if not comp:
            if not args.json:
                console.print(f"[red]Не удалось извлечь данные с домена '{clean_dom}'.[/red]")
            continue

        leads = engine.get_all_leads(query=comp.inn)
        all_leads.extend(leads)

        if not args.json:
            console.print(Panel(
                f"[bold white]{comp.name}[/bold white]\n"
                f"[dim]Домен:[/dim] [green]{comp.domain}[/green] | [dim]ИНН:[/dim] {comp.inn}\n"
                f"[dim]Email приемной:[/dim] [cyan]{comp.general_email or '—'}[/cyan]\n"
                f"[dim]Телефон приемной:[/dim] [cyan]{comp.general_phone or '—'}[/cyan]\n"
                f"[dim]Telegram:[/dim] {comp.telegram or '—'} | [dim]VK:[/dim] {comp.vk or '—'}\n"
                f"[dim]Найдено контактов ЛПР:[/dim] [bold yellow]{len(comp.decision_makers)}[/bold yellow]",
                title=f"[bold green]✓ Сайт успешно обработан: {clean_dom}[/bold green]"
            ))

            t = Table(title=f"Команда и ЛПР: {clean_dom}", show_lines=True)
            t.add_column("ФИО", style="magenta")
            t.add_column("Должность", style="yellow")
            t.add_column("Email", style="green")
            t.add_column("Статус", style="blue")
            t.add_column("Телефон", style="cyan")
            t.add_column("Скоринг", justify="right", style="bold")

            for dm in comp.decision_makers:
                t.add_row(
                    dm.full_name,
                    dm.title or "Руководитель",
                    dm.email or "—",
                    dm.email_status or "—",
                    dm.phone or "—",
                    f"{dm.confidence_score}%"
                )
            console.print(t)

    if args.json:
        print(json.dumps(all_leads, ensure_ascii=False, indent=2))

    if args.export_excel and all_leads:
        export_to_excel(all_leads, args.export_excel)
        console.print(f"[bold green]✓ Экспорт в Excel: {args.export_excel}[/bold green]")

    if args.export_csv and all_leads:
        export_to_csv(all_leads, args.export_csv)
        console.print(f"[bold green]✓ Экспорт в CSV: {args.export_csv}[/bold green]")


if __name__ == "__main__":
    main()
