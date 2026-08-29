#!/usr/bin/env python3
"""
B2B Lead Enrichment Engine — Полномасштабный автоматический сборщик всех организаций России.

Запуск:
    python3 mass_harvester.py
    python3 mass_harvester.py --limit 500
    python3 mass_harvester.py --region "Москва" --industry "ИТ"
"""

import sys
import time
import argparse
import signal
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout
from rich.text import Text

from core.engine import EnrichmentEngine
from core.nationwide_harvester import NationwideHarvester, RUSSIAN_REGIONS, RUSSIAN_INDUSTRIES
from core.exporter import export_to_excel, export_to_csv

console = Console()


def create_status_layout(stats: dict, total_db_leads: int, total_db_companies: int) -> Layout:
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=4),
        Layout(name="stats", size=6),
        Layout(name="body", ratio=1)
    )

    # Header
    status_icon = "🟢 В ПРОЦЕССЕ СБОРА" if stats.get("is_running") else "🔴 ОСТАНОВЛЕН"
    header_text = Text.from_markup(
        f"[bold white on blue]  🚀 B2B NATIONWIDE HARVESTER — НЕПРЕРЫВНЫЙ ПОИСК ВСЕХ ПРЕДПРИЯТИЙ РОССИИ  [/bold white on blue]\n"
        f"[bold cyan]Статус:[/bold cyan] {status_icon}  |  "
        f"[bold yellow]Текущий регион:[/bold yellow] {stats.get('current_region', 'Все 89 регионов')}  |  "
        f"[bold magenta]Отрасль:[/bold magenta] {stats.get('current_industry', 'Все отрасли')}"
    )
    layout["header"].update(Panel(header_text, border_style="blue"))

    # Stats Bar
    speed = stats.get("speed_per_minute", 0)
    session_comps = stats.get("total_harvested_session", 0)
    session_dms = stats.get("total_dms_session", 0)
    uptime = stats.get("uptime_seconds", 0)

    stats_table = Table.grid(expand=True)
    stats_table.add_column(ratio=1)
    stats_table.add_column(ratio=1)
    stats_table.add_column(ratio=1)
    stats_table.add_column(ratio=1)
    stats_table.add_column(ratio=1)

    stats_table.add_row(
        Panel(f"[bold green]{session_comps}[/bold green]\n[dim]Собрано за сессию[/dim]", border_style="green"),
        Panel(f"[bold magenta]{session_dms}[/bold magenta]\n[dim]Контактов ЛПР[/dim]", border_style="magenta"),
        Panel(f"[bold cyan]{speed} орг/мин[/bold cyan]\n[dim]Скорость сбора[/dim]", border_style="cyan"),
        Panel(f"[bold white]{total_db_companies}[/bold white]\n[dim]Всего в базе БД[/dim]", border_style="blue"),
        Panel(f"[bold yellow]{uptime} сек[/bold yellow]\n[dim]Время работы[/dim]", border_style="yellow")
    )
    layout["stats"].update(stats_table)

    # Table of recent items
    recents = stats.get("recent_companies", [])
    t = Table(title="[bold green]Лента найденных предприятий и ЛПР в реальном времени[/bold green]", expand=True, show_lines=True)
    t.add_column("Время", style="dim", width=8)
    t.add_column("ИНН", style="cyan", width=12)
    t.add_column("Организация", style="bold white", width=24)
    t.add_column("Регион / Отрасль", style="dim", width=22)
    t.add_column("ФИО Руководителя / Должность", style="magenta", width=26)
    t.add_column("Корпоративный Email", style="green", width=22)
    t.add_column("Телефон / Время", style="yellow", width=18)
    t.add_column("Скоринг", style="bold green", justify="right", width=8)

    for c in recents[:8]:
        dm_name = c["dms"][0]["name"] if c.get("dms") else "—"
        dm_title = c["dms"][0]["title"] if c.get("dms") else "—"
        dm_email = c["dms"][0]["email"] if c.get("dms") else "—"
        dm_phone = c["dms"][0]["phone"] if c.get("dms") else "—"
        score = f"{c.get('solvency_score', 85)}%"

        t.add_row(
            c.get("timestamp", "-"),
            c.get("inn", "-"),
            c.get("name", "-")[:23],
            f"{c.get('region', '-')[:12]}\n[dim]{c.get('industry', '-')[:14]}[/dim]",
            f"{dm_name}\n[dim]{dm_title}[/dim]",
            dm_email,
            dm_phone,
            score
        )

    layout["body"].update(t)
    return layout


def main():
    parser = argparse.ArgumentParser(
        description="Непрерывный автопоиск всех организаций России и их ЛПР",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--limit", type=int, default=10000, help="Лимит организаций (по умолчанию 10 000)")
    parser.add_argument("--region", type=str, default=None, help="Фильтр по региону РФ (например, Москва, Свердловская, Татарстан)")
    parser.add_argument("--industry", type=str, default=None, help="Фильтр по отрасли (например, ИТ, Ритейл, Строительство, Банки)")
    parser.add_argument("--export-excel", type=str, default="leads_russia_all.xlsx", help="Файл для авто-экспорта Excel")
    parser.add_argument("--export-csv", type=str, default="leads_russia_all.csv", help="Файл для авто-экспорта CSV")

    args = parser.parse_args()

    engine = EnrichmentEngine()
    harvester = NationwideHarvester(engine=engine)

    def handle_sigint(signum, frame):
        harvester.stop()
        console.print("\n[bold yellow]Остановка сборщика... Сохранение базы...[/bold yellow]")
        leads = engine.get_all_leads()
        if args.export_excel:
            export_to_excel(leads, args.export_excel)
            console.print(f"[bold green]✓ База успешно сохранена в {args.export_excel} ({len(leads)} лидов)![/bold green]")
        if args.export_csv:
            export_to_csv(leads, args.export_csv)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    console.print(Panel(
        f"[bold green]Запуск автопоиска предприятий по всей России![/bold green]\n"
        f"Охват: [bold cyan]89 регионов РФ[/bold cyan] | [bold magenta]13 ключевых отраслей экономики[/bold magenta]\n"
        f"Режим: [bold yellow]Непрерывный фоновый сбор с верификацией контактов и скорингом[/bold yellow]\n\n"
        f"Для остановки и выгрузки нажмите [bold red]Ctrl+C[/bold red]",
        title="[bold blue]DataForge Nationwide Engine[/bold blue]"
    ))

    harvester.start(region_code=args.region, industry_keyword=args.industry, max_limit=args.limit)

    with Live(console=console, screen=True, refresh_per_second=4) as live:
        while harvester.is_running:
            stats = harvester.get_status()
            db_stats = engine.get_dashboard_stats()
            layout = create_status_layout(stats, db_stats["total_dms"], db_stats["total_companies"])
            live.update(layout)
            time.sleep(0.25)

    # Итоговое сохранение
    leads = engine.get_all_leads()
    if args.export_excel:
        export_to_excel(leads, args.export_excel)
        console.print(f"\n[bold green]✓ База экспортирована в {args.export_excel} ({len(leads)} лидов)![/bold green]")
    if args.export_csv:
        export_to_csv(leads, args.export_csv)


if __name__ == "__main__":
    main()
