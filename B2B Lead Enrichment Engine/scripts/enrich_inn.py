#!/usr/bin/env python3
"""
Скрипт прямого обогащения контрагентов по ИНН / ОГРН из официальных реестров.

Примеры использования:
    python3 scripts/enrich_inn.py 7707083893
    python3 scripts/enrich_inn.py 7736207543 7802849641 --export-excel leads_enriched.xlsx
    python3 scripts/enrich_inn.py 7743003908 --json
"""

import sys
import os
import argparse
import json
from pathlib import Path

# Добавляем родительскую директорию в PYTHONPATH
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from engine import EnrichmentEngine
from exporter import export_to_excel, export_to_csv, export_to_vcard

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Реальное обогащение компании по ИНН/ОГРН")
    parser.add_argument("inns", nargs="+", help="Один или несколько ИНН (10 или 12 цифр)")
    parser.add_argument("--export-excel", type=str, help="Путь для сохранения Excel файла (.xlsx)")
    parser.add_argument("--export-csv", type=str, help="Путь для сохранения CSV файла")
    parser.add_argument("--export-vcard", type=str, help="Путь для сохранения контактов vCard (.vcf)")
    parser.add_argument("--json", action="store_true", help="Вывести результат в формате JSON")
    parser.add_argument("--no-scrape", action="store_true", help="Отключить веб-краулинг сайта")

    args = parser.parse_args()
    engine = EnrichmentEngine()

    all_leads = []

    for inn in args.inns:
        inn_clean = inn.strip()
        if not args.json:
            console.print(f"[bold cyan]Запрос в реестры для ИНН: {inn_clean}...[/bold cyan]")

        comp = engine.fetch_and_enrich(inn_clean, scrape_web=not args.no_scrape, verify_emails=True)

        if not comp:
            if not args.json:
                console.print(f"[red]Организация с ИНН '{inn_clean}' не найдена в источниках.[/red]")
            continue

        leads = engine.get_all_leads(query=comp.inn)
        all_leads.extend(leads)

        if not args.json:
            console.print(Panel(
                f"[bold white]{comp.name}[/bold white]\n"
                f"[dim]ИНН:[/dim] [cyan]{comp.inn}[/cyan] | [dim]ОГРН:[/dim] {comp.ogrn or '—'} | [dim]КПП:[/dim] {comp.kpp or '—'}\n"
                f"[dim]Сайт:[/dim] [green]{comp.website or '—'}[/green] | [dim]Регион:[/dim] {comp.region or comp.city or '—'}\n"
                f"[dim]Отрасль (ОКВЭД):[/dim] {comp.okved_name or '—'}\n"
                f"[dim]Рейтинг надежности:[/dim] [bold green]{comp.solvency_score}/100 ({comp.risk_level})[/bold green]\n"
                f"[dim]Найдено ЛПР:[/dim] [bold yellow]{len(comp.decision_makers)}[/bold yellow]",
                title=f"[bold green]✓ Найдено в ЕГРЮЛ: {comp.short_name or comp.name}[/bold green]"
            ))

            t = Table(title=f"Контакты руководства: {comp.name}", show_lines=True)
            t.add_column("ФИО ЛПР", style="magenta")
            t.add_column("Должность", style="yellow")
            t.add_column("Email", style="green")
            t.add_column("Статус Email", style="blue")
            t.add_column("Телефон", style="cyan")
            t.add_column("Пояс", style="dim")
            t.add_column("Скоринг", justify="right", style="bold")

            for dm in comp.decision_makers:
                t.add_row(
                    dm.full_name,
                    f"{dm.title}\n[dim]({dm.role_level})[/dim]",
                    dm.email or "—",
                    dm.email_status or "—",
                    dm.phone or "—",
                    dm.phone_timezone or "MSK",
                    f"{dm.confidence_score}%"
                )
            console.print(t)

    if args.json:
        print(json.dumps(all_leads, ensure_ascii=False, indent=2))

    if args.export_excel and all_leads:
        export_to_excel(all_leads, args.export_excel)
        console.print(f"[bold green]✓ Экспортировано в Excel: {args.export_excel}[/bold green]")

    if args.export_csv and all_leads:
        export_to_csv(all_leads, args.export_csv)
        console.print(f"[bold green]✓ Экспортировано в CSV: {args.export_csv}[/bold green]")

    if args.export_vcard and all_leads:
        export_to_vcard(all_leads, args.export_vcard)
        console.print(f"[bold green]✓ Экспортировано в vCard: {args.export_vcard}[/bold green]")


if __name__ == "__main__":
    main()
