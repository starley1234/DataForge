#!/usr/bin/env python3
"""
CLI-утилита быстрой проверки контрагентов и благонадежности (Rusprofile Due Diligence 360°).

Использование:
    python3 scripts/check_counterparty.py 7707083893
    python3 scripts/check_counterparty.py 7736207543 --export-excel dossier.xlsx
    python3 scripts/check_counterparty.py 7710668322 --markdown
"""

import sys
import os
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from core.counterparty_intelligence import CounterpartyIntelligenceEngine

console = Console()


def print_dossier_rich(dossier: dict):
    s = dossier["summary"]
    l = dossier["leadership"]
    f = dossier["finance"]
    p = dossier["procurement"]
    c = dossier["courts"]
    rf = dossier["risk_factors"]

    # Цветовой бейдж рейтинга
    score_color = "green" if s["reliability_score"] >= 75 else ("yellow" if s["reliability_score"] >= 50 else "red")

    # Главная панель компании
    header_text = Text.from_markup(
        f"[bold white]{s['name']}[/bold white]\n"
        f"[dim]ИНН:[/dim] [cyan]{s['inn']}[/cyan]  |  [dim]ОГРН:[/dim] [cyan]{s['ogrn']}[/cyan]  |  [dim]КПП:[/dim] [cyan]{s['kpp']}[/cyan]\n"
        f"[dim]Статус:[/dim] [bold {'green' if s['status'] == 'ACTIVE' else 'red'}]{s['status_text']}[/bold {'green' if s['status'] == 'ACTIVE' else 'red'}]  |  "
        f"[dim]Возраст бизнеса:[/dim] [bold]{s['age_years']} лет[/bold] (с {s['registration_date']})\n"
        f"[dim]Адрес:[/dim] {s['address']}\n"
        f"[dim]Основной ОКВЭД:[/dim] {s['okved']} {s['okved_name']}"
    )
    console.print(Panel(
        header_text,
        title=f"[bold {score_color}]🛡️ Rusprofile 360°: Индекс надежности {s['reliability_score']}/100 ({s['reliability_text']})[/bold {score_color}]",
        border_style=score_color
    ))

    # Сетка ключевых показателей (Финансы, Госзакупки, Суды, Руководство)
    table_grid = Table.grid(expand=True, padding=(0, 2))
    table_grid.add_column(ratio=1)
    table_grid.add_column(ratio=1)

    tax_debt_val = f"{f['tax_debt']:,.0f} ₽"
    tax_debt_str = f"[red]{tax_debt_val}[/red]" if f['has_tax_debt'] else "[green]Отсутствует[/green]"

    def_sum_val = f"{c['defendant_sum']:,.0f} ₽"
    def_cases_str = f"[yellow]{c['defendant_count']} дел ({def_sum_val})[/yellow]" if c['defendant_count'] > 0 else "[green]0 дел[/green]"

    fssp_debt_val = f"{dossier['fssp']['active_debt_sum']:,.0f} ₽"
    fssp_debt_str = f"[red]{fssp_debt_val}[/red]" if dossier['fssp']['active_debt_sum'] > 0 else "[green]0 ₽[/green]"

    fin_text = (
        f"[bold]Выручка (2025):[/bold] [green]{f['revenue_latest']:,.0f} ₽[/green]\n"
        f"[bold]Чистая прибыль:[/bold] [green]{f['profit_latest']:,.0f} ₽[/green]\n"
        f"[bold]Чистые активы:[/bold] {f['net_assets']:,.0f} ₽\n"
        f"[bold]Уплачено налогов:[/bold] {f['taxes_paid_total']:,.0f} ₽\n"
        f"[bold]Налоговая задолженность:[/bold] {tax_debt_str}\n"
        f"[bold]Блокировки счетов ФНС:[/bold] {'[red]ИМЕЮТСЯ РЕШЕНИЯ ⚠️[/red]' if f['account_blocks_count'] > 0 else '[green]Нет[/green]'}"
    )
    
    proc_court_text = (
        f"[bold]Госконтракты (Поставщик):[/bold] [cyan]{p['supplier_contracts_count']} шт.[/cyan] ([bold]{p['supplier_contracts_sum']:,.0f} ₽[/bold])\n"
        f"[bold]Реестр РНП ФАС:[/bold] {'[red]В ЧЕРНОМ СПИСКЕ ❌[/red]' if p['in_rnp'] else '[green]Не числится[/green]'}\n"
        f"[bold]Арбитраж (Истец):[/bold] {c['plaintiff_count']} дел ({c['plaintiff_sum']:,.0f} ₽)\n"
        f"[bold]Арбитраж (Ответчик):[/bold] {def_cases_str}\n"
        f"[bold]Долги ФССП:[/bold] {fssp_debt_str}\n"
        f"[bold]Штат сотрудников:[/bold] [bold]{s['employees_count']} чел.[/bold]"
    )

    table_grid.add_row(
        Panel(fin_text, title="[bold cyan]📊 Финансы и налоги (ГИР БО ФНС)[/bold cyan]", border_style="cyan"),
        Panel(proc_court_text, title="[bold yellow]⚖️ Госзакупки, Суды и ФССП[/bold yellow]", border_style="yellow")
    )
    console.print(table_grid)

    # Факторы риска
    rf_table = Table(title="[bold]Матрица факторов благонадежности и рисков[/bold]", expand=True, show_lines=True)
    rf_table.add_column("Категория", style="bold", width=22)
    rf_table.add_column("Факты и маркеры проверки", style="white")

    pos_str = "\n".join([f"✓ {p_item}" for p_item in rf["positive"]])
    rf_table.add_row("[bold green]🟢 Положительные[/bold green]", pos_str or "—")

    if rf["warnings"]:
        warn_str = "\n".join([f"⚠️ {w_item}" for w_item in rf["warnings"]])
        rf_table.add_row("[bold yellow]🟡 Внимание[/bold yellow]", warn_str)

    if rf["critical"]:
        crit_str = "\n".join([f"❌ {c_item}" for c_item in rf["critical"]])
        rf_table.add_row("[bold red]🔴 Стоп-факторы[/bold red]", crit_str)

    console.print(rf_table)

    # Учредители и Связи
    founders_str = ", ".join([f"{f_item['name']} ({f_item['share_percent']}%)" for f_item in dossier["founders"]])
    console.print(f"\n[bold]Руководитель:[/bold] [magenta]{l['ceo_title']} {l['ceo_name']}[/magenta] (ИНН: {l['ceo_inn']})")
    console.print(f"[bold]Учредители:[/bold] {founders_str}")

    # Найденные контакты ЛПР
    leads = dossier.get("leads", [])
    if leads:
        console.print(f"\n[bold green]Найдено контактов руководства в базе ({len(leads)}):[/bold green]")
        for lead in leads[:4]:
            console.print(f"  • [bold]{lead['dm_full_name']}[/bold] ({lead['dm_title']}) | Email: [cyan]{lead['dm_email'] or '—'}[/cyan] | Телефон: [yellow]{lead['dm_phone'] or '—'}[/yellow]")


def main():
    parser = argparse.ArgumentParser(description="Rusprofile 360° Due Diligence — Полная проверка контрагентов РФ")
    parser.add_argument("query", type=str, help="ИНН, ОГРН или наименование компании")
    parser.add_argument("--export-excel", type=str, help="Сохранить отчет о должной осмотрительности в Excel (.xlsx)")
    parser.add_argument("--markdown", action="store_true", help="Вывести отчет в формате Markdown")
    args = parser.parse_args()

    engine = CounterpartyIntelligenceEngine()
    console.print(f"[bold blue]Сбор данных по 38 государственным реестрам РФ для: {args.query}...[/bold blue]")
    
    dossier = engine.get_full_dossier(args.query)
    if not dossier:
        console.print(f"[red]Организация '{args.query}' не найдена.[/red]")
        sys.exit(1)

    if args.markdown:
        md_report = engine.generate_due_diligence_report_md(dossier)
        print(md_report)
        return

    print_dossier_rich(dossier)

    if args.export_excel:
        engine.export_due_diligence_excel(dossier, args.export_excel)
        console.print(f"\n[bold green]✓ Отчет о должной осмотрительности успешно сохранен в {args.export_excel}[/bold green]")


if __name__ == "__main__":
    main()
