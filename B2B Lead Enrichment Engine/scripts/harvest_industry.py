#!/usr/bin/env python3
"""
Скрипт массового сбора и харвестинга актуальных компаний по отраслям, вакансиям и ключевым словам.

Примеры использования:
    python3 scripts/harvest_industry.py --keyword "ИТ разработка" --limit 10
    python3 scripts/harvest_industry.py --city "Москва" --export-excel msk_leads.xlsx
"""

import sys
import os
import argparse
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from rich.table import Table
from rich.progress import track
from core.harvester import UniversalB2BHarvester
from core.exporter import export_to_excel, export_to_csv, export_to_vcard

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Харвестер и сборщик B2B лидов по отраслям и вакансиям")
    parser.add_argument("--keyword", type=str, help="Ключевое слово отрасли (например: 'ИТ', 'Банки', 'Ритейл', 'Логистика', 'Производство')")
    parser.add_argument("--city", type=str, help="Фильтр по городу / региону (например: 'Москва', 'Санкт-Петербург')")
    parser.add_argument("--limit", type=int, default=15, help="Максимальное количество компаний для сбора (по умолчанию 15)")
    parser.add_argument("--export-excel", type=str, help="Путь для выгрузки Excel (.xlsx)")
    parser.add_argument("--export-csv", type=str, help="Путь для выгрузки CSV")
    parser.add_argument("--export-vcard", type=str, help="Путь для выгрузки vCard (.vcf)")

    args = parser.parse_args()
    harvester = UniversalB2BHarvester()

    console.print(f"[bold cyan]Запуск B2B Harvester: поиск по ключевому запросу '{args.keyword or 'Все отрасли'}'...[/bold cyan]")

    all_comps = harvester.registry.get_all()
    filtered_queries = []

    for c in all_comps:
        text = f"{c.name} {c.short_name or ''} {c.tags or ''} {c.okved_name or ''}".lower()
        if args.keyword and args.keyword.lower() not in text:
            continue
        if args.city and args.city.lower() not in (c.region or "").lower() and args.city.lower() not in (c.city or "").lower():
            continue
        filtered_queries.append(c.inn)

    target_inns = filtered_queries[:args.limit] if filtered_queries else [c.inn for c in all_comps[:args.limit]]

    console.print(f"[bold green]Найдено {len(target_inns)} целевых организаций. Запуск комплексного обогащения...[/bold green]")

    harvested = []
    for inn in track(target_inns, description="Сбор досье и контактов ЛПР..."):
        comp = harvester.harvest_company(inn, city=args.city)
        if comp:
            harvested.append(comp)

    leads = harvester.engine.get_all_leads()
    console.print(f"\n[bold green]✓ Успешно собрано контактов ЛПР: {len(leads)}[/bold green]")

    t = Table(title="Собранная база ЛПР", show_lines=True)
    t.add_column("Организация", style="bold white")
    t.add_column("ФИО ЛПР", style="magenta")
    t.add_column("Должность", style="yellow")
    t.add_column("Email", style="green")
    t.add_column("Телефон", style="cyan")
    t.add_column("Регион", style="dim")
    t.add_column("Надежность", justify="right", style="bold")

    for l in leads[:20]:
        t.add_row(
            l.get("company_name", "")[:28],
            l.get("dm_full_name", ""),
            l.get("dm_title", ""),
            l.get("dm_email") or "—",
            l.get("dm_phone") or "—",
            l.get("region") or "—",
            f"{l.get('confidence_score', 50)}%"
        )
    console.print(t)

    if args.export_excel:
        export_to_excel(leads, args.export_excel)
        console.print(f"[bold green]✓ Экспортировано в Excel: {args.export_excel}[/bold green]")

    if args.export_csv:
        export_to_csv(leads, args.export_csv)
        console.print(f"[bold green]✓ Экспортировано в CSV: {args.export_csv}[/bold green]")

    if args.export_vcard:
        export_to_vcard(leads, args.export_vcard)
        console.print(f"[bold green]✓ Экспортировано в vCard: {args.export_vcard}[/bold green]")


if __name__ == "__main__":
    main()
