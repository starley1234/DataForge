#!/usr/bin/env python3
"""
Скрипт высокопроизводительной пакетной обработки списков компаний из файлов Excel / CSV.

Примеры использования:
    python3 scripts/batch_enrich.py input_leads.xlsx --export-excel enriched.xlsx
    python3 scripts/batch_enrich.py raw_inns.csv --export-amocrm amo.csv --export-bitrix24 b24.csv
"""

import sys
import os
import time
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeRemainingColumn
from engine import EnrichmentEngine
from batch_processor import BatchProcessor
from exporter import (
    export_to_excel, export_to_csv, export_to_amocrm_csv,
    export_to_bitrix24_csv, export_to_hubspot_csv, export_to_vcard
)

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Пакетное обогащение базы контрагентов из файла")
    parser.add_argument("input_file", help="Путь к исходному файлу (.xlsx, .xls, .csv)")
    parser.add_argument("--type", choices=["inn", "name", "domain"], default="inn", help="Тип данных в файле")
    parser.add_argument("--export-excel", type=str, help="Выгрузить результат в стилизованный Excel (.xlsx)")
    parser.add_argument("--export-csv", type=str, help="Выгрузить результат в CSV (UTF-8-BOM)")
    parser.add_argument("--export-amocrm", type=str, help="Выгрузить для импорта в amoCRM")
    parser.add_argument("--export-bitrix24", type=str, help="Выгрузить для импорта в Битрикс24")
    parser.add_argument("--export-hubspot", type=str, help="Выгрузить для импорта в HubSpot / Salesforce")
    parser.add_argument("--export-vcard", type=str, help="Выгрузить в формате vCard (.vcf)")

    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        console.print(f"[red]Файл '{args.input_file}' не найден![/red]")
        sys.exit(1)

    engine = EnrichmentEngine()
    bp = BatchProcessor(engine)

    console.print(f"[bold cyan]Чтение файла: {args.input_file}...[/bold cyan]")
    with open(args.input_file, "rb") as f:
        file_bytes = f.read()

    items = bp.parse_file_to_items(file_bytes, args.input_file)
    if not items:
        console.print("[red]Не удалось распознать колонку с ИНН или названиями организаций в файле.[/red]")
        sys.exit(1)

    console.print(f"[bold green]Найдено {len(items)} записей для обработки. Запуск фонового конвейера...[/bold green]")

    task_id = bp.start_batch_enrichment(items, task_type=args.type, scrape_web=True, verify_emails=True)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[bold cyan]{task.percentage:>3.0f}%"),
        TimeRemainingColumn(),
        console=console
    ) as progress:
        p_task = progress.add_task("Обогащение базы...", total=len(items))

        while True:
            status = bp.get_task_status(task_id)
            if not status:
                break

            processed = status.get("processed_items", 0)
            progress.update(p_task, completed=processed)

            if status.get("status") in ("completed", "failed", "cancelled"):
                break
            time.sleep(0.5)

    final_status = bp.get_task_status(task_id)
    console.print(f"\n[bold green]✓ Пакетная обработка завершена![/bold green]")
    console.print(f"Всего: [bold]{final_status['total_items']}[/bold] | "
                  f"Успешно: [bold green]{final_status['success_items']}[/bold green] | "
                  f"Ошибок: [bold red]{final_status['failed_items']}[/bold red]")

    leads = engine.get_all_leads()

    if args.export_excel:
        export_to_excel(leads, args.export_excel)
        console.print(f"[bold green]✓ Экспорт в Excel: {args.export_excel}[/bold green]")

    if args.export_csv:
        export_to_csv(leads, args.export_csv)
        console.print(f"[bold green]✓ Экспорт в CSV: {args.export_csv}[/bold green]")

    if args.export_amocrm:
        export_to_amocrm_csv(leads, args.export_amocrm)
        console.print(f"[bold green]✓ Экспорт в amoCRM: {args.export_amocrm}[/bold green]")

    if args.export_bitrix24:
        export_to_bitrix24_csv(leads, args.export_bitrix24)
        console.print(f"[bold green]✓ Экспорт в Битрикс24: {args.export_bitrix24}[/bold green]")

    if args.export_hubspot:
        export_to_hubspot_csv(leads, args.export_hubspot)
        console.print(f"[bold green]✓ Экспорт в HubSpot: {args.export_hubspot}[/bold green]")

    if args.export_vcard:
        export_to_vcard(leads, args.export_vcard)
        console.print(f"[bold green]✓ Экспорт в vCard: {args.export_vcard}[/bold green]")


if __name__ == "__main__":
    main()
